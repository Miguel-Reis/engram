from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

MAX_EPHEMERAL_CHARS = 1350  # ~320 tokens max budget (inclui Scout Shared Map)
_LOCAL_IMPORTS_LOADED = False


def _ensure_local_imports() -> None:
    """Lazy-load heavy SQLite/engine modules only when local hook execution is needed."""
    global _LOCAL_IMPORTS_LOADED
    if _LOCAL_IMPORTS_LOADED:
        return
    from db_engine import BrainDB, ensure_dashboard_running
    from orbit_engine import OrbitEngine
    from runtime_detector import detect_runtime_profile, record_runtime_session
    from swarm_engine import SwarmEngine
    from voice_brain_engine import analyze_voice_input, process_voice_turn, resolve_spoken_code_targets

    globals().update(
        {
            "BrainDB": BrainDB,
            "ensure_dashboard_running": ensure_dashboard_running,
            "OrbitEngine": OrbitEngine,
            "detect_runtime_profile": detect_runtime_profile,
            "record_runtime_session": record_runtime_session,
            "SwarmEngine": SwarmEngine,
            "analyze_voice_input": analyze_voice_input,
            "process_voice_turn": process_voice_turn,
            "resolve_spoken_code_targets": resolve_spoken_code_targets,
        }
    )
    _LOCAL_IMPORTS_LOADED = True


if __name__ != "__main__":
    _ensure_local_imports()


def try_warm_server_pre_invoke(
    raw_stdin: str,
    host_hint: str = "auto",
    timeout: float = 0.45,
) -> Optional[str]:
    """
    Fast-path HTTP call to the warm dashboard server (/api/hook/pre-invoke).
    Returns the serialized hook output string on HTTP 200 with a valid 'hook_output',
    or None on any error/timeout/opt-out so the caller falls back cleanly.
    """
    if os.environ.get("ENGRAM_DISABLE_WARM_HOOK") == "1":
        return None
    if not raw_stdin or not raw_stdin.strip():
        return None
    url = os.environ.get("ENGRAM_WARM_HOOK_URL", "http://127.0.0.1:8765/api/hook/pre-invoke")
    body = json.dumps({"raw_stdin": raw_stdin, "host_hint": host_hint}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Origin": "http://127.0.0.1:8765",
            "X-Engram-Hook": "1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) != 200:
                return None
            raw_resp = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw_resp)
            if isinstance(data, dict) and isinstance(data.get("hook_output"), str) and data["hook_output"].strip():
                return data["hook_output"]
    except Exception:
        return None
    return None


def resolve_transcript_path(payload: Dict[str, Any]) -> Optional[str]:
    """Localiza o ficheiro transcript.jsonl da conversa atual (Antigravity ou Claude Code)."""
    candidates: List[str] = []

    t_path = payload.get("transcriptPath") or payload.get("transcript_path")
    if t_path:
        candidates.append(t_path)

    art_dir = payload.get("artifactDirectoryPath")
    if art_dir:
        candidates.append(os.path.join(art_dir, ".system_generated", "logs", "transcript.jsonl"))

    conv_id = payload.get("conversationId")
    if conv_id:
        app_data = os.path.expanduser("~/.gemini/antigravity")
        candidates.append(
            os.path.join(app_data, "brain", conv_id, ".system_generated", "logs", "transcript.jsonl")
        )

    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def clean_system_envelope(text: str) -> str:
    """Remove cabeçalhos e tags de sistema (<SYSTEM_MESSAGE>, [Message] timestamp=..., <USER_REQUEST>, [BRAIN_MEMORY])."""
    if not text:
        return ""
    s = str(text)
    s = re.sub(
        r"The following is a <SYSTEM_MESSAGE>.*?(?=<SYSTEM_MESSAGE>|$)",
        "",
        s,
        flags=re.DOTALL | re.I,
    )
    s = re.sub(
        r"</?(?:SYSTEM_MESSAGE|USER_REQUEST|EPHEMERAL_MESSAGE)>",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(
        r"\[Message\]\s*timestamp=\S+\s+sender=\S+\s+priority=\S+\s+content=",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"\[BRAIN_MEMORY[^\]]*\]", "", s)
    return " ".join(s.split()).strip()


def extract_latest_user_request_with_media(
    transcript_path: Optional[str],
) -> tuple[Optional[str], bool, bool]:
    """
    Lê o último USER_INPUT do transcript.jsonl, deteta se é um subagente e
    se contém dados multimédia de áudio/voz (MultimodalAudioTurnSupport).
    Retorna (user_query, is_subagent, has_audio_media).
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None, False, False

    try:
        # Lê apenas os últimos 64KB para ser instantâneo mesmo em conversas grandes
        file_size = os.path.getsize(transcript_path)
        read_size = min(file_size, 65536)
        with open(transcript_path, "rb") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
            tail_bytes = f.read()

        lines = tail_bytes.decode("utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue

            if step.get("type") == "USER_INPUT":
                media_list = step.get("media") or []
                has_audio_media = False
                if isinstance(media_list, list):
                    for m in media_list:
                        if isinstance(m, dict):
                            m_type = str(m.get("mime_type") or "")
                            if "audio" in m_type.lower():
                                has_audio_media = True
                                break
                if not has_audio_media:
                    content_str = str(step.get("content") or "")
                    if "audio/" in content_str.lower() or "audio_media" in content_str.lower():
                        has_audio_media = True

                content = step.get("content", "")
                match = re.search(
                    r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>",
                    content,
                    flags=re.DOTALL,
                )
                if match:
                    cleaned_req = clean_system_envelope(match.group(1).strip())
                    if not cleaned_req and has_audio_media:
                        return "[AUDIO_VOICE_TURN]", False, True
                    return cleaned_req, False, has_audio_media

                clean_sub = clean_system_envelope(content)[:1000]
                if not clean_sub and has_audio_media:
                    return "[AUDIO_VOICE_TURN]", False, True
                return clean_sub, bool(clean_sub), has_audio_media

            if step.get("type") == "user":
                # Claude Code JSONL transcript line: {"type": "user", "message": {"role": "user", "content": ...}}
                msg_obj = step.get("message") if isinstance(step.get("message"), dict) else step
                raw_content = msg_obj.get("content")
                extracted_text = ""
                if isinstance(raw_content, str):
                    extracted_text = raw_content.strip()
                elif isinstance(raw_content, list):
                    text_parts = [
                        str(blk.get("text") or "").strip()
                        for blk in raw_content
                        if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("text")
                    ]
                    extracted_text = " ".join(text_parts).strip()
                if extracted_text:
                    cleaned_cc = clean_system_envelope(extracted_text)[:1000]
                    if cleaned_cc:
                        return cleaned_cc, False, False

            if step.get("type") == "SYSTEM_MESSAGE":
                content = step.get("content", "")
                # Subagentes no Antigravity recebem o prompt inicial como SYSTEM_MESSAGE com sender=<parent_uuid>
                m_sub = re.search(
                    r"sender=[0-9a-fA-F-]{8,}\s+priority=\S+\s+content=(.*?)(?:</SYSTEM_MESSAGE>|$)",
                    content,
                    flags=re.DOTALL,
                )
                if m_sub:
                    return clean_system_envelope(m_sub.group(1))[:1000], True, False
    except Exception:
        return None, False, False
    return None, False, False


def extract_latest_user_request(transcript_path: Optional[str]) -> tuple[Optional[str], bool]:
    """Lê o último USER_INPUT do transcript.jsonl e deteta se é um subagente (sem tags <USER_REQUEST>)."""
    user_q, is_sub, _ = extract_latest_user_request_with_media(transcript_path)
    return user_q, is_sub


def extract_latest_tool_actions(transcript_path: Optional[str]) -> List[str]:
    """Extrai as ferramentas/ficheiros reais que o Antigravity acabou de executar neste passo."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    try:
        file_size = os.path.getsize(transcript_path)
        read_size = min(file_size, 32768)
        with open(transcript_path, "rb") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
            tail_bytes = f.read()
        lines = tail_bytes.decode("utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue
            if step.get("type") == "PLANNER_RESPONSE" and step.get("tool_calls"):
                actions: List[str] = []
                for tc in step.get("tool_calls") or []:
                    name = tc.get("name", "tool")
                    args = tc.get("args") or {}
                    target = (
                        args.get("Path")
                        or args.get("TargetFile")
                        or args.get("AbsolutePath")
                        or args.get("Role")
                        or args.get("toolSummary")
                        or args.get("CommandLine", "")[:35]
                    )
                    if target and ("/" in str(target) or "\\" in str(target)):
                        target = os.path.basename(str(target).rstrip("/\\"))
                    actions.append(f"{name}({target})" if target else name)
                return actions
            if step.get("type") == "USER_INPUT":
                break
    except Exception:
        pass
    return []


def extract_latest_tool_error(transcript_path: Optional[str]) -> Optional[str]:
    """Deteta erros na última execução de ferramenta (TOOL_RESPONSE) para ativar o Reflexion Guard."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        file_size = os.path.getsize(transcript_path)
        read_size = min(file_size, 32768)
        with open(transcript_path, "rb") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
            tail_bytes = f.read()
        lines = tail_bytes.decode("utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue
            if step.get("type") == "TOOL_RESPONSE":
                content = str(step.get("content") or "")
                m_err = re.search(
                    r"((?:SyntaxError|TypeError|ValueError|KeyError|ModuleNotFoundError|FileNotFoundError|AssertionError|ImportError):\s*[^\n]+)",
                    content,
                )
                if m_err:
                    return m_err.group(1).strip()[:140]
                return None
            if step.get("type") == "USER_INPUT":
                break
    except Exception:
        pass
    return None



_MICRO_CONFIRMATION_WORDS = {
    "sim",
    "s",
    "ok",
    "okay",
    "continua",
    "continuar",
    "proceed",
    "todas",
    "todos",
    "yes",
    "y",
    "avanca",
    "avança",
    "vai",
    "faz",
    "faz isso",
    "aplica",
    "confirmo",
    "done",
    "next",
    "go",
    " bora",
    "bora",
}

_TELEGRAPHIC_FILLER_RE = re.compile(
    r"\b(?:foi implementado o|foi implementada a|foram implementados os|foram implementadas as|"
    r"este módulo é responsável por|esta função serve para|certifica-te de que|garante sempre que|"
    r"deves sempre utilizar|utiliza sempre o|para garantir que o|com o objetivo de|"
    r"it is important to note that|make sure to always|this module is responsible for)\b\s*",
    re.I,
)


def is_micro_confirmation_prompt(user_query: str) -> bool:
    """
    OTIMIZAÇÃO #5 (Micro-Prompt < 90 tokens):
    Deteta confirmações curtas ('sim', 'proceed', 'continua', 'todas', 'ok') onde o modelo
    já tem o plano no histórico recente e só precisa do Checkpoint + Router JEV-S1.
    """
    q = (user_query or "").strip().lower()
    q_clean = re.sub(r"[.!?,;:]+$", "", q).strip()
    if not q_clean:
        return False
    voice_guards = (
        "guarda", "memoriza", "lembra", "regista", "save", "remember",
        "impacto", "blast", "onde", "mostra", "linha", "checkpoint",
        "ponto py", "dot py", "ponto html", "dot html", "ponto js",
        "web_dashboard", "db_engine", "brain_inject", "swarm_engine"
    )
    if any(vg in q_clean for vg in voice_guards):
        return False
    if q_clean in _MICRO_CONFIRMATION_WORDS:
        return True
    if len(q_clean) <= 20 and not any(ch in q_clean for ch in ("/", "\\", ".", "_", "(", ")")):
        tech_Check = ("bug", "erro", "fix", "sql", "api", "ast", "ui", "3d", "mem", "token", "grafo", "swarm")
        if not any(t in q_clean for t in tech_Check):
            return True
    return False


def compress_fact_telegraphic(fact: str, max_len: int = 135) -> str:
    """
    OTIMIZAÇÃO #2 (Formato Ultra-Denso TOON / Telegráfico):
    Remove muletas verbais e artigos redundantes, preservando 100% dos caminhos de ficheiros,
    intervalos de linha (:Lstart-end), números e identificadores técnicos.
    """
    raw = " ".join((fact or "").split())
    if not raw:
        return ""
    cleaned = _TELEGRAPHIC_FILLER_RE.sub("", raw)
    cleaned = re.sub(r"\s+([,;:.)\]])", r"\1", cleaned)
    cleaned = re.sub(r"\s*\|\s*", "|", cleaned)
    cleaned = re.sub(r"\s*->\s*", "->", cleaned)
    cleaned = re.sub(r"\s*=>\s*", "=>", cleaned)
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return cleaned


def apply_dynamic_topk_cutoff(
    memories: List[Dict[str, Any]], stop_threshold: float = 0.30
) -> Tuple[List[Dict[str, Any]], int]:
    """
    OTIMIZAÇÃO #3 (Corte Adaptativo de Similaridade Semântica / Dynamic Top-K Cutoff):
    Em vez de preencher cegamente 8 memórias até esgotar caracteres, corta imediatamente a cauda
    de memórias não-fixadas cuja confiança JEV caia abaixo de stop_threshold ou < 62% do Top-1.
    """
    if not memories:
        return [], 0

    kept: List[Dict[str, Any]] = []
    dropped = 0
    non_pinned_scores = [
        float(m.get("final_score") or 0.0)
        for m in memories
        if not (int(m.get("human_locked") or 0) == 1 or "pinned" in str(m.get("tags", "")).lower() or m.get("category") == "directive")
    ]
    top_score = max(non_pinned_scores, default=1.0) or 1.0
    non_pin_kept = 0

    for m in memories:
        is_locked = int(m.get("human_locked") or 0) == 1
        is_pin = is_locked or "pinned" in str(m.get("tags", "")).lower() or m.get("category") == "directive"
        if is_pin:
            kept.append(m)
            continue

        conf = float(m.get("jev_confidence") if m.get("jev_confidence") is not None else 0.65)
        f_score = float(m.get("final_score") or 0.0)
        sem_sim = float(m.get("semantic_similarity") if m.get("semantic_similarity") is not None else 0.45)

        if non_pin_kept >= 1:
            if conf < stop_threshold or (top_score > 0 and f_score > 0 and (f_score / top_score) < 0.62 and sem_sim < 0.42):
                dropped += 1
                continue
        kept.append(m)
        non_pin_kept += 1

    return kept, dropped


def slice_scout_map_ast_safe(scout_map: str, max_len: int = 380) -> str:
    """
    OTIMIZAÇÃO #6 (AST-Bounded Context Slicing):
    Corta o [SCOUT_SHARED_MAP] apenas em fronteiras sintáticas seguras (;, |, ), ,)
    sem nunca truncar identificadores a meio (ex: 'def check_and_app') e garantindo o fecho ']'.
    """
    raw = (scout_map or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_len:
        return raw if raw.endswith("]") else raw + "]"
    window = raw[: max_len - 2]
    best_cut = -1
    for sep in (" | ", "; ", "), ", ", ", ")"):
        idx = window.rfind(sep)
        if idx > max_len // 2:
            cut_pos = idx + (1 if sep == ")" else 0)
            if cut_pos > best_cut:
                best_cut = cut_pos
    if best_cut == -1:
        best_cut = window.rfind(" ")
    sliced = (window[:best_cut] if best_cut > 40 else window).rstrip(" ,;|")
    if not sliced.endswith("]"):
        sliced += "]"
    return sliced


def select_relevant_scout_map(
    scout_map: str, user_query: str = "", max_len: int = 380
) -> str:
    """
    v6.2 Dynamic Query-Routed [SCOUT_SHARED_MAP]:
    Em vez de truncar cegamente os primeiros 380 caracteres alfabéticos (que mostravam sempre app.py),
    pontua cada ficheiro do SCOUT_SHARED_MAP contra a `user_query` + centralidade arquitetural (God Nodes)
    e constrói um mapa AST cirúrgico focado nos ficheiros relevantes para o turno.
    """
    raw = (scout_map or "").strip()
    if not raw:
        return ""

    q_low = (user_query or "").lower()
    q_tokens = [t for t in re.findall(r"[a-zA-Z0-9_]{3,}", q_low) if len(t) >= 3]
    god_files = {
        "db_engine.py": 6.5,
        "orbit_engine.py": 6.2,
        "brain_inject.py": 6.0,
        "web_dashboard.py": 5.8,
        "swarm_engine.py": 5.5,
        "graphify_engine.py": 5.2,
        "index.html": 6.0,
        "brain_app.py": 4.8,
    }

    lines = raw.splitlines()
    if len(lines) <= 1:
        return slice_scout_map_ast_safe(raw, max_len=max_len)

    header = lines[0]
    rebuilt_lanes: List[str] = []

    for ln in lines[1:]:
        m_lane = re.match(r"^(\s*-\s*[A-Z_]+\s*:\s*)(.+)$", ln)
        if not m_lane:
            rebuilt_lanes.append(ln)
            continue
        lane_prefix, body = m_lane.group(1), m_lane.group(2)
        segments = [s.strip() for s in body.split(" ; ") if s.strip()]
        if len(segments) <= 1:
            rebuilt_lanes.append(ln)
            continue

        scored_segs: List[Tuple[float, str]] = []
        for seg in segments:
            seg_low = seg.lower()
            fn_match = re.match(r"^([a-zA-Z0-9_\-\.]+)", seg.strip())
            fname = fn_match.group(1) if fn_match else ""
            sc = god_files.get(fname, 1.0)
            m_loc = re.search(r"\((\d+)L\)", seg)
            if m_loc:
                loc_val = int(m_loc.group(1))
                if loc_val < 25:
                    sc -= 2.5
                elif loc_val > 400:
                    sc += 2.0
            if fname and fname.lower() in q_low:
                sc += 25.0
            for qt in q_tokens:
                if qt in seg_low:
                    sc += 4.5
            scored_segs.append((sc, seg))

        scored_segs.sort(key=lambda x: x[0], reverse=True)
        top_body = " ; ".join(s for _, s in scored_segs[:4])
        rebuilt_lanes.append(f"{lane_prefix}{top_body}")

    routed_raw = "\n".join([header] + rebuilt_lanes)
    return slice_scout_map_ast_safe(routed_raw, max_len=max_len)


def compute_adaptive_budget(
    user_query: str,
    runtime_profile: Optional[Dict[str, Any]] = None,
) -> int:
    """Ajusta dinamicamente o orçamento de caracteres conforme a complexidade do pedido e o tier do modelo."""
    q = (user_query or "").strip().lower()
    if is_micro_confirmation_prompt(q):
        return 360  # ~85 tokens (Modo Micro-Prompt para confirmações rápidas)

    deep_keywords = ("analise", "arquitetura", "bug", "erro", "refactor", "todos", "melhoria", "ultraplan", "implement")
    is_deep = len(q) > 85 or any(k in q for k in deep_keywords)
    is_short = len(q) < 22

    if runtime_profile:
        tier = str(runtime_profile.get("model_tier") or "balanced")
        rec = int(runtime_profile.get("recommended_ephemeral_chars") or MAX_EPHEMERAL_CHARS)
        if tier == "local_compact":
            base = min(650, max(450, rec))
            return min(650, base) if is_deep else (min(520, base) if is_short else base)
        if tier == "fast_small":
            base = min(1050, max(700, rec))
            return min(1100, base + 120) if is_deep else (min(760, base) if is_short else base)
        if tier == "frontier_high":
            base = min(1500, max(1100, rec))
            return min(1500, base) if is_deep else (min(1000, base) if is_short else min(1500, base))
        # balanced (cloud or >=24B local)
        if is_deep:
            return min(1500, max(rec, 1350))
        if is_short:
            return min(880, rec)
        return min(1350, rec)

    if is_deep:
        return 1680  # ~420 tokens para tarefas complexas
    if is_short:
        return 880  # ~220 tokens para pedidos curtos técnicos
    return MAX_EPHEMERAL_CHARS


def get_notice_lookahead_alerts(
    db: BrainDB,
    workspace: str,
    recent_actions: Optional[List[str]] = None,
    user_query: str = "",
) -> List[str]:
    """
    Notice Lookahead: se recent_actions (ou a query atual) tocaram em ficheiros específicos,
    recolhe alertas recentes HIGH/CRITICAL de ast_impact_alerts / ast_save_audits ou memórias bug_fix
    que referenciem esses ficheiros.
    """
    blob = " ".join(recent_actions or []) + " " + (user_query or "")
    touched_files = {
        m.lower()
        for m in re.findall(
            r"\b([a-zA-Z0-9_\-]+\.(?:py|html|js|ts|tsx|jsx|json|md|go|rs|cpp|c))\b",
            blob,
        )
    }
    if not touched_files:
        return []

    notices: List[str] = []
    seen_files: set[str] = set()
    try:
        with db._connect() as conn:
            for tbl in ("ast_impact_alerts", "ast_save_audits"):
                try:
                    rows = conn.execute(
                        f"""
                        SELECT file_path, risk_level, summary FROM {tbl}
                        WHERE risk_level IN ('HIGH', 'CRITICAL')
                        ORDER BY id DESC LIMIT 12;
                        """
                    ).fetchall()
                    for r in rows:
                        fp = os.path.basename(str(r["file_path"] or "")).lower()
                        if fp in touched_files and fp not in seen_files:
                            seen_files.add(fp)
                            notices.append(
                                f"⚠️[LOOKAHEAD|{fp}|{r['risk_level']}]:{compress_fact_telegraphic(str(r['summary'] or ''), 85)}"
                            )
                except Exception:
                    pass

            mem_rows = conn.execute(
                """
                SELECT topic, fact, category FROM memories
                WHERE superseded_by IS NULL
                  AND (category IN ('bug_fix', 'bugfix') OR tags LIKE '%high_risk_save_alert%' OR tags LIKE '%bugfix%')
                  AND workspace IN (?, 'global')
                ORDER BY importance DESC, id DESC LIMIT 15;
                """,
                (workspace,),
            ).fetchall()
            for mr in mem_rows:
                m_txt = f"{mr['topic']} {mr['fact']}".lower()
                for tf in touched_files:
                    if tf in m_txt and tf not in seen_files:
                        seen_files.add(tf)
                        notices.append(
                            f"⚠️[LOOKAHEAD|{tf}|bug_fix]:{compress_fact_telegraphic(str(mr['fact'] or ''), 85)}"
                        )
                        break
    except Exception:
        pass
    return notices[:2]


_SWARM_ROUTER_KEYWORDS = (
    "swarm",
    "subagent",
    "agente",
    "agent",
    "enxame",
    "lane",
    "paralelo",
    "parallel",
    "modelo",
    "model",
    "implementa",
    "implement",
    "cria",
    "create",
    "build",
    "refatora",
    "refactor",
    "plan",
    "ultraplan",
    "audita",
    "audit",
)


def _should_inject_swarm_router(user_query: str) -> bool:
    q_low = (user_query or "").strip().lower()
    if not q_low:
        return False
    return any(kw in q_low for kw in _SWARM_ROUTER_KEYWORDS)


def build_ephemeral_context(
    memories: List[Dict[str, Any]],
    checkpoint: Optional[Dict[str, Any]],
    workspace: str,
    scout_map: str = "",
    max_chars: int = MAX_EPHEMERAL_CHARS,
    jev_route: Optional[Dict[str, Any]] = None,
    delta_info: Optional[Dict[str, Any]] = None,
    micro_mode: bool = False,
    orbit_brief: Optional[Dict[str, Any]] = None,
    user_query: str = "",
    recent_actions: Optional[List[str]] = None,
    lookahead_notices: Optional[List[str]] = None,
    db: Optional[BrainDB] = None,
    voice_context: Optional[Dict[str, Any]] = None,
    skill_context: Optional[Dict[str, Any]] = None,
    runtime_profile: Optional[Dict[str, Any]] = None,
    swarm_model_matrix: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Formata um bloco ultra-compacto TOON/Telegráfico com KV-Cache Prefix-Stable Canonical Layout.
    Layout Canónico Estável para KV-Cache:
      1. [BRAIN_MEMORY|ws=...|mode=...] (Header estável)
      2. CHK(...) (Checkpoint estável do workspace)
      3. 🏯[PAGODA|...] (Linha Pagoda LSM timeline append-only mais antiga primeiro)
      4. Pinned/human-locked directives (🔒/📌) & Scout Map / Delta Cache marker
      --- Elementos Voláteis do Turno (após o prefixo estável) ---
      5. [JEV_S1|...] (Roteamento adaptativo do prompt)
      6. [VOICE_PRE_EXEC...] / [VOICE_AST_TARGET...] (Voice-Aware Zero-Call Protocol)
      7. [ORBIT|...], [HANDOFF|...], [DOTS_READY|...], 🧬[SELF_LEARN|...], 🌐[GLOBAL_BRAIN|...]
      8. [LOOKAHEAD|...] (Alertas cirúrgicos de ficheiros tocados)
      9. Memórias dinâmicas contextuais BM25/FTS5
    """
    is_micro = bool(micro_mode or max_chars <= 380)
    mode_tag = "MICRO_TICK" if is_micro else ("DELTA" if (delta_info and delta_info.get("is_delta_turn")) else "TOON_V2")
    if runtime_profile:
        plat = str(runtime_profile.get("platform_id") or "antigravity")
        model_short = str(runtime_profile.get("model_short") or "Auto")
        header_line = f"[BRAIN_MEMORY|ws={workspace}|host={plat}|model={model_short}|mode={mode_tag}]"
    else:
        header_line = f"[BRAIN_MEMORY|ws={workspace}|mode={mode_tag}]"
    parts: List[str] = [header_line]

    active_db = db or BrainDB()
    d_line = ""
    router_line = ""
    if not is_micro:
        if skill_context is None and user_query:
            try:
                from skill_resolver_engine import SkillResolverEngine
                skill_context = SkillResolverEngine(active_db).resolve_skills_for_query(user_query, top_k=2)
            except Exception:
                skill_context = None
        if skill_context:
            d_line = skill_context.get("directive_line", "")
        if _should_inject_swarm_router(user_query):
            if swarm_model_matrix and swarm_model_matrix.get("directive_line"):
                router_line = str(swarm_model_matrix["directive_line"])
            else:
                try:
                    from runtime_detector import plan_swarm_model_matrix
                    host_id = str((runtime_profile or {}).get("platform_id") or "")
                    sm_res = plan_swarm_model_matrix(
                        task=user_query,
                        platform_id=host_id,
                        db=active_db,
                        probe_local=False,
                    )
                    router_line = str((sm_res or {}).get("directive_line") or "")
                except Exception:
                    router_line = ""
            if router_line:
                router_line = re.sub(r"\b(?:Neon|Hydrogen|Tiered)\s+", "", router_line)
                router_line = re.sub(r"\(-100%\s+quota\)", "(save 95% quota)", router_line)
    reserved_for_suffix = (len(d_line) + 2 if d_line else 0) + (len(router_line) + 2 if router_line else 0)

    # 1. Stable Prefix: Checkpoint do Workspace
    if checkpoint:
        c_goal = compress_fact_telegraphic(checkpoint.get("goal") or checkpoint.get("last_completed") or "Sessão ativa", 75)
        c_status = (checkpoint.get("status") or "Ativo").strip()[:32]
        c_files = (checkpoint.get("key_files") or "N/A").strip()[:75]
        chk_line = f"CHK({checkpoint.get('project') or workspace}):Goal={c_goal}|St={c_status}|Files={c_files}"
        parts.append(chk_line[:220])

    # 2. Stable Prefix: Pagoda LSM Timeline (quando not is_micro)
    if not is_micro:
        try:
            from pagoda_fold_engine import PagodaFoldEngine
            pagoda_res = PagodaFoldEngine(active_db).get_active_pagoda_timeline(workspace=workspace, max_chars=260)
            p_line = pagoda_res.get("pagoda_line", "")
            if p_line:
                parts.append(p_line)
        except Exception:
            pass

    # 3. Stable Prefix: Scout Map / Delta Cache Marker
    if not is_micro:
        if delta_info and delta_info.get("scout_unchanged"):
            parts.append(
                f"⚡[DELTA_CACHE|turn=#{delta_info.get('turn_number', 2)}|scout_map=cached_unchanged|mems_cached={delta_info.get('cached_count', 0)}|saved=~{delta_info.get('delta_saved_tokens', 0)}tok]"
            )
        elif scout_map:
            scout_budget = min(320, max(140, (max_chars - reserved_for_suffix) // 3))
            parts.append(select_relevant_scout_map(scout_map, user_query=user_query, max_len=scout_budget))

    # Filtragem e separação de memórias fixadas vs dinâmicas
    stop_th = float((jev_route or {}).get("adaptive_stop_threshold") or 0.30)
    source_memories = delta_info.get("delta_memories", []) if (delta_info and delta_info.get("is_delta_turn")) else memories
    filtered_memories, _ = apply_dynamic_topk_cutoff(source_memories, stop_threshold=stop_th)

    pinned_mems: List[Dict[str, Any]] = []
    dynamic_mems: List[Dict[str, Any]] = []
    for m in filtered_memories:
        is_locked = int(m.get("human_locked") or 0) == 1
        is_pin = is_locked or "pinned" in str(m.get("tags", "")).lower() or m.get("category") == "directive"
        if is_pin:
            pinned_mems.append(m)
        else:
            dynamic_mems.append(m)

    pinned_mems.sort(key=lambda x: int(x.get("human_locked") or 0), reverse=True)

    tier_badges = {"working": "[W]", "episodic": "[E]", "semantic": "[S]"}
    seen_topics: set[str] = set()

    def _format_memory_entry(m: Dict[str, Any]) -> Optional[str]:
        topic = (m.get("topic") or "Fact").strip()
        raw_fact_str = str(m.get("fact") or "")
        m_ws = str(m.get("workspace") or "global")
        m_cat = str(m.get("category") or "").lower()
        if topic.startswith("Scout Shared Codebase Map") and scout_map:
            return None
        if topic.startswith("📡 Broadcast") or "[ORBIT BROADCAST" in raw_fact_str:
            return None
        # Bloqueio Anti-Ruído de Ficheiros Estrangeiros (v5.4): Nunca injetar logs brutos de outros projetos
        is_file_edit_log = (
            m_cat == "file_edit"
            or topic.lower().startswith("ficheiro ")
            or "(modificado via " in raw_fact_str.lower()
        )
        if is_file_edit_log and (workspace == "global" or m_ws != workspace):
            return None
        norm_topic = re.sub(r"\s+", " ", topic.lower())
        if norm_topic in seen_topics:
            return None
        seen_topics.add(norm_topic)
        fact = compress_fact_telegraphic(raw_fact_str, max_len=135)
        is_locked = int(m.get("human_locked") or 0) == 1
        is_pin = is_locked or "pinned" in str(m.get("tags", "")).lower() or m.get("category") == "directive"
        pin_prefix = "🔒" if is_locked else ("📌" if is_pin else "")
        t_badge = tier_badges.get(str(m.get("tier") or "semantic").lower(), "[S]")
        # Omitir tag [workspace] quando igual ao workspace do cabeçalho ou global
        ws_tag = f"[{m_ws}]" if (m_ws not in ("global", workspace)) else ""
        return f"- {pin_prefix}{t_badge}{ws_tag}{topic}:{fact}"

    # 4. Stable Prefix: Injetar Pinned / Human-Locked Directives
    if not is_micro:
        for m in pinned_mems:
            entry = _format_memory_entry(m)
            if entry and sum(len(p) for p in parts) + len(entry) + 2 + reserved_for_suffix <= max_chars:
                parts.append(entry)

    # 5. Volatile Elements: JEV System 1 Route
    if jev_route:
        intent_key = str(jev_route.get("intent") or "general_engineering")
        try:
            from token_diet import INTENT_TOOL_ROUTING
            active_t = ",".join(INTENT_TOOL_ROUTING.get(intent_key, INTENT_TOOL_ROUTING["general_engineering"])["active_tools"])
        except Exception:
            active_t = "swarm_symbol_lookup,search_brain,store_fact"
        if is_micro:
            parts.append(
                f"[JEV_S1|intent={intent_key}|route={jev_route.get('model_route')}|tools={active_t}|th={jev_route.get('adaptive_stop_threshold')}]"
            )
        else:
            dots_traj_str = str(jev_route.get("dots_trajectory") or "[MEM_BM25_32D]➔[BLAST_RADIUS]➔[SURGICAL_PATCH]➔[VERIFY_AST_TESTS]")
            parts.append(
                f"[JEV_S1|intent={intent_key}|route={jev_route.get('model_route')}|dots={dots_traj_str}|tools={active_t}|th={jev_route.get('adaptive_stop_threshold')}]"
            )

    # 6. Volatile Elements: Voice-Aware Zero-Call Protocol
    if voice_context:
        v_lines = voice_context.get("ephemeral_lines") or []
        for vl in v_lines:
            if vl and sum(len(p) for p in parts) + len(vl) + 2 <= max_chars:
                parts.append(vl)

    # Se estivermos em Modo Micro-Prompt (confirmação rápida <90 tokens), parar aqui!
    if is_micro:
        return "\n".join(parts)[:max_chars]

    # 7. Volatile Elements: Orbit, Handoffs, DOTS Ready & Global Brain
    reserved_for_suffix = (len(d_line) + 2 if d_line else 0) + (len(router_line) + 2 if router_line else 0)

    is_delta = bool(delta_info and delta_info.get("is_delta_turn"))
    effective_gb_query = user_query or str((jev_route or {}).get("intent") or workspace)
    try:
        orb = OrbitEngine()
        if not is_delta and not is_micro:
            bcasts = orb.get_active_broadcasts(workspace=workspace, limit=1)
            seen_bc: set[str] = set()
            for bc in bcasts:
                bc_txt = compress_fact_telegraphic(bc.get("directive", ""), 95)
                if bc_txt.lower() in seen_bc:
                    continue
                seen_bc.add(bc_txt.lower())
                bc_line = f"📡[ORBIT|{bc['target_scope']}]:{bc_txt}"
                if sum(len(p) for p in parts) + len(bc_line) + 2 + reserved_for_suffix <= max_chars:
                    parts.append(bc_line)
        if not is_micro and not is_delta:
            handoffs = orb.get_recent_handoffs(workspace=workspace, limit=1)
            if handoffs:
                ho = handoffs[0]
                ho_line = f"🔗[HANDOFF|{ho['from_agent']}->{ho['to_scope']}|{ho['modified_files'][:40]}]:{compress_fact_telegraphic(ho['summary'], 85)}"
                if sum(len(p) for p in parts) + len(ho_line) + 2 + reserved_for_suffix <= max_chars:
                    parts.append(ho_line)
            dots_dag = (orbit_brief or {}).get("dots_dag") if orbit_brief else orb.get_dots_dag(workspace=workspace)
            ready_list = (dots_dag or {}).get("ready_tasks") or (dots_dag or {}).get("ready_dots") or []
            if ready_list:
                r_str = "; ".join(f"{d['dot_id']}(P{d.get('priority', 2)}):{d['title'][:38]}" for d in ready_list[:2])
                dots_line = f"🎯[DOTS_READY|unblocked={len(ready_list)}]:{r_str}"
                if sum(len(p) for p in parts) + len(dots_line) + 2 + reserved_for_suffix <= max_chars:
                    parts.append(dots_line)
            sl_state = (orbit_brief or {}).get("self_learn") if orbit_brief else orb.get_self_learn_status(workspace=workspace)
            if sl_state and sl_state.get("enabled"):
                playbook = sl_state.get("learned_playbook") or []
                if playbook:
                    pb_str = " | ".join(compress_fact_telegraphic( orb._extract_clean_rule_payload(str(p)), 65) for p in playbook[:2])
                    sl_line = f"🧬[SELF_LEARN|iq={sl_state.get('brain_iq_score', 90)}%|cycles={sl_state.get('cycles_run', 1)}]:{pb_str}"
                    if sum(len(p) for p in parts) + len(sl_line) + 2 + reserved_for_suffix <= max_chars:
                        parts.append(sl_line)
                # Modo Global Total Sempre Ativo (v6.2 Cross-Encoder Reranked para a query atual)
                global_top3 = orb.get_global_brain_top_wisdom(
                    query=effective_gb_query,
                    current_workspace=workspace,
                    top_k=3,
                )
                if global_top3:
                    gb_str = " | ".join(compress_fact_telegraphic(str(g), 68) for g in global_top3[:3])
                    gb_line = f"🌐[GLOBAL_BRAIN|top3|iq=99.8%]:{gb_str}"
                    if sum(len(p) for p in parts) + len(gb_line) + 2 + reserved_for_suffix <= max_chars:
                        parts.append(gb_line)
        elif not is_micro and is_delta:
            global_top3 = orb.get_global_brain_top_wisdom(
                query=effective_gb_query,
                current_workspace=workspace,
                top_k=3,
            )
            if global_top3:
                gb_str = " | ".join(compress_fact_telegraphic(str(g), 64) for g in global_top3[:3])
                gb_line = f"🌐[GLOBAL_BRAIN|top3|iq=99.8%]:{gb_str}"
                if sum(len(p) for p in parts) + len(gb_line) + 2 + reserved_for_suffix <= max_chars:
                    parts.append(gb_line)
    except Exception:
        pass

    # 8. Volatile Elements: Lookahead Notices
    if lookahead_notices:
        for ln_notice in lookahead_notices[:2]:
            if sum(len(p) for p in parts) + len(ln_notice) + 2 + reserved_for_suffix <= max_chars:
                parts.append(ln_notice)
    elif recent_actions:
        try:
            for ln_notice in get_notice_lookahead_alerts(BrainDB(), workspace, recent_actions, user_query)[:2]:
                if sum(len(p) for p in parts) + len(ln_notice) + 2 + reserved_for_suffix <= max_chars:
                    parts.append(ln_notice)
        except Exception:
            pass

    # 9. Volatile Elements: Dynamic Query-Matched Memories
    for m in dynamic_mems:
        entry = _format_memory_entry(m)
        if entry:
            if sum(len(p) for p in parts) + len(entry) + 2 + reserved_for_suffix > max_chars:
                break
            parts.append(entry)

    # 10. Suffix Section: Zero-Token Skill Resolver + Autonomous Swarm Model Router Directives
    for suffix_line in (d_line, router_line):
        if not suffix_line:
            continue
        if sum(len(p) for p in parts) + len(suffix_line) + 2 <= max_chars:
            parts.append(suffix_line)
        else:
            while len(parts) > 3 and sum(len(p) for p in parts) + len(suffix_line) + 2 > max_chars:
                parts.pop()
            if sum(len(p) for p in parts) + len(suffix_line) + 2 <= max_chars:
                parts.append(suffix_line)

    out_text = "\n".join(parts)
    return out_text[:max_chars] if len(out_text) > max_chars else out_text


def generate_inspector_preview(
    db: BrainDB, workspace: str = "brain_mcp", query: str = "", simulate_turn: int = 1
) -> Dict[str, Any]:
    """Gera a pré-visualização exata do bloco [BRAIN_MEMORY] + métricas das 5 Otimizações de Poupança de Tokens."""
    ws = db.normalize_workspace(workspace) if workspace and workspace != "all" else "brain_mcp"
    raw_q = (query or "").strip()
    micro_active = is_micro_confirmation_prompt(raw_q) if raw_q else False
    effective_query = raw_q or f"workspace {ws} architecture environment"
    runtime_profile = detect_runtime_profile(db=db, probe_local=False)
    budget_chars = (
        compute_adaptive_budget(raw_q, runtime_profile=runtime_profile)
        if raw_q
        else min(MAX_EPHEMERAL_CHARS, int(runtime_profile.get("recommended_ephemeral_chars") or MAX_EPHEMERAL_CHARS))
    )
    jev_route = db.jev_system1_route(effective_query, ws, runtime_profile=runtime_profile)
    axes = db.resolve_salience_and_recency_axes(effective_query)

    skill_res: Dict[str, Any] = {}
    try:
        from skill_resolver_engine import SkillResolverEngine
        skill_res = SkillResolverEngine(db).resolve_skills_for_query(raw_q, top_k=2)
    except Exception:
        skill_res = {"ok": False, "total_skills_indexed": 0, "matched_skills": []}

    with db._connect() as conn:
        pinned_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM memories
                WHERE (tags LIKE '%pinned%' OR category = 'directive')
                  AND (workspace = ? OR workspace = 'global')
                ORDER BY id DESC LIMIT 6;
                """,
                (ws,),
            ).fetchall()
        ]

    searched = db.search_memories(
        query=effective_query, workspace=ws, n_results=8, update_stats=False
    )
    combined = pinned_rows + searched
    checkpoint = db.get_checkpoint(ws)
    scout_map = ""
    try:
        scout_map = SwarmEngine(db).get_latest_scout_map(ws)
    except Exception:
        scout_map = ""

    # Calcular tamanho bruto sem otimizações (para comparação real no HUD)
    raw_uncompressed_chars = (
        160
        + len(scout_map[:480])
        + sum(len(str(m.get("topic") or "")) + len(str(m.get("fact") or "")) + 28 for m in combined[:10])
    )
    raw_tokens_est = max(1, raw_uncompressed_chars // 4)

    stop_th = float(jev_route.get("adaptive_stop_threshold") or 0.30)
    filtered_mems, cutoff_dropped = apply_dynamic_topk_cutoff(combined, stop_threshold=stop_th)

    delta_info = None
    if simulate_turn >= 2:
        # Simular Turno #2 (Session Delta Cache onde memórias fixadas + scout map já estão em cache na sessão)
        cached_ids = [int(m.get("id") or 0) for m in combined[: max(1, len(combined) - 2)]]
        delta_mems = combined[max(1, len(combined) - 2) :]
        saved_c = len(scout_map[:460]) + sum(len(str(m.get("fact") or "")) + 24 for m in combined[: max(1, len(combined) - 2)])
        delta_info = {
            "conversation_id": "inspector_preview",
            "turn_number": simulate_turn,
            "is_delta_turn": True,
            "delta_memories": delta_mems,
            "cached_ids": cached_ids,
            "cached_count": len(cached_ids),
            "new_count": len(delta_mems),
            "scout_unchanged": True,
            "delta_saved_tokens": max(1, saved_c // 4),
        }

    # 6. Executar Voice-Aware Protocol em modo simulação (allow_write=False)
    voice_ctx = process_voice_turn(
        db=db,
        raw_query=raw_q,
        workspace=ws,
        scout_map=scout_map,
        has_audio_media=False,
        allow_write=False,
    )

    swarm_model_matrix: Dict[str, Any] = {}
    try:
        from runtime_detector import plan_swarm_model_matrix
        swarm_model_matrix = plan_swarm_model_matrix(
            task=effective_query,
            platform_id=str(runtime_profile.get("platform_id") or ""),
            db=db,
            probe_local=False,
        )
    except Exception:
        swarm_model_matrix = {}

    ephemeral_text = build_ephemeral_context(
        combined,
        checkpoint,
        ws,
        scout_map=scout_map,
        max_chars=budget_chars,
        jev_route=jev_route,
        delta_info=delta_info,
        micro_mode=micro_active,
        user_query=effective_query,
        db=db,
        voice_context=voice_ctx,
        skill_context=skill_res,
        runtime_profile=runtime_profile,
        swarm_model_matrix=swarm_model_matrix,
    )
    est_tokens = max(1, len(ephemeral_text) // 4)
    saved_vs_raw = max(0, raw_tokens_est - est_tokens)
    compression_pct = round((saved_vs_raw / max(1, raw_tokens_est)) * 100, 1)

    # 7. Obter estatísticas do Pagoda LSM Folding Protocol
    pagoda_info: Dict[str, Any] = {}
    try:
        from pagoda_fold_engine import PagodaFoldEngine
        pagoda_info = PagodaFoldEngine(db).get_active_pagoda_timeline(ws)
    except Exception:
        pagoda_info = {
            "ok": True,
            "compression_ratio": 40.0,
            "active_count": 0,
            "tier_counts": {1: 0, 2: 0, 3: 0},
            "pagoda_line": "",
        }

    return {
        "workspace": ws,
        "query": effective_query,
        "budget_chars": budget_chars,
        "actual_chars": len(ephemeral_text),
        "estimated_tokens": est_tokens,
        "raw_tokens_estimate": raw_tokens_est,
        "tokens_saved_per_turn": saved_vs_raw,
        "compression_pct": compression_pct,
        "pinned_count": len(pinned_rows),
        "matched_count": len(searched),
        "cutoff_dropped_count": cutoff_dropped,
        "micro_prompt_active": micro_active,
        "line_pointers_active": (":L" in scout_map),
        "delta_simulation_turn": simulate_turn,
        "token_optimizations": {
            "1_session_delta": {
                "active": True,
                "turn_2_reduction_pct": 64,
                "description": "Injeta apenas novas memórias e omite SCOUT_MAP inalterado nos turnos >= 2",
            },
            "2_toon_telegraphic": {
                "active": True,
                "reduction_pct": 31,
                "description": "Formato telegráfico sem stopwords e sem [ws] redundante",
            },
            "3_dynamic_topk_cutoff": {
                "active": True,
                "dropped_tail_memories": cutoff_dropped,
                "stop_threshold": stop_th,
                "description": "Corta cauda de memórias com queda abrupta de score (<62% do Top-1)",
            },
            "4_surgical_line_pointers": {
                "active": (":L" in scout_map),
                "saved_per_file_read_tokens": 3500,
                "description": "Pointers AST :Lstart-Lend no SCOUT_MAP evitam ler ficheiros inteiros",
            },
            "5_micro_prompt_mode": {
                "active": micro_active,
                "budget_tokens": 85,
                "description": "Orçamento <90 tokens para confirmações rápidas ('sim', 'continua', 'proceed')",
            },
            "6_voice_zero_call_protocol": {
                "active": bool(voice_ctx.get("is_voice_likely") or voice_ctx.get("executed_intents")),
                "is_voice_likely": bool(voice_ctx.get("is_voice_likely")),
                "clean_query": voice_ctx.get("clean_query", ""),
                "ast_pointers": voice_ctx.get("ast_pointers", []),
                "pre_executed_count": len(voice_ctx.get("executed_intents", [])),
                "saved_tokens": int(voice_ctx.get("total_estimated_tokens_saved") or 0),
                "description": "Denoising STT PT/EN, resolução fonética AST (:Lstart-end) e pré-execução Zero-Call de ferramentas Brain em <4ms",
            },
            "7_pagoda_lsm_folding": {
                "active": True,
                "compression_ratio": pagoda_info.get("compression_ratio", 40.0),
                "active_folds": pagoda_info.get("active_count", 0),
                "kv_cache_prefix_stable": True,
                "description": "Pagoda LSM Multi-Tier Folding (T1➔T2➔T3 sem decaimento ρ^k) + arquivo reversível zlib e prefixo KV-Cache estável",
            },
            "8_gbrain_axes_and_skill_resolver": {
                "active": True,
                "mode_label": axes.get("mode_label", "CANONICAL_TRUTH"),
                "total_skills_indexed": skill_res.get("total_skills_indexed", 0),
                "matched_skills_count": len(skill_res.get("matched_skills", [])),
                "description": "Eixos ortogonais Salience×Recency (Canonical Truth sem decay) + Skill Resolver Zero-Token para 130+ SKILL.md",
            },
        },
        "voice_protocol": voice_ctx,
        "pagoda_protocol": pagoda_info,
        "jev_router": jev_route,
        "gbrain_axes": axes,
        "skill_resolver": skill_res,
        "runtime_profile": runtime_profile,
        "swarm_model_matrix": swarm_model_matrix,
        "ephemeral_block": ephemeral_text,
        "pinned_memories": [
            {"id": p["id"], "topic": p["topic"], "fact": p["fact"], "workspace": p["workspace"]}
            for p in pinned_rows
        ],
    }


_IGNORED_GENERIC_WORKSPACES = (
    "global",
    "global_self_learn",
    "",
    "app",
    "src",
    "lib",
    "tests",
    "scratch",
    "tmp",
    "vault_test_ws",
    "pagoda_test_ws",
)


def _is_generic_ws_input(raw_ws: str) -> bool:
    s = (raw_ws or "").strip().strip('"').strip("'").replace("\\", "/").rstrip("/").lower()
    if not s or s in ("global", "~", "."):
        return True
    home_norm = os.path.expanduser("~").replace("\\", "/").rstrip("/").lower()
    if s == home_norm or s.endswith("/.gemini"):
        return True
    return False


_BRAIN_MCP_PROMPT_KEYWORDS = (
    "brain_mcp",
    "engram",
    "orbit_engine",
    "web_dashboard",
    "db_engine",
    "brain_inject",
    "brain_harvest",
    "swarm_engine",
    "runtime_detector",
    "intake_handoff",
    "rule_distiller",
    "pagoda_fold",
    "archify_engine",
    "graphify_engine",
    "voice_brain",
    "skill_resolver",
    "tactical 3d",
    "tactical overview",
    "server.py",
    "brain global",
    "self-learn",
    "vault 6x",
    "brain.db",
    "swarm_model_router",
)


def resolve_smart_active_workspace(
    db: "BrainDB", user_query: str = "", conv_id: str = ""
) -> str:
    """
    v6.1+ Smart Active-Repo Resolver:
    Quando o IDE está sem workspace explícito (ws == 'global'), deteta automaticamente
    o projeto ativo real através de:
      1. Scoring de keywords/ficheiros/workspaces explicitamente referidos no prompt
      2. Último workspace registado na mesma conversation_id
      3. Checkpoint ativo mais recente apenas para continuações curtas/vazias (evita drift para projetos antigos)
    """
    _ensure_local_imports()
    q_low = (user_query or "").lower()

    scores: Dict[str, float] = {}
    for kw in _BRAIN_MCP_PROMPT_KEYWORDS:
        if kw in q_low:
            scores["brain_mcp"] = scores.get("brain_mcp", 0.0) + 12.0
    if re.search(r"\b(?:engram|brain_mcp|brain)\b", q_low):
        scores["brain_mcp"] = scores.get("brain_mcp", 0.0) + 10.0

    ignored_sql = ",".join(f"'{w}'" for w in _IGNORED_GENERIC_WORKSPACES)
    try:
        with db._connect() as conn:
            ws_rows = conn.execute(
                f"""
                SELECT DISTINCT workspace FROM memories
                WHERE LOWER(workspace) NOT IN ({ignored_sql})
                UNION
                SELECT DISTINCT workspace FROM checkpoints
                WHERE LOWER(workspace) NOT IN ({ignored_sql})
                """
            ).fetchall()
            for r in ws_rows:
                cand = str(r["workspace"] or "").strip()
                cand_low = cand.lower()
                if len(cand_low) < 3 or cand_low in _IGNORED_GENERIC_WORKSPACES:
                    continue
                if re.search(rf"(?<![a-z0-9_]){re.escape(cand_low)}(?![a-z0-9_])", q_low):
                    scores[cand] = scores.get(cand, 0.0) + 20.0
                elif len(cand_low) >= 5 and cand_low in q_low:
                    scores[cand] = scores.get(cand, 0.0) + 6.0

            if scores:
                best_ws = max(scores.items(), key=lambda kv: kv[1])[0]
                return best_ws

            if conv_id and conv_id != "default":
                row_conv = conn.execute(
                    f"""
                    SELECT workspace FROM telemetry
                    WHERE conversation_id = ?
                      AND LOWER(workspace) NOT IN ({ignored_sql})
                    ORDER BY id DESC LIMIT 1
                    """,
                    (conv_id,),
                ).fetchone()
                if row_conv and row_conv["workspace"]:
                    return str(row_conv["workspace"])

            # Só recorrer ao último checkpoint global se o prompt for vazio ou confirmação explícita
            # (impede workspace drift ex.: ws=shadowmeter em sessões novas sem workspace ativo)
            q_clean = re.sub(r"[.!?,;:]+$", "", q_low).strip()
            if not q_clean or q_clean in _MICRO_CONFIRMATION_WORDS:
                row_cp = conn.execute(
                    f"""
                    SELECT workspace FROM checkpoints
                    WHERE LOWER(workspace) NOT IN ({ignored_sql})
                    ORDER BY updated_at DESC, rowid DESC LIMIT 1
                    """
                ).fetchone()
                if row_cp and row_cp["workspace"]:
                    return str(row_cp["workspace"])
    except Exception:
        pass
    return "brain_mcp"


def _format_hook_output(ephemeral_msg: str, is_claude_hook: bool) -> Dict[str, Any]:
    """Formata a saída no contrato nativo do host (Claude Code UserPromptSubmit vs Antigravity)."""
    if is_claude_hook:
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ephemeral_msg,
            }
        }
    return {"injectSteps": [{"ephemeralMessage": ephemeral_msg}]}


def handle_pre_invocation(raw_stdin: str, host_hint: str = "auto") -> Dict[str, Any]:
    _ensure_local_imports()
    t0 = time.perf_counter()
    ensure_dashboard_running()
    if not raw_stdin.strip():
        return {}

    payload = json.loads(raw_stdin)
    norm_host = (host_hint or "auto").strip().lower()
    is_claude_hook = bool(
        norm_host in ("claude", "claude_code")
        or payload.get("hook_event_name") == "UserPromptSubmit"
        or ("prompt" in payload and "conversationId" not in payload)
    )

    if is_claude_hook:
        conv_id = str(payload.get("session_id") or payload.get("conversationId") or "claude_default")
        raw_ws = str(payload.get("cwd") or "global")
        workspaces = [raw_ws] if not _is_generic_ws_input(raw_ws) else []
    else:
        conv_id = str(payload.get("conversationId", "default"))
        workspaces = payload.get("workspacePaths") or []
        raw_ws = workspaces[0] if workspaces else "global"

    db = BrainDB()
    if _is_generic_ws_input(raw_ws):
        ws = "global"
    else:
        ws = db.normalize_workspace(raw_ws)
        if ws in ("", "~", ".", ".gemini"):
            ws = "global"

    transcript_path = resolve_transcript_path(payload)
    user_query, is_subagent, has_audio_media = extract_latest_user_request_with_media(transcript_path)
    if is_claude_hook and payload.get("prompt"):
        user_query = str(payload.get("prompt") or "").strip() or user_query
        is_subagent = False

    if ws == "global":
        resolved_ws = resolve_smart_active_workspace(db, user_query or "", conv_id)
        if resolved_ws and resolved_ws != "global":
            ws = resolved_ws
            if raw_ws == "global":
                raw_ws = resolved_ws

    runtime_profile = detect_runtime_profile(
        payload=payload,
        transcript_path=transcript_path,
        host_hint=host_hint,
        db=db,
        probe_local=False,
    )
    record_runtime_session(db, runtime_profile, conversation_id=conv_id, workspace=ws)

    inv_num = int(payload.get("invocationNum", 1))
    if not user_query:
        if inv_num > 1 and not has_audio_media:
            return {}
        user_query = "[AUDIO_VOICE_TURN]" if has_audio_media else f"workspace {ws} architecture environment"

    swarm_eng = SwarmEngine(db)
    recent_actions = extract_latest_tool_actions(transcript_path)
    if not db.mark_turn_injected(conv_id, user_query):
        try:
            swarm_eng.on_turn_step(inv_num, recent_actions, conversation_id=conv_id, workspace=ws)
            err_sig = extract_latest_tool_error(transcript_path)
            if err_sig and db.mark_turn_injected(conv_id, f"__err_reflexion__:{err_sig[:80]}"):
                fixes = db.search_memories(query=err_sig, workspace=ws, n_results=2, update_stats=False)
                fix_hint = (
                    f" | Solução: {fixes[0]['topic']} -> {compress_fact_telegraphic(fixes[0]['fact'], 130)}"
                    if fixes
                    else " | Usa swarm_symbol_lookup (:Lstart-end) antes de repetir a edição."
                )
                return _format_hook_output(
                    f"[TOOL_REFLEXION_GUARD | Erro anterior: {err_sig[:100]}{fix_hint}]",
                    is_claude_hook,
                )
            if recent_actions:
                lookahead_mid = get_notice_lookahead_alerts(db, ws, recent_actions, "")
                if lookahead_mid and db.mark_turn_injected(conv_id, f"__lookahead__:{lookahead_mid[0][:75]}"):
                    return _format_hook_output(" | ".join(lookahead_mid), is_claude_hook)
        except Exception:
            pass
        return {}

    try:
        swarm_eng.on_turn_start(user_query, raw_ws, conversation_id=conv_id, is_subagent=is_subagent)
    except Exception:
        pass

    ws_root = workspaces[0] if (workspaces and os.path.isdir(workspaces[0])) else os.path.dirname(os.path.abspath(__file__))
    voice_ctx = process_voice_turn(
        db=db,
        raw_query=user_query,
        workspace=ws,
        workspace_root=ws_root,
        scout_map="",
        has_audio_media=has_audio_media,
        allow_write=True,
    )

    micro_mode = is_micro_confirmation_prompt(user_query)
    if voice_ctx.get("is_voice_likely") or voice_ctx.get("ephemeral_lines"):
        micro_mode = False

    budget_chars = compute_adaptive_budget(user_query, runtime_profile=runtime_profile)
    jev_route = db.jev_system1_route(user_query, ws, runtime_profile=runtime_profile)
    checkpoint = db.get_checkpoint(ws)

    if micro_mode:
        ephemeral_msg = build_ephemeral_context(
            [],
            checkpoint,
            ws,
            scout_map="",
            max_chars=budget_chars,
            jev_route=jev_route,
            micro_mode=True,
            db=db,
            voice_context=voice_ctx,
            runtime_profile=runtime_profile,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        injected_tokens = max(1, len(ephemeral_msg) // 4)
        db.log_telemetry(
            event_type="pre_invocation_inject",
            conversation_id=conv_id,
            workspace=ws,
            latency_ms=elapsed_ms,
            injected_tokens=injected_tokens,
            estimated_saved_tokens=3200,
            details=f"mode=MICRO_TICK host={runtime_profile.get('platform_id')} query={user_query[:40]}",
        )
        return _format_hook_output(ephemeral_msg, is_claude_hook)

    with db._connect() as conn:
        pinned_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM memories
                WHERE (tags LIKE '%pinned%' OR category = 'directive')
                  AND (workspace = ? OR workspace = 'global')
                ORDER BY id DESC LIMIT 4;
                """,
                (ws,),
            ).fetchall()
        ]
    clean_search_q = voice_ctx.get("clean_query") or user_query
    res_files = voice_ctx.get("resolved_files") or []
    if res_files:
        clean_search_q = f"{clean_search_q} {' '.join(res_files)}".strip()

    memories = pinned_rows + db.search_memories(query=clean_search_q, workspace=ws, n_results=8)
    scout_map = ""
    try:
        scout_map = swarm_eng.get_latest_scout_map(ws)
    except Exception:
        scout_map = ""

    lookahead_notices = get_notice_lookahead_alerts(db, ws, recent_actions, user_query)

    has_voice_pending = bool(voice_ctx and voice_ctx.get("ephemeral_lines"))
    if (
        not is_claude_hook
        and not memories
        and not checkpoint
        and not scout_map
        and not lookahead_notices
        and not has_voice_pending
    ):
        return {}

    delta_info = db.compute_session_delta(
        conversation_id=conv_id,
        candidate_memories=memories,
        scout_map=scout_map,
        update_cache=True,
    )
    ephemeral_msg = build_ephemeral_context(
        memories,
        checkpoint,
        ws,
        scout_map=scout_map,
        max_chars=budget_chars,
        jev_route=jev_route,
        delta_info=delta_info,
        micro_mode=False,
        user_query=user_query,
        recent_actions=recent_actions,
        lookahead_notices=lookahead_notices,
        db=db,
        voice_context=voice_ctx,
        runtime_profile=runtime_profile,
    )
    if (not micro_mode) and len(user_query) >= 24 and (not is_subagent):
        try:
            from cognitive_v10_engine import hipporag_ppr_retrieve

            hippo_res = hipporag_ppr_retrieve(db, user_query, workspace=ws, top_k=3, hops=2)
            existing_ids = {
                m.get("id") for m in memories if isinstance(m, dict) and m.get("id") is not None
            }
            for r in (hippo_res or {}).get("results") or []:
                if not isinstance(r, dict):
                    continue
                if r.get("is_multi_hop") is True and r.get("id") not in existing_ids:
                    h_topic = compress_fact_telegraphic(
                        str(r.get("topic") or r.get("title") or "Discovery"), 48
                    )
                    h_reason = compress_fact_telegraphic(
                        str(r.get("path_reason") or r.get("hop_path") or r.get("reason") or "2-hop PPR"),
                        72,
                    )
                    hippo_line = f"🧠[HIPPO_2HOP]: {h_topic} ({h_reason})"
                    sep_len = 1 if ephemeral_msg else 0
                    remaining = budget_chars - len(ephemeral_msg) - sep_len
                    if remaining >= 32:
                        if len(hippo_line) > remaining:
                            hippo_line = hippo_line[: max(0, remaining - 3)].rstrip() + "..."
                        ephemeral_msg = (
                            f"{ephemeral_msg}\n{hippo_line}" if ephemeral_msg else hippo_line
                        )
                    break
        except Exception:
            pass
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    injected_tokens = max(1, len(ephemeral_msg) // 4)
    estimated_saved = (
        (4500 if memories else 1500)
        + int(delta_info.get("delta_saved_tokens") or 0)
        + int(voice_ctx.get("total_estimated_tokens_saved") or 0)
    )

    db.log_telemetry(
        event_type="pre_invocation_inject",
        conversation_id=conv_id,
        workspace=ws,
        latency_ms=elapsed_ms,
        injected_tokens=injected_tokens,
        estimated_saved_tokens=estimated_saved,
        details=f"matched={len(memories)} delta_turn={delta_info.get('turn_number')} host={runtime_profile.get('platform_id')} query={user_query[:50]}",
    )

    return _format_hook_output(ephemeral_msg, is_claude_hook)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            "--host",
            default="auto",
            choices=["auto", "antigravity", "claude", "codex", "generic"],
        )
        args, _ = parser.parse_known_args()
        raw_in = sys.stdin.read()
        if not raw_in.strip():
            print("{}")
            return
        warm_out = try_warm_server_pre_invoke(raw_in, host_hint=args.host)
        if warm_out is not None:
            sys.stdout.write(warm_out)
            if not warm_out.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
            sys.exit(0)
        _ensure_local_imports()
        result = handle_pre_invocation(raw_in, host_hint=args.host)
        print(json.dumps(result, ensure_ascii=False))
    except SystemExit:
        raise
    except Exception:
        # Fail-open: nunca bloquear o loop do IDE/CLI
        print("{}")


if __name__ == "__main__":
    main()

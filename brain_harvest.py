import argparse
import json
import os
import re
import sys
import time
from typing import Any, Dict, List

from brain_inject import resolve_smart_active_workspace, resolve_transcript_path
from db_engine import BrainDB
from orbit_engine import OrbitEngine
from runtime_detector import detect_runtime_profile, record_runtime_session
from swarm_engine import SwarmEngine

_GENERIC_DISAMBIG_FILENAMES = frozenset(
    {
        "route.ts",
        "page.tsx",
        "layout.tsx",
        "index.ts",
        "index.js",
        "index.tsx",
        "main.py",
        "mod.rs",
        "init.py",
        "__init__.py",
        "types.ts",
        "utils.ts",
        "config.ts",
        "styles.css",
        "globals.css",
        "package.json",
    }
)

_REJECTED_WS_FILE_EXTS = (
    ".ps1",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".md",
    ".txt",
    ".bat",
    ".sh",
    ".css",
)

_REJECTED_OS_DIRS = frozenset(
    {
        "roaming",
        "appdata",
        "temp",
        "tmp",
        "desktop",
        "downloads",
        "users",
    }
)


def _is_rejected_workspace_name(ws_name: str) -> bool:
    """Rejeita nomes de ficheiros únicos ou diretórios genéricos de SO como workspace."""
    low = str(ws_name or "").strip().lower()
    if not low:
        return True
    if low in _REJECTED_OS_DIRS:
        return True
    if low.endswith(_REJECTED_WS_FILE_EXTS):
        return True
    return False


def _format_disambiguated_filename(target_file: str) -> str:
    """Desambigua nomes genéricos (route.ts, index.ts, main.py, etc.) com a pasta pai (parent/route.ts)."""
    tf_norm = str(target_file or "").replace("\\", "/").rstrip("/")
    bname = os.path.basename(tf_norm)
    if not bname:
        return ""
    if bname.lower() in _GENERIC_DISAMBIG_FILENAMES:
        parent = os.path.basename(os.path.dirname(tf_norm).rstrip("/"))
        if parent and not parent.endswith(":"):
            return f"{parent}/{bname}"
    return bname


def _derive_file_workspace(target_file: str, fallback_ws: str, db: BrainDB) -> str:
    """Infere o workspace real de um ficheiro evitando poluição por nomes de ficheiros ou pastas de SO."""
    tf_norm = str(target_file or "").replace("\\", "/")
    tf_low = tf_norm.lower()
    safe_fallback = (
        "global" if _is_rejected_workspace_name(fallback_ws) else (fallback_ws or "global").strip().lower()
    )

    if "/scratch/" in tf_low:
        parts = [p for p in tf_low.split("/scratch/")[-1].split("/") if p]
        if len(parts) >= 2 and not _is_rejected_workspace_name(parts[0]):
            return parts[0]
        return safe_fallback

    if "/desktop/" in tf_low:
        parts = [p for p in tf_low.split("/desktop/")[-1].split("/") if p]
        if len(parts) >= 2 and not _is_rejected_workspace_name(parts[0]):
            return parts[0]
        return safe_fallback

    cur_dir = os.path.dirname(tf_norm)
    for _ in range(4):
        if not cur_dir or cur_dir.endswith(":"):
            break
        try:
            norm_dir = db.normalize_workspace(cur_dir)
        except Exception:
            break
        if norm_dir and norm_dir != "global" and not _is_rejected_workspace_name(norm_dir):
            return norm_dir
        parent_dir = os.path.dirname(cur_dir.rstrip("/"))
        if not parent_dir or parent_dir == cur_dir:
            break
        cur_dir = parent_dir

    return safe_fallback


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


def harvest_latest_turn(transcript_path: str, workspace: str, conv_id: str, db: BrainDB) -> int:
    """Analisa os passos do último turno no transcript.jsonl e extrai memórias a custo 0 de tokens."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return 0

    file_size = os.path.getsize(transcript_path)
    read_size = min(file_size, 131072)  # Últimos 128KB
    with open(transcript_path, "rb") as f:
        if file_size > read_size:
            f.seek(file_size - read_size)
        tail_bytes = f.read()

    lines = tail_bytes.decode("utf-8", errors="ignore").splitlines()
    steps: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            steps.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not steps:
        return 0

    # Isola apenas os passos após o último USER_INPUT (Antigravity) ou type == "user" (Claude Code)
    last_user_idx = 0
    turn_user_goal = ""
    turn_user_prompt = ""
    is_subagent = False
    for idx in range(len(steps) - 1, -1, -1):
        st_type = steps[idx].get("type")
        if st_type == "USER_INPUT":
            last_user_idx = idx
            raw_u = str(steps[idx].get("content") or "")
            m_req = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", raw_u, flags=re.DOTALL)
            if m_req:
                turn_user_prompt = clean_system_envelope(m_req.group(1))[:600]
                turn_user_goal = turn_user_prompt[:110]
            elif "<SYSTEM_MESSAGE>" in raw_u or "sender=" in raw_u:
                is_subagent = True
                turn_user_prompt = clean_system_envelope(raw_u)[:600]
                turn_user_goal = turn_user_prompt[:110]
            else:
                turn_user_prompt = clean_system_envelope(raw_u)[:600]
                turn_user_goal = turn_user_prompt[:110]
            break
        if st_type == "user":
            msg_obj = steps[idx].get("message") if isinstance(steps[idx].get("message"), dict) else steps[idx]
            raw_c = msg_obj.get("content")
            u_text = ""
            if isinstance(raw_c, str):
                u_text = raw_c.strip()
            elif isinstance(raw_c, list):
                u_text = " ".join(
                    str(b.get("text") or "").strip()
                    for b in raw_c
                    if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
                ).strip()
            if u_text:
                last_user_idx = idx
                turn_user_prompt = clean_system_envelope(u_text)[:600]
                turn_user_goal = turn_user_prompt[:110]
                break
        if st_type == "SYSTEM_MESSAGE" and last_user_idx == 0:
            raw_sys = str(steps[idx].get("content") or "")
            if "sender=" in raw_sys and "sender=system" not in raw_sys:
                last_user_idx = idx
                is_subagent = True
                turn_user_goal = clean_system_envelope(raw_sys)[:110]
                break

    # Hook zero-LLM: deteta correções do utilizador no prompt e regista para o Nightly Rule Distiller
    if turn_user_prompt and not is_subagent:
        try:
            from rule_distiller_engine import detect_correction_signal, record_correction

            if detect_correction_signal(turn_user_prompt):
                record_correction(db, turn_user_prompt, workspace=workspace, source="harvest_hook")
        except Exception:
            pass

    turn_steps = steps[last_user_idx:]
    harvested_count = 0
    modified_files: List[str] = []
    completed_actions: List[str] = []
    detected_errors: List[str] = []
    turn_input_tokens = 0
    turn_cached_tokens = 0
    turn_output_tokens = 0

    for step in turn_steps:
        if step.get("type") == "TOOL_RESPONSE":
            t_out = str(step.get("content") or "")
            err_match = re.search(
                r"((?:SyntaxError|TypeError|ValueError|KeyError|ModuleNotFoundError|ImportError|FileNotFoundError|AssertionError|AttributeError|OperationalError): [^\n]+)",
                t_out,
            )
            if err_match:
                err_txt = err_match.group(1).strip()[:120]
                if err_txt not in detected_errors:
                    detected_errors.append(err_txt)
            continue

        st_type = step.get("type")
        if st_type not in ("PLANNER_RESPONSE", "assistant"):
            continue

        if st_type == "assistant":
            msg_obj = step.get("message") if isinstance(step.get("message"), dict) else step
            usage = msg_obj.get("usage") if isinstance(msg_obj.get("usage"), dict) else {}
            turn_input_tokens += int(usage.get("input_tokens", 0) or 0)
            turn_cached_tokens += int(usage.get("cache_read_input_tokens", 0) or 0)
            turn_output_tokens += int(usage.get("output_tokens", 0) or 0)
            raw_c = msg_obj.get("content")
            content = ""
            tool_calls = []
            if isinstance(raw_c, str):
                content = raw_c
            elif isinstance(raw_c, list):
                text_chunks: List[str] = []
                for blk in raw_c:
                    if not isinstance(blk, dict):
                        continue
                    if blk.get("type") == "text" and blk.get("text"):
                        text_chunks.append(str(blk.get("text")))
                    elif blk.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "name": str(blk.get("name") or ""),
                                "args": blk.get("input") if isinstance(blk.get("input"), dict) else {},
                            }
                        )
                content = "\n".join(text_chunks)
        else:
            turn_input_tokens += int(step.get("input_tokens", 0) or 0)
            turn_cached_tokens += int(step.get("cache_read_tokens", 0) or 0)
            turn_output_tokens += int(step.get("output_tokens", 0) or 0)
            content = step.get("content", "") or ""
            tool_calls = step.get("tool_calls") or []

        # 1. Extrai marcadores explícitos <!-- brain: Topico | Facto --> (suporta setas ->, =>, <, >)
        explicit_matches = re.findall(
            r"<!--\s*brain:\s*([^|\n`{}]{3,85}?)\s*\|\s*(.{6,450}?)\s*-->",
            content,
        )
        for topic, fact in explicit_matches:
            t_clean = topic.strip()
            f_clean = " ".join(fact.strip().split())
            if any(x in t_clean.lower() for x in ("topico", "short topic", "\\s*")):
                continue
            _, is_new = db.store_fact(
                topic=t_clean,
                fact=f_clean,
                workspace=workspace,
                category="explicit_note",
                tags="auto_harvested explicit",
                importance=4,
            )
            if is_new:
                harvested_count += 1

        # 2. Extrai edições de ficheiros (1 memória consolidada por ficheiro para não poluir o grafo)
        for tc in tool_calls:
            t_name = tc.get("name", "")
            args = tc.get("args") or {}
            if t_name in (
                "write_to_file",
                "replace_file_content",
                "multi_replace_file_content",
                "write_file",
                "edit_file",
                "Write",
                "Edit",
                "MultiEdit",
            ):
                target_file = str(
                    args.get("TargetFile")
                    or args.get("Path")
                    or args.get("AbsolutePath")
                    or args.get("filePath")
                    or args.get("file_path")
                    or ""
                ).strip('"').replace("\\\\", "/")
                desc = str(args.get("Description") or args.get("Instruction") or "Atualização de código").strip('"')[:160]
                if target_file and "/brain/" not in target_file:
                    tf_norm = target_file.replace("\\", "/")
                    bname = os.path.basename(tf_norm)
                    # 1. Ignorar ficheiros temporários/scratch não notáveis
                    if any(x in bname.lower() for x in ("verify_", "tmp_", "temp_")):
                        continue

                    # 2. Inferir workspace real do ficheiro (rejeitando nomes de ficheiro e pastas de SO)
                    file_ws = _derive_file_workspace(tf_norm, workspace, db)
                    display_bname = _format_disambiguated_filename(tf_norm) or bname

                    topic_key = f"Ficheiro {display_bname} ({file_ws})"
                    fact_val = f"Path: {tf_norm} — Última edição: {desc}"

                    if not db.passes_notability_gate(topic_key, fact_val, "code_change"):
                        continue

                    # Apenas anexa aos ficheiros modificados do workspace atual se for local (ou se workspace for global)
                    if file_ws == workspace or workspace == "global":
                        if display_bname not in modified_files:
                            modified_files.append(display_bname)
                        if desc:
                            completed_actions.append(f"{display_bname}: {desc}")

                    with db._connect() as conn:
                        existing = conn.execute(
                            "SELECT id FROM memories WHERE workspace = ? AND topic = ? LIMIT 1;",
                            (file_ws.lower(), topic_key),
                        ).fetchone()
                        if existing:
                            conn.execute(
                                "UPDATE memories SET fact = ?, last_accessed = CURRENT_TIMESTAMP WHERE id = ?;",
                                (fact_val, existing["id"]),
                            )
                        else:
                            db.store_fact(
                                topic=topic_key,
                                fact=fact_val,
                                workspace=file_ws,
                                category="code_change",
                                tags=f"{bname} {display_bname} {file_ws} file edit",
                                importance=3,
                            )
                            harvested_count += 1

    # 3. Atualiza o Checkpoint automático do workspace + Auto-Refresh do Scout Map se houve alterações de código
    if detected_errors and modified_files:
        bug_target = modified_files[-1]
        db.store_fact(
            topic=f"Auto-Bugfix: {bug_target} ({workspace})",
            fact=f"Erro resolvido no turno: {detected_errors[-1]} -> Corrigido em {', '.join(modified_files[:3])}.",
            workspace=workspace,
            category="optimization",
            tags=f"bugfix {bug_target} {workspace} erro",
            importance=4,
        )

    if modified_files or completed_actions:
        checkpoint_goal = "" if is_subagent else (turn_user_goal or f"Desenvolvimento ativo em {workspace}")
        db.save_checkpoint(
            workspace=workspace,
            project=workspace,
            goal=checkpoint_goal,
            status="Ativo • Auto-Synced",
            last_completed="; ".join(completed_actions[-3:])[:300],
            key_files=", ".join(modified_files[-6:])[:200],
        )
        try:
            SwarmEngine(db).run_codebase_scout(os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            pass

    if harvested_count > 0:
        try:
            db.run_memory_doctor()
        except Exception:
            pass

    # 4. Regista telemetria real do turno
    db.log_telemetry(
        event_type="stop_harvest",
        conversation_id=conv_id,
        workspace=workspace,
        latency_ms=0.0,
        injected_tokens=0,
        estimated_saved_tokens=harvested_count * 1200,
        details=(
            f"harvested={harvested_count} "
            f"in_tok={turn_input_tokens} "
            f"cache_tok={turn_cached_tokens} "
            f"out_tok={turn_output_tokens}"
        ),
    )
    try:
        SwarmEngine(db).on_turn_complete(modified_files, completed_actions, conversation_id=conv_id)
        if modified_files or completed_actions or harvested_count > 0:
            OrbitEngine(db).record_handoff(
                from_agent=f"conv:{conv_id[:8]}",
                workspace=workspace,
                summary=turn_user_goal or ("; ".join(completed_actions[-2:]) if completed_actions else "Turno concluído com memória colhida"),
                modified_files=", ".join(modified_files[:5]),
                key_findings="; ".join(completed_actions[-3:])[:240],
                to_scope="next_agent",
            )
        if modified_files or completed_actions or harvested_count > 0 or detected_errors:
            try:
                from pagoda_fold_engine import PagodaFoldEngine
                raw_payload = {
                    "goal": turn_user_goal,
                    "workspace": workspace,
                    "conversation_id": conv_id,
                    "modified_files": modified_files,
                    "completed_actions": completed_actions,
                    "detected_errors": detected_errors,
                    "tokens": {
                        "in": turn_input_tokens,
                        "cache": turn_cached_tokens,
                        "out": turn_output_tokens,
                    },
                }
                fold_title = (
                    f"Edit: {', '.join(modified_files[:3])}"
                    if (is_subagent and modified_files)
                    else (turn_user_goal if not is_subagent else "")
                ) or f"Turno {workspace}"
                PagodaFoldEngine(db).fold_turn_episode(
                    workspace=workspace,
                    title=fold_title,
                    summary="; ".join(completed_actions[-2:]) or turn_user_goal or "Memória colhida",
                    raw_payload=raw_payload,
                    key_files=", ".join(modified_files[-5:]),
                )
            except Exception:
                pass
    except Exception:
        pass
    return harvested_count


def handle_stop(raw_stdin: str, host_hint: str = "auto") -> Dict[str, Any]:
    t0 = time.perf_counter()
    if raw_stdin.strip():
        payload = json.loads(raw_stdin)
        norm_host = (host_hint or "auto").strip().lower()
        is_claude_hook = bool(
            norm_host in ("claude", "claude_code")
            or payload.get("hook_event_name") == "Stop"
            or ("session_id" in payload and "conversationId" not in payload)
        )
        if is_claude_hook:
            conv_id = str(payload.get("session_id") or payload.get("conversationId") or "claude_default")
            raw_ws = str(payload.get("cwd") or "global")
        else:
            conv_id = str(payload.get("conversationId", "default"))
            workspaces = payload.get("workspacePaths") or []
            raw_ws = workspaces[0] if workspaces else "global"

        db = BrainDB()
        ws = db.normalize_workspace(raw_ws)
        if _is_rejected_workspace_name(ws):
            ws = "global"
        if ws == "global":
            resolved_ws = resolve_smart_active_workspace(db, "", conv_id)
            if resolved_ws and resolved_ws != "global":
                ws = resolved_ws
        transcript_path = resolve_transcript_path(payload)
        try:
            runtime_profile = detect_runtime_profile(
                payload=payload,
                transcript_path=transcript_path,
                host_hint=host_hint,
                db=db,
                probe_local=False,
            )
            record_runtime_session(db, runtime_profile, conversation_id=conv_id, workspace=ws)
        except Exception:
            pass

        if transcript_path:
            harvest_latest_turn(transcript_path, ws, conv_id, db)
        else:
            try:
                SwarmEngine(db).on_turn_complete([], [], conversation_id=conv_id)
            except Exception:
                pass

    # Devolve "allow" (qualquer valor diferente de "continue" permite terminar normalmente)
    return {"decision": "allow"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            "--host",
            default="auto",
            choices=["auto", "antigravity", "claude", "codex"],
        )
        args, _ = parser.parse_known_args()
        raw_in = sys.stdin.read()
        result = handle_stop(raw_in, host_hint=args.host)
        print(json.dumps(result, ensure_ascii=False))
    except Exception:
        print('{"decision": "allow"}')


if __name__ == "__main__":
    main()

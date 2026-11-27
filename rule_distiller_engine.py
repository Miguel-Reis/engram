"""
rule_distiller_engine.py — Nightly Correction -> Canonical Rule Distiller for Engram v9.1.

Zero-LLM fast correction signal detection (PT-PT & EN), deduplicated occurrence
tracking via token Jaccard similarity, nightly promotion to canonical Brain rules,
optional AGENTS.md injection, and status reporting for the dashboard/API.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional, Set, Tuple


_STOP_TOKENS: Set[str] = {
    "a", "o", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "para", "por", "com", "sem", "que",
    "se", "e", "ou", "isso", "isto", "esse", "essa", "este", "esta",
    "the", "an", "and", "or", "in", "on", "at", "to", "for", "of",
    "with", "without", "that", "this", "is", "are", "be", "it", "you",
}

_CORRECTION_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("nunca uses", re.compile(r"\bnunca\s+uses\b", re.IGNORECASE)),
    ("nunca faças", re.compile(r"\bnunca\s+fa(?:ç|c)as\b", re.IGNORECASE)),
    ("não uses", re.compile(r"\bn(?:ã|a)o\s+uses\b", re.IGNORECASE)),
    ("não faças", re.compile(r"\bn(?:ã|a)o\s+fa(?:ç|c)as\b", re.IGNORECASE)),
    ("usa sempre", re.compile(r"\busa\s+sempre\b", re.IGNORECASE)),
    ("lembra-te sempre", re.compile(r"\blembra[-\s]te\s+sempre\b", re.IGNORECASE)),
    ("evita usar", re.compile(r"\bevita\s+usar\b", re.IGNORECASE)),
    ("corrige isso", re.compile(r"\bcorrige\s+isso\b", re.IGNORECASE)),
    ("na verdade", re.compile(r"\bna\s+verdade\b", re.IGNORECASE)),
    ("a partir de agora", re.compile(r"\ba\s+partir\s+de\s+agora\b", re.IGNORECASE)),
    ("deixa de usar", re.compile(r"\bdeixa\s+de\s+usar\b", re.IGNORECASE)),
    ("never use", re.compile(r"\bnever\s+use\b", re.IGNORECASE)),
    ("always use", re.compile(r"\balways\s+use\b", re.IGNORECASE)),
    ("stop doing", re.compile(r"\bstop\s+doing\b", re.IGNORECASE)),
    ("don't use", re.compile(r"\bdon['’]?t\s+use\b", re.IGNORECASE)),
    ("do not use", re.compile(r"\bdo\s+not\s+use\b", re.IGNORECASE)),
    ("remember to always", re.compile(r"\bremember\s+to\s+always\b", re.IGNORECASE)),
    ("prefer over", re.compile(r"\bprefer\s+.{2,60}?\s+over\b", re.IGNORECASE)),
    ("from now on", re.compile(r"\bfrom\s+now\s+on\b", re.IGNORECASE)),
    ("avoid using", re.compile(r"\bavoid\s+using\b", re.IGNORECASE)),
]

_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\u00C0-\u024F]{2,}")


from engram.core.utils import utc_now_iso as _utc_now_iso


def _ensure_brain_meta(conn: Any) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS brain_meta (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at TEXT
        );
        """
    )


def _get_meta(conn: Any, key: str, default: str = "") -> str:
    _ensure_brain_meta(conn)
    row = conn.execute("SELECT value FROM brain_meta WHERE key = ?;", (key,)).fetchone()
    return str(row["value"]) if row and row["value"] is not None else default


def _set_meta(conn: Any, key: str, value: str) -> None:
    _ensure_brain_meta(conn)
    now_iso = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO brain_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at;
        """,
        (key, str(value), now_iso),
    )


def ensure_distiller_tables(db: Any) -> None:
    """Create engram_corrections, its workspace/status index, and brain_meta if absent."""
    with db._connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS engram_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace TEXT DEFAULT 'brain_mcp',
                source TEXT DEFAULT 'chat',
                pattern_key TEXT NOT NULL,
                correction_text TEXT NOT NULL,
                occurrences INTEGER DEFAULT 1,
                promoted_rule_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_engram_corrections_ws_status ON engram_corrections(workspace, status);"
        )
        _ensure_brain_meta(conn)


def _strip_code_and_noise(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = _FENCED_CODE_RE.sub(" ", text)
    cleaned = re.sub(r"`[^`]{40,}`", " ", cleaned)
    return " ".join(cleaned.split()).strip()


def _tokenize_for_similarity(text: str) -> Set[str]:
    raw_tokens = _TOKEN_RE.findall((text or "").lower())
    meaningful = {t for t in raw_tokens if t not in _STOP_TOKENS and len(t) >= 2}
    return meaningful if meaningful else set(raw_tokens)


def _build_pattern_key(text: str) -> str:
    raw_tokens = _TOKEN_RE.findall((text or "").lower())
    filtered = [t for t in raw_tokens if t not in _STOP_TOKENS][:10]
    if not filtered:
        filtered = raw_tokens[:8]
    slug = "_".join(filtered)
    slug = re.sub(r"[^a-z0-9_\u00C0-\u024F]+", "_", slug).strip("_")
    return slug[:80] or "correction_rule"


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return (inter / union) if union else 0.0


def detect_correction_signal(text: str) -> Optional[Dict[str, Any]]:
    """
    Zero-LLM (<1ms) detector for PT-PT and EN user correction patterns.
    Ignores fenced code blocks, overly short (<12 chars), or noisy strings.
    """
    cleaned = _strip_code_and_noise(text)
    if len(cleaned) < 12:
        return None
    # Reject strings that look mostly like symbol/punctuation noise or stacktraces
    alpha_count = sum(1 for ch in cleaned if ch.isalpha())
    if alpha_count < 8 or (alpha_count / max(1, len(cleaned))) < 0.35:
        return None

    for trigger_label, pat in _CORRECTION_PATTERNS:
        m = pat.search(cleaned)
        if m:
            # Extract sentence/clause around the trigger for a crisp normalized rule
            start_idx = max(0, cleaned.rfind(".", 0, m.start()) + 1)
            end_match = re.search(r"[.!?\n]", cleaned[m.start():])
            end_idx = (m.start() + end_match.start() + 1) if end_match else len(cleaned)
            clause = cleaned[start_idx:end_idx].strip(" .-\t")
            normalized_rule = (clause if len(clause) >= 12 else cleaned)[:280]
            pattern_key = _build_pattern_key(normalized_rule)
            return {
                "matched": True,
                "trigger": trigger_label,
                "normalized_rule": normalized_rule,
                "pattern_key": pattern_key,
            }
    return None


def record_correction(
    db: Any,
    text: str,
    workspace: str = "brain_mcp",
    source: str = "chat",
) -> Dict[str, Any]:
    """
    Record a correction signal in engram_corrections, merging with any existing
    pending correction in the same workspace if pattern_key matches or Jaccard >= 0.55.
    """
    ensure_distiller_tables(db)
    ws = str(workspace or "brain_mcp").strip().lower() or "brain_mcp"
    src = str(source or "chat").strip() or "chat"

    signal = detect_correction_signal(text)
    if signal:
        norm_rule = signal["normalized_rule"]
        pattern_key = signal["pattern_key"]
    else:
        cleaned = _strip_code_and_noise(text)
        if len(cleaned) < 6:
            return {"ok": False, "error": "Correction text too short."}
        norm_rule = cleaned[:280]
        pattern_key = _build_pattern_key(norm_rule)

    if hasattr(db, "redact_secrets"):
        norm_rule = db.redact_secrets(norm_rule)

    new_tokens = _tokenize_for_similarity(norm_rule)
    now_iso = _utc_now_iso()

    with db._connect() as conn:
        pending_rows = conn.execute(
            """
            SELECT id, pattern_key, correction_text, occurrences
            FROM engram_corrections
            WHERE LOWER(workspace) = ? AND status = 'pending'
            ORDER BY id DESC;
            """,
            (ws,),
        ).fetchall()

        matched_row = None
        for row in pending_rows:
            if row["pattern_key"] == pattern_key:
                matched_row = row
                break
            sim = _jaccard_similarity(new_tokens, _tokenize_for_similarity(row["correction_text"]))
            if sim >= 0.55:
                matched_row = row
                break

        if matched_row is not None:
            row_id = int(matched_row["id"])
            new_occ = int(matched_row["occurrences"] or 1) + 1
            conn.execute(
                """
                UPDATE engram_corrections
                SET occurrences = ?, updated_at = ?
                WHERE id = ?;
                """,
                (new_occ, now_iso, row_id),
            )
            return {
                "ok": True,
                "id": row_id,
                "pattern_key": str(matched_row["pattern_key"]),
                "occurrences": new_occ,
                "merged": True,
                "status": "pending",
            }

        cur = conn.execute(
            """
            INSERT INTO engram_corrections
                (workspace, source, pattern_key, correction_text, occurrences, promoted_rule_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, '', 'pending', ?, ?);
            """,
            (ws, src, pattern_key, norm_rule, now_iso, now_iso),
        )
        return {
            "ok": True,
            "id": int(cur.lastrowid),
            "pattern_key": pattern_key,
            "occurrences": 1,
            "merged": False,
            "status": "pending",
        }


def _scan_memory_correction_candidates(
    conn: Any,
    ws_filter: str,
    min_occ: int,
) -> List[Dict[str, Any]]:
    """
    Scan recent non-rule memories for repeated correction cues that are not yet
    tracked or promoted in engram_corrections / canonical rules.
    """
    if ws_filter and ws_filter != "all":
        mem_rows = conn.execute(
            """
            SELECT id, workspace, fact FROM memories
            WHERE LOWER(workspace) = ?
              AND category NOT IN ('rule', 'learned_rule', 'directive')
              AND superseded_by IS NULL
            ORDER BY id DESC LIMIT 120;
            """,
            (ws_filter,),
        ).fetchall()
        existing_rows = conn.execute(
            "SELECT pattern_key, correction_text FROM engram_corrections WHERE LOWER(workspace) = ?;",
            (ws_filter,),
        ).fetchall()
    else:
        mem_rows = conn.execute(
            """
            SELECT id, workspace, fact FROM memories
            WHERE category NOT IN ('rule', 'learned_rule', 'directive')
              AND superseded_by IS NULL
            ORDER BY id DESC LIMIT 160;
            """
        ).fetchall()
        existing_rows = conn.execute(
            "SELECT pattern_key, correction_text FROM engram_corrections;"
        ).fetchall()

    known_keys = {str(r["pattern_key"]) for r in existing_rows}
    known_tokens = [_tokenize_for_similarity(str(r["correction_text"])) for r in existing_rows]

    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for mr in mem_rows:
        sig = detect_correction_signal(str(mr["fact"] or ""))
        if not sig:
            continue
        r_ws = str(mr["workspace"] or "brain_mcp").lower()
        pk = sig["pattern_key"]
        if pk in known_keys:
            continue
        sig_tokens = _tokenize_for_similarity(sig["normalized_rule"])
        if any(_jaccard_similarity(sig_tokens, kt) >= 0.55 for kt in known_tokens):
            continue

        # Merge into existing group if Jaccard >= 0.55 in same workspace
        merged_key = None
        for (g_ws, g_pk), g_val in grouped.items():
            if g_ws != r_ws:
                continue
            if g_pk == pk or _jaccard_similarity(sig_tokens, g_val["tokens"]) >= 0.55:
                merged_key = (g_ws, g_pk)
                break
        if merged_key:
            grouped[merged_key]["occurrences"] += 1
        else:
            grouped[(r_ws, pk)] = {
                "id": None,
                "workspace": r_ws,
                "pattern_key": pk,
                "correction_text": sig["normalized_rule"],
                "occurrences": 1,
                "tokens": sig_tokens,
            }

    return [v for v in grouped.values() if int(v["occurrences"]) >= min_occ]


def run_nightly_rule_distillation(
    db: Any,
    workspace: str = "brain_mcp",
    min_occurrences: int = 2,
    dry_run: bool = False,
    auto_inject_agents_md: bool = False,
) -> Dict[str, Any]:
    """
    Promote pending corrections (and repeated correction signals in memories)
    with occurrences >= min_occurrences into canonical Brain rules.
    """
    ensure_distiller_tables(db)
    ws = str(workspace or "brain_mcp").strip().lower() or "brain_mcp"
    min_occ = max(1, int(min_occurrences))
    now_iso = _utc_now_iso()

    with db._connect() as conn:
        if ws != "all":
            qualifying_rows = conn.execute(
                """
                SELECT id, workspace, pattern_key, correction_text, occurrences
                FROM engram_corrections
                WHERE status = 'pending' AND occurrences >= ? AND LOWER(workspace) = ?
                ORDER BY occurrences DESC, id ASC;
                """,
                (min_occ, ws),
            ).fetchall()
        else:
            qualifying_rows = conn.execute(
                """
                SELECT id, workspace, pattern_key, correction_text, occurrences
                FROM engram_corrections
                WHERE status = 'pending' AND occurrences >= ?
                ORDER BY occurrences DESC, id ASC;
                """,
                (min_occ,),
            ).fetchall()

        candidates: List[Dict[str, Any]] = [dict(r) for r in qualifying_rows]
        mem_candidates = _scan_memory_correction_candidates(conn, ws, min_occ)
        candidates.extend(mem_candidates)

    promoted_rules: List[Dict[str, Any]] = []
    touched_workspaces: Set[str] = set()

    for item in candidates:
        row_ws = str(item.get("workspace") or "brain_mcp").strip().lower() or "brain_mcp"
        pk = str(item["pattern_key"])
        corr_text = str(item["correction_text"])
        occ = int(item.get("occurrences") or 1)
        row_id = item.get("id")
        promoted_rule_id = ""

        if not dry_run:
            mem_id, _ = db.store_fact(
                topic=f"Rule: {pk}",
                fact=corr_text,
                workspace=row_ws,
                category="rule",
                tags="auto-rule, nightly-distiller, canonical",
                importance=10,
                source_agent="nightly_distiller",
            )
            promoted_rule_id = str(mem_id)
            with db._connect() as conn:
                if row_id is not None:
                    conn.execute(
                        """
                        UPDATE engram_corrections
                        SET status = 'promoted', promoted_rule_id = ?, updated_at = ?
                        WHERE id = ?;
                        """,
                        (promoted_rule_id, now_iso, int(row_id)),
                    )
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO engram_corrections
                            (workspace, source, pattern_key, correction_text, occurrences, promoted_rule_id, status, created_at, updated_at)
                        VALUES (?, 'memory_scan', ?, ?, ?, ?, 'promoted', ?, ?);
                        """,
                        (row_ws, pk, corr_text, occ, promoted_rule_id, now_iso, now_iso),
                    )
                    row_id = int(cur.lastrowid)
            touched_workspaces.add(row_ws)

        promoted_rules.append(
            {
                "id": row_id,
                "workspace": row_ws,
                "pattern_key": pk,
                "correction_text": corr_text,
                "occurrences": occ,
                "promoted_rule_id": promoted_rule_id,
            }
        )

    if auto_inject_agents_md and not dry_run and promoted_rules:
        try:
            from orbit_engine import OrbitEngine

            orbit = OrbitEngine(db)
            for t_ws in sorted(touched_workspaces):
                try:
                    orbit.inject_rules_into_repo_agents_md(workspace=t_ws)
                except Exception:
                    pass
        except Exception:
            pass

    with db._connect() as conn:
        if not dry_run:
            _set_meta(conn, "last_nightly_distill_at", now_iso)
            last_run_at = now_iso
        else:
            last_run_at = _get_meta(conn, "last_nightly_distill_at", "")

        if ws != "all":
            rem_row = conn.execute(
                "SELECT COUNT(*) AS c FROM engram_corrections WHERE status = 'pending' AND LOWER(workspace) = ?;",
                (ws,),
            ).fetchone()
        else:
            rem_row = conn.execute(
                "SELECT COUNT(*) AS c FROM engram_corrections WHERE status = 'pending';"
            ).fetchone()
        pending_remaining = int(rem_row["c"] or 0) if rem_row else 0

    return {
        "ok": True,
        "promoted_count": len(promoted_rules),
        "promoted_rules": promoted_rules,
        "pending_remaining": pending_remaining,
        "dry_run": bool(dry_run),
        "last_run_at": last_run_at,
    }


def get_distiller_status(
    db: Any,
    workspace: str = "all",
    limit: int = 12,
) -> Dict[str, Any]:
    """Return pending corrections, promoted rules + canonical rule/decision memories, and metadata."""
    ensure_distiller_tables(db)
    ws = str(workspace or "all").strip().lower() or "all"
    lim = max(1, min(100, int(limit or 12)))

    with db._connect() as conn:
        last_run_at = _get_meta(conn, "last_nightly_distill_at", "")
        ws_clause = "" if ws == "all" else "AND LOWER(workspace) = ?"
        ws_params: Tuple[Any, ...] = () if ws == "all" else (ws,)

        pending_count = int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM engram_corrections WHERE status = 'pending' {ws_clause};",
                ws_params,
            ).fetchone()["c"]
            or 0
        )
        promoted_count = int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM engram_corrections WHERE status = 'promoted' {ws_clause};",
                ws_params,
            ).fetchone()["c"]
            or 0
        )

        pending_rows = conn.execute(
            f"""
            SELECT id, workspace, source, pattern_key, correction_text, occurrences, status, created_at, updated_at
            FROM engram_corrections
            WHERE status = 'pending' {ws_clause}
            ORDER BY occurrences DESC, updated_at DESC, id DESC
            LIMIT ?;
            """,
            (*ws_params, lim),
        ).fetchall()

        promoted_rows = conn.execute(
            f"""
            SELECT id, workspace, source, pattern_key, correction_text, occurrences, promoted_rule_id, status, updated_at
            FROM engram_corrections
            WHERE status = 'promoted' {ws_clause}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?;
            """,
            (*ws_params, lim),
        ).fetchall()

        if ws == "all":
            mem_rules = conn.execute(
                """
                SELECT id, workspace, topic, fact, category, importance, created_at
                FROM memories
                WHERE category IN ('rule', 'learned_rule', 'directive', 'decision')
                  AND superseded_by IS NULL
                ORDER BY importance DESC, id DESC
                LIMIT ?;
                """,
                (lim,),
            ).fetchall()
        else:
            mem_rules = conn.execute(
                """
                SELECT id, workspace, topic, fact, category, importance, created_at
                FROM memories
                WHERE LOWER(workspace) IN (?, 'global')
                  AND category IN ('rule', 'learned_rule', 'directive', 'decision')
                  AND superseded_by IS NULL
                ORDER BY importance DESC, id DESC
                LIMIT ?;
                """,
                (ws, lim),
            ).fetchall()

    rules_out: List[Dict[str, Any]] = []
    seen_mem_ids: Set[str] = set()
    for r in promoted_rows:
        m_id = str(r["promoted_rule_id"] or "")
        if m_id:
            seen_mem_ids.add(m_id)
        rules_out.append(
            {
                "id": int(r["id"]),
                "memory_id": m_id,
                "workspace": str(r["workspace"]),
                "pattern_key": str(r["pattern_key"]),
                "rule_text": str(r["correction_text"]),
                "occurrences": int(r["occurrences"] or 1),
                "source": "nightly_distiller",
                "updated_at": str(r["updated_at"] or ""),
            }
        )

    for mr in mem_rules:
        if len(rules_out) >= lim:
            break
        m_id = str(mr["id"])
        if m_id in seen_mem_ids:
            continue
        seen_mem_ids.add(m_id)
        rules_out.append(
            {
                "id": int(mr["id"]),
                "memory_id": m_id,
                "workspace": str(mr["workspace"]),
                "pattern_key": str(mr["topic"]),
                "rule_text": str(mr["fact"]),
                "occurrences": 1,
                "source": str(mr["category"] or "rule"),
                "updated_at": str(mr["created_at"] or ""),
            }
        )

    return {
        "ok": True,
        "pending_count": pending_count,
        "promoted_count": promoted_count,
        "last_run_at": last_run_at,
        "pending": [dict(r) for r in pending_rows],
        "rules": rules_out[:lim],
    }

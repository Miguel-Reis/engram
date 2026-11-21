"""
intake_handoff_engine.py — External Voice/Note Intake (Telegram/Webhook) + Cross-IDE HANDOFF.md.

Provides:
- Voice/STT denoising via voice_brain_engine.analyze_voice_input
- Automatic routing into DOTS tasks (OrbitEngine.manage_dot_task) or daily Vault inbox notes
- Telegram Bot API polling & masked configuration storage in brain_meta
- Portable Cross-IDE HANDOFF.md generator with active model, rules, git/open files, tasks & resume prompt
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


_TASK_INTENT_RE = re.compile(
    r"^(?:todo\s*:|task\s*:|tarefa\s*:|fazer\s*:|lembrar\s+de\b|criar\s+task\b|fix\s+|implementar\s+)"
    r"|\b(?:criar\s+task|lembrar\s+de)\b",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _mask_token(token: str) -> str:
    tok = (token or "").strip()
    if not tok:
        return ""
    if len(tok) <= 8:
        return "*" * len(tok)
    return f"{tok[:4]}...{tok[-4:]}"


def ensure_intake_tables(db: Any) -> None:
    """Create engram_intake_log, its workspace index, and brain_meta if absent."""
    with db._connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS engram_intake_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT DEFAULT 'telegram',
                sender TEXT DEFAULT 'user',
                workspace TEXT DEFAULT 'brain_mcp',
                raw_text TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                routed_to TEXT DEFAULT 'vault_note',
                target_ref TEXT DEFAULT '',
                audio_duration_sec REAL DEFAULT 0.0,
                created_at TEXT
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_engram_intake_ws ON engram_intake_log(workspace, id DESC);"
        )
        _ensure_brain_meta(conn)


def _clean_with_voice_denoiser(raw_text: str, has_audio: bool) -> str:
    try:
        from voice_brain_engine import analyze_voice_input

        res = analyze_voice_input(raw_text, has_audio_media=has_audio)
        cleaned = str(res.get("clean_query") or "").strip()
        if cleaned:
            return cleaned
    except Exception:
        pass
    return " ".join(str(raw_text or "").split()).strip()


def ingest_external_note(
    db: Any,
    text: str,
    channel: str = "telegram",
    sender: str = "user",
    workspace: str = "brain_mcp",
    mode: str = "auto",
    audio_duration_sec: float = 0.0,
) -> Dict[str, Any]:
    """
    Ingest an external note or voice transcription, denoise it, route it to
    DOTS tasks and/or daily Vault inbox notes, and store a sourced Brain memory.
    """
    ensure_intake_tables(db)
    raw_text = str(text or "").strip()
    if not raw_text:
        return {"ok": False, "error": "Input text cannot be empty."}

    ws = str(workspace or "brain_mcp").strip().lower() or "brain_mcp"
    if ws in ("all", "*"):
        ws = "brain_mcp"
    ch = str(channel or "telegram").strip().lower() or "telegram"
    snd = str(sender or "user").strip() or "user"
    mode_norm = str(mode or "auto").strip().lower() or "auto"
    dur = max(0.0, float(audio_duration_sec or 0.0))

    cleaned_text = _clean_with_voice_denoiser(raw_text, has_audio=(dur > 0.0))
    if hasattr(db, "redact_secrets"):
        raw_text_safe = db.redact_secrets(raw_text)
        cleaned_text = db.redact_secrets(cleaned_text)
    else:
        raw_text_safe = raw_text

    is_task_intent = mode_norm == "task" or (
        mode_norm == "auto"
        and bool(_TASK_INTENT_RE.search(cleaned_text) or _TASK_INTENT_RE.search(raw_text_safe))
    )

    from orbit_engine import OrbitEngine

    orbit = OrbitEngine(db)
    task_created = False
    vault_file = ""
    routed_to = "vault_note"
    target_ref = ""

    if is_task_intent:
        task_title = re.sub(
            r"^(?:todo|task|tarefa|fazer|criar\s+task)\s*:\s*",
            "",
            cleaned_text,
            flags=re.IGNORECASE,
        ).strip()[:120] or cleaned_text[:120]
        try:
            dag = orbit.manage_dot_task(
                action="create",
                title=task_title,
                workspace=ws,
                lane="INTAKE",
                summary=f"[{ch} @{snd}] {cleaned_text}",
            )
            created_dot_id = ""
            for item in reversed(dag.get("items") or []):
                if str(item.get("title") or "").strip() == task_title:
                    created_dot_id = str(item.get("dot_id") or "")
                    break
            task_created = True
            routed_to = "dot_task"
            target_ref = created_dot_id or task_title[:40]
        except Exception:
            task_created = False

    if mode_norm in ("auto", "vault") and not task_created:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        date_str = now_dt.strftime("%Y-%m-%d")
        time_str = now_dt.strftime("%H:%M")
        vault_file = f"inbox_{date_str}.md"

        try:
            vault_dir = orbit._get_vault_dir(ws)
            inbox_path = vault_dir / vault_file
            if inbox_path.is_file():
                existing = inbox_path.read_text(encoding="utf-8", errors="replace").rstrip()
            else:
                existing = (
                    f"# Inbox — {date_str} ({ws})\n\n"
                    "## 💎 Compiled Truth\n"
                    f"External intake stream for `{ws}`.\n\n"
                    "## 📥 Captured Notes"
                )
            bullet = f"- **[{time_str}Z]** #{ch} (@{snd}): {cleaned_text} [[atlas]]"
            updated_md = f"{existing}\n{bullet}"
            orbit.save_vault_note(
                workspace=ws,
                filename=vault_file,
                content=updated_md,
                sync_to_db=False,
            )
            try:
                orbit.enforce_vault_backlinks(ws)
            except Exception:
                pass
            routed_to = "vault_note"
            target_ref = vault_file
        except Exception:
            pass

    mem_id, _ = db.store_fact(
        topic=f"Intake [{ch}] {cleaned_text[:60]}",
        fact=cleaned_text,
        workspace=ws,
        category="intake_task" if task_created else "intake_note",
        tags=f"channel:{ch}, source:{ch}, intake, {snd}",
        importance=4,
        source_agent=f"intake:{ch}",
    )

    now_iso = _utc_now_iso()
    with db._connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO engram_intake_log
                (channel, sender, workspace, raw_text, cleaned_text, routed_to, target_ref, audio_duration_sec, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (ch, snd, ws, raw_text_safe, cleaned_text, routed_to, target_ref, dur, now_iso),
        )
        intake_id = int(cur.lastrowid)

    return {
        "ok": True,
        "intake_id": intake_id,
        "channel": ch,
        "cleaned_text": cleaned_text,
        "routed_to": routed_to,
        "target_ref": target_ref,
        "task_created": task_created,
        "vault_file": vault_file,
        "memory_id": mem_id,
    }


def configure_telegram_bridge(
    db: Any,
    bot_token: str = "",
    chat_id: str = "",
    enabled: Optional[bool] = None,
    poll_interval_sec: int = 15,
) -> Dict[str, Any]:
    """Persist Telegram bridge configuration in brain_meta without ever returning the raw token."""
    ensure_intake_tables(db)
    with db._connect() as conn:
        existing_token = _get_meta(conn, "telegram_bot_token", "")
        existing_chat_id = _get_meta(conn, "telegram_chat_id", "")
        existing_enabled = _get_meta(conn, "telegram_enabled", "0") == "1"

        final_token = bot_token.strip() if bot_token.strip() else existing_token
        final_chat_id = chat_id.strip() if chat_id.strip() else existing_chat_id
        final_enabled = bool(existing_enabled if enabled is None else enabled)
        final_interval = max(5, min(3600, int(poll_interval_sec or 15)))

        if bot_token.strip():
            _set_meta(conn, "telegram_bot_token", final_token)
        if chat_id.strip():
            _set_meta(conn, "telegram_chat_id", final_chat_id)
        _set_meta(conn, "telegram_enabled", "1" if final_enabled else "0")
        _set_meta(conn, "telegram_poll_interval_sec", str(final_interval))

    return {
        "ok": True,
        "token_configured": bool(final_token),
        "token_masked": _mask_token(final_token),
        "chat_id": final_chat_id,
        "enabled": final_enabled,
        "poll_interval_sec": final_interval,
    }


def poll_telegram_once(db: Any, workspace: str = "brain_mcp") -> Dict[str, Any]:
    """
    Poll Telegram getUpdates once with a 3s timeout if configured and enabled.
    Ingests matching text/caption updates via ingest_external_note.
    """
    ensure_intake_tables(db)
    ws = str(workspace or "brain_mcp").strip().lower() or "brain_mcp"
    if ws in ("all", "*"):
        ws = "brain_mcp"

    with db._connect() as conn:
        token = _get_meta(conn, "telegram_bot_token", "").strip()
        allowed_chat_id = _get_meta(conn, "telegram_chat_id", "").strip()
        enabled = _get_meta(conn, "telegram_enabled", "0") == "1"
        last_offset_raw = _get_meta(conn, "telegram_last_update_id", "0")

    if not enabled or not token:
        return {"ok": True, "skipped": True, "ingested": 0}

    try:
        offset = int(last_offset_raw or "0")
    except ValueError:
        offset = 0

    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=1"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        err_msg = str(exc).replace(token, _mask_token(token))
        return {"ok": False, "skipped": False, "ingested": 0, "error": err_msg[:200]}

    if not isinstance(payload, dict) or not payload.get("ok"):
        return {"ok": False, "skipped": False, "ingested": 0, "error": "Telegram API returned not-ok."}

    updates = payload.get("result") or []
    ingested_items: List[Dict[str, Any]] = []
    max_update_id = offset - 1

    for upd in updates:
        if not isinstance(upd, dict):
            continue
        upd_id = int(upd.get("update_id") or 0)
        if upd_id > max_update_id:
            max_update_id = upd_id

        msg = upd.get("message") or upd.get("edited_message")
        if not isinstance(msg, dict):
            continue

        chat_obj = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
        msg_chat_id = str(chat_obj.get("id") or "")
        if allowed_chat_id and msg_chat_id != allowed_chat_id:
            continue

        msg_text = str(msg.get("text") or msg.get("caption") or "").strip()
        if not msg_text:
            continue

        from_obj = msg.get("from") if isinstance(msg.get("from"), dict) else {}
        sender_name = str(
            from_obj.get("username")
            or from_obj.get("first_name")
            or msg_chat_id
            or "telegram_user"
        )
        voice_obj = msg.get("voice") or msg.get("audio")
        audio_dur = float(voice_obj.get("duration") or 0.0) if isinstance(voice_obj, dict) else 0.0

        res = ingest_external_note(
            db,
            text=msg_text,
            channel="telegram",
            sender=sender_name,
            workspace=ws,
            mode="auto",
            audio_duration_sec=audio_dur,
        )
        if res.get("ok"):
            ingested_items.append(res)

    if max_update_id >= offset:
        with db._connect() as conn:
            _set_meta(conn, "telegram_last_update_id", str(max_update_id + 1))

    return {
        "ok": True,
        "skipped": False,
        "ingested": len(ingested_items),
        "items": ingested_items,
        "last_update_id": max_update_id + 1 if max_update_id >= offset else offset,
    }


def _collect_git_modified_files(repo_dir: Path) -> List[str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
            return lines[:15]
    except Exception:
        pass
    return []


def generate_cross_ide_handoff(
    db: Any,
    workspace: str = "brain_mcp",
    source_ide: str = "antigravity",
    target_ide: str = "codex_cli",
    current_task: str = "",
    open_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a portable plain-Markdown HANDOFF.md for switching IDEs/CLI agents
    and persist it inside .brain_vault/<workspace>/HANDOFF.md.
    """
    ensure_intake_tables(db)
    ws = str(workspace or "brain_mcp").strip().lower() or "brain_mcp"
    if ws in ("all", "*"):
        ws = "brain_mcp"
    src_ide = str(source_ide or "antigravity").strip()
    tgt_ide = str(target_ide or "codex_cli").strip()
    now_iso = _utc_now_iso()

    active_model = "unknown"
    try:
        from runtime_detector import detect_runtime_profile

        prof = detect_runtime_profile(db=db, probe_local=False)
        active_model = str(prof.get("model_display") or prof.get("model_raw") or "unknown")
    except Exception:
        pass

    rules_list: List[str] = []
    pending_tasks: List[str] = []
    checkpoint_goal = ""
    with db._connect() as conn:
        rule_rows = conn.execute(
            """
            SELECT topic, fact, category FROM memories
            WHERE LOWER(workspace) IN (?, 'global')
              AND category IN ('rule', 'learned_rule', 'directive', 'decision', 'architecture')
              AND superseded_by IS NULL
            ORDER BY importance DESC, id DESC
            LIMIT 6;
            """,
            (ws,),
        ).fetchall()
        for rr in rule_rows:
            rules_list.append(f"- **[{rr['category']}] {rr['topic']}**: {str(rr['fact'])[:200]}")

        try:
            task_rows = conn.execute(
                """
                SELECT dot_id, title, status, lane
                FROM dots_tasks
                WHERE status != 'done' AND LOWER(workspace) IN (?, 'global', 'brain_mcp')
                ORDER BY priority DESC, id ASC
                LIMIT 8;
                """,
                (ws,),
            ).fetchall()
            for tr in task_rows:
                pending_tasks.append(f"- `{tr['dot_id']}` [{tr['status']}/{tr['lane']}]: {tr['title']}")
        except Exception:
            pass

        chk = conn.execute(
            "SELECT goal, status, next_tasks FROM checkpoints WHERE LOWER(workspace) = ? LIMIT 1;",
            (ws,),
        ).fetchone()
        if chk and chk["goal"]:
            checkpoint_goal = str(chk["goal"])

    effective_task = (current_task or checkpoint_goal or f"Continue active development in `{ws}`").strip()

    files_list = [str(f).strip() for f in (open_files or []) if str(f).strip()]
    if not files_list:
        files_list = _collect_git_modified_files(Path(__file__).resolve().parent)

    rules_md = "\n".join(rules_list) if rules_list else "- No canonical rules recorded yet."
    files_md = "\n".join(f"- `{f}`" for f in files_list) if files_list else "- No open/modified files reported."
    tasks_md = "\n".join(pending_tasks) if pending_tasks else "- No pending DOTS tasks."

    resume_prompt = (
        f"You are taking over workspace `{ws}` from `{src_ide}` into `{tgt_ide}`.\n"
        f"Current task: {effective_task}\n"
        f"Read `.brain_vault/{ws}/HANDOFF.md` and follow all Active Canonical Rules before editing files."
    )

    markdown = (
        f"# Cross-IDE Handoff — `{ws}`\n\n"
        f"- **Route**: `{src_ide}` -> `{tgt_ide}`\n"
        f"- **Timestamp (UTC)**: `{now_iso}`\n"
        f"- **Active Model**: `{active_model}`\n\n"
        "## 🎯 Current Task\n"
        f"{effective_task}\n\n"
        "## 📜 Active Canonical Rules & Decisions\n"
        f"{rules_md}\n\n"
        "## 📂 Open / Modified Files\n"
        f"{files_md}\n\n"
        "## ✅ Pending Tasks\n"
        f"{tasks_md}\n\n"
        "## 🚀 Resume Prompt\n"
        "```text\n"
        f"{resume_prompt}\n"
        "```\n"
    )

    from orbit_engine import OrbitEngine

    orbit = OrbitEngine(db)
    save_res = orbit.save_vault_note(
        workspace=ws,
        filename="HANDOFF.md",
        content=markdown,
        sync_to_db=False,
    )
    file_path = str(save_res.get("path") or (orbit._get_vault_dir(ws) / "HANDOFF.md"))

    with db._connect() as conn:
        _set_meta(conn, f"handoff_updated_at:{ws}", now_iso)
        _set_meta(conn, f"handoff_path:{ws}", file_path)

    return {
        "ok": True,
        "workspace": ws,
        "source_ide": src_ide,
        "target_ide": tgt_ide,
        "vault_file": "HANDOFF.md",
        "file_path": file_path,
        "markdown": markdown,
        "resume_prompt": resume_prompt,
    }


def _build_waveform(recent_rows: List[Dict[str, Any]]) -> List[float]:
    if not recent_rows:
        return [0.18, 0.24, 0.32, 0.22, 0.40, 0.28, 0.36, 0.20, 0.44, 0.30, 0.25, 0.38, 0.22, 0.34, 0.26, 0.19]
    bars: List[float] = []
    for idx in range(16):
        row = recent_rows[idx % len(recent_rows)]
        dur = float(row.get("audio_duration_sec") or 0.0)
        txt_len = len(str(row.get("cleaned_text") or ""))
        if dur > 0:
            amp = min(1.0, max(0.15, 0.22 + (dur / 25.0)))
        else:
            amp = min(1.0, max(0.15, 0.18 + ((txt_len % 140) / 170.0)))
        # Subtle deterministic modulation across bars
        mod = ((idx * 7 + txt_len) % 10) * 0.02
        val = round(min(1.0, max(0.15, amp - mod if idx % 2 else amp + mod)), 3)
        bars.append(val)
    return bars


def get_intake_handoff_status(
    db: Any,
    workspace: str = "brain_mcp",
    limit: int = 10,
) -> Dict[str, Any]:
    """Return Telegram bridge state, recent intake items, waveform telemetry, and HANDOFF.md status."""
    ensure_intake_tables(db)
    ws = str(workspace or "brain_mcp").strip().lower() or "brain_mcp"
    if ws in ("all", "*"):
        ws = "brain_mcp"
    lim = max(1, min(100, int(limit or 10)))

    with db._connect() as conn:
        token = _get_meta(conn, "telegram_bot_token", "")
        chat_id = _get_meta(conn, "telegram_chat_id", "")
        enabled = _get_meta(conn, "telegram_enabled", "0") == "1"
        handoff_updated_at = _get_meta(conn, f"handoff_updated_at:{ws}", "")

        if ws != "all":
            total_row = conn.execute(
                "SELECT COUNT(*) AS c FROM engram_intake_log WHERE LOWER(workspace) = ?;",
                (ws,),
            ).fetchone()
            rows = conn.execute(
                """
                SELECT id, channel, sender, workspace, raw_text, cleaned_text, routed_to, target_ref, audio_duration_sec, created_at
                FROM engram_intake_log
                WHERE LOWER(workspace) = ?
                ORDER BY id DESC
                LIMIT ?;
                """,
                (ws, lim),
            ).fetchall()
        else:
            total_row = conn.execute("SELECT COUNT(*) AS c FROM engram_intake_log;").fetchone()
            rows = conn.execute(
                """
                SELECT id, channel, sender, workspace, raw_text, cleaned_text, routed_to, target_ref, audio_duration_sec, created_at
                FROM engram_intake_log
                ORDER BY id DESC
                LIMIT ?;
                """,
                (lim,),
            ).fetchall()

    recent_items = [dict(r) for r in rows]
    total_ingested = int(total_row["c"] or 0) if total_row else 0

    from orbit_engine import OrbitEngine

    orbit = OrbitEngine(db)
    vault_ws = "brain_mcp" if ws == "all" else ws
    handoff_path = orbit._get_vault_dir(vault_ws) / "HANDOFF.md"
    handoff_exists = handoff_path.is_file()
    preview = ""
    if handoff_exists:
        try:
            preview = handoff_path.read_text(encoding="utf-8", errors="replace")[:400]
            if not handoff_updated_at:
                mtime = handoff_path.stat().st_mtime
                handoff_updated_at = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    return {
        "ok": True,
        "telegram_configured": bool(token.strip()),
        "telegram_enabled": enabled,
        "token_masked": _mask_token(token),
        "chat_id": chat_id,
        "total_ingested": total_ingested,
        "recent_items": recent_items,
        "waveform": _build_waveform(recent_items),
        "handoff": {
            "exists": handoff_exists,
            "vault_file": "HANDOFF.md",
            "updated_at": handoff_updated_at,
            "preview": preview,
        },
    }

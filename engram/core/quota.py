"""Shared 5-hour quota burn-rate radar (zero circular dependencies)."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def compute_5h_quota_radar(db: Any, window_hours: float = 5.0) -> Dict[str, Any]:
    """
    Live 5h Quota & Burn Rate Meter:
    Analyzes active transcript logs modified within the sliding 5h window and
    SQLite telemetry savings without coupling runtime_detector to orbit_engine.
    """
    now_ts = time.time()
    window_sec = max(3600.0, float(window_hours) * 3600.0)
    cutoff_ts = now_ts - window_sec
    cutoff_iso = datetime.fromtimestamp(cutoff_ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    brain_root = Path.home() / ".gemini" / "antigravity" / "brain"
    active_conv_count = 0
    turns_in_window = 0
    oldest_active_mtime = now_ts

    if brain_root.is_dir():
        try:
            for conv_dir in brain_root.iterdir():
                if not conv_dir.is_dir():
                    continue
                t_file = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
                if not t_file.is_file():
                    continue
                mtime = t_file.stat().st_mtime
                if mtime < cutoff_ts:
                    continue
                if mtime < oldest_active_mtime:
                    oldest_active_mtime = mtime
                active_conv_count += 1
                try:
                    with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if '"USER_INPUT"' not in line and '"PLANNER_RESPONSE"' not in line:
                                continue
                            m_ca = re.search(r'"created_at"\s*:\s*"([^"]+)"', line)
                            if m_ca and m_ca.group(1) < cutoff_iso:
                                continue
                            turns_in_window += 1
                except Exception:
                    pass
        except Exception:
            pass

    tokens_saved_5h = 0
    telemetry_turns_5h = 0
    if db is not None:
        try:
            with db._connect() as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt, COALESCE(SUM(estimated_saved_tokens), 0) AS saved
                    FROM telemetry
                    WHERE created_at >= datetime('now', '-5 hours')
                    """
                ).fetchone()
                if row:
                    telemetry_turns_5h = int(row["cnt"] or 0)
                    tokens_saved_5h = int(row["saved"] or 0)
        except Exception:
            pass

    effective_turns = max(telemetry_turns_5h, turns_in_window // 2, 1)
    elapsed_hrs = max(0.25, min(window_hours, (now_ts - oldest_active_mtime) / 3600.0))
    burn_rate_per_hr = round(effective_turns / elapsed_hrs, 1)

    nominal_cap = 300
    usage_pct = round(min(99.0, (effective_turns / float(nominal_cap)) * 100.0), 1)
    remaining_pct = round(max(0.0, 100.0 - usage_pct), 1)
    reset_sec = max(60.0, (oldest_active_mtime + window_sec) - now_ts)
    reset_in_minutes = int(round(reset_sec / 60.0))
    reset_h = reset_in_minutes // 60
    reset_m = reset_in_minutes % 60

    status_level = "HEALTHY"
    if usage_pct >= 80.0:
        status_level = "HIGH_BURN"
    elif usage_pct >= 55.0:
        status_level = "MODERATE"

    return {
        "ok": True,
        "window_hours": window_hours,
        "active_conversations_5h": active_conv_count,
        "turns_5h": effective_turns,
        "nominal_cap_5h": nominal_cap,
        "usage_pct": usage_pct,
        "remaining_pct": remaining_pct,
        "burn_rate_per_hr": burn_rate_per_hr,
        "reset_in_minutes": reset_in_minutes,
        "reset_formatted": f"{reset_h}h{reset_m:02d}m",
        "tokens_saved_5h": tokens_saved_5h,
        "status_level": status_level,
    }

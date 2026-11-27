"""Shared zero-dependency utility functions used across Engram engines."""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict

# Canonical workspace slug aliases to prevent fragmentation across '-' vs '_' or legacy names.
WORKSPACE_CANONICAL_ALIASES: Dict[str, str] = {
    "jarvis_cortex_os": "jarvis-cortex-os",
    "project-jarvis": "jarvis-cortex-os",
    "jarvis": "jarvis-cortex-os",
    "pt.shadowhub.meter.v2": "shadowmeter2",
    "shadowmeter": "shadowmeter2",
    "shadowmeter_2": "shadowmeter2",
}


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format ending with Z."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_int(value: Any, default: int = 0, min_v: int | None = None, max_v: int | None = None) -> int:
    """Parse integer safely with optional clamping."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    if min_v is not None and parsed < min_v:
        parsed = min_v
    if max_v is not None and parsed > max_v:
        parsed = max_v
    return parsed


def canonical_workspace_alias(workspace: str) -> str:
    """Map known fragmented workspace aliases to their canonical workspace identifier."""
    raw = str(workspace or "").strip().lower()
    if not raw:
        return "global"
    return WORKSPACE_CANONICAL_ALIASES.get(raw, raw)


def normalize_workspace_slug(raw_workspace: str) -> str:
    """Normalize a workspace name/slug cleanly while preserving canonical project names."""
    ws = str(raw_workspace or "").strip().lower()
    if not ws:
        return "global"
    ws = re.sub(r"\s+", "-", ws)
    ws = re.sub(r"[^a-z0-9._\-]", "", ws)
    ws = ws.strip(".-_") or "global"
    return canonical_workspace_alias(ws)

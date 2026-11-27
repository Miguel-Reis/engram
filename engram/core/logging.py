"""Lightweight rotating logger & in-memory error ring buffer (zero external deps)."""

from __future__ import annotations

import collections
import logging
import os
import threading
import traceback
from typing import Any, Deque, Dict, List, Optional

from engram.core.utils import utc_now_iso

_LOG_LOCK = threading.Lock()
_LOGGER: Optional[logging.Logger] = None
_RECENT_ERRORS: Deque[Dict[str, Any]] = collections.deque(maxlen=60)
_ERROR_TOTAL = 0

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR = os.path.join(_REPO_ROOT, ".engram_logs")
_LOG_FILE = os.path.join(_LOG_DIR, "engram.log")


def get_logger(name: str = "engram") -> logging.Logger:
    """Return a lazily initialized rotating file logger (never raises on disk errors)."""
    global _LOGGER
    if _LOGGER is None:
        with _LOG_LOCK:
            if _LOGGER is None:
                logger = logging.getLogger("engram")
                logger.setLevel(logging.INFO)
                logger.propagate = False
                if not logger.handlers:
                    try:
                        import logging.handlers as _lh

                        os.makedirs(_LOG_DIR, exist_ok=True)
                        handler = _lh.RotatingFileHandler(
                            _LOG_FILE,
                            maxBytes=1_500_000,
                            backupCount=2,
                            encoding="utf-8",
                        )
                        handler.setFormatter(
                            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
                        )
                        logger.addHandler(handler)
                    except Exception:
                        logger.addHandler(logging.NullHandler())
                _LOGGER = logger
    return _LOGGER if name == "engram" else logging.getLogger(f"engram.{name}")


def log_error(component: str, context: str, exc: Optional[BaseException] = None) -> None:
    """Record a non-fatal error in both the rotating log file and in-memory telemetry ring buffer."""
    global _ERROR_TOTAL
    err_type = type(exc).__name__ if exc is not None else "Error"
    err_msg = str(exc) if exc is not None else ""
    entry: Dict[str, Any] = {
        "ts": utc_now_iso(),
        "component": str(component or "core"),
        "context": str(context or "")[:180],
        "error_type": err_type,
        "message": err_msg[:300],
    }
    with _LOG_LOCK:
        _ERROR_TOTAL += 1
        _RECENT_ERRORS.appendleft(entry)
    try:
        logger = get_logger(component)
        if exc is not None:
            tb = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            logger.warning("%s | %s", context, tb)
        else:
            logger.warning("%s", context)
    except Exception:
        pass


def log_warning(component: str, message: str) -> None:
    """Record an operational warning without failing caller control flow."""
    try:
        get_logger(component).warning("%s", message)
    except Exception:
        pass


def get_recent_errors(limit: int = 15) -> Dict[str, Any]:
    """Return bounded error telemetry snapshot for /api/db/health and UI diagnostics."""
    with _LOG_LOCK:
        items: List[Dict[str, Any]] = list(_RECENT_ERRORS)[: max(1, min(60, int(limit or 15)))]
        total = _ERROR_TOTAL
    return {
        "total_logged_errors": total,
        "recent": items,
        "log_file": _LOG_FILE,
    }

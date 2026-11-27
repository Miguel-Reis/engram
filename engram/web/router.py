"""Zero-dependency declarative HTTP router for Engram Web Studio OS."""

from __future__ import annotations

import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Tuple

from engram.core.logging import log_error

RouteHandler = Callable[..., Any]


class RouteRegistry:
    """
    Lightweight exact + prefix HTTP route registry used by web_dashboard.py.
    Supports method-scoped handlers (`GET`, `POST`, `DELETE`) with unified exception
    capture and structured JSON fallback responses.
    """

    def __init__(self) -> None:
        self._exact: Dict[Tuple[str, str], RouteHandler] = {}
        self._prefixes: Dict[str, List[Tuple[str, RouteHandler]]] = {
            "GET": [],
            "POST": [],
            "DELETE": [],
        }

    def add(self, method: str, path: str, handler: RouteHandler, prefix: bool = False) -> None:
        m = str(method or "GET").upper()
        if prefix:
            self._prefixes.setdefault(m, []).append((path, handler))
            # Match longest prefix first
            self._prefixes[m].sort(key=lambda item: -len(item[0]))
        else:
            self._exact[(m, path)] = handler

    def get(self, path: str, prefix: bool = False) -> Callable[[RouteHandler], RouteHandler]:
        def _dec(fn: RouteHandler) -> RouteHandler:
            self.add("GET", path, fn, prefix=prefix)
            return fn

        return _dec

    def post(self, path: str, prefix: bool = False) -> Callable[[RouteHandler], RouteHandler]:
        def _dec(fn: RouteHandler) -> RouteHandler:
            self.add("POST", path, fn, prefix=prefix)
            return fn

        return _dec

    def delete(self, path: str, prefix: bool = False) -> Callable[[RouteHandler], RouteHandler]:
        def _dec(fn: RouteHandler) -> RouteHandler:
            self.add("DELETE", path, fn, prefix=prefix)
            return fn

        return _dec

    def resolve(self, method: str, path: str) -> Optional[RouteHandler]:
        m = str(method or "GET").upper()
        exact_fn = self._exact.get((m, path))
        if exact_fn is not None:
            return exact_fn
        for pref, fn in self._prefixes.get(m, []):
            if path.startswith(pref):
                return fn
        return None

    def dispatch(
        self,
        method: str,
        handler_obj: Any,
        parsed: urllib.parse.ParseResult,
        body: Any = None,
        body_raw: str = "",
        db: Any = None,
    ) -> bool:
        """Execute matched route handler; returns True if handled, False to fall through."""
        fn = self.resolve(method, parsed.path)
        if fn is None:
            return False
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            fn(handler_obj, parsed=parsed, qs=qs, body=body, body_raw=body_raw, db=db)
        except Exception as exc:
            log_error("web_router", f"{method} {parsed.path}", exc)
            handler_obj._send_json({"ok": False, "error": str(exc), "path": parsed.path}, 500)
        return True

    def list_routes(self) -> List[Dict[str, Any]]:
        """Inspect all registered declarative routes (useful for diagnostics and tests)."""
        out: List[Dict[str, Any]] = []
        for (m, p) in sorted(self._exact.keys()):
            out.append({"method": m, "path": p, "prefix": False})
        for m, items in sorted(self._prefixes.items()):
            for p, _ in items:
                out.append({"method": m, "path": p, "prefix": True})
        return out

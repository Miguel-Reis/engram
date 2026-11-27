"""Safe zero-build static asset loader with strict path-traversal protection."""

from __future__ import annotations

import os
from typing import Optional, Tuple

_MIME_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".html": "text/html; charset=utf-8",
    ".woff2": "font/woff2",
}


def resolve_static_asset(repo_root: str, url_path: str) -> Optional[Tuple[bytes, str]]:
    """
    Resolve `/static/<subpath>` safely inside `<repo_root>/static/`.
    Rejects any path traversal (`..`, absolute paths, symlinks escaping `static/`).
    """
    if not url_path.startswith("/static/"):
        return None
    rel = url_path[len("/static/") :].lstrip("/")
    if not rel or ".." in rel or "\\" in rel or rel.startswith("/"):
        return None
    static_root = os.path.realpath(os.path.join(repo_root, "static"))
    target = os.path.realpath(os.path.join(static_root, *rel.split("/")))
    if not (target == static_root or target.startswith(static_root + os.sep)):
        return None
    if not os.path.isfile(target):
        return None
    ext = os.path.splitext(target)[1].lower()
    mime = _MIME_TYPES.get(ext, "application/octet-stream")
    with open(target, "rb") as fh:
        return fh.read(), mime

"""Architecture integrity tests: zero circular imports, MCP facade, and JS syntax."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_zero_circular_imports_across_root_modules() -> None:
    py_files = sorted(REPO_ROOT.glob("*.py"))
    internal_mods = {p.stem for p in py_files}
    graph: dict[str, set[str]] = defaultdict(set)

    for pf in py_files:
        tree = ast.parse(pf.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    m = alias.name.split(".")[0]
                    if m in internal_mods and m != pf.stem:
                        graph[pf.stem].add(m)
            elif isinstance(node, ast.ImportFrom) and node.module:
                m = node.module.split(".")[0]
                if m in internal_mods and m != pf.stem:
                    graph[pf.stem].add(m)

    cycles = set()
    for a, deps in graph.items():
        for b in deps:
            if a in graph.get(b, set()):
                cycles.add(tuple(sorted((a, b))))
            for c in graph.get(b, set()):
                if a in graph.get(c, set()) and len({a, b, c}) == 3:
                    cycles.add(tuple(sorted((a, b, c))))

    assert not cycles, f"Circular imports detected: {sorted(cycles)}"


def test_mcp_unified_search_facade_signature(isolated_db) -> None:
    import server

    server.db = isolated_db
    isolated_db.store_fact(
        topic="Unified Search Facade",
        fact="Engram v11.1 search_brain supports hybrid, neural, hipporag, and temporal modes.",
        workspace="brain_mcp",
        category="architecture",
    )
    out = server.search_brain("Unified Search Facade", workspace="brain_mcp", mode="hybrid")
    assert "Unified Search Facade" in out
    assert len(server.mcp._tools) == 35


def test_frontend_zero_build_js_syntax() -> None:
    node_exe = shutil.which("node")
    if not node_exe:
        return
    # Validate all static/js/*.js files
    for js_file in sorted((REPO_ROOT / "static" / "js").glob("*.js")):
        res = subprocess.run([node_exe, "--check", str(js_file)], capture_output=True, text=True)
        assert res.returncode == 0, f"{js_file.name} syntax error: {res.stderr}"

    # Validate inline script blocks inside index.html
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:\s+[^>]*)?>(.*?)</script>", html, flags=re.S | re.I)
    for idx, sc in enumerate(scripts):
        if not sc.strip():
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(sc)
            tmp_name = tmp.name
        try:
            res = subprocess.run([node_exe, "--check", tmp_name], capture_output=True, text=True)
            assert res.returncode == 0, f"index.html script[{idx}] syntax error: {res.stderr}"
        finally:
            os.unlink(tmp_name)

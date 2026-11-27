"""Hermetic tests for hook cold-start laziness, RouteRegistry, static asset security & app.py bind."""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

from engram.web.router import RouteRegistry
from engram.web.static_assets import resolve_static_asset

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_route_registry_exact_prefix_and_error_handling() -> None:
    router = RouteRegistry()
    captured = {}

    @router.get("/api/ping")
    def _ping(handler, **_kw):
        handler._send_json({"pong": True}, 200)

    @router.delete("/api/items/", prefix=True)
    def _del_item(handler, parsed, **_kw):
        handler._send_json({"deleted": parsed.path.split("/")[-1]}, 200)

    @router.post("/api/boom")
    def _boom(_handler, **_kw):
        raise ValueError("simulated route failure")

    class _FakeHandler:
        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    h = _FakeHandler()
    assert router.dispatch("GET", h, urllib.parse.urlparse("/api/ping")) is True
    assert captured == {"payload": {"pong": True}, "status": 200}

    assert router.dispatch("DELETE", h, urllib.parse.urlparse("/api/items/42")) is True
    assert captured == {"payload": {"deleted": "42"}, "status": 200}

    assert router.dispatch("POST", h, urllib.parse.urlparse("/api/boom")) is True
    assert captured["status"] == 500
    assert captured["payload"]["ok"] is False

    assert router.dispatch("GET", h, urllib.parse.urlparse("/api/unknown")) is False
    assert len(router.list_routes()) == 3


def test_static_asset_resolver_blocks_path_traversal() -> None:
    assert resolve_static_asset(str(REPO_ROOT), "/static/../brain.db") is None
    assert resolve_static_asset(str(REPO_ROOT), "/static/..\\brain.db") is None
    assert resolve_static_asset(str(REPO_ROOT), "/static/../../etc/passwd") is None
    assert resolve_static_asset(str(REPO_ROOT), "/not-static/file.js") is None

    css_asset = resolve_static_asset(str(REPO_ROOT), "/static/css/studio.css")
    assert css_asset is not None
    raw_css, css_mime = css_asset
    assert "text/css" in css_mime and len(raw_css) > 10_000

    js_asset = resolve_static_asset(str(REPO_ROOT), "/static/js/neural_studio.js")
    assert js_asset is not None
    raw_js, js_mime = js_asset
    assert "javascript" in js_mime and b"fetchNeuralStudioPage" in raw_js


def test_security_regressions_app_bind_and_do_delete() -> None:
    app_src = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert '"0.0.0.0"' not in app_src and "'0.0.0.0'" not in app_src
    assert '"127.0.0.1"' in app_src

    wd_src = (REPO_ROOT / "web_dashboard.py").read_text(encoding="utf-8")
    del_idx = wd_src.find("def do_DELETE(")
    assert del_idx != -1
    del_block = wd_src[del_idx : del_idx + 1200]
    assert "/api/v10/status" not in del_block
    assert "/api/v10/hipporag" not in del_block
    assert "/api/v10/temporal" not in del_block


def test_hooks_cli_empty_stdin_fast_path_skips_heavy_imports() -> None:
    """Running brain_inject.py / brain_harvest.py with empty stdin must exit cleanly without loading heavy engines."""
    env = dict(os.environ, ENGRAM_DISABLE_WARM_HOOK="1")
    for script, expected in (("brain_inject.py", "{}"), ("brain_harvest.py", '"allow"')):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / script)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert proc.returncode == 0, f"{script} failed: {proc.stderr}"
        assert expected in proc.stdout

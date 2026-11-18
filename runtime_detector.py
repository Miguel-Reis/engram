import concurrent.futures
import json
import os
import platform
import re
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCAL_PROBE_LOCK = threading.Lock()
_LOCAL_PROBE_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
_LOCAL_PROBE_TTL_SEC = 30.0

_LOCAL_MODEL_MARKERS = (
    "ollama",
    "lmstudio",
    "lm-studio",
    "llamacpp",
    "llama.cpp",
    "gguf",
    "mlx",
    "qwen",
    "llama",
    "mistral",
    "mixtral",
    "gemma",
    "phi",
    "codestral",
    "devstral",
    "starcoder",
    "deepseek-r1",
    "yi:",
    "granite",
    "command-r",
    "smollm",
    "tinyllama",
    "vicuna",
    "orca",
)

_LOCAL_SIZE_SUFFIX_RE = re.compile(r":\d+(?:\.\d+)?b\b", re.IGNORECASE)
_FAST_SMALL_RE = re.compile(r"(?:^|[-_:/.\s()])(?:flash|mini|haiku|lite|nano|spark)(?:$|[-_:/.\s()])", re.IGNORECASE)
_FRONTIER_HIGH_RE = re.compile(r"(?:^|[-_:/.\s()])(?:opus|high|ultra|thinking|pro-high|o3|o4)(?:$|[-_:/.\s()])", re.IGNORECASE)
_PARAM_BILLIONS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b\b", re.IGNORECASE)
_SETTINGS_CHANGE_RE = re.compile(
    r"<USER_SETTINGS_CHANGE>\s*The user changed setting\s+[`'\"]?Model Selection[`'\"]?\s+from\s+.*?\s+to\s+[`'\"]?([^\n<`'\"]+?)[`'\"]?(?:\.(?=\s|$|<)|(?=<)|$)",
    re.IGNORECASE,
)

_PLATFORM_DISPLAY_NAMES = {
    "antigravity": "Antigravity",
    "claude_code": "Claude Code",
    "codex_cli": "Codex CLI",
    "cursor": "Cursor",
    "windsurf": "Windsurf",
    "opencode": "OpenCode",
    "generic_mcp": "Generic MCP",
}


def _format_model_display(
    model_raw: str,
    model_family: str,
    is_local_model: bool,
    param_billions: Optional[float],
) -> str:
    """Format a raw model identifier into a clean human-readable display label."""
    raw = (model_raw or "").strip()
    if not raw:
        return "Auto-Detected Model"
    low = raw.lower()

    # Gemini formatting: e.g. gemini-4-neon-high -> Gemini 4 (High)
    if model_family == "gemini":
        m_neon = re.match(
            r"^gemini-(\d+(?:\.\d+)?)-neon(?:-(high|low|medium|pro|flash|lite))?$",
            low,
        )
        if m_neon:
            ver, mod = m_neon.group(1), m_neon.group(2)
            if mod:
                return f"Gemini {ver} ({mod.capitalize()})"
            return f"Gemini {ver}"
        m_gem = re.match(r"^gemini-(\d+(?:\.\d+)?)(?:-(.+))?$", low)
        if m_gem:
            ver, rest = m_gem.group(1), m_gem.group(2) or ""
            if not rest:
                return f"Gemini {ver}"
            tokens = [t for t in rest.split("-") if t]
            if tokens and tokens[-1] in ("high", "low", "medium"):
                tier_word = tokens.pop().capitalize()
                core = " ".join(t.capitalize() for t in tokens)
                return f"Gemini {ver} {core} ({tier_word})".replace("  ", " ").strip()
            return f"Gemini {ver} {' '.join(t.capitalize() for t in tokens)}".strip()

    # Claude formatting: e.g. claude-opus-4-6 -> Claude Opus 4.6
    if model_family == "claude":
        cleaned = re.sub(r"-\d{8}$", "", low)
        m_c1 = re.match(r"^claude-(opus|sonnet|haiku)-(\d+)-(\d+)$", cleaned)
        if m_c1:
            tier_w, maj, minor = m_c1.group(1).capitalize(), m_c1.group(2), m_c1.group(3)
            return f"Claude {tier_w} {maj}.{minor}"
        m_c2 = re.match(r"^claude-(\d+)-(\d+)-(opus|sonnet|haiku)$", cleaned)
        if m_c2:
            maj, minor, tier_w = m_c2.group(1), m_c2.group(2), m_c2.group(3).capitalize()
            return f"Claude {tier_w} {maj}.{minor}"
        m_c3 = re.match(r"^claude-(opus|sonnet|haiku)-(\d+(?:\.\d+)?)$", cleaned)
        if m_c3:
            return f"Claude {m_c3.group(1).capitalize()} {m_c3.group(2)}"

    # OpenAI formatting: e.g. gpt-5.3-codex -> GPT-5.3 Codex
    if model_family == "openai":
        m_gpt = re.match(r"^gpt-(\d+(?:\.\d+)?[a-z]?)(?:-(.+))?$", low)
        if m_gpt:
            ver, rest = m_gpt.group(1), m_gpt.group(2)
            if not rest:
                return f"GPT-{ver}"
            rest_fmt = " ".join(w.capitalize() for w in rest.split("-") if w)
            return f"GPT-{ver} {rest_fmt}".strip()
        if low.startswith(("o1", "o3", "o4")):
            parts = low.split("-")
            return " ".join([parts[0]] + [p.capitalize() for p in parts[1:]])

    # Local LLM formatting: e.g. qwen2.5-coder:32b -> Qwen 2.5 Coder 32B (Local)
    if is_local_model:
        base_part, _, tag_part = raw.partition(":")
        # Strip provider prefixes like ollama/ or lmstudio-community/
        if "/" in base_part:
            base_part = base_part.split("/")[-1]
        base_part = re.sub(r"\.gguf$", "", base_part, flags=re.IGNORECASE)
        # Insert space between letters and version numbers: qwen2.5 -> Qwen 2.5, llama3.3 -> Llama 3.3
        spaced = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", base_part)
        words = [w for w in re.split(r"[-_]+", spaced) if w]
        fmt_words: List[str] = []
        for w in words:
            if w.lower() in ("r1", "v2", "v3", "vl"):
                fmt_words.append(w.upper())
            elif re.match(r"^\d+(?:\.\d+)?$", w):
                fmt_words.append(w)
            else:
                fmt_words.append(w.capitalize())
        size_label = ""
        if tag_part and tag_part.lower() != "latest":
            if _PARAM_BILLIONS_RE.fullmatch(tag_part.strip()):
                size_label = f" {tag_part.strip().upper()}"
            elif param_billions is not None:
                p_str = f"{int(param_billions)}B" if param_billions.is_integer() else f"{param_billions}B"
                if p_str.lower() not in " ".join(fmt_words).lower():
                    size_label = f" {p_str}"
        elif param_billions is not None:
            p_str = f"{int(param_billions)}B" if param_billions.is_integer() else f"{param_billions}B"
            if p_str.lower() not in " ".join(fmt_words).lower():
                size_label = f" {p_str}"
        label = f"{' '.join(fmt_words)}{size_label}".strip() or raw
        return f"{label} (Local)"

    # Generic cloud formatting
    words = [w for w in re.split(r"[-_/]+", raw) if w]
    return " ".join(w.upper() if len(w) <= 3 and w.isalpha() else w.capitalize() for w in words)


def _compact_model_short(model_display: str) -> str:
    """Create a short, whitespace-free model token for the [BRAIN_MEMORY|...] header."""
    s = (model_display or "Auto").replace("(Local)", "").strip()
    s = s.replace("(", "").replace(")", "")
    tokens = [t for t in s.split() if t]
    if not tokens:
        return "Auto"
    return "-".join(tokens[:4])[:28]


def _estimate_pricing(model_family: str, model_tier: str, is_local_model: bool) -> Dict[str, float]:
    """Return realistic tiered USD pricing per 1M tokens."""
    if is_local_model or model_family.startswith("local_"):
        return {"input": 0.0, "output": 0.0, "cache_read": 0.0}
    if model_family == "claude":
        if model_tier == "fast_small":
            return {"input": 0.80, "output": 4.00, "cache_read": 0.08}
        if model_tier == "frontier_high":
            return {"input": 15.00, "output": 75.00, "cache_read": 1.50}
        return {"input": 3.00, "output": 15.00, "cache_read": 0.30}
    if model_family == "gemini":
        if model_tier == "fast_small":
            return {"input": 0.15, "output": 0.60, "cache_read": 0.0375}
        if model_tier == "frontier_high":
            return {"input": 2.50, "output": 15.00, "cache_read": 0.625}
        return {"input": 1.25, "output": 10.00, "cache_read": 0.3125}
    if model_family == "openai":
        if model_tier == "fast_small":
            return {"input": 0.15, "output": 0.60, "cache_read": 0.075}
        if model_tier == "frontier_high":
            return {"input": 10.00, "output": 40.00, "cache_read": 2.50}
        return {"input": 2.50, "output": 10.00, "cache_read": 1.25}
    if model_family == "deepseek":
        return {"input": 0.27, "output": 1.10, "cache_read": 0.07}
    return {"input": 1.25, "output": 5.00, "cache_read": 0.30}


def classify_model_profile(
    model_raw: str,
    is_local_hint: bool = False,
    provider_hint: str = "",
) -> Dict[str, Any]:
    """
    Classify any cloud or local LLM identifier into canonical family, tier,
    adaptive context budget, context window estimate, and pricing metadata.
    """
    norm_raw = " ".join(str(model_raw or "").strip().split())
    low = norm_raw.lower()
    prov_low = (provider_hint or "").strip().lower()

    m_param = _PARAM_BILLIONS_RE.search(low)
    param_billions: Optional[float] = float(m_param.group(1)) if m_param else None

    is_local_model = bool(
        is_local_hint
        or prov_low in ("ollama", "lmstudio", "llamacpp", "vllm", "jan")
        or any(marker in low for marker in _LOCAL_MODEL_MARKERS)
        or bool(_LOCAL_SIZE_SUFFIX_RE.search(low))
    )

    # Determine model_family
    if is_local_model:
        if "lmstudio" in low or "lm-studio" in low or prov_low == "lmstudio":
            model_family = "local_lmstudio"
        elif "llamacpp" in low or "llama.cpp" in low or "gguf" in low or prov_low == "llamacpp":
            model_family = "local_llamacpp"
        elif "vllm" in low or prov_low == "vllm":
            model_family = "local_vllm"
        else:
            model_family = "local_ollama"
    elif "gemini" in low:
        model_family = "gemini"
    elif "claude" in low or low in ("opus", "sonnet", "haiku"):
        model_family = "claude"
    elif any(k in low for k in ("gpt-", "gpt4", "gpt5", "codex", "o1-", "o3-", "o4-")) or low in ("o1", "o3", "o4"):
        model_family = "openai"
    elif "deepseek" in low:
        model_family = "deepseek"
    else:
        model_family = "unknown"

    # Determine model_tier and adaptive budgets
    if is_local_model:
        if param_billions is not None and param_billions >= 24.0:
            model_tier = "balanced"
            recommended_ephemeral_chars = 950
            context_window_est = 65_536
            stop_threshold_delta = 0.0
        else:
            model_tier = "local_compact"
            recommended_ephemeral_chars = 600
            context_window_est = 32_768
            stop_threshold_delta = 0.08
    elif _FAST_SMALL_RE.search(low):
        model_tier = "fast_small"
        recommended_ephemeral_chars = 950
        context_window_est = 128_000
        stop_threshold_delta = 0.04
    elif _FRONTIER_HIGH_RE.search(low) or "pro-high" in low:
        model_tier = "frontier_high"
        recommended_ephemeral_chars = 1500
        context_window_est = 200_000 if model_family == "claude" else 1_000_000
        stop_threshold_delta = -0.02
    else:
        model_tier = "balanced"
        recommended_ephemeral_chars = 1250
        context_window_est = 200_000
        stop_threshold_delta = 0.0

    model_display = _format_model_display(norm_raw, model_family, is_local_model, param_billions)
    pricing = _estimate_pricing(model_family, model_tier, is_local_model)

    return {
        "model_raw": norm_raw,
        "model_display": model_display,
        "model_short": _compact_model_short(model_display),
        "model_family": model_family,
        "is_local_model": is_local_model,
        "param_billions": param_billions,
        "model_tier": model_tier,
        "recommended_ephemeral_chars": recommended_ephemeral_chars,
        "context_window_est": context_window_est,
        "stop_threshold_delta": stop_threshold_delta,
        "pricing_per_1m": pricing,
    }


def _http_get_json(url: str, timeout_s: float) -> Optional[Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if raw.strip() else None


def _probe_single_runtime(spec: Dict[str, str], timeout_s: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    provider = spec["provider"]
    base_url = spec["url"].rstrip("/")
    result: Dict[str, Any] = {
        "provider": provider,
        "url": base_url,
        "active": False,
        "loaded_models": [],
        "available_models": [],
        "available_count": 0,
        "latency_ms": 0.0,
    }
    try:
        if provider == "ollama":
            ps_data = _http_get_json(f"{base_url}/api/ps", timeout_s)
            result["active"] = True
            if isinstance(ps_data, dict):
                for m in ps_data.get("models") or []:
                    if not isinstance(m, dict):
                        continue
                    details = m.get("details") or {}
                    size_vram = m.get("size_vram") or m.get("size") or 0
                    result["loaded_models"].append(
                        {
                            "name": str(m.get("name") or m.get("model") or ""),
                            "size_vram_gb": round(float(size_vram) / (1024 ** 3), 2) if size_vram else 0.0,
                            "context_length": int(m.get("context_length") or 0) or None,
                            "parameter_size": str(details.get("parameter_size") or ""),
                        }
                    )
            try:
                tags_data = _http_get_json(f"{base_url}/api/tags", max(0.05, timeout_s))
                if isinstance(tags_data, dict):
                    names = [
                        str(m.get("name") or m.get("model") or "")
                        for m in (tags_data.get("models") or [])
                        if isinstance(m, dict) and (m.get("name") or m.get("model"))
                    ]
                    result["available_count"] = len(names)
                    result["available_models"] = names[:15]
            except Exception:
                pass
        else:
            models_data = _http_get_json(f"{base_url}/v1/models", timeout_s)
            result["active"] = True
            if isinstance(models_data, dict):
                data_list = models_data.get("data") or []
                names = [
                    str(m.get("id") or "")
                    for m in data_list
                    if isinstance(m, dict) and m.get("id")
                ]
                result["available_count"] = len(names)
                result["available_models"] = names[:15]
                for m_name in names[:4]:
                    result["loaded_models"].append(
                        {
                            "name": m_name,
                            "size_vram_gb": 0.0,
                            "context_length": None,
                            "parameter_size": "",
                        }
                    )
    except Exception:
        pass
    result["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    return result


def _normalize_ollama_url(raw_host: str) -> str:
    h = (raw_host or "").strip()
    if not h:
        return "http://127.0.0.1:11434"
    if "://" not in h:
        h = f"http://{h}"
    h = h.replace("://0.0.0.0", "://127.0.0.1").replace("://[::]", "://127.0.0.1")
    # Append default port if host-only (e.g. http://127.0.0.1)
    scheme, _, rest = h.partition("://")
    if ":" not in rest.split("/")[0]:
        h = f"{scheme}://{rest.rstrip('/')}:11434"
    return h.rstrip("/")


def detect_local_llm_runtimes(
    timeout_ms: int = 150,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Probe standard local LLM runtimes (Ollama, LM Studio, llama.cpp, vLLM, Jan)
    in parallel with strict timeout and a 30-second module-level cache.
    """
    now = time.monotonic()
    with _LOCAL_PROBE_LOCK:
        cached = _LOCAL_PROBE_CACHE.get("data")
        if (
            not force_refresh
            and cached is not None
            and (now - float(_LOCAL_PROBE_CACHE.get("ts") or 0.0)) < _LOCAL_PROBE_TTL_SEC
        ):
            return cached

    t0 = time.perf_counter()
    timeout_s = max(0.03, min(2.0, float(timeout_ms) / 1000.0))
    specs = [
        {"provider": "ollama", "url": _normalize_ollama_url(os.environ.get("OLLAMA_HOST", ""))},
        {"provider": "lmstudio", "url": os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234")},
        {"provider": "llamacpp", "url": os.environ.get("LLAMACPP_URL", "http://127.0.0.1:8080")},
        {"provider": "vllm", "url": os.environ.get("VLLM_URL", "http://127.0.0.1:8000")},
        {"provider": "jan", "url": os.environ.get("JAN_URL", "http://127.0.0.1:1337")},
    ]

    runtimes: List[Dict[str, Any]] = []
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=len(specs))
    try:
        future_map = {ex.submit(_probe_single_runtime, spec, timeout_s): spec for spec in specs}
        done, not_done = concurrent.futures.wait(future_map.keys(), timeout=timeout_s + 0.03)
        for fut in done:
            try:
                runtimes.append(fut.result())
            except Exception:
                spec = future_map[fut]
                runtimes.append(
                    {
                        "provider": spec["provider"],
                        "url": spec["url"],
                        "active": False,
                        "loaded_models": [],
                        "available_models": [],
                        "available_count": 0,
                        "latency_ms": float(timeout_ms),
                    }
                )
        for fut in not_done:
            fut.cancel()
            spec = future_map[fut]
            runtimes.append(
                {
                    "provider": spec["provider"],
                    "url": spec["url"],
                    "active": False,
                    "loaded_models": [],
                    "available_models": [],
                    "available_count": 0,
                    "latency_ms": float(timeout_ms),
                }
            )
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    # Preserve deterministic provider order
    order_idx = {s["provider"]: idx for idx, s in enumerate(specs)}
    runtimes.sort(key=lambda r: order_idx.get(r["provider"], 99))

    active_providers_count = sum(1 for r in runtimes if r.get("active"))
    loaded_models_count = sum(len(r.get("loaded_models") or []) for r in runtimes)
    primary_loaded: Optional[Dict[str, Any]] = None
    for r in runtimes:
        loaded = r.get("loaded_models") or []
        if loaded and loaded[0].get("name"):
            primary_loaded = {
                "provider": r["provider"],
                "url": r["url"],
                **loaded[0],
            }
            break

    payload = {
        "ok": True,
        "active_providers_count": active_providers_count,
        "loaded_models_count": loaded_models_count,
        "primary_loaded_local_model": primary_loaded,
        "runtimes": runtimes,
        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
    }

    with _LOCAL_PROBE_LOCK:
        _LOCAL_PROBE_CACHE["ts"] = time.monotonic()
        _LOCAL_PROBE_CACHE["data"] = payload
    return payload


def build_platform_topology(
    platform_id: str,
    model_display: str,
    intent: str = "general_engineering",
    is_local_model: bool = False,
) -> str:
    """Build platform-native subagent/execution routing hint for [JEV_S1]."""
    m_label = (model_display or "Auto-Detected Model").strip()
    if is_local_model:
        return f"LOCAL ({m_label}) ➔ Single-Pass Surgical AST (Zero-Overhead)"

    plat = (platform_id or "generic_mcp").strip().lower()
    if plat == "antigravity":
        if intent == "bugfix_diagnosis":
            return f"SCOUT (flash_lite) ➔ DEBUGGER ({m_label}) ➔ VERIFY (flash)"
        if intent == "ui_3d_interactive":
            return f"SCOUT (flash_lite) ➔ UI-01 ({m_label}) + API-01 (flash)"
        if intent == "quota_performance":
            return f"SCOUT (flash_lite · Read 1x) ➔ Lean Profile ({m_label})"
        if intent == "security_privacy_gate":
            return f"SECURITY-AUDITOR ({m_label}) + AI-Defence Scan"
        return f"ARCH ({m_label}) ➔ Parallel Lanes (flash / flash_lite)"

    if plat == "claude_code":
        if intent == "bugfix_diagnosis":
            return f"ARCH ({m_label}) ➔ Agent Tool (haiku scout / sonnet fix)"
        if intent == "security_privacy_gate":
            return f"SECURITY ({m_label}) ➔ Agent Tool (sonnet audit)"
        return f"ARCH ({m_label}) ➔ Agent Tool (haiku / sonnet)"

    if plat == "codex_cli":
        return f"CODEX ({m_label}) ➔ Parallel Exec Lanes"

    return f"MCP ({m_label}) ➔ Single-Pass AST + Pagoda"


def _detect_os_info() -> tuple[str, str]:
    if sys.platform.startswith("win"):
        os_plat = "windows"
    elif sys.platform == "darwin":
        os_plat = "macos"
    else:
        os_plat = "linux"
    try:
        os_rel = platform.platform(terse=True)
    except Exception:
        os_rel = os_plat
    return os_plat, os_rel


def _normalize_host_hint(host_hint: str) -> str:
    h = (host_hint or "").strip().lower()
    aliases = {
        "claude": "claude_code",
        "claude-code": "claude_code",
        "claude_code": "claude_code",
        "codex": "codex_cli",
        "codex-cli": "codex_cli",
        "codex_cli": "codex_cli",
        "antigravity": "antigravity",
        "agy": "antigravity",
        "cursor": "cursor",
        "windsurf": "windsurf",
        "opencode": "opencode",
        "generic": "generic_mcp",
        "generic_mcp": "generic_mcp",
    }
    return aliases.get(h, h)


def _detect_host_platform(
    payload: Optional[Dict[str, Any]],
    host_hint: str,
    db: Any,
) -> str:
    norm_hint = _normalize_host_hint(host_hint)
    if norm_hint and norm_hint != "auto":
        return norm_hint

    if isinstance(payload, dict) and payload:
        if any(k in payload for k in ("hook_event_name", "session_id")) or (
            "prompt" in payload and "conversationId" not in payload
        ):
            return "claude_code"
        if any(k in payload for k in ("conversationId", "workspacePaths", "invocationNum")):
            return "antigravity"

    if os.environ.get("CLAUDE_CODE_ENTRYPOINT") or os.environ.get("CLAUDECODE"):
        return "claude_code"
    if os.environ.get("CODEX_CI") or os.environ.get("CODEX_HOME"):
        return "codex_cli"
    if os.environ.get("CURSOR_TRACE_ID") or os.environ.get("CURSOR_AGENT"):
        return "cursor"
    if any(k.startswith("WINDSURF_") for k in os.environ):
        return "windsurf"
    if os.environ.get("OPENCODE"):
        return "opencode"

    if db is not None:
        latest = get_latest_runtime_session(db)
        if latest and latest.get("platform_id"):
            return str(latest["platform_id"])

    if (Path.home() / ".gemini" / "antigravity").is_dir():
        return "antigravity"
    return "generic_mcp"


def _scan_transcript_for_model(transcript_path: Optional[str]) -> tuple[str, str]:
    """
    Scan last 48KB of transcript file chronologically so the latest model signal
    (whether <USER_SETTINGS_CHANGE> or JSON step model field) wins.
    Returns (model_raw, detection_source).
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return "", ""
    try:
        file_size = os.path.getsize(transcript_path)
        read_size = min(file_size, 49152)
        with open(transcript_path, "rb") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
            tail_bytes = f.read()

        latest_model = ""
        latest_source = ""
        for raw_line in tail_bytes.decode("utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line:
                continue

            step_model = ""
            content_blob = line
            if line.startswith("{"):
                try:
                    step = json.loads(line)
                    if isinstance(step, dict):
                        step_model = str(
                            step.get("model")
                            or (step.get("message") or {}).get("model")
                            or ""
                        ).strip()
                        if step_model:
                            latest_model = step_model
                            latest_source = "transcript_step"
                        c_val = step.get("content")
                        if isinstance(c_val, str):
                            content_blob = c_val
                except Exception:
                    pass

            m_set = None
            for m in _SETTINGS_CHANGE_RE.finditer(content_blob):
                m_set = m
            if m_set:
                cand = m_set.group(1).strip().strip("`'\". ")
                if cand:
                    latest_model = cand
                    latest_source = "transcript_settings"

        return latest_model, latest_source
    except Exception:
        return "", ""


def _read_model_from_host_configs(platform_id: str = "") -> tuple[str, bool, str, str]:
    """Return (model_raw, is_local_hint, provider_hint, source) scoped to the active host platform."""
    home = Path.home()
    plat = (platform_id or "").strip().lower()

    # 1. ~/.claude/settings.json (apenas quando o host ativo é Claude Code)
    if plat == "claude_code":
        claude_cfg = home / ".claude" / "settings.json"
        if claude_cfg.is_file():
            try:
                data = json.loads(claude_cfg.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict) and data.get("model"):
                    return str(data["model"]).strip(), False, "", "config_claude"
            except Exception:
                pass

    # 2. ~/.codex/config.toml (apenas quando o host ativo é Codex CLI)
    if plat == "codex_cli":
        codex_cfg = home / ".codex" / "config.toml"
        if codex_cfg.is_file():
            try:
                txt = codex_cfg.read_text(encoding="utf-8", errors="ignore")
                m_mod = re.search(r'^\s*model\s*=\s*"([^"]+)"', txt, re.MULTILINE)
                m_prov = re.search(r'^\s*model_provider\s*=\s*"([^"]+)"', txt, re.MULTILINE)
                prov = m_prov.group(1).strip().lower() if m_prov else ""
                if m_mod:
                    local_hint = prov in ("ollama", "lmstudio", "llamacpp", "local")
                    return m_mod.group(1).strip(), local_hint, prov, "config_codex"
            except Exception:
                pass

    # 3. ~/.config/opencode/opencode.json (apenas quando o host ativo é OpenCode)
    if plat == "opencode":
        oc_cfg = home / ".config" / "opencode" / "opencode.json"
        if oc_cfg.is_file():
            try:
                data = json.loads(oc_cfg.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict) and data.get("model"):
                    return str(data["model"]).strip(), False, "", "config_opencode"
            except Exception:
                pass

    return "", False, "", ""


def detect_runtime_profile(
    payload: Optional[Dict[str, Any]] = None,
    transcript_path: Optional[str] = None,
    host_hint: str = "",
    db: Any = None,
    probe_local: bool = False,
) -> Dict[str, Any]:
    """
    Multi-signal runtime detector (<2ms passive, <150ms cached local probe).
    Detects OS, IDE/CLI host platform, active LLM model, local vs cloud profile,
    adaptive ephemeral budget, and platform-native subagent topology.
    """
    os_platform, os_release = _detect_os_info()
    platform_id = _detect_host_platform(payload, host_hint, db)
    platform_display = _PLATFORM_DISPLAY_NAMES.get(platform_id, platform_id)

    client_version = ""
    if isinstance(payload, dict):
        client_version = str(
            payload.get("clientVersion")
            or payload.get("client_version")
            or ""
        ).strip()

    model_raw = ""
    detection_source = "fallback"
    is_local_hint = False
    provider_hint = ""

    # Signal 1: Direct payload field
    if isinstance(payload, dict):
        cand = (
            payload.get("model")
            or payload.get("model_id")
            or (payload.get("modelInfo") or {}).get("model")
        )
        if cand:
            model_raw = str(cand).strip()
            detection_source = "payload"

    # Signal 2: Transcript tail scan (48KB)
    if not model_raw and transcript_path:
        t_model, t_src = _scan_transcript_for_model(transcript_path)
        if t_model:
            model_raw = t_model
            detection_source = t_src or "transcript"

    # Signal 3: Environment variables & local base URLs (only apply base_url local hint when host matches or model came from env/unknown)
    relevant_urls: List[str] = []
    if platform_id == "claude_code":
        relevant_urls.append(str(os.environ.get("ANTHROPIC_BASE_URL") or ""))
    elif platform_id in ("codex_cli", "opencode", "cursor", "windsurf", "generic_mcp"):
        relevant_urls.append(str(os.environ.get("OPENAI_BASE_URL") or ""))
    if not model_raw:
        relevant_urls.extend([
            str(os.environ.get("OPENAI_BASE_URL") or ""),
            str(os.environ.get("ANTHROPIC_BASE_URL") or ""),
            str(os.environ.get("LM_STUDIO_URL") or ""),
        ])
    base_url_blob = " ".join(relevant_urls).lower()
    if "127.0.0.1" in base_url_blob or "localhost" in base_url_blob:
        is_local_hint = True
        if ":1234" in base_url_blob:
            provider_hint = "lmstudio"
        elif ":11434" in base_url_blob:
            provider_hint = "ollama"
        elif ":8080" in base_url_blob:
            provider_hint = "llamacpp"
        elif ":8000" in base_url_blob:
            provider_hint = "vllm"

    if not model_raw:
        for env_key in (
            "ANTHROPIC_MODEL",
            "OPENAI_MODEL",
            "CODEX_MODEL",
            "GEMINI_MODEL",
            "OLLAMA_MODEL",
            "LLM_MODEL",
        ):
            val = (os.environ.get(env_key) or "").strip()
            if val:
                model_raw = val
                detection_source = f"env:{env_key}"
                if env_key == "OLLAMA_MODEL":
                    is_local_hint = True
                    provider_hint = provider_hint or "ollama"
                break

    # Signal 4: Latest persisted runtime session in DB (real active session takes precedence over static files)
    if not model_raw and db is not None:
        conv_id = None
        if isinstance(payload, dict):
            conv_id = payload.get("conversationId") or payload.get("session_id")
        latest = get_latest_runtime_session(db, conversation_id=str(conv_id) if conv_id else None)
        if not latest and conv_id:
            latest = get_latest_runtime_session(db, conversation_id=None)
        if latest and latest.get("model_raw"):
            model_raw = str(latest["model_raw"]).strip()
            is_local_hint = bool(latest.get("is_local_model"))
            detection_source = "db_session"
            if not client_version and latest.get("client_version"):
                client_version = str(latest["client_version"])

    # Signal 5: Host config files (scoped strictly to the active platform_id)
    if not model_raw:
        c_model, c_local, c_prov, c_src = _read_model_from_host_configs(platform_id=platform_id)
        if c_model:
            model_raw = c_model
            is_local_hint = is_local_hint or c_local
            provider_hint = provider_hint or c_prov
            detection_source = c_src

    # Signal 6: Local LLM runtime probe (when requested and still unknown or local hint)
    if (probe_local and (not model_raw or is_local_hint)):
        probe_res = detect_local_llm_runtimes(timeout_ms=150)
        primary_local = probe_res.get("primary_loaded_local_model")
        if primary_local and primary_local.get("name") and not model_raw:
            model_raw = str(primary_local["name"]).strip()
            is_local_hint = True
            provider_hint = str(primary_local.get("provider") or provider_hint)
            detection_source = f"local_probe:{provider_hint or 'local'}"

    if (
        detection_source in ("payload", "transcript_step", "transcript_settings", "db_session", "config_claude")
        and (
            model_raw.lower().startswith(("gemini-", "claude-", "gpt-"))
            or model_raw.lower() in ("opus", "sonnet", "haiku")
        )
    ):
        is_local_hint = False
        provider_hint = ""

    classified = classify_model_profile(
        model_raw,
        is_local_hint=is_local_hint,
        provider_hint=provider_hint,
    )
    topology_hint = build_platform_topology(
        platform_id=platform_id,
        model_display=classified["model_display"],
        intent="general_engineering",
        is_local_model=classified["is_local_model"],
    )

    return {
        "os_platform": os_platform,
        "os_release": os_release,
        "platform_id": platform_id,
        "platform_display": platform_display,
        "client_version": client_version,
        "detection_source": detection_source,
        "topology_hint": topology_hint,
        **classified,
    }


def _ensure_runtime_table(conn: Any) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            workspace TEXT NOT NULL DEFAULT 'brain_mcp',
            platform_id TEXT NOT NULL DEFAULT 'antigravity',
            client_version TEXT NOT NULL DEFAULT '',
            os_platform TEXT NOT NULL DEFAULT 'windows',
            model_raw TEXT NOT NULL DEFAULT '',
            model_display TEXT NOT NULL DEFAULT '',
            model_family TEXT NOT NULL DEFAULT 'unknown',
            model_tier TEXT NOT NULL DEFAULT 'balanced',
            is_local_model INTEGER NOT NULL DEFAULT 0,
            context_window_est INTEGER NOT NULL DEFAULT 128000,
            recommended_ephemeral_chars INTEGER NOT NULL DEFAULT 1250,
            detection_source TEXT NOT NULL DEFAULT 'fallback',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runtime_conv ON runtime_sessions(conversation_id, updated_at);"
    )


def record_runtime_session(
    db: Any,
    profile: Dict[str, Any],
    conversation_id: str = "default",
    workspace: str = "brain_mcp",
) -> bool:
    """Idempotently persist/update the active runtime session in SQLite."""
    if db is None or not isinstance(profile, dict):
        return False
    conv = (conversation_id or "default").strip() or "default"
    ws = (workspace or "brain_mcp").strip() or "brain_mcp"
    try:
        with db._connect() as conn:
            _ensure_runtime_table(conn)
            existing = conn.execute(
                "SELECT id FROM runtime_sessions WHERE conversation_id = ? ORDER BY id DESC LIMIT 1;",
                (conv,),
            ).fetchone()
            vals = (
                ws,
                str(profile.get("platform_id") or "antigravity"),
                str(profile.get("client_version") or ""),
                str(profile.get("os_platform") or "windows"),
                str(profile.get("model_raw") or ""),
                str(profile.get("model_display") or "Auto-Detected Model"),
                str(profile.get("model_family") or "unknown"),
                str(profile.get("model_tier") or "balanced"),
                1 if profile.get("is_local_model") else 0,
                int(profile.get("context_window_est") or 128000),
                int(profile.get("recommended_ephemeral_chars") or 1250),
                str(profile.get("detection_source") or "fallback"),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE runtime_sessions
                    SET workspace = ?, platform_id = ?, client_version = ?, os_platform = ?,
                        model_raw = ?, model_display = ?, model_family = ?, model_tier = ?,
                        is_local_model = ?, context_window_est = ?, recommended_ephemeral_chars = ?,
                        detection_source = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (*vals, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO runtime_sessions (
                        conversation_id, workspace, platform_id, client_version, os_platform,
                        model_raw, model_display, model_family, model_tier,
                        is_local_model, context_window_est, recommended_ephemeral_chars,
                        detection_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (conv, *vals),
                )
        return True
    except Exception:
        return False


def get_latest_runtime_session(
    db: Any,
    conversation_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the most recent persisted runtime session (optionally filtered by conversation_id)."""
    if db is None:
        return None
    try:
        with db._connect() as conn:
            _ensure_runtime_table(conn)
            if conversation_id:
                row = conn.execute(
                    """
                    SELECT * FROM runtime_sessions
                    WHERE conversation_id = ?
                    ORDER BY updated_at DESC, id DESC LIMIT 1;
                    """,
                    (conversation_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM runtime_sessions
                    ORDER BY updated_at DESC, id DESC LIMIT 1;
                    """
                ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["is_local_model"] = bool(d.get("is_local_model"))
            return d
    except Exception:
        return None


def get_runtime_history(db: Any, limit: int = 12) -> List[Dict[str, Any]]:
    """Return recent runtime sessions ordered by most recently updated."""
    if db is None:
        return []
    try:
        with db._connect() as conn:
            _ensure_runtime_table(conn)
            rows = conn.execute(
                """
                SELECT * FROM runtime_sessions
                ORDER BY updated_at DESC, id DESC LIMIT ?;
                """,
                (max(1, int(limit)),),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                d["is_local_model"] = bool(d.get("is_local_model"))
                out.append(d)
            return out
    except Exception:
        return []

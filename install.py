import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_DIR = Path(__file__).resolve().parent
HOME_DIR = Path.home()
GEMINI_DIR = HOME_DIR / ".gemini"
CONFIG_DIR = GEMINI_DIR / "config"
PLUGINS_DIR = CONFIG_DIR / "plugins" / "antigravity-brain"
RULES_DIR = PLUGINS_DIR / "rules"


def configure_hooks_and_plugin(silent: bool = False, targets: str = "antigravity") -> Dict[str, Any]:
    """Configura automaticamente os hooks globais, plugin e MCP para qualquer utilizador."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    python_cmd = "python" if os.name == "nt" else "python3"
    inject_script = (REPO_DIR / "brain_inject.py").as_posix()
    harvest_script = (REPO_DIR / "brain_harvest.py").as_posix()
    server_script = (REPO_DIR / "server.py").as_posix()

    hooks_payload = {
        "hooks": {
            "PreInvocation": [
                {
                    "command": f'{python_cmd} "{inject_script}"',
                    "timeout": 5000,
                }
            ],
            "Stop": [
                {
                    "command": f'{python_cmd} "{harvest_script}"',
                    "timeout": 8000,
                }
            ],
        }
    }

    # 1. Atualizar ~/.gemini/config/hooks.json preservando outros hooks se existirem
    global_hooks_path = CONFIG_DIR / "hooks.json"
    existing_hooks: Dict[str, Any] = {}
    if global_hooks_path.is_file():
        try:
            existing_hooks = json.loads(global_hooks_path.read_text(encoding="utf-8"))
        except Exception:
            existing_hooks = {}

    merged_hooks = existing_hooks.get("hooks", {})
    merged_hooks["PreInvocation"] = hooks_payload["hooks"]["PreInvocation"]
    merged_hooks["Stop"] = hooks_payload["hooks"]["Stop"]
    existing_hooks["hooks"] = merged_hooks
    global_hooks_path.write_text(
        json.dumps(existing_hooks, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 2. Atualizar ~/.gemini/config/plugins/antigravity-brain/
    plugin_json_path = PLUGINS_DIR / "plugin.json"
    plugin_manifest = {
        "name": "antigravity-brain",
        "version": "8.5.0",
        "description": "Zero-Round-Trip SQLite FTS5 + 128-D LSH Memory Engine, Autonomous Swarm & Subagent Model Router, Multi-Model & Multi-Platform Runtime Intelligence, 7-IDE Cross-OS Bridge, Pagoda LSM Folds, Archify Delta, GBrain Dossiers & Local Skill Resolver",
        "hooks": "./hooks.json",
        "rules": ["./rules/AGENTS.md"],
    }
    plugin_json_path.write_text(
        json.dumps(plugin_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (PLUGINS_DIR / "hooks.json").write_text(
        json.dumps(hooks_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    agents_md_content = """# Antigravity Brain v2 — Zero-Round-Trip Memory Protocol

1. **Pre-Injected Context (`[BRAIN_MEMORY]`)**: Prior to responding, check if an ephemeral `[BRAIN_MEMORY]` block was injected. Trust its file paths, checkpoints, and environment facts so you do not waste tool calls re-discovering project structure.
2. **Zero-Token Memory Harvesting (`<!-- brain: Topic | Fact -->`)**: Whenever you solve a non-trivial bug, discover a critical IP/config/path, or make an architectural decision, append a hidden HTML comment at the very end of your response:
   `<!-- brain: Short Topic | Concise actionable fact with exact paths/values -->`
   The `Stop` hook (`brain_harvest.py`) automatically indexes these comments and any edited files into `brain.db` at zero LLM token cost.
3. **Explicit Search**: Only call the `antigravity-brain` MCP tool (`search_brain`) if you need a deep query that was not covered by the automatic `[BRAIN_MEMORY]` injection.
4. **Scout-First Asymmetric Swarm Protocol (`SCOUT ➔ PLAN ➔ SWARM ➔ VERIFY`)**:
   - **Shared Codebase Map (`[SCOUT_SHARED_MAP]`)**: Before launching multi-file work, run `SwarmEngine.run_codebase_scout()` (or `swarm_scout` / `swarm_start`) so the codebase is indexed **1 time** and shared in `brain.db` across all agents via `PreInvocation`.
   - **Decoupled Architect & Lightweight Lanes**: Read the goal and `[SCOUT_SHARED_MAP]` once as the Architect, decompose into isolated lanes (`UI`, `API`, `TESTS`, `DOCS`), and delegate parallel execution via `invoke_subagent` with `Model="flash"` or `"flash_lite"`, passing the exact target file and symbols so workers never re-read the codebase.
5. **Voice-Aware Zero-Call Protocol (`[VOICE_PRE_EXEC]` & `[VOICE_AST_TARGET]`)**:
   - When the user speaks via voice/STT and `[BRAIN_MEMORY]` contains `[VOICE_PRE_EXEC|...]` (e.g., `store_fact=OK`, `swarm_impact_graph=...`, `swarm_symbol_lookup=...`), **do NOT call that MCP tool again** — the result is already persisted/computed in `<4ms`.
   - When `[VOICE_AST_TARGET: file.py:Lstart-Lend]` is present, call `read_file` directly on that exact line range instead of running exploratory `grep` or reading whole files, and keep spoken replies concise (`[VOICE_CONCISE_MODE]`).
6. **Pagoda LSM Folds & Archify Zero-Token Delta (`brain_decompress_fold` & `swarm_archify_delta`)**:
   - **Pagoda LSM Multi-Tier Reversible Folding (`brain_decompress_fold`)**: Checkpoints and turn episodes are compacted into lossless multi-tier zlib folds (`Tier-1/2/3`), reducing context bloat while remaining instantly reversible via fold ID.
   - **Archify Evidence Console & Git Delta (`swarm_archify_delta`)**: Query deterministic zero-LLM architecture maps, git deltas between revisions, upstream/downstream reachability, and conclusion-first explainers without wasting inference tokens.
7. **GBrain Orthogonal Axes, Skill Resolver & Compiled Vault Dossiers (`brain_resolve_skill` & `brain_explain_ranking`)**:
   - **Orthogonal Salience × Recency Ranking**: Memory retrieval separates importance (pinned/canonical truth) from time decay (Ebbinghaus recency). Debug ranking math and Autocut decisions via `brain_explain_ranking`.
   - **Local Skill Resolver (`brain_resolve_skill`)**: When complex agent skills are omitted due to context-budget limits, resolve authoritative `SKILL.md` rules and trigger definitions locally at zero LLM token cost.
   - **Compiled Truth & Dossiers (`.brain_vault/<ws>/*.md`)**: Maintain two-zone dossiers (`## 💎 Compiled Truth` + `## 📅 Chronological Timeline`) with bidirectional back-links (`## 🔗 Bidirectional Back-Links`) to guarantee single source of truth across agent sessions.
8. **Multi-Model Runtime Intelligence & Autonomous Swarm Model Router (`brain_runtime_info`, `brain_route_agent_model` & `brain://runtime/profile`)**:
   - **Automatic Cloud & Local Model Detection**: `runtime_detector.py` detects the active host IDE/CLI (`antigravity`, `claude_code`, `codex_cli`, `cursor`, `windsurf`, `opencode`, `claude_desktop`), OS, active cloud model (Claude, GPT/Codex, Gemini, DeepSeek, Llama, Qwen), and local LLM runtimes (`Ollama`, `LM Studio`, `vLLM`, `llama.cpp`), scaling context budgets dynamically.
   - **Autonomous Subagent & Swarm Model Routing**: Whenever launching subagents or swarms (`invoke_subagent`, `swarm`, or `Agent`), automatically use the Brain's `🤖[SWARM_MODEL_ROUTER]` model choice injected in `[BRAIN_MEMORY]` (or call `brain_route_agent_model`) unless the user explicitly overrides the model.
   - **Model-Agnostic Swarm Routing & 7-IDE Bridge**: Inspect active runtime telemetry via `brain_runtime_info` or `GET /api/runtime`, configure routing policy via `POST /api/runtime/policy` (`auto|quality|balanced|economy|local_first`), report custom models via `brain_runtime_info(report_model=...)`, and safely connect any of the 7 supported IDEs/CLIs across Windows, macOS, and Linux via `POST /api/runtime/connect` or `install.py --targets ...`.
"""
    (RULES_DIR / "AGENTS.md").write_text(agents_md_content, encoding="utf-8")

    # 3. Sincronizar automaticamente com ~/.gemini/antigravity/scratch/brain_mcp se existir noutro caminho
    scratch_brain_dir = GEMINI_DIR / "antigravity" / "scratch" / "brain_mcp"
    try:
        if scratch_brain_dir.is_dir() and scratch_brain_dir.resolve() != REPO_DIR.resolve():
            import shutil

            for fname in (
                "server.py",
                "db_engine.py",
                "runtime_detector.py",
                "skill_resolver_engine.py",
                "pagoda_fold_engine.py",
                "archify_engine.py",
                "orbit_engine.py",
                "voice_brain_engine.py",
                "swarm_engine.py",
                "graphify_engine.py",
                "ast_impact_watcher.py",
                "token_diet.py",
                "brain_inject.py",
                "brain_harvest.py",
                "web_dashboard.py",
                "auto_updater.py",
                "app.py",
                "index.html",
                "install.py",
                "install.bat",
                "update.bat",
            ):
                src_f = REPO_DIR / fname
                if src_f.is_file():
                    shutil.copy2(src_f, scratch_brain_dir / fname)
    except Exception:
        pass

    # 4. Registar o servidor MCP em ~/.gemini/config/mcp_config.json
    mcp_cfg_path = CONFIG_DIR / "mcp_config.json"
    mcp_cfg: Dict[str, Any] = {"mcpServers": {}}
    if mcp_cfg_path.is_file():
        try:
            mcp_cfg = json.loads(mcp_cfg_path.read_text(encoding="utf-8"))
        except Exception:
            mcp_cfg = {"mcpServers": {}}

    servers = mcp_cfg.setdefault("mcpServers", {})
    servers["antigravity-brain"] = {
        "command": python_cmd,
        "args": ["-u", server_script],
    }
    mcp_cfg_path.write_text(
        json.dumps(mcp_cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 5. Limpar antigo registo Auto-Start do Windows (HKCU\...\Run\AntigravityBrain) e atalhos legados se existirem
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
            ) as key:
                try:
                    winreg.DeleteValue(key, "AntigravityBrain")
                except FileNotFoundError:
                    pass
        except Exception:
            pass

        for d_cand in (
            HOME_DIR / "Desktop",
            HOME_DIR / "Ambiente de Trabalho",
            HOME_DIR / "OneDrive" / "Desktop",
            HOME_DIR / "OneDrive" / "Ambiente de Trabalho",
        ):
            if d_cand.is_dir():
                for sc_name in ("Antigravity Brain.lnk", "Antigravity Brain.url"):
                    sc_path = d_cand / sc_name
                    if sc_path.is_file():
                        try:
                            sc_path.unlink()
                        except Exception:
                            pass

    bridge_result: Dict[str, Any] = {}
    targets_clean = str(targets or "antigravity").strip() or "antigravity"
    if targets_clean.lower() != "antigravity":
        try:
            if str(REPO_DIR) not in sys.path:
                sys.path.insert(0, str(REPO_DIR))
            from orbit_engine import OrbitEngine

            if targets_clean.lower() == "all":
                target_list: List[str] = [
                    "antigravity",
                    "claude_code",
                    "codex_cli",
                    "cursor",
                    "windsurf",
                    "opencode",
                    "claude_desktop",
                ]
            else:
                target_list = [t.strip() for t in targets_clean.split(",") if t.strip()]
            if target_list:
                bridge_result = OrbitEngine().connect_all_ai_tools(target_ids=target_list)
        except Exception:
            bridge_result = {}

    if not silent:
        print("✅ Hooks globais configurados em:", global_hooks_path)
        print("✅ Plugin Antigravity Brain v8.5 instalado em:", PLUGINS_DIR)
        print("✅ Servidor MCP registado em:", mcp_cfg_path)
        if bridge_result.get("updated_tools"):
            print("✅ Ponte Multi-IDE conectada para:", ", ".join(bridge_result["updated_tools"]))

    return {
        "hooks_path": str(global_hooks_path),
        "plugin_dir": str(PLUGINS_DIR),
        "mcp_config": str(mcp_cfg_path),
        "startup_registered": False,
        "targets": targets_clean,
        "bridge_result": bridge_result,
    }


def main() -> None:
    if getattr(sys, "stdout", None) is not None and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--no-restart", action="store_true")
    parser.add_argument(
        "--targets",
        default="antigravity",
        help="Comma-separated targets: antigravity|all|claude_code,codex_cli,cursor,windsurf,opencode,claude_desktop",
    )
    args, _unknown = parser.parse_known_args()

    silent = bool(args.silent)
    no_restart = bool(args.no_restart) or os.environ.get("BRAIN_NO_RESTART") == "1"
    if not silent:
        print("=" * 68)
        print(" 🧠 INSTALADOR & AUTO-CONFIGURADOR — ANTIGRAVITY BRAIN v8.5")
        print("=" * 68)

    configure_hooks_and_plugin(silent=silent, targets=args.targets)

    # Inicializar base de dados + Scout + Servidor Web (c/ hot-restart após git pull / update.bat)
    if str(REPO_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_DIR))

    from db_engine import BrainDB, ensure_dashboard_running, seed_initial_memories
    from swarm_engine import SwarmEngine

    db = BrainDB()
    seed_initial_memories(db)
    SwarmEngine(db).ensure_default_run()
    started = ensure_dashboard_running(force_restart=not no_restart)

    if not silent:
        print(f"✅ Base de dados SQLite FTS5 pronta: {REPO_DIR / 'brain.db'}")
        print(f"✅ Dashboard Web & Swarm Monitor ativo ({started}): http://127.0.0.1:8765")
        print("   -> Vista Grafo Obsidian : http://127.0.0.1:8765/#graph")
        print("   -> Vista Swarm Monitor  : http://127.0.0.1:8765/#swarm")
        print("=" * 68)


if __name__ == "__main__":
    main()

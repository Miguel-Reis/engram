# Multi-Platform Bridge, Swarm Router & Automation

← [Back to README](../README.md)

---

## 1. Cross-OS 7-IDE Bridge (`install.py` & `orbit_engine.py`)

Engram connects a single shared `brain.db` and Markdown Vault across **7 AI IDEs & CLIs** on **Windows, macOS, and Linux**:

| Client | MCP Registration | Native Hook Adapter |
|---|---|---|
| **Antigravity** | `~/.gemini/config/mcp_config.json` | `PreInvocation` / `Stop` (`hooks.json`) |
| **Claude Code** | `~/.claude.json` | `UserPromptSubmit` / `Stop` (`--host claude`) |
| **Codex CLI** | `~/.codex/config.toml` | Shared MCP + `HANDOFF.md` |
| **Cursor** | `~/.cursor/mcp.json` | Shared MCP + `HANDOFF.md` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` | Shared MCP + `HANDOFF.md` |
| **OpenCode** | `~/.config/opencode/opencode.json` | Shared MCP + `HANDOFF.md` |
| **Claude Desktop** | Platform AppData `claude_desktop_config.json` | Shared MCP |

Connect any target via CLI (`python install.py --targets claude_code,cursor`) or with 1 click inside the **Inspector → Multi-Platform Runtime** panel.

---

## 2. Cloud + Local LLM Runtime Detection & Autonomous Swarm Router (`runtime_detector.py`)

- **Passive Multi-Signal Detection**: Identifies the active host IDE, OS (zero-WMI cached), cloud model family & tier (`Gemini 4 (XHigh/High)`, `Claude Opus/Sonnet/Haiku`, `GPT-5 / Codex`, `DeepSeek`, `Llama`, `Qwen`), and live **local LLM runtimes** via parallel `150ms` cached probes (`Ollama :11434`, `LM Studio :1234`, `llama.cpp :8080`, `vLLM :8000`, `Jan :1337`) including loaded VRAM models.
- **Autonomous Swarm & Subagent Model Router (`brain_route_agent_model`)**:
  - Dynamically scores every lane (`SCOUT`, `DOCS`, `UI`, `API`, `TESTS`, `ARCHITECT`, `SECURITY`) based on task complexity, blast radius, active 5h quota zone (`GREEN` / `AMBER` / `RED`), local VRAM availability, and persisted routing policy (`auto` | `balanced` | `economy` | `quality` | `local_first`).
  - Automatically injects the routing matrix directive (`🤖[SWARM_MODEL_ROUTER|...]`) into `[BRAIN_MEMORY]`, degrading lightweight lanes (`SCOUT`, `DOCS`) to `flash_lite` / `haiku` / `gpt-5-mini` under `RED` quota to preserve frontier quota for architecture and security tasks.

---

## 3. Nightly Correction ➔ Rule Distiller (`rule_distiller_engine.py`)

Turns repeated user corrections into permanent agent rules automatically:

1. **Zero-Token Capture**: `brain_harvest.py` scans turns with `detect_correction_signal()` (PT-PT & EN patterns such as *"usa sempre..."*, *"nunca uses..."*, *"always use..."*, *"never do..."*) and deduplicates similar corrections via Jaccard similarity (`>= 0.55`) into `engram_corrections`.
2. **Nightly Promotion**: When a correction reaches `occurrences >= min_occurrences` (default `2`), `run_nightly_rule_distillation()` promotes it to a canonical `importance=10` rule in `brain.db` and optionally compiles it into `AGENTS.md`.
3. **Controls**: Trigger manually from the Tactical 3D **`⚡ Distill Rules`** button, Widget 5 (`NIGHTLY CORRECTIONS ➔ RULES`), `POST /api/rules/distill`, or MCP tool `brain_distill_rules`.

---

## 4. Voice / Telegram Intake & Cross-IDE `HANDOFF.md` (`intake_handoff_engine.py`)

### Voice & Telegram Note Intake
- Cleans raw spoken transcripts via `VoiceSttDenoiser` (`voice_brain_engine.py`).
- **Smart Auto-Routing**: Task-intent messages (`todo:`, `task:`, `tarefa:`, `fix `, `implementar `) automatically create a live Kanban/DOTS task + sourced memory; all notes append timestamped `[[wiki-linked]]` bullets to `.brain_vault/<workspace>/inbox_<YYYY-MM-DD>.md` with backlink enforcement.
- **Optional Telegram Bot Bridge**: Configure `bot_token` (stored encrypted via Windows **DPAPI**) and `chat_id` directly from the Tactical 3D **`⚙ Telegram`** popover.

### Cross-IDE `HANDOFF.md` Exporter
- Quit one IDE mid-task (e.g., Antigravity or Claude Code) and resume in another (e.g., Codex CLI or Cursor) in 2 seconds.
- `generate_cross_ide_handoff()` compiles active model/runtime, current task, top canonical rules, `git status --short` modified files, pending DOTS tasks, and a copy-ready resume prompt into `.brain_vault/<workspace>/HANDOFF.md` (`⇄ Handoff.md` button or `brain_export_handoff` MCP tool).

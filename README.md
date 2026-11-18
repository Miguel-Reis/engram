<div align="center">

# 🧠 Engram v9.0 — Universal AI Memory & Swarm OS

**Zero-Round-Trip Persistent Memory Engine, Autonomous Swarm & Subagent Model Router (`<0.5ms`), Multi-Model Cloud + Local LLM Detection (Ollama / LM Studio / vLLM / llama.cpp), 7-IDE Cross-OS MCP & Hook Bridge (Windows / macOS / Linux), GBrain Salience × Recency Ranking, Compiled Vault Dossiers, Local Zero-Token Skill Resolver, Pagoda LSM Folds, Archify Zero-Token Delta & 25 MCP Tools**

[![Version](https://img.shields.io/badge/version-9.0.0_Engram_OS-10b981?style=for-the-badge)](https://github.com/Miguel-Reis/engram/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B%20(Zero--Deps)-38bdf8?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Engine](https://img.shields.io/badge/SQLite_WAL-FTS5_%2B_Pagoda_LSM_%2B_128--Bit_BQ-10b981?style=for-the-badge&logo=sqlite&logoColor=white)](./db_engine.py)
[![Archify](https://img.shields.io/badge/Archify-Zero--Token_Delta_%26_Evidence_Console-06b6d4?style=for-the-badge)](./archify_engine.py)
[![MCP 2026](https://img.shields.io/badge/MCP_2026-25_Tools_%2B_Resources_%2B_Prompts-e4e4e7?style=for-the-badge)](./server.py)
[![Tests](https://img.shields.io/badge/Tests-27%2F27_Passing-10b981?style=for-the-badge)](./test_brain.py)

*Built with 100% Python Standard Library (`sqlite3`, `ast`, `http.server`, `concurrent.futures`) and Vanilla HTML5 / Canvas2D / ECS `Float32Array` SoA — zero `pip` packages required, zero cloud telemetry, sub-10ms local execution.*

[Quick Install](#-quick-install) • [Frontier Technologies](#-frontier-20252026-technologies-v90) • [Architecture](#-how-it-works-zero-round-trip-memory-protocol) • [Token Diet (-96%)](#-5-stage-token-diet--context-pipeline) • [Carbon Studio OS](#️-carbon-studio-os-dashboard-http1270018765) • [MCP 2026 Server](#-mcp-2026-server-25-tools--resources--prompts) • [Testing](#-verification--test-suite-2727-pass)

</div>

---

## 🚀 Frontier 2025–2026 Technologies (v9.0)

**Engram v9.0** integrates state-of-the-art cognitive memory, autonomous Swarm model routing, multi-model runtime detection, cross-OS 7-IDE bridging, and codebase graph breakthroughs in pure Python + SQLite WAL:

| Technology | Module & Symbols | How It Works & Impact |
| :--- | :--- | :--- |
| **1. 128-Bit Binary Quantization (BQ) + Hardware `POPCNT` Hamming** | [`db_engine.py`](./db_engine.py) · `quantize_vector_128bit()`, `hamming_similarity_128bit()`, `compute_semantic_vector()` | Packs 128-D subword LSH vectors (16-D concept clusters + 64-D unigram/bigram LSH + 48-D word-bounded `<w>` 3/4-gram morphological shingles) into a **16-byte (128-bit) hex signature**. Bitwise XOR + CPU `int.bit_count()` scans 10,000 memories in **`<0.2ms` (32× smaller storage)**. |
| **2. HippoRAG 2 — Personalized PageRank (PPR) + 4-Way Weighted RRF** | [`db_engine.py`](./db_engine.py) · `compute_memory_ppr()`, `search_memories()` | Seeds a teleportation vector with top lexical/semantic hits and runs **3 sparse power iterations** over `memory_edges` (`fixed_by`, `supersedes`, `evolves`, `co_learned`), fusing **FTS5 BM25 + 128-Bit BQ/128-D Cosine + PPR Graph Rank + Ebbinghaus Salience** via 4-Way Reciprocal Rank Fusion ($k=60$). |
| **3. GBrain Orthogonal Salience × Recency Ranking** | [`db_engine.py`](./db_engine.py) · `search_memories()`, `explain_memory_query()` | Orthogonalizes memory relevance: importance/salience (pinned directives, canonical rules, importance weights) is decoupled from temporal decay (Ebbinghaus spaced retention). Complete ranking math and Autocut decisions are explainable via `brain_explain_ranking`. |
| **4. Local Zero-Token Skill Resolver (`brain_resolve_skill`)** | [`skill_resolver_engine.py`](./skill_resolver_engine.py) · `resolve_skills_for_query()`<br>[`server.py`](./server.py) · `brain_resolve_skill` | Locally catalogs and resolves all 130+ installed Antigravity agent skills across plugins, rescuing skills excluded by IDE context-budget limits at **0 model tokens**. |
| **5. Two-Zone Compiled Vault Dossiers & Bidirectional Back-Links** | [`orbit_engine.py`](./orbit_engine.py) · `compile_vault_dossier()`, `enforce_vault_backlinks()` | Structures `.brain_vault/<ws>/*.md` notes with `## 💎 Compiled Truth` at the top and `## 📅 Chronological Timeline` below. Automatically enforces reciprocal backlinks (`## 🔗 Bidirectional Back-Links`) on every cross-referenced note. |
| **6. Ebbinghaus Spaced-Reinforcement Forgetting Curve** | [`db_engine.py`](./db_engine.py) · `compute_ebbinghaus_retention()` | Models Bjork dual-strength memory retention: half-life $H = S_{\text{tier}} \cdot (1 + 1.2\ln(1 + \text{access\_count})) \cdot (\text{importance}/3)$, where $S_{\text{working}}=3\text{d}$, $S_{\text{episodic}}=14\text{d}$, $S_{\text{semantic}}=120\text{d}$. Frequently used rules become permanent while stale episodic logs decay naturally. |
| **7. Graphiti-Style Bi-Temporal Automatic Contradiction Superseding** | [`db_engine.py`](./db_engine.py) · `store_fact()` | Tracks `valid_from`, `valid_until`, and `superseded_by`. When a new fact updates an active unlocked memory on the same workspace, category, and primary file/topic, the engine automatically stamps `valid_until = CURRENT_TIMESTAMP`, links `superseded_by = new_id`, and creates a `supersedes` edge. |
| **8. Git Co-Change Historical Coupling + Test-Case Graph & Atomic Sandbox Rollback** | [`graphify_engine.py`](./graphify_engine.py) · `_mine_git_cochange_edges()`<br>[`ast_impact_watcher.py`](./ast_impact_watcher.py) · `analyze_git_diff_blast_radius()`<br>[`swarm_engine.py`](./swarm_engine.py) · `manage_subagent_sandbox()` | Mines `git log` commit history to compute pairwise file coupling $\text{Coupling}(A,B) = \frac{\lvert C(A \cap B)\rvert}{\sqrt{\lvert C(A)\rvert\cdot\lvert C(B)\rvert}}$ (`CO_CHANGED` edges), links `TEST_CASE` nodes (`def test_*`) to production symbols, and performs **physical `zlib`+`base64` disk restoration** when a subagent sandbox fails AST or secret checks. |
| **9. MCP 2025–2026 Native `Resources`, `Prompts` & `Tool Annotations`** | [`server.py`](./server.py) · `StdioMCPServer` | Implements `resources/list`, `resources/templates/list`, `resources/read` (`brain://memories/pinned`, `brain://scout/map`, `brain://graph/report`, `brain://orbit/briefing`, `brain://voice/protocol`, `brain://skills/catalog`, `brain://pagoda/timeline`, `brain://workspace/{ws}/checkpoint`), `prompts/list` & `prompts/get`, `readOnlyHint`/`idempotentHint` annotations, and exact UTF-8 byte framing. |
| **10. Pagoda LSM Multi-Tier Reversible Context Folding** | [`pagoda_fold_engine.py`](./pagoda_fold_engine.py) · `fold_current_checkpoint()`, `fold_turn_episode()`, `decompress_fold()` | Compacts project milestones and turn history into **lossless multi-tier `zlib` archives (`Tier-1/2/3`)**, saving up to 80% context tokens while remaining instantly reversible via fold ID. |
| **11. Archify Zero-Token Evidence Console & Git Architecture Delta** | [`archify_engine.py`](./archify_engine.py) · `build_archify_spec()`, `compute_architecture_delta()`, `compute_reachability_focus()` | Computes deterministic architecture maps, in-memory git deltas (`HEAD~1 vs Worktree`), 7-signal reachability focus, and conclusion-first explainers with **zero LLM tokens and zero external dependencies**. |
| **12. Multi-Model Runtime Intelligence & 7-IDE Cross-OS Bridge** | [`runtime_detector.py`](./runtime_detector.py) · `detect_runtime_profile()`, `detect_local_llm_runtimes()`<br>[`orbit_engine.py`](./orbit_engine.py) · `get_mcp_bridge_status()`, `connect_all_ai_tools()` | Auto-detects active host IDE/CLI, OS (**Windows / macOS / Linux**), cloud models (Claude, GPT/Codex, Gemini, DeepSeek, Llama, Qwen), and local runtimes (**Ollama, LM Studio, vLLM, llama.cpp**). Safely connects **7 IDEs/CLIs** (`antigravity`, `claude_code`, `codex_cli`, `cursor`, `windsurf`, `opencode`, `claude_desktop`) and adapts Swarm routing dynamically. |
| **13. Autonomous Swarm & Subagent Model Router (`<0.5ms`)** | [`runtime_detector.py`](./runtime_detector.py) · `recommend_agent_model()`, `plan_swarm_model_matrix()`<br>[`server.py`](./server.py) · `brain_route_agent_model` | Scores task complexity (`0..100`), role, blast radius, file count, 5h quota zone (`GREEN`/`AMBER`/`RED`), and routing policy (`auto`, `quality`, `balanced`, `economy`, `local_first`) to select exact platform parameters (`flash_lite`/`flash`/`pro`, `haiku`/`sonnet`/`opus`, `gpt-5-mini`/`gpt-5.3-codex`/`o3`, or loaded local VRAM models) and inject `🤖[SWARM_MODEL_ROUTER]` directives. |

---

## 🧠 How It Works (Zero-Round-Trip Memory Protocol)

```mermaid
flowchart LR
    subgraph Hooks["100% Automatic Agent Lifecycle Hooks"]
        H1["⚡ PreInvocation\n(brain_inject.py)"]
        H2["🔧 Active Turn & 48x Swarm\n(server.py + swarm_engine.py)"]
        H3["🌾 Stop Hook\n(brain_harvest.py)"]
    end

    subgraph Core["Engram v9.0 Core (SQLite WAL · Schema v72)"]
        DB[("🗄️ brain.db\nFTS5 BM25 + 128-Bit BQ\n+ HippoRAG 2 PPR")]
        JEV["🧭 JEV-S1 Router (<0.05ms)\nWorking [W] · Semantic [S] · Episodic [E]\n+ Notice Lookahead"]
        AST["🌳 Graphify AST & Git Co-Change\n562 Nodes · 1,823 Edges · Blast Radius"]
        ORB["🛰️ Orbit OS & Global Brain\nTop-3 Universal Wisdom · 5h Quota Radar"]
    end

    subgraph UI["Carbon Studio OS v7.1 (http://127.0.0.1:8765)"]
        U1["01 Córtex · 02 Swarm 48x · 03 Office 3D"]
        U2["04 Self-Learn · 05 Prompt Forge · 06 Vault 6x"]
        U3["07 Tasks (.dots) · 08 Orbit OS · 09 AST & BFS"]
    end

    H1 <--> JEV & DB & ORB
    H2 <--> AST & DB & ORB
    H3 --> DB & AST
    DB & AST & ORB <--> U1 & U2 & U3
```

| Lifecycle Stage | Script / Engine | What Happens Automatically |
| :--- | :--- | :--- |
| **1. Before Model Turn** | `PreInvocation` ➔ [`brain_inject.py`](./brain_inject.py) | • **Smart Active-Repo Resolver**: Infers active workspace from prompt keywords, checkpoints, or modified paths.<br>• **JEV-S1 Router + DOTS Trajectory**: Classifies intent in `<0.05ms` and synthesizes optimal reasoning steps.<br>• **Global Brain Top-3 + Notice Lookahead**: Injects `🌐[GLOBAL_BRAIN\|top3]` cross-project rules, `⚠️[LOOKAHEAD]` file alerts, and query-routed `[SCOUT_SHARED_MAP]`. |
| **2. During Turn** | `MCP Stdio` ➔ [`server.py`](./server.py)<br>`Swarm/Orbit` ➔ [`swarm_engine.py`](./swarm_engine.py) | • Exposes **18 native MCP tools**, **6 MCP Resources (`brain://...`)**, and **3 MCP Prompts**.<br>• Orchestrates up to **48 parallel Swarm workers (`4 lanes × 12 workers`, `96/96` Verify Gates)** with physical rollback sandboxes. |
| **3. After Model Turn** | `Stop` ➔ [`brain_harvest.py`](./brain_harvest.py)<br>`Watcher` ➔ [`ast_impact_watcher.py`](./ast_impact_watcher.py) | • Strips `<SYSTEM_MESSAGE>` envelopes and harvests `<!-- brain: Topic \| Fact -->` notes at **0 LLM token cost**.<br>• Runs **AI-Defence secret redaction** (PEM keys, DB URIs, Stripe, JWT, GitHub/AWS/Google/Anthropic tokens), bi-temporal superseding, and AST blast-radius checks. |

---

## 🪙 5-Stage Token Diet & Context Pipeline

| Optimization Technology | Implementation | Measured Impact |
| :--- | :--- | :--- |
| **1. Session Memory Delta (`DELTA_CACHE`)** | [`db_engine.py`](./db_engine.py) · `compute_session_delta()` | Tracks per-conversation SHA-1 state (`session_delta_cache`). Turn `#2+` injects only new/modified memories + a 1-line delta badge (**`-70%` repeated context tokens**). |
| **2. TOON Telegraphic Format** | [`brain_inject.py`](./brain_inject.py) · `compress_fact_telegraphic()` | Strips conversational filler while preserving identifiers, paths, and `:Lstart-end` pointers (**`-35%` character footprint**). |
| **3. Query-Routed Scout Map** | [`brain_inject.py`](./brain_inject.py) · `select_relevant_scout_map()` | Prioritizes files and AST symbols matching the active prompt intent inside `[SCOUT_SHARED_MAP]`. |
| **4. Micro-Prompt Fast-Path (`<90 tok`)** | [`brain_inject.py`](./brain_inject.py) · `is_micro_confirmation_prompt()` | Detects short confirmations (`"sim"`, `"ok"`, `"continua"`, `"proceed"`) and switches to `MICRO_TICK` mode (**`<90 tokens` total**). |
| **5. Dynamic Intent Pruning & TOON MCP Schemas** | [`token_diet.py`](./token_diet.py) · [`server.py`](./server.py) | Selects only the 4–6 relevant MCP tools per intent (**`-96.4%` active tool overhead, `~6,076` tokens saved**). |

---

## 🖥️ Carbon Studio OS Dashboard (`http://127.0.0.1:8765`)

Redesigned end-to-end with the **Carbon Studio OS v8.1** design system (**Matte Carbon `#08080a`**, **Obsidian Zinc `#111116`**, **Hairline Borders `#22222b`**, and **Precision Emerald `#10b981`**), featuring the 7-Studio Navigation Rail + AST Inspector + Voice-Aware Zero-Call Protocol:

| Index | View / Route | Key Capabilities |
| :--- | :--- | :--- |
| **`01`** | **Córtex** (`/#graph`) | • **Blueprint Architectural Board**: 12 domain cards with technical corner brackets (`┌ ┐ └ ┘`), priority tags (`P1`–`P5`), and 5-Column Category Kanban drill-down.<br>• **Bento Gallery (`⊞ Galeria`) & Planetary Astrolabe (`◎ Orbital`)**.<br>• **2×3 Bento Document Inspector**: Workspace, Category, Priority, 128-D RRF Vector, Injections, Timestamp, Time-Travel Rollback, and Causal Lineage. |
| **`02`** | **Swarm** (`/#swarm`) | • **48-Agent Asymmetric Fleet (`4 Lanes × 12 Workers`)**: Live pipeline across `UI`, `API`, `TESTS`, and `DOCS` with `96/96` dual verification gates, Ruflo Pheromone EMA, and physical rollback sandboxes. |
| **`03`** | **Office 3D** (`/#office`) | • **60 FPS Isometric 3D Command Studio**: Dual-Wing (`Wing A` / `Wing B`) 48-agent floorplan, **3D Holographic Desk Heatmap Towers**, Frustum Culling (`-85%` off-screen draw calls), and Agent Follow Camera. |
| **`04`** | **Self-Learn** (`/#selflearn`) | • **60 FPS Neural Pipeline Canvas**: Interactive 5-stage evolution loop, **Global Brain Top-3 Universal Wisdom**, **Rule Conflict Resolver**, **File-Edit GC**, and **Bugfix-to-Test Synthesizer**. |
| **`05`** | **Prompt Forge** (`/#promptforge`) | • **6-Section Technical Specification Synthesizer**: Combines AST `:Lstart-end` pointers, Self-Learn Meta-Rules, DOTS tasks, and **Antigravity Skills (`SKILL.md`)** in `PT-PT` or `EN-EN` with 1-click **Swarm 48x Launch**. |
| **`06`** | **Vault 6x** (`/#vault`) | • **Interactive Markdown Vault Studio**: Live `.md` editor with `[[wikilinks]]`, **Defuddle Web/HTML Clipper** (with IPv4/IPv6 SSRF protection), **Universal `AGENTS.md` Repo Sync**, and 6 live telemetry canvases. |
| **`07`** | **Tasks** (`/#tasks`) | • **Dedicated 4-Column Kanban & Topological `.dots/*.md` DAG Studio**: Unifies DOTS DAG tasks, live Antigravity subagents, and 48-worker Swarm lanes with an interactive Bézier DAG canvas (`#tasksDagCanvas`). |
| **`08`** | **AST & BFS Inspector** (`/#ast`) | • **Codebase Knowledge Graph & AST Explorer**: Symbol lookup (`:Lstart-end`), Git Co-Change blast-radius prediction, God Nodes, multi-modal BFS shortest path (`2,349x` compression), and Voice Phonetic AST target resolution. |
| **`OS`** | **Orbit Mission** (`/#orbit`) | • **Mission Control Modal**: Approval Inbox (*"Needs Your Yes"*), Trust Hierarchy locks, Fleet Broadcasts, 4-IDE MCP Bridge, **Live 5h Quota Radar**, and Engineering ROI Ledger. |

> **Keyboard Shortcuts**:
> - `Ctrl+K` / `⌘K` — Open **Omni-Search Command Palette** (jump to any view, run studio actions, or search live memory nodes)
> - `1`–`8` — Switch directly to views `01 Córtex` through `08 AST & BFS Inspector`
> - `Alt+1`–`Alt+8` — Quick-jump across workspace accordions in Córtex
> - `Escape` — Close the topmost active modal (`#cmdPaletteModal`, `#vaultNoteEditorModal`, `#orbitOsModal`, `#astInspectorModal`, etc.)
> - `[` / `]` — Cycle 3D Follow Camera across active agents in `#office`

---

## 🧰 MCP 2026 Server (25 Tools + Resources + Prompts)

[`server.py`](./server.py) implements a zero-dependency **MCP JSON-RPC 2.0 Stdio Server** (`v9.0.0`) with exact UTF-8 byte framing, `initialize` `clientInfo` host capture, and MCP 2026 `Tool Annotations` (`readOnlyHint`, `idempotentHint`, `destructiveHint`):

### Native MCP Resources (`resources/list`, `resources/read`, `resources/templates/list`)
- `brain://memories/pinned` — Active human-locked directives and global meta-rules
- `brain://scout/map` — Latest `[SCOUT_SHARED_MAP]` AST index with `:Lstart-end` pointers
- `brain://graph/report` — Deterministic `GRAPH_REPORT.md` architecture summary & God Nodes
- `brain://orbit/briefing` — Executive Morning Brief, 5h Quota Radar & Engineering ROI
- `brain://voice/protocol` — Active Voice-Aware Zero-Call Protocol & Phonetic AST Guide
- `brain://skills/catalog` — Installed Antigravity skills catalog and local zero-token resolution guide
- `brain://pagoda/timeline` — Active Pagoda LSM multi-tier reversible fold timeline & compression telemetry
- `brain://runtime/profile` — Active host platform, OS, detected cloud/local model, local LLM runtimes & 7-IDE bridge status
- `brain://workspace/{workspace}/checkpoint` — Active milestone checkpoint for any workspace
- `brain://symbol/{symbol_name}` — Surgical AST symbol slice (`:Lstart-end`)

### Native MCP Prompts (`prompts/list`, `prompts/get`)
- `ultraplan-scout` — Zero-re-read architectural planning template with Scout Map & God Nodes
- `bugfix-lineage` — Root-cause debugging template with causal bugfix history & AST alerts
- `swarm-dispatch` — 4-Lane Asymmetric Swarm decomposition template (`UI`, `API`, `TESTS`, `DOCS`)

### 25 Native MCP Tools (`tools/list`, `tools/call`)
| Category | Tool Name | Read-Only | Description |
| :--- | :--- | :---: | :--- |
| **Core Memory** | `store_fact` | `false` | Store or update an architectural fact, bug fix, or directive with bi-temporal superseding & secret redaction. |
| **Core Memory** | `search_brain` | `true` | Hybrid **4-Way RRF** search (**FTS5 BM25 + 128-Bit BQ Hamming + 128-D Cosine + HippoRAG 2 PPR + Ebbinghaus**). |
| **Core Memory** | `forget_fact` | `false` | Remove obsolete or superseded memories by ID or topic. |
| **Core Memory** | `save_checkpoint` | `false` | Save a structured workspace milestone (`goal`, `next_step`, `modified_files`). |
| **Core Memory** | `brain_stats` | `true` | Retrieve per-workspace memory counts, 5-hour quota telemetry, and database health metrics. |
| **Token Diet** | `brain_prune_tools` | `true` | Dynamically select the minimal subset of MCP tools for a task intent (`-96.4%` schema overhead). |
| **Swarm & Sandbox** | `swarm_scout` | `false` | Run the `SCOUT-01` codebase indexer once and persist `[SCOUT_SHARED_MAP]` in `brain.db`. |
| **Swarm & Sandbox** | `swarm_start` | `false` | Launch a 24- or 48-task asymmetric Swarm run across `UI`, `API`, `TESTS`, and `DOCS` lanes. |
| **Swarm & Sandbox** | `swarm_update_task` | `false` | Update progress, status, and dual verification gates (`verify_1`, `verify_2`) for a Swarm task. |
| **Swarm & Sandbox** | `swarm_status` | `true` | Query live Swarm runs, Ruflo pheromone EMA scores, and active subagent fleet state. |
| **Swarm & Sandbox** | `swarm_sandbox` | `false` | Manage transactional Copy-on-Write subagent sandboxes with physical `zlib`+`base64` file rollback. |
| **AST & Graphify** | `swarm_symbol_lookup` | `true` | Locate exact line ranges (`:Lstart-end`) and snippets for Python/JS/TS/Go/Rust symbols in `<5ms`. |
| **AST & Graphify** | `swarm_impact_graph` | `true` | Compute reverse call/import + Git co-change blast radius and targeted `test_*` functions. |
| **AST & Graphify** | `swarm_watch_audit` | `false` | Trigger or inspect automated File-Save AST diff & AI-Defence secret audits. |
| **AST & Graphify** | `swarm_graph_path` | `true` | Find the shortest multi-modal BFS relational path between any two entities (`UI ➔ API ➔ Python ➔ SQL`). |
| **AST & Graphify** | `swarm_architecture_report` | `false` | Generate the deterministic [`GRAPH_REPORT.md`](./GRAPH_REPORT.md) with God Nodes, communities, and Git couplings. |
| **Orbit Agent OS** | `orbit_mission_control` | `false` | Manage Approval Inbox, Fleet Broadcasts, Handoffs, DOTS DAG tasks, Self-Learn, Vault, or Prompt Forge. |
| **Orbit Agent OS** | `orbit_briefing_roi` | `true` | Generate the executive Morning Brief, 5h Quota Radar, and Engineering ROI report. |
| **Voice Protocol** | `brain_voice_optimize` | `false` | Denoise spoken/STT queries, resolve spoken symbols to `:Lstart-end` AST pointers, and pre-execute Brain intents (`brain://voice/protocol`). |
| **Pagoda LSM** | `brain_decompress_fold` | `true` | Losslessly decompress a Pagoda LSM multi-tier fold (`Tier-1/2/3`) by fold ID (`brain://pagoda/timeline`). |
| **Archify Engine** | `swarm_archify_delta` | `true` | Zero-token deterministic architecture map, git delta, reachability focus & conclusion-first explainer (`ARCHIFY_MAP.html`). |
| **Local Skills** | `brain_resolve_skill` | `true` | Zero-token local `SKILL.md` resolver across 130+ installed Antigravity skills, rescuing context-budget-excluded skills. |
| **Ranking Explain** | `brain_explain_ranking` | `true` | Explainable hybrid search debugger (`Salience × Recency` orthogonal axes + `BM25/LSH/PPR` math + `Autocut` drop reasons). |
| **Runtime Info** | `brain_runtime_info` | `true` | Detect or explicitly report active host IDE/CLI, OS, cloud/local LLM model, local runtimes, and 7-IDE MCP bridge status. |
| **Model Router** | `brain_route_agent_model` | `true` | Route a subagent or Swarm lane to the optimal platform model (`flash_lite`/`flash`/`pro`, `haiku`/`sonnet`/`opus`, `gpt-5-mini`/`o3`, or local VRAM) by complexity, risk, policy & 5h quota. |

---

## 🚀 Quick Install

### Option A — One-Line PowerShell Install (Windows)

```powershell
git clone https://github.com/Miguel-Reis/engram.git "$HOME\.gemini\antigravity\scratch\brain_mcp"; python "$HOME\.gemini\antigravity\scratch\brain_mcp\install.py"
```

### Option B — Standard Git Clone (Windows / macOS / Linux)

```bash
git clone https://github.com/Miguel-Reis/engram.git
cd engram
python install.py          # Windows (Antigravity default)
python3 install.py         # macOS / Linux (Antigravity default)
python install.py --targets claude_code,codex_cli,cursor,windsurf,opencode,claude_desktop
```

Running [`install.py`](./install.py) automatically:
1. Configures global `PreInvocation` and `Stop` hooks in `~/.gemini/config/hooks.json`.
2. Installs the agent rules (`AGENTS.md`) and runtime in `~/.gemini/config/plugins/engram`.
3. Registers the `engram` MCP server in `~/.gemini/config/mcp_config.json` (and optionally merges configs across all 7 IDEs/CLIs via `--targets`).
4. Starts the **Carbon Studio OS Web Dashboard** on [`http://127.0.0.1:8765`](http://127.0.0.1:8765).

---

## 🧪 Verification & Test Suite (`27/27 PASS`)

Run the full end-to-end verification suite ([`test_brain.py`](./test_brain.py)):

```bash
python test_brain.py
```

Output (`27/27 PASS`):

```text
[PASS] Pesquisa FTS5 BM25: 2 resultados em 12.26ms
[PASS] Checkpoints por workspace operacionais
[PASS] PreInvocation Hook: injetou 1350 chars (~337 tokens) em 381.39ms
[PASS] Guarda Anti-Repetição de Turno verificada ({})
[PASS] Stop Hook verificado ({'decision': 'allow'})
[PASS] Contrato HTML/JS do Modo Follow 3D verificado
[PASS] AST Symbol Lookup (Python + JS): brain_inject.py:L872 & index.html:L9600
[PASS] Reverse Call/Impact Graph: 14 ficheiros afetados (113 referências, Risco: HIGH)
[PASS] Opção A (Hybrid Semantic Vector 128-D LSH + RRF BM25): cosine_bilingue=0.708, top_hit='Otimização de Quota 5h (Token Diet)'
[PASS] Opção C (Dynamic Tool Pruning): 4/18 tools ativas (-96.4% / ~6076 tokens poupados)
[PASS] Opção D (Subagent Transactional Sandbox): Sandbox #68 -> MERGED (AST Gate=True, Secret Scan=True)
[PASS] Contrato das 6 Melhorias de UI/UX verificado em index.html
[PASS] Automated File-Save AST & Impact Watcher: db_engine.py -> HIGH (10 ficheiros, 113 refs) & Symbol Diff + CRITICAL Gate OK
[PASS] Graphify Engine: 562 nós multi-modais, 1823 arestas (EXTRACTED=1183, INFERRED=578, AMBIGUOUS=62), BFS Path 'triggerAstSaveAuditUI -> ast_save_audits' em 3 saltos (2104.9x) & GRAPH_REPORT.md OK
[PASS] 3D Holographic Desk Heatmap Towers: 18 secretárias mapeadas (Top: swarm_engine.py @ 99% [HOT]) & Hitboxes/HUD OK
[PASS] MCP Stdio Server (server.py): Handshake 'initialize' OK, 18 tools registadas & 'brain_stats' executado sem dependências externas
[PASS] Orbit Agent OS (6 Tecnologias): Trust Hierarchy (Human Wins), Broadcast (1 ags), Hand-off Chaining, Inbox (2 pending), 4-IDE MCP Bridge & ROI OK
[PASS] office3DCanvas Frustum Culling: Visível no foco=(498.5, 341.9), Agente fora de vista descartado=(2217.7, 655.4) -> CULLED OK
[PASS] Brain UI & Zero-Overlap Blueprint Board + Bento Gallery + Acordeão de Pastas OK
[PASS] 4 Pilares de Melhorias (Deduplicação Semântica, Bulk Actions, Kanban 5 Colunas, Filtros & Sync Office 3D + Eco-FPS) OK
[PASS] 5 Otimizações de Poupança de Tokens (Session Delta, TOON Telegráfico, Top-K Cutoff, Pointers :Lstart-end e Micro-Prompt <90 tok) OK
[PASS] Auditoria Total v4.6 (FTS5 BM25 Prefix Fix, AST-Safe Scout Slice, Arrow Regex, Time-Travel Rollback & Security Hardening) OK
[PASS] Pack Completo DOTS v4.7 (DAG .dots/*.md + Trajetórias Cognitivas DOTS + Motor Físico ECS Float32Array SoA) OK
[PASS] Self-Learn Studio Gráfico (60 FPS Neural Pipeline) & Prompt Forge + Antigravity Skills v4.9 OK
[PASS] Remoção Limpa da App Desktop (100% Web Dashboard Carbon Studio OS v7.1) OK
[PASS] Motor Bilingue PT-PT <-> EN-EN (Zero Francês + HUD/Canvas/3D/Prompt Forge i18n) OK
[PASS] Pack Completo v6.0, v6.1, v6.2 & v7.0 Studio OS (Left Dock Rail, IDE Status Bar, Raycast Omnibox, Progressive Disclosure, @starting-style, 128-D LSH + RRF) OK
```

---

## 📂 Repository Structure

| File | Role |
| :--- | :--- |
| [`db_engine.py`](./db_engine.py) | Thread-safe SQLite WAL engine (`PRAGMA user_version = 72`), FTS5 BM25 sub-tokenized search, **128-Bit Binary Quantization (`POPCNT`)**, **128-D Subword LSH**, **HippoRAG 2 PPR**, **Ebbinghaus retention**, **Bi-Temporal contradiction superseding**, and `memory_revisions` rollback. |
| [`brain_inject.py`](./brain_inject.py) | `PreInvocation` hook: Smart Active-Repo Resolver, Session Delta (`DELTA_CACHE`), TOON telegraphic formatter, Query-Routed `[SCOUT_SHARED_MAP]`, Global Brain Top-3 injection, and **Notice Lookahead**. |
| [`brain_harvest.py`](./brain_harvest.py) | `Stop` hook: `<SYSTEM_MESSAGE>` hygiene filter, zero-token harvesting of `<!-- brain: Topic \| Fact -->` annotations, file edits, subagent handoffs, and Memory Doctor compaction. |
| [`orbit_engine.py`](./orbit_engine.py) | Orbit Agent OS engine: Approval Inbox, Trust Hierarchy, Fleet Broadcasts, `.dots/*.md` DAG with cycle detection, Recursive Self-Learning, Global Meta-Brain, Prompt Forge, Vault 6x Studio, and **7-Platform Cross-OS IDE Bridge** (`antigravity`, `claude_code`, `codex_cli`, `cursor`, `windsurf`, `opencode`, `claude_desktop`). |
| [`runtime_detector.py`](./runtime_detector.py) | **Multi-Model & Multi-Platform Runtime Detector**: Detects active host IDE/CLI, OS, cloud models, and local LLM runtimes (`Ollama`, `LM Studio`, `vLLM`, `llama.cpp`) with dynamic context budgeting and Swarm topology synthesis. |
| [`voice_brain_engine.py`](./voice_brain_engine.py) | **Voice-Aware Zero-Call Protocol Engine**: Denoises spoken/STT queries, resolves spoken symbols phonetically to AST `:Lstart-end` pointers, and pre-executes Brain intents in zero model calls (up to 68% token reduction). |
| [`swarm_engine.py`](./swarm_engine.py) | Asymmetric 48-worker Swarm orchestrator (`4 lanes × 12 workers`), `SCOUT-01` AST indexer, Ruflo Pheromone EMA, **physical `zlib`+`base64` rollback sandboxes**, and 3D Office state manager. |
| [`graphify_engine.py`](./graphify_engine.py) | Multi-modal AST & architecture knowledge graph (`562` nodes, `1,823` edges), **Git Co-Change Coupling Miner (`CO_CHANGED`)**, `TEST_CASE` indexer, God Node detector, and BFS shortest-path solver. |
| [`ast_impact_watcher.py`](./ast_impact_watcher.py) | Persistent SQLite AST symbol SHA-256 snapshotter, **Git Diff Blast-Radius Analyzer**, multi-language brace scanner, and unified AI-Defence secret scanner. |
| [`pagoda_fold_engine.py`](./pagoda_fold_engine.py) | **Pagoda LSM Reversible Folding Engine**: Multi-tier `zlib` compaction (`Tier-1/2/3`), checkpoint folding, token savings telemetry, and lossless decompression by ID. |
| [`archify_engine.py`](./archify_engine.py) | **Archify Zero-Token Architecture Engine**: Deterministic architecture map (`signal-flow`), git architecture delta, upstream/downstream reachability focus, conclusion-first explainers, and standalone HTML Evidence Console export. |
| [`token_diet.py`](./token_diet.py) | Dynamic intent-based MCP tool pruner across all 25 tools, platform-aware Swarm topology routing, and 5-hour quota profiler (`LEAN` vs `FULL`). |
| [`server.py`](./server.py) | Zero-dependency **MCP 2026 JSON-RPC 2.0 `stdio` server** (`v9.0.0`) with `clientInfo` capture, UTF-8 byte framing, 25 tools (`readOnlyHint` annotations), 8 native `Resources` (`brain://...`), and 3 `Prompts`. |
| [`web_dashboard.py`](./web_dashboard.py) | Local HTTP/SSE server (`127.0.0.1:8765`) powered by a 16-worker `ThreadPoolExecutor`, `/api/runtime`, `/api/runtime/route-model`, `/api/runtime/policy` & `/api/runtime/connect` endpoints, strict `POST`/`DELETE` CSRF protection, `4 MB` payload cap, and secret-redacted edits. |
| [`index.html`](./index.html) | Single-file **Engram v9.0 — Carbon Studio OS** UI (`01 Córtex`, `02 Swarm`, `03 Office 3D`, `04 Self-Learn`, `05 Prompt Forge`, `06 Vault 6x`, `07 Tasks`, `08 AST & BFS Inspector`, `Orbit Mission Control`). |
| [`install.py`](./install.py) / [`auto_updater.py`](./auto_updater.py) | Cross-OS automated installer (`--targets`), runtime synchronizer, and GitHub `origin/main` hot-reload updater. |
| [`test_brain.py`](./test_brain.py) | End-to-end 27-suite automated verification benchmark. |

---

## 📄 License

Released under the **MIT License**. Created and maintained by [Miguel Reis](https://github.com/Miguel-Reis).

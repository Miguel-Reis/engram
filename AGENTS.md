# AGENTS.md — Engram (`brain_mcp`)

# Engram v10.0 — Universal AI Memory, Bi-Temporal Graph, HippoRAG PPR & Swarm OS

1. **Pre-Injected Context (`[BRAIN_MEMORY]`)**: Prior to responding, check if an ephemeral `[BRAIN_MEMORY]` block was injected. Trust its file paths, checkpoints, and environment facts so you do not waste tool calls re-discovering project structure.
2. **Zero-Token Memory Harvesting (`<!-- brain: Topic | Fact -->`)**: Whenever you solve a non-trivial bug, discover a critical IP/config/path, or make an architectural decision, append a hidden HTML comment at the very end of your response:
   `<!-- brain: Short Topic | Concise actionable fact with exact paths/values -->`
   The `Stop` hook (`brain_harvest.py`) automatically indexes these comments and any edited files into `brain.db` at zero LLM token cost.
3. **Explicit Search**: Only call the `engram` MCP tool (`search_brain`) if you need a deep query that was not covered by the automatic `[BRAIN_MEMORY]` injection.
4. **Scout-First Asymmetric Swarm Protocol (`SCOUT ➔ PLAN ➔ SWARM ➔ VERIFY`)**:
   - **Shared Codebase Map (`[SCOUT_SHARED_MAP]`)**: Before launching multi-file work, run `SwarmEngine.run_codebase_scout()` (or `swarm_scout` / `swarm_start`) so the codebase is indexed **1 time** and shared in `brain.db` across all agents via `PreInvocation`.
   - **Decoupled Architect & Lightweight Lanes**: Read the goal and `[SCOUT_SHARED_MAP]` once as the Architect, decompose into isolated lanes (`UI`, `API`, `TESTS`, `DOCS`), and delegate parallel execution via `invoke_subagent` with `Model="flash"` or `"flash_lite"`, passing the exact target file and symbols so workers never re-read the codebase.
5. **Voice-Aware Zero-Call Protocol (`[VOICE_PRE_EXEC]` & `[VOICE_AST_TARGET]`)**:
   - **Spoken AST Resolution (`[VOICE_AST_TARGET]`)**: When the user speaks or query contains voice transcription markers, consult injected `[VOICE_AST_TARGET]` pointers (`:Lstart-end`) to edit or inspect code immediately without exploratory symbol lookups.
   - **Zero-Call Pre-Execution (`[VOICE_PRE_EXEC]`)**: When voice commands request memory storage, status queries, or symbol lookups, trust the pre-executed results injected under `[VOICE_PRE_EXEC]` instead of making redundant tool calls, saving up to 68% tokens.
6. **Pagoda LSM Folds & Archify Zero-Token Delta (`brain_decompress_fold` & `swarm_archify_delta`)**:
   - **Pagoda LSM Multi-Tier Reversible Folding (`brain_decompress_fold`)**: Checkpoints and turn episodes are compacted into lossless multi-tier zlib folds (`Tier-1/2/3`), reducing context bloat while remaining instantly reversible via fold ID.
   - **Archify Evidence Console & Git Delta (`swarm_archify_delta`)**: Query deterministic zero-LLM architecture maps, git deltas between revisions, upstream/downstream reachability, and conclusion-first explainers without wasting inference tokens.
7. **GBrain Orthogonal Axes, Skill Resolver & Compiled Vault Dossiers (`brain_resolve_skill` & `brain_explain_ranking`)**:
   - **Orthogonal Salience × Recency Ranking**: Memory retrieval separates importance (pinned/canonical truth) from time decay (Ebbinghaus recency). Debug ranking math and Autocut decisions via `brain_explain_ranking`.
   - **Local Skill Resolver (`brain_resolve_skill`)**: When complex agent skills are omitted due to context-budget limits, resolve authoritative `SKILL.md` rules and trigger definitions locally at zero LLM token cost.
   - **Compiled Truth & Dossiers (`.brain_vault/<ws>/*.md`)**: Maintain two-zone dossiers (`## 💎 Compiled Truth` + `## 📅 Chronological Timeline`) with bidirectional back-links (`## 🔗 Bidirectional Back-Links`) to guarantee single source of truth across agent sessions.
8. **Multi-Model Runtime Intelligence & Autonomous Swarm Model Router (`brain_runtime_info`, `brain_route_agent_model` & `brain://runtime/profile`)**:
   - **Automatic Cloud & Local Model Detection**: `runtime_detector.py` detects the active host IDE/CLI (`antigravity`, `claude_code`, `codex_cli`, `cursor`, `windsurf`, `opencode`, `claude_desktop`), OS (`Windows`/`macOS`/`Linux`), active cloud model (Claude, GPT/Codex, Gemini, DeepSeek, Llama, Qwen), and local LLM runtimes (`Ollama`, `LM Studio`, `vLLM`, `llama.cpp`), dynamically adapting context budgets and Swarm subagent topologies.
   - **Autonomous Subagent & Swarm Model Routing**: Whenever launching subagents or swarms (`invoke_subagent`, `swarm`, or `Agent`), automatically use the Brain's `🤖[SWARM_MODEL_ROUTER]` model choice injected in `[BRAIN_MEMORY]` (or call `brain_route_agent_model`) unless the user explicitly overrides the model.
   - **7-IDE Cross-OS Bridge & Runtime Telemetry**: Inspect runtime detection via `brain_runtime_info`, `brain://runtime/profile`, or `GET /api/runtime`; manage routing policies via `POST /api/runtime/policy` (`auto|quality|balanced|economy|local_first`); report explicit models via `brain_runtime_info(report_model=...)` or `POST /api/runtime/connect`; and safely merge MCP/hook configs across all 7 supported IDEs/CLIs without overwriting existing settings.
9. **Engram v10.0 Cognitive Memory, Nightly Rules, Intake/Handoff & DB Hygiene (`brain_hipporag_search`, `brain_temporal_fact`, `brain_temporal_query`, `brain_distill_rules`, `brain_ingest_note`, `brain_export_handoff`, `brain_db_maintenance`)**:
   - **Bi-Temporal Knowledge Graph**: Record evolving decisions via `brain_temporal_fact` (auto-invalidating outdated facts via `valid_to` + `SUPERSEDES` edges) and inspect historical state via `brain_temporal_query(as_of="YYYY-MM-DD")`.
   - **HippoRAG Multi-Hop Recall & Local Neural Embeddings**: Use `brain_hipporag_search` for 2-hop Personalized PageRank discovery across semantic anchors + knowledge graph edges (`🧠[HIPPO_2HOP]` is auto-augmented in `PreInvocation`).
   - **Nightly Rules, Intake & Cross-IDE Handoff**: Distill recurring corrections via `brain_distill_rules`, ingest voice/external notes via `brain_ingest_note`, export portable `HANDOFF.md` via `brain_export_handoff`, and keep `brain.db` compact via `brain_db_maintenance`.

<!-- BRAIN_AUTO_RULES_START -->
## 🧠 Engram Global Brain — Core Repository Guidelines (`brain_mcp`)
- Always validate Python changes with `python -m py_compile` and `python test_brain.py` (37/37 suites) before committing.
- Always validate `index.html` JavaScript with `node --check` and escape all dynamic HTML attributes via `escapeHtml()`.
- Keep local credentials (such as `telegram_bot_token`) encrypted via Windows DPAPI and masked on all GET responses.
- Never hardcode absolute user paths or unrelated project details in repository documentation.
<!-- BRAIN_AUTO_RULES_END -->

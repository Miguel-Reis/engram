# Architecture & Performance (`v9.2` – `v10.0`)

← [Back to README](../README.md)

---

## 1. Zero-Round-Trip Hook Lifecycle

Engram avoids wasting agent turns on manual memory searches by hooking directly into the host IDE/CLI lifecycle:

1. **Before each turn (`PreInvocation` / `UserPromptSubmit` → `brain_inject.py`)**:
   - **Warm Hook HTTP Fast-Path (`POST http://127.0.0.1:8765/api/hook/pre-invoke`)**: When the local dashboard server is running, `brain_inject.py` routes the stdin hook payload over loopback (`X-Engram-Hook: 1`) directly into already-warm Python memory — avoiding cold imports and repeated schema DDL. If the server is stopped, it falls back seamlessly to local SQLite execution.
   - **Adaptive Token Budget & Session Delta**: Scales context budget by active model tier, emits `[BRAIN_MEMORY]` in compact telegraphic TOON format, skips re-injecting facts already delivered in the same conversation (`session_memory_delta`), and collapses micro-confirmations (`sim`, `ok`) to `<90` tokens.
   - **Zero-Token Multi-Hop & Voice Pre-Execution**: Runs fast local Voice STT denoising/phonetic AST resolution (`voice_brain_engine.py`), JEV System-1 intent routing, Autonomous Swarm Model Router directives, and HippoRAG 2-hop discoveries (`🧠[HIPPO_2HOP]`).
2. **After each turn (`Stop` → `brain_harvest.py`)**:
   - Indexes inline `<!-- brain: Topic | Fact -->` comments at zero LLM token cost.
   - Harvests edited files with **parent-directory disambiguation** (`users/route.ts` instead of bare `route.ts`) to prevent overwrite collisions, rejecting single-file names and OS directories as workspaces.
   - Captures recurring user correction signals (`detect_correction_signal`) for the Nightly Rule Distiller.

---

## 2. Storage Engine, Auto-TTL & DB Hygiene (`db_engine.py`)

Engram uses a single portable SQLite database (`brain.db`) configured in **WAL mode** with **FTS5 BM25** full-text search and 128-D LSH binary quantization.

### Built-in Bloat Protection (`v9.2`)
- **Per-Process Schema Fast-Path**: `_INITIALIZED_DB_PATHS` ensures DDL/PRAGMA checks execute once per process instead of on every HTTP request.
- **Revision Cap**: `store_fact()` skips whitespace-identical updates and caps `memory_revisions` to the latest **10** revisions per `memory_id`.
- **Automated Maintenance (`run_db_maintenance`)**:
  - Purges orphan `memory_revisions` and orphan `memory_edges`.
  - Applies rolling retention caps across append-only logs (`self_learn_events`: 500, `swarm_logs`: 1,500, `telemetry`: 2,000, `agent_handoffs`: 500, `ast_save_audits`: 400, `pagoda_folds`: 300, `memory_edges`: top 8,000 by weight).
  - Optional `purge_test_ws=True` removes temporary/polluted workspaces (`test`, stray filenames) and consolidates fragmented project aliases.
  - Runs `PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM`, scheduled lightly every 12 hours in the background sentinel and triggerable on demand via `POST /api/db/maintenance`, MCP tool `brain_db_maintenance`, or the Inspector UI.

---

## 3. Lossless Folding & Zero-Token Architecture Intelligence

- **Pagoda LSM Folding (`pagoda_fold_engine.py`)**: Compacts older turn episodes and checkpoints into lossless `zlib`-archived multi-tier folds (`Tier-1/2/3`) to eliminate context rot while remaining 100% reversible via `brain_decompress_fold`.
- **Graphify Multi-Modal AST Graph (`graphify_engine.py`)**: Indexes Python, JS, TS, HTML, CSS, SQL, and Markdown symbols, detects topological communities and God Nodes, computes BFS shortest paths (`swarm_graph_path`), and emits `GRAPH_REPORT.md`.
- **Archify Evidence Console (`archify_engine.py`)**: Deterministic zero-LLM Git architecture diffs (`HEAD~1 vs WORKTREE`), upstream/downstream reachability focus, conclusion-first explainers, and portable standalone HTML exports (`/api/archify/export.html`).
- **Transactional CoW Sandboxes (`swarm_engine.py`)**: Copy-on-Write subagent sandboxes with SHA-256 pre/post snapshots, AST syntax gates, and secret leak scanning before merge.

---

## 4. Local-First Security Posture

- **Loopback Binding & Origin/CSRF Guard**: `web_dashboard.py` binds exclusively to `127.0.0.1:8765` and enforces strict local `Origin`/`Referer` checks on all `POST` and `DELETE` endpoints (returning `403 Forbidden` to cross-origin callers).
- **Native Windows DPAPI Encryption at Rest**: External credentials such as `telegram_bot_token` in `intake_handoff_engine.py` are encrypted via `ctypes.windll.crypt32.CryptProtectData` (`dpapi:<base64>`) before touching SQLite and are always masked in API responses.
- **Zero-WMI OS Telemetry**: `runtime_detector.py` detects OS metadata via `sys.platform` and `sys.getwindowsversion()` (`<0.1ms` cached), eliminating slow WMI subprocess/COM queries on Windows.
- **Strict Read/Write Isolation**: All HTML attributes use `escapeHtml()` to prevent XSS, and `test_brain.py` validates security gates across 37 suites.

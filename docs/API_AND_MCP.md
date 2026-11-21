# API & 32 MCP Tools Reference

← [Back to README](../README.md)

---

## 1. MCP Tools (`server.py` — 32 Stdio Tools)

### Core Memory & Checkpoints (`#1–#5`)
| # | Tool | Description |
|---:|---|---|
| 1 | `store_fact` | Store a sourced fact with hybrid SQLite FTS5 BM25 + LSH indexing. |
| 2 | `search_brain` | Hybrid BM25 + semantic similarity search across workspaces. |
| 3 | `forget_fact` | Delete a memory by ID. |
| 4 | `save_checkpoint` | Save a compact workspace checkpoint for instant session resume. |
| 5 | `brain_stats` | Memory counts, injection latency, and estimated token savings. |

### Engram v10.0 Cognitive Memory (`#30–#32`)
| # | Tool | Description |
|---:|---|---|
| 30 | `brain_hipporag_search` | HippoRAG Personalized PageRank (PPR) multi-hop retrieval (`hops=2`, optional `as_of`). |
| 31 | `brain_temporal_fact` | Store a bi-temporal fact (`valid_from`) with automatic supersession (`SUPERSEDES` edge). |
| 32 | `brain_temporal_query` | Point-in-time `as_of` Time-Travel query and supersession timeline inspection. |

### Multi-Platform Runtime, Routing & Hygiene (`#24–#29`)
| # | Tool | Description |
|---:|---|---|
| 24 | `brain_runtime_info` | Detect/report host IDE, OS, cloud/local LLMs, VRAM & 7-IDE MCP bridge status. |
| 25 | `brain_route_agent_model` | Autonomous Swarm & subagent model router by role, complexity, blast radius, quota & policy. |
| 26 | `brain_distill_rules` | Record a user correction signal and distill recurring corrections into canonical rules. |
| 27 | `brain_ingest_note` | Ingest external note/voice/Telegram message into Vault `.md`, Kanban task & sourced memory. |
| 28 | `brain_export_handoff` | Export portable plain-Markdown `HANDOFF.md` for seamless cross-IDE task resume. |
| 29 | `brain_db_maintenance` | Run SQLite rolling retention pruning, orphan cleanup, and optional `VACUUM` + test-workspace purge. |

### Swarm, AST, Graphify & Archify (`#6–#16`, `#21`)
| # | Tool | Description |
|---:|---|---|
| 6 | `swarm_scout` | Single-pass Scout-01 codebase indexer storing `[SCOUT_SHARED_MAP]` in `brain.db`. |
| 7 | `swarm_start` | Launch an Asymmetric Swarm Run with parallel lanes (`UI`, `API`, `TESTS`, `DOCS`). |
| 8 | `swarm_update_task` | Update live Swarm worker task status on the dashboard. |
| 9 | `swarm_status` | Return active Swarm run state, lane progress, and Scout Shared Map. |
| 10 | `swarm_symbol_lookup` | AST symbol locator returning exact `file:Lstart-Lend` line ranges (Python/JS/TS/HTML). |
| 11 | `swarm_impact_graph` | Reverse call & import dependency graph (blast radius) and recommended tests. |
| 12 | `brain_prune_tools` | Intent-based dynamic tool pruning (selects 3–4 relevant tools for current query). |
| 13 | `swarm_sandbox` | Transactional Copy-on-Write subagent sandboxes with SHA-256, AST & secret gates. |
| 14 | `swarm_watch_audit` | Preemptive AST & blast-radius file-save analyzer. |
| 15 | `swarm_graph_path` | Graphify multi-modal BFS shortest path finder across code, API & DB symbols. |
| 16 | `swarm_architecture_report` | Generate `GRAPH_REPORT.md` with communities, God Nodes & confidence tags. |
| 21 | `swarm_archify_delta` | Zero-token Archify architecture map, git delta, reachability focus & explainer. |

### Orbit, Voice, Pagoda & GBrain (`#17–#20`, `#22–#23`)
| # | Tool | Description |
|---:|---|---|
| 17 | `orbit_mission_control` | Orbit Agent OS Inbox approvals, broadcasts, and handoff chaining. |
| 18 | `orbit_briefing_roi` | Morning brief, engineering savings / ROI calculator & self-learn summary. |
| 19 | `brain_voice_optimize` | STT denoiser, phonetic AST resolver & zero-call pre-executor. |
| 20 | `brain_decompress_fold` | Losslessly decompress a Pagoda LSM Fold `#ID` from `brain.db` zlib archive. |
| 22 | `brain_resolve_skill` | `<1ms` local `SKILL.md` resolver across all installed plugins. |
| 23 | `brain_explain_ranking` | Explainable hybrid search math debugger (`Salience × Recency`, BM25, LSH, PPR, Autocut). |

---

## 2. Key Local REST API Endpoints (`http://127.0.0.1:8765`)

All mutating endpoints (`POST`/`DELETE`) enforce localhost `Origin`/`Referer` validation.

| Group | Method & Path | Purpose |
|---|---|---|
| **Health & Hooks** | `GET /api/health`, `GET /api/db/health` | Service status, DB + WAL MB, table counts, Warm Hook readiness |
| | `POST /api/hook/pre-invoke` | Warm in-process `PreInvocation` hook fast-path (`X-Engram-Hook: 1`) |
| | `POST /api/db/maintenance` | Trigger retention pruning, orphan cleanup, `VACUUM` & optional test purge |
| **Cognitive v10.0** | `GET /api/v10/status` | Bi-temporal counts, HippoRAG graph stats & neural embedding coverage |
| | `GET /api/v10/hipporag?q=...&hops=2&as_of=...` | Multi-hop Personalized PageRank retrieval |
| | `GET /api/v10/temporal?q=...&as_of=...` | Point-in-time Time-Travel query & `SUPERSEDES` lineage |
| | `POST /api/v10/temporal/store` | Store bi-temporal fact with automatic supersession |
| | `POST /api/v10/embeddings/index` | Index active memories into `memory_neural_embeddings` |
| **Tactical & Intake** | `GET /api/tactical/overview` | Single aggregated payload for Tactical 3D Córtex + 6 telemetry widgets |
| | `GET /api/rules/distiller`, `POST /api/rules/distill` | Log correction signals & trigger Nightly Rule Distillation |
| | `GET /api/intake/status`, `POST /api/intake/ingest` | Ingest voice/text notes into Vault `.md`, Kanban tasks & sourced memories |
| | `POST /api/intake/telegram-config` | Configure DPAPI-encrypted Telegram Bot polling bridge |
| | `POST /api/handoff/export` | Generate portable Cross-IDE `HANDOFF.md` & resume prompt |
| **Runtime & Swarm** | `GET /api/runtime`, `GET /api/runtime/route-model` | Active cloud/local LLM runtime profile & Swarm lane routing matrix |
| | `POST /api/runtime/policy`, `POST /api/runtime/connect` | Persist routing policy & connect 7-IDE MCP/hook targets |
| | `GET /api/graph`, `GET /api/swarm`, `GET /api/office`, `GET /api/events` | Knowledge graph, Swarm monitor, Office 3D state & live SSE stream |
| **Code & Vault** | `GET /api/ast/graphify`, `GET /api/ast/path`, `GET /api/archify/*` | Graphify BFS, Archify Git Delta & standalone HTML export |
| | `GET /api/pagoda/*`, `GET /api/skills/resolve`, `GET /api/memories/explain` | Pagoda decompression, local skill resolver & ranking math debugger |
| | `GET /api/orbit/overview`, `POST /api/orbit/action` | Vault 6x dossiers, backlinks, Self-Learn, Prompt Forge & DOTS tasks |

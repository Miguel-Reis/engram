# Changelog

← [Back to README](../README.md)

---

## `v11.0` — Local Neural Cortex
- **4-Layer Local Neural Stack (`neural_cortex_engine.py`)**:
  - **Layer 1**: Multilingual ONNX Bi-Encoder (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, `384-D` via `fastembed`) + native **`sqlite-vec` (`vec0`)** C SIMD vector search with zero-download `256-D`/NumPy fallback.
  - **Layer 2**: Cross-Encoder Neural Reranker (`Xenova/ms-marco-MiniLM-L-6-v2` ONNX + bilinear fallback).
  - **Layer 3**: **Personal Online 2-Layer MLP (`12 → 24 → 12 → 1`, 625 params, Adam in pure NumPy)** trained on local `brain.db` usage + `👍/👎` feedback, gradient feature-importance extraction, and Hebbian synapse weight reinforcement.
  - **Layer 4**: Neural Intent Classifier (6 engineering intents) + Bilingual Semantic Correction Detector integrated into `brain_harvest.py`.
- **5 New REST Endpoints + 3 MCP Tools (`#33–#35`, 35 total) + Inspector Neural Cortex Studio UI** (live SVG loss curve, learned feature weights, 4-layer search & `👍/👎` feedback).
- **Test Coverage**: Expanded to **38/38** automated suites in `test_brain.py`.

## `v10.0` — Next-Gen Cognitive Memory
- **Bi-Temporal Knowledge Graph (`cognitive_v10_engine.py`, `db_engine.py`)**: Added `valid_from` / `valid_to` / `invalidated_by` columns on `memories` and `memory_edges`, automatic `SUPERSEDES` conflict invalidation, `as_of` point-in-time Time-Travel queries, and evolution history lineage.
- **HippoRAG Personalized PageRank (PPR)**: Pure-Python multi-hop graph retrieval over semantic anchors + active edges (`<10ms`) + automatic `🧠[HIPPO_2HOP]` PreInvocation hook augmentation.
- **Local Neural Embeddings**: Auto-detection for local Ollama embedding models and `sqlite_vec`, paired with a zero-dependency **256-D bilingual PT-PT ⇄ EN-EN float32** semantic fallback stored in `memory_neural_embeddings`.
- **5 New REST Endpoints + 3 MCP Tools (`#30–#32`) + Inspector v10 Cognitive Lab UI**: `brain_hipporag_search`, `brain_temporal_fact`, `brain_temporal_query`.
- **Test Coverage**: Expanded to **37/37** automated suites in `test_brain.py`.

## `v9.2` — Turbo & Hygiene
- **Warm Hook HTTP Fast-Path**: Added `POST /api/hook/pre-invoke` on the warm dashboard server and loopback fast-path in `brain_inject.py`.
- **Zero-WMI OS Detection**: Eliminated 70ms Windows WMI overhead in `runtime_detector.py` (`0.0002ms` cached).
- **XHigh Classifier, RED-Quota Router & Workspace Drift Fixes**: Clean `Gemini 4 (XHigh)` classification (`frontier_high`), positive quota-saving degradation under `RED` quota, smart workspace resolution, and `GLOBAL_BRAIN` file-path noise filtering.
- **Database Auto-TTL & `VACUUM`**: Added `get_db_health()`, `run_db_maintenance()`, per-memory 10-revision cap, orphan edge/revision pruning, collision-safe `parent/filename` harvesting, 3600s idle sentinel throttling, MCP tool `#29` (`brain_db_maintenance`), and Inspector DB Hygiene controls.
- **Windows DPAPI Secret Encryption**: Encrypted `telegram_bot_token` at rest via `CryptProtectData`.

## `v9.1` — Amber Tactical 3D Córtex & Complete 7-Repo Second Brain Suite
- **Amber Tactical 3D Dashboard (`✦ Tactical 3D`)**: Default 60 FPS Free-Flight 3D Neural Constellation (`WASD+QE`, infinite pan, fly-through scroll, `dblclick` fly-to-star, spinning gyroscopic core rings, rotating hexagonal domain beacons, ~840 synaptic filaments, animated electric sparks, proximity labels) + collapsible `184px` 3×2 telemetry dock + bottom ticker.
- **Nightly Correction ➔ Rule Distiller (`rule_distiller_engine.py`)**: Automatic capture & deduplication of recurring corrections promoted into canonical rules (`brain_distill_rules`).
- **Voice/Telegram Intake & Cross-IDE `HANDOFF.md` (`intake_handoff_engine.py`)**: Voice-denoised intake routed to Markdown Vault / Kanban tasks + portable cross-IDE state exporter (`brain_ingest_note`, `brain_export_handoff`).
- **Full Multi-Viewport Visual Audit**: Verified zero console errors, zero overflow/clipping across all 7 studios & 5 modals at `1800×920` and `1366×768`.

## `v9.0` — Rebrand to Engram
- Renamed project, plugin, MCP server, and repository from `antigravity-brain` to **Engram — Universal AI Memory & Swarm OS** with 100% database preservation.

## `v8.4` – `v8.5` — Multi-Platform Runtime & Autonomous Swarm Model Router
- Cloud + Local LLM VRAM probing (`Ollama`, `LM Studio`, `vLLM`, `llama.cpp`, `Jan`), 7-IDE cross-OS bridge (`Windows`/`macOS`/`Linux`), adaptive model-tier context budgets, and autonomous role/quota-aware Swarm Model Routing (`brain_runtime_info`, `brain_route_agent_model`).

## `v8.1` – `v8.3` — Voice Zero-Call, Pagoda LSM, Archify & GBrain Pack
- **v8.3**: GBrain orthogonal `Salience × Recency` axes, `brain_explain_ranking`, `<1ms` Local Skill Resolver (`brain_resolve_skill`), and Compiled Vault Dossiers with bidirectional backlinks.
- **v8.2**: Pagoda LSM lossless multi-tier zlib folding (`brain_decompress_fold`), KV-cache prefix stability, and Archify zero-token Git Architecture Delta + standalone HTML export (`swarm_archify_delta`).
- **v8.1**: Voice-Aware Zero-Call Protocol (`voice_brain_engine.py`, `brain_voice_optimize`) and `<50ms` Windows hot-reload process cleanup.

## `v2.0` – `v7.1` — Foundation through Carbon Studio OS
- Zero-Round-Trip SQLite FTS5 BM25 + 128-D LSH hooks, Scout-First Asymmetric Swarm, Graphify multi-modal AST BFS, Office 3D Holographic Heatmap Towers, Orbit Agent OS, DOTS DAG Kanban, Self-Learn Studio, Prompt Forge, Vault 6x, and bilingual PT-PT ⇄ EN-EN UI.

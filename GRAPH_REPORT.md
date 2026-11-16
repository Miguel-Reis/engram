# 🕸️ GRAPH_REPORT.md — Antigravity Brain Multi-Modal Knowledge Graph

> **Gerado automaticamente por `graphify_engine.py`** (Zero-LLM Deterministic AST + SQL + HTTP + MCP Graph)

## 1. Telemetria Executiva & Eficiência de Tokens
- **Total de Nós Multi-Modais**: `653` (`FILE`: 19, `CLASS`: 11, `FUNCTION`: 243, `JS_FUNCTION`: 279, `API_ROUTE`: 50, `MCP_TOOL`: 23, `SQL_TABLE`: 27)
- **Total de Arestas Tipadas**: `2225`
  - 🟢 **EXTRACTED (1.00)**: `1446` arestas (AST / DDL / Rota literal 100% determinística)
  - 🔵 **INFERRED (0.85)**: `703` arestas (Resolução cruzada de métodos e handlers)
  - 🟡 **AMBIGUOUS (0.55)**: `76` arestas (Despacho polimórfico / múltiplos candidatos)
- **Compressão de Contexto (Graphify Token Diet)**: `473,572` tokens brutos ➔ `360` tokens de índice (**`1315.5x` menos tokens**)

## 2. Top God Nodes (Centros de Gravidade Arquitetónica)
| # | Entidade | Tipo | Ficheiro | Grau (In/Out) | Alcance Ficheiros | Score Centralidade | Comunidade |
|---|---|---|---|---|---|---|---|
| 1 | **`BrainDB`** | `CLASS` | `db_engine.py:L91` | 94 (50↙ / 44↗) | 13 files | **258.17** | Core Memory & SQLite FTS5 Engine |
| 2 | **`BrainDB._connect`** | `FUNCTION` | `db_engine.py:L162` | 99 (99↙ / 0↗) | 10 files | **230.94** | Core Memory & SQLite FTS5 Engine |
| 3 | **`SwarmEngine`** | `CLASS` | `swarm_engine.py:L54` | 79 (41↙ / 38↗) | 9 files | **210.56** | Asymmetric Swarm & CoW Sandbox |
| 4 | **`run_all_tests`** | `FUNCTION` | `test_brain.py:L10` | 108 (1↙ / 107↗) | 15 files | **200.65** | HTTP Gateway, MCP Server & Token Diet |
| 5 | **`test_suite:run_all_tests`** | `TEST_CASE` | `test_brain.py:L10` | 108 (1↙ / 107↗) | 15 files | **200.65** | HTTP Gateway, MCP Server & Token Diet |
| 6 | **`BrainDashboardHandler.do_POST`** | `FUNCTION` | `web_dashboard.py:L1251` | 99 (25↙ / 74↗) | 11 files | **192.87** | HTTP Gateway, MCP Server & Token Diet |
| 7 | **`/api/orbit/action`** | `API_ROUTE` | `web_dashboard.py:L14578` | 59 (29↙ / 30↗) | 3 files | **168.08** | HTTP Gateway, MCP Server & Token Diet |
| 8 | **`BrainDashboardHandler.do_GET`** | `FUNCTION` | `web_dashboard.py:L818` | 71 (27↙ / 44↗) | 13 files | **157.48** | HTTP Gateway, MCP Server & Token Diet |
| 9 | **`OrbitEngine`** | `CLASS` | `orbit_engine.py:L17` | 55 (11↙ / 44↗) | 6 files | **137.52** | HTTP Gateway, MCP Server & Token Diet |
| 10 | **`memories`** | `SQL_TABLE` | `db_engine.py:L215` | 34 (34↙ / 0↗) | 7 files | **118.49** | Core Memory & SQLite FTS5 Engine |

## 3. Comunidades Topológicas Detetadas
- **Core Memory & SQLite FTS5 Engine** (`85` nós) — Exemplos: `memories`, `memory_edges`, `brain_branches`, `memory_revisions`, `memories_fts`, `checkpoints`
- **Asymmetric Swarm & CoW Sandbox** (`48` nós) — Exemplos: `swarm_runs`, `swarm_tasks`, `swarm_logs`, `swarm_sandboxes`, `swarm_scout`, `swarm_start`
- **AST Inspector, Graphify & Save Watcher** (`47` nós) — Exemplos: `ast_save_audits`, `ast_file_hashes`, `ast_symbol_snapshots`, `ast_impact_alerts`, `orbit_broadcasts`, `_extract_ast_summary_from_code`
- **HTTP Gateway, MCP Server & Token Diet** (`180` nós) — Exemplos: `classify_semantic_type`, `_get_shared_graphify`, `ArchifyEngine`, `ArchifyEngine.__init__`, `ArchifyEngine._run_git`, `ArchifyEngine._get_git_provenance`
- **Obsidian 2D Graph & 3D Agent Office UI** (`293` nós) — Exemplos: `office_agents`, `SwarmEngine._ensure_core_office_agents`, `SwarmEngine._sync_live_conversations_to_office`, `SwarmEngine.get_office_state`, `SwarmEngine.assign_office_agent_directive`, `SwarmEngine.spawn_custom_office_agent`

## 4. Cadeias Causais Full-Stack Verificadas (BFS Shortest Paths)
- **triggerAstSaveAuditUI ➔ ast_save_audits** (3 saltos, poupança `2573.8x`):  
  `triggerAstSaveAuditUI` (JS_FUNCTION) ➔ `/api/ast/watch` (API_ROUTE) ➔ `AstImpactWatcher.get_watcher_status` (FUNCTION) ➔ `ast_save_audits` (SQL_TABLE)
- **swarm_watch_audit ➔ BrainDB** (2 saltos, poupança `3587.7x`):  
  `swarm_watch_audit` (MCP_TOOL) ➔ `server.py` (FILE) ➔ `BrainDB` (CLASS)
- **createAndVerifySandboxUI ➔ swarm_sandboxes** (3 saltos, poupança `2573.8x`):  
  `createAndVerifySandboxUI` (JS_FUNCTION) ➔ `/api/swarm/sandbox` (API_ROUTE) ➔ `SwarmEngine.manage_subagent_sandbox` (FUNCTION) ➔ `swarm_sandboxes` (SQL_TABLE)

# 🕸️ GRAPH_REPORT.md — Engram Multi-Modal Knowledge Graph

> **Gerado automaticamente por `graphify_engine.py`** (Zero-LLM Deterministic AST + SQL + HTTP + MCP Graph)

## 1. Telemetria Executiva & Eficiência de Tokens
- **Total de Nós Multi-Modais**: `808` (`FILE`: 22, `CLASS`: 12, `FUNCTION`: 323, `JS_FUNCTION`: 325, `API_ROUTE`: 64, `MCP_TOOL`: 29, `SQL_TABLE`: 32)
- **Total de Arestas Tipadas**: `2850`
  - 🟢 **EXTRACTED (1.00)**: `2006` arestas (AST / DDL / Rota literal 100% determinística)
  - 🔵 **INFERRED (0.85)**: `764` arestas (Resolução cruzada de métodos e handlers)
  - 🟡 **AMBIGUOUS (0.55)**: `80` arestas (Despacho polimórfico / múltiplos candidatos)
- **Compressão de Contexto (Graphify Token Diet)**: `573,270` tokens brutos ➔ `360` tokens de índice (**`1592.4x` menos tokens**)

## 2. Top God Nodes (Centros de Gravidade Arquitetónica)
| # | Entidade | Tipo | Ficheiro | Grau (In/Out) | Alcance Ficheiros | Score Centralidade | Comunidade |
|---|---|---|---|---|---|---|---|
| 1 | **`BrainDB`** | `CLASS` | `db_engine.py:L92` | 105 (57↙ / 48↗) | 13 files | **276.97** | Core Memory & SQLite FTS5 Engine |
| 2 | **`BrainDB._connect`** | `FUNCTION` | `db_engine.py:L166` | 120 (120↙ / 0↗) | 14 files | **274.41** | Core Memory & SQLite FTS5 Engine |
| 3 | **`run_all_tests`** | `FUNCTION` | `test_brain.py:L10` | 133 (1↙ / 132↗) | 19 files | **248.17** | HTTP Gateway, MCP Server & Token Diet |
| 4 | **`test_suite:run_all_tests`** | `TEST_CASE` | `test_brain.py:L10` | 133 (1↙ / 132↗) | 19 files | **248.17** | HTTP Gateway, MCP Server & Token Diet |
| 5 | **`BrainDashboardHandler.do_POST`** | `FUNCTION` | `web_dashboard.py:L2044` | 124 (33↙ / 91↗) | 15 files | **241.24** | HTTP Gateway, MCP Server & Token Diet |
| 6 | **`SwarmEngine`** | `CLASS` | `swarm_engine.py:L54` | 79 (41↙ / 38↗) | 9 files | **206.02** | Asymmetric Swarm & CoW Sandbox |
| 7 | **`BrainDashboardHandler.do_GET`** | `FUNCTION` | `web_dashboard.py:L1514` | 88 (33↙ / 55↗) | 14 files | **183.75** | HTTP Gateway, MCP Server & Token Diet |
| 8 | **`OrbitEngine`** | `CLASS` | `orbit_engine.py:L17` | 67 (21↙ / 46↗) | 10 files | **180.26** | HTTP Gateway, MCP Server & Token Diet |
| 9 | **`/api/orbit/action`** | `API_ROUTE` | `web_dashboard.py:L16205` | 59 (29↙ / 30↗) | 3 files | **159.94** | HTTP Gateway, MCP Server & Token Diet |
| 10 | **`memories`** | `SQL_TABLE` | `db_engine.py:L219` | 39 (39↙ / 0↗) | 9 files | **133.77** | Core Memory & SQLite FTS5 Engine |

## 3. Comunidades Topológicas Detetadas
- **Core Memory & SQLite FTS5 Engine** (`102` nós) — Exemplos: `memories`, `memory_edges`, `brain_branches`, `memory_revisions`, `memories_fts`, `checkpoints`
- **Asymmetric Swarm & CoW Sandbox** (`49` nós) — Exemplos: `swarm_runs`, `swarm_tasks`, `swarm_logs`, `swarm_sandboxes`, `plan_swarm_model_matrix`, `swarm_scout`
- **AST Inspector, Graphify & Save Watcher** (`47` nós) — Exemplos: `ast_save_audits`, `ast_file_hashes`, `ast_symbol_snapshots`, `ast_impact_alerts`, `orbit_broadcasts`, `_extract_ast_summary_from_code`
- **HTTP Gateway, MCP Server & Token Diet** (`271` nós) — Exemplos: `classify_semantic_type`, `_get_shared_graphify`, `ArchifyEngine`, `ArchifyEngine.__init__`, `ArchifyEngine._run_git`, `ArchifyEngine._get_git_provenance`
- **Obsidian 2D Graph & 3D Agent Office UI** (`339` nós) — Exemplos: `office_agents`, `SwarmEngine._ensure_core_office_agents`, `SwarmEngine._sync_live_conversations_to_office`, `SwarmEngine.get_office_state`, `SwarmEngine.assign_office_agent_directive`, `SwarmEngine.spawn_custom_office_agent`

## 4. Cadeias Causais Full-Stack Verificadas (BFS Shortest Paths)
- **triggerAstSaveAuditUI ➔ ast_save_audits** (3 saltos, poupança `3115.6x`):  
  `triggerAstSaveAuditUI` (JS_FUNCTION) ➔ `/api/ast/watch` (API_ROUTE) ➔ `AstImpactWatcher.get_watcher_status` (FUNCTION) ➔ `ast_save_audits` (SQL_TABLE)
- **swarm_watch_audit ➔ BrainDB** (2 saltos, poupança `4343.0x`):  
  `swarm_watch_audit` (MCP_TOOL) ➔ `server.py` (FILE) ➔ `BrainDB` (CLASS)
- **createAndVerifySandboxUI ➔ swarm_sandboxes** (3 saltos, poupança `3115.6x`):  
  `createAndVerifySandboxUI` (JS_FUNCTION) ➔ `/api/swarm/sandbox` (API_ROUTE) ➔ `SwarmEngine.manage_subagent_sandbox` (FUNCTION) ➔ `swarm_sandboxes` (SQL_TABLE)

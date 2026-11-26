# 🕸️ GRAPH_REPORT.md — Engram Multi-Modal Knowledge Graph

> **Gerado automaticamente por `graphify_engine.py`** (Zero-LLM Deterministic AST + SQL + HTTP + MCP Graph)

## 1. Telemetria Executiva & Eficiência de Tokens
- **Total de Nós Multi-Modais**: `928` (`FILE`: 24, `CLASS`: 13, `FUNCTION`: 392, `JS_FUNCTION`: 352, `API_ROUTE`: 74, `MCP_TOOL`: 35, `SQL_TABLE`: 37)
- **Total de Arestas Tipadas**: `3349`
  - 🟢 **EXTRACTED (1.00)**: `2454` arestas (AST / DDL / Rota literal 100% determinística)
  - 🔵 **INFERRED (0.85)**: `815` arestas (Resolução cruzada de métodos e handlers)
  - 🟡 **AMBIGUOUS (0.55)**: `80` arestas (Despacho polimórfico / múltiplos candidatos)
- **Compressão de Contexto (Graphify Token Diet)**: `644,709` tokens brutos ➔ `360` tokens de índice (**`1790.9x` menos tokens**)

## 2. Top God Nodes (Centros de Gravidade Arquitetónica)
| # | Entidade | Tipo | Ficheiro | Grau (In/Out) | Alcance Ficheiros | Score Centralidade | Comunidade |
|---|---|---|---|---|---|---|---|
| 1 | **`BrainDB._connect`** | `FUNCTION` | `db_engine.py:L166` | 139 (139↙ / 0↗) | 16 files | **304.17** | Core Memory & SQLite FTS5 Engine |
| 2 | **`BrainDB`** | `CLASS` | `db_engine.py:L92` | 110 (62↙ / 48↗) | 13 files | **286.03** | Core Memory & SQLite FTS5 Engine |
| 3 | **`run_all_tests`** | `FUNCTION` | `test_brain.py:L10` | 148 (1↙ / 147↗) | 21 files | **275.41** | HTTP Gateway, MCP Server & Token Diet |
| 4 | **`test_suite:run_all_tests`** | `TEST_CASE` | `test_brain.py:L10` | 148 (1↙ / 147↗) | 21 files | **275.41** | HTTP Gateway, MCP Server & Token Diet |
| 5 | **`BrainDashboardHandler.do_POST`** | `FUNCTION` | `web_dashboard.py:L2178` | 138 (38↙ / 100↗) | 17 files | **266.89** | HTTP Gateway, MCP Server & Token Diet |
| 6 | **`BrainDashboardHandler.do_GET`** | `FUNCTION` | `web_dashboard.py:L1543` | 99 (38↙ / 61↗) | 16 files | **205.37** | HTTP Gateway, MCP Server & Token Diet |
| 7 | **`SwarmEngine`** | `CLASS` | `swarm_engine.py:L54` | 79 (41↙ / 38↗) | 9 files | **203.62** | Asymmetric Swarm & CoW Sandbox |
| 8 | **`OrbitEngine`** | `CLASS` | `orbit_engine.py:L17` | 67 (21↙ / 46↗) | 10 files | **178.83** | HTTP Gateway, MCP Server & Token Diet |
| 9 | **`memories`** | `SQL_TABLE` | `db_engine.py:L219` | 53 (53↙ / 0↗) | 11 files | **170.01** | Core Memory & SQLite FTS5 Engine |
| 10 | **`/api/orbit/action`** | `API_ROUTE` | `web_dashboard.py:L17442` | 59 (29↙ / 30↗) | 3 files | **155.19** | HTTP Gateway, MCP Server & Token Diet |

## 3. Comunidades Topológicas Detetadas
- **Core Memory & SQLite FTS5 Engine** (`107` nós) — Exemplos: `memory_neural_embeddings`, `memories`, `memory_edges`, `brain_branches`, `memory_revisions`, `memories_fts`
- **Asymmetric Swarm & CoW Sandbox** (`49` nós) — Exemplos: `swarm_runs`, `swarm_tasks`, `swarm_logs`, `swarm_sandboxes`, `plan_swarm_model_matrix`, `swarm_scout`
- **AST Inspector, Graphify & Save Watcher** (`50` nós) — Exemplos: `ast_save_audits`, `ast_file_hashes`, `ast_symbol_snapshots`, `ast_impact_alerts`, `orbit_broadcasts`, `_extract_ast_summary_from_code`
- **HTTP Gateway, MCP Server & Token Diet** (`356` nós) — Exemplos: `classify_semantic_type`, `_get_shared_graphify`, `ArchifyEngine`, `ArchifyEngine.__init__`, `ArchifyEngine._run_git`, `ArchifyEngine._get_git_provenance`
- **Obsidian 2D Graph & 3D Agent Office UI** (`366` nós) — Exemplos: `office_agents`, `SwarmEngine._ensure_core_office_agents`, `SwarmEngine._sync_live_conversations_to_office`, `SwarmEngine.get_office_state`, `SwarmEngine.assign_office_agent_directive`, `SwarmEngine.spawn_custom_office_agent`

## 4. Cadeias Causais Full-Stack Verificadas (BFS Shortest Paths)
- **triggerAstSaveAuditUI ➔ ast_save_audits** (3 saltos, poupança `3503.9x`):  
  `triggerAstSaveAuditUI` (JS_FUNCTION) ➔ `/api/ast/watch` (API_ROUTE) ➔ `AstImpactWatcher.get_watcher_status` (FUNCTION) ➔ `ast_save_audits` (SQL_TABLE)
- **swarm_watch_audit ➔ BrainDB** (2 saltos, poupança `4884.2x`):  
  `swarm_watch_audit` (MCP_TOOL) ➔ `server.py` (FILE) ➔ `BrainDB` (CLASS)
- **createAndVerifySandboxUI ➔ swarm_sandboxes** (3 saltos, poupança `3503.9x`):  
  `createAndVerifySandboxUI` (JS_FUNCTION) ➔ `/api/swarm/sandbox` (API_ROUTE) ➔ `SwarmEngine.manage_subagent_sandbox` (FUNCTION) ➔ `swarm_sandboxes` (SQL_TABLE)

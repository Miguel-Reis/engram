# 🕸️ GRAPH_REPORT.md — Antigravity Brain Multi-Modal Knowledge Graph

> **Gerado automaticamente por `graphify_engine.py`** (Zero-LLM Deterministic AST + SQL + HTTP + MCP Graph)

## 1. Telemetria Executiva & Eficiência de Tokens
- **Total de Nós Multi-Modais**: `684` (`FILE`: 20, `CLASS`: 11, `FUNCTION`: 264, `JS_FUNCTION`: 284, `API_ROUTE`: 52, `MCP_TOOL`: 24, `SQL_TABLE`: 28)
- **Total de Arestas Tipadas**: `2367`
  - 🟢 **EXTRACTED (1.00)**: `1576` arestas (AST / DDL / Rota literal 100% determinística)
  - 🔵 **INFERRED (0.85)**: `715` arestas (Resolução cruzada de métodos e handlers)
  - 🟡 **AMBIGUOUS (0.55)**: `76` arestas (Despacho polimórfico / múltiplos candidatos)
- **Compressão de Contexto (Graphify Token Diet)**: `499,299` tokens brutos ➔ `360` tokens de índice (**`1386.9x` menos tokens**)

## 2. Top God Nodes (Centros de Gravidade Arquitetónica)
| # | Entidade | Tipo | Ficheiro | Grau (In/Out) | Alcance Ficheiros | Score Centralidade | Comunidade |
|---|---|---|---|---|---|---|---|
| 1 | **`BrainDB`** | `CLASS` | `db_engine.py:L91` | 95 (51↙ / 44↗) | 13 files | **258.49** | Core Memory & SQLite FTS5 Engine |
| 2 | **`BrainDB._connect`** | `FUNCTION` | `db_engine.py:L162` | 102 (102↙ / 0↗) | 11 files | **238.09** | Core Memory & SQLite FTS5 Engine |
| 3 | **`run_all_tests`** | `FUNCTION` | `test_brain.py:L10` | 113 (1↙ / 112↗) | 16 files | **210.79** | HTTP Gateway, MCP Server & Token Diet |
| 4 | **`test_suite:run_all_tests`** | `TEST_CASE` | `test_brain.py:L10` | 113 (1↙ / 112↗) | 16 files | **210.79** | HTTP Gateway, MCP Server & Token Diet |
| 5 | **`SwarmEngine`** | `CLASS` | `swarm_engine.py:L54` | 79 (41↙ / 38↗) | 9 files | **209.33** | Asymmetric Swarm & CoW Sandbox |
| 6 | **`BrainDashboardHandler.do_POST`** | `FUNCTION` | `web_dashboard.py:L1281` | 104 (26↙ / 78↗) | 12 files | **202.55** | HTTP Gateway, MCP Server & Token Diet |
| 7 | **`BrainDashboardHandler.do_GET`** | `FUNCTION` | `web_dashboard.py:L818` | 76 (28↙ / 48↗) | 14 files | **167.13** | HTTP Gateway, MCP Server & Token Diet |
| 8 | **`/api/orbit/action`** | `API_ROUTE` | `web_dashboard.py:L14908` | 59 (29↙ / 30↗) | 3 files | **166.19** | HTTP Gateway, MCP Server & Token Diet |
| 9 | **`OrbitEngine`** | `CLASS` | `orbit_engine.py:L17` | 58 (13↙ / 45↗) | 7 files | **149.25** | HTTP Gateway, MCP Server & Token Diet |
| 10 | **`memories`** | `SQL_TABLE` | `db_engine.py:L215` | 34 (34↙ / 0↗) | 7 files | **117.28** | Core Memory & SQLite FTS5 Engine |

## 3. Comunidades Topológicas Detetadas
- **Core Memory & SQLite FTS5 Engine** (`87` nós) — Exemplos: `memories`, `memory_edges`, `brain_branches`, `memory_revisions`, `memories_fts`, `checkpoints`
- **Asymmetric Swarm & CoW Sandbox** (`48` nós) — Exemplos: `swarm_runs`, `swarm_tasks`, `swarm_logs`, `swarm_sandboxes`, `swarm_scout`, `swarm_start`
- **AST Inspector, Graphify & Save Watcher** (`47` nós) — Exemplos: `ast_save_audits`, `ast_file_hashes`, `ast_symbol_snapshots`, `ast_impact_alerts`, `orbit_broadcasts`, `_extract_ast_summary_from_code`
- **HTTP Gateway, MCP Server & Token Diet** (`204` nós) — Exemplos: `classify_semantic_type`, `_get_shared_graphify`, `ArchifyEngine`, `ArchifyEngine.__init__`, `ArchifyEngine._run_git`, `ArchifyEngine._get_git_provenance`
- **Obsidian 2D Graph & 3D Agent Office UI** (`298` nós) — Exemplos: `office_agents`, `SwarmEngine._ensure_core_office_agents`, `SwarmEngine._sync_live_conversations_to_office`, `SwarmEngine.get_office_state`, `SwarmEngine.assign_office_agent_directive`, `SwarmEngine.spawn_custom_office_agent`

## 4. Cadeias Causais Full-Stack Verificadas (BFS Shortest Paths)
- **triggerAstSaveAuditUI ➔ ast_save_audits** (3 saltos, poupança `2713.6x`):  
  `triggerAstSaveAuditUI` (JS_FUNCTION) ➔ `/api/ast/watch` (API_ROUTE) ➔ `AstImpactWatcher.get_watcher_status` (FUNCTION) ➔ `ast_save_audits` (SQL_TABLE)
- **swarm_watch_audit ➔ BrainDB** (2 saltos, poupança `3782.6x`):  
  `swarm_watch_audit` (MCP_TOOL) ➔ `server.py` (FILE) ➔ `BrainDB` (CLASS)
- **createAndVerifySandboxUI ➔ swarm_sandboxes** (3 saltos, poupança `2713.6x`):  
  `createAndVerifySandboxUI` (JS_FUNCTION) ➔ `/api/swarm/sandbox` (API_ROUTE) ➔ `SwarmEngine.manage_subagent_sandbox` (FUNCTION) ➔ `swarm_sandboxes` (SQL_TABLE)

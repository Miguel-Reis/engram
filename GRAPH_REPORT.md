# 🕸️ GRAPH_REPORT.md — Antigravity Brain Multi-Modal Knowledge Graph

> **Gerado automaticamente por `graphify_engine.py`** (Zero-LLM Deterministic AST + SQL + HTTP + MCP Graph)

## 1. Telemetria Executiva & Eficiência de Tokens
- **Total de Nós Multi-Modais**: `628` (`FILE`: 18, `CLASS`: 10, `FUNCTION`: 228, `JS_FUNCTION`: 276, `API_ROUTE`: 48, `MCP_TOOL`: 21, `SQL_TABLE`: 26)
- **Total de Arestas Tipadas**: `2106`
  - 🟢 **EXTRACTED (1.00)**: `1388` arestas (AST / DDL / Rota literal 100% determinística)
  - 🔵 **INFERRED (0.85)**: `648` arestas (Resolução cruzada de métodos e handlers)
  - 🟡 **AMBIGUOUS (0.55)**: `70` arestas (Despacho polimórfico / múltiplos candidatos)
- **Compressão de Contexto (Graphify Token Diet)**: `447,853` tokens brutos ➔ `360` tokens de índice (**`1244.0x` menos tokens**)

## 2. Top God Nodes (Centros de Gravidade Arquitetónica)
| # | Entidade | Tipo | Ficheiro | Grau (In/Out) | Alcance Ficheiros | Score Centralidade | Comunidade |
|---|---|---|---|---|---|---|---|
| 1 | **`BrainDB`** | `CLASS` | `db_engine.py:L91` | 88 (48↙ / 40↗) | 13 files | **247.34** | Core Memory & SQLite FTS5 Engine |
| 2 | **`BrainDB._connect`** | `FUNCTION` | `db_engine.py:L162` | 95 (95↙ / 0↗) | 9 files | **223.04** | Core Memory & SQLite FTS5 Engine |
| 3 | **`SwarmEngine`** | `CLASS` | `swarm_engine.py:L54` | 79 (41↙ / 38↗) | 9 files | **211.71** | Asymmetric Swarm & CoW Sandbox |
| 4 | **`BrainDashboardHandler.do_POST`** | `FUNCTION` | `web_dashboard.py:L1148` | 97 (25↙ / 72↗) | 11 files | **190.95** | HTTP Gateway, MCP Server & Token Diet |
| 5 | **`run_all_tests`** | `FUNCTION` | `test_brain.py:L10` | 101 (1↙ / 100↗) | 14 files | **187.72** | HTTP Gateway, MCP Server & Token Diet |
| 6 | **`test_suite:run_all_tests`** | `TEST_CASE` | `test_brain.py:L10` | 101 (1↙ / 100↗) | 14 files | **187.72** | HTTP Gateway, MCP Server & Token Diet |
| 7 | **`/api/orbit/action`** | `API_ROUTE` | `web_dashboard.py:L14189` | 56 (28↙ / 28↗) | 3 files | **162.65** | HTTP Gateway, MCP Server & Token Diet |
| 8 | **`BrainDashboardHandler.do_GET`** | `FUNCTION` | `web_dashboard.py:L767` | 65 (25↙ / 40↗) | 12 files | **146.05** | HTTP Gateway, MCP Server & Token Diet |
| 9 | **`OrbitEngine`** | `CLASS` | `orbit_engine.py:L17` | 53 (11↙ / 42↗) | 6 files | **134.22** | HTTP Gateway, MCP Server & Token Diet |
| 10 | **`memories`** | `SQL_TABLE` | `db_engine.py:L215` | 32 (32↙ / 0↗) | 7 files | **115.07** | Core Memory & SQLite FTS5 Engine |

## 3. Comunidades Topológicas Detetadas
- **Core Memory & SQLite FTS5 Engine** (`80` nós) — Exemplos: `memories`, `memory_edges`, `brain_branches`, `memory_revisions`, `memories_fts`, `checkpoints`
- **Asymmetric Swarm & CoW Sandbox** (`48` nós) — Exemplos: `swarm_runs`, `swarm_tasks`, `swarm_logs`, `swarm_sandboxes`, `swarm_scout`, `swarm_start`
- **AST Inspector, Graphify & Save Watcher** (`47` nós) — Exemplos: `ast_save_audits`, `ast_file_hashes`, `ast_symbol_snapshots`, `ast_impact_alerts`, `orbit_broadcasts`, `_extract_ast_summary_from_code`
- **HTTP Gateway, MCP Server & Token Diet** (`163` nós) — Exemplos: `classify_semantic_type`, `ArchifyEngine`, `ArchifyEngine.__init__`, `ArchifyEngine._run_git`, `ArchifyEngine._get_git_provenance`, `ArchifyEngine.build_archify_spec`
- **Obsidian 2D Graph & 3D Agent Office UI** (`290` nós) — Exemplos: `office_agents`, `SwarmEngine._ensure_core_office_agents`, `SwarmEngine._sync_live_conversations_to_office`, `SwarmEngine.get_office_state`, `SwarmEngine.assign_office_agent_directive`, `SwarmEngine.spawn_custom_office_agent`

## 4. Cadeias Causais Full-Stack Verificadas (BFS Shortest Paths)
- **triggerAstSaveAuditUI ➔ ast_save_audits** (3 saltos, poupança `2434.0x`):  
  `triggerAstSaveAuditUI` (JS_FUNCTION) ➔ `/api/ast/watch` (API_ROUTE) ➔ `AstImpactWatcher.get_watcher_status` (FUNCTION) ➔ `ast_save_audits` (SQL_TABLE)
- **swarm_watch_audit ➔ BrainDB** (2 saltos, poupança `3392.8x`):  
  `swarm_watch_audit` (MCP_TOOL) ➔ `server.py` (FILE) ➔ `BrainDB` (CLASS)
- **createAndVerifySandboxUI ➔ swarm_sandboxes** (3 saltos, poupança `2434.0x`):  
  `createAndVerifySandboxUI` (JS_FUNCTION) ➔ `/api/swarm/sandbox` (API_ROUTE) ➔ `SwarmEngine.manage_subagent_sandbox` (FUNCTION) ➔ `swarm_sandboxes` (SQL_TABLE)

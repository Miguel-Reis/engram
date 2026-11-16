"""
archify_engine.py — Archify Zero-Token Deterministic Architecture Map, Git Delta, Reachability & Explainer
Inspired by tt-a1i/archify (Apache-2.0, DESIGN.md 'The Evidence Console' + architecture-delta.mjs + explainer/).
100% pure-Python, zero-dependency, zero-LLM-token engine backed by GraphifyEngine + ast + git.
"""

from __future__ import annotations

import ast
import html
import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 7 Semantic Signals (Archify Semantic Palette)
SEMANTIC_PALETTE: Dict[str, Dict[str, str]] = {
    "frontend": {"color": "#22D3EE", "label": "Frontend / Studio UI"},
    "backend": {"color": "#34D399", "label": "Core Engine / Backend"},
    "database": {"color": "#A78BFA", "label": "Persistence / SQLite & Pagoda"},
    "security": {"color": "#FB7185", "label": "Security / AST Gate & Sandbox"},
    "messagebus": {"color": "#FB923C", "label": "Hooks & MCP Protocol Bus"},
    "cloud": {"color": "#FBBF24", "label": "Git Sync / Updater & Diet"},
    "external": {"color": "#94A3B8", "label": "External / Transcripts"},
}


def classify_semantic_type(identifier: str, node_type: str = "") -> str:
    """Classifica deterministicamente um identificador, ficheiro ou símbolo num dos 7 sinais semânticos."""
    s = identifier.lower().replace("\\", "/")
    nt = (node_type or "").upper()

    if nt in ("SQL_TABLE", "SQLITE_TABLE", "DB"):
        return "database"
    if nt in ("API_ROUTE", "HTTP_ROUTE", "MCP_TOOL"):
        return "messagebus"
    if nt in ("JS_FUNCTION", "CSS", "HTML"):
        return "frontend"

    base = os.path.basename(s)
    if base.startswith("file:"):
        base = base[5:]
    if base.startswith("sql:"):
        return "database"
    if base.startswith("api:"):
        return "messagebus"
    if base.startswith("js:"):
        return "frontend"

    if base in ("index.html", "app.js") or base.endswith((".html", ".css", ".js", ".jsx", ".tsx")):
        return "frontend"
    if any(k in base for k in ("db_engine", "pagoda", "database", "sqlite")) or base.endswith((".db", ".sqlite")):
        return "database"
    if any(k in base for k in ("ast_impact", "security", "sandbox", "audit")):
        return "security"
    if any(k in base for k in ("brain_inject", "brain_harvest", "server.py", "mcp")):
        return "messagebus"
    if any(k in base for k in ("auto_updater", "install", "token_diet", "diet", "updater")) or base.endswith((".bat", ".sh")):
        return "cloud"
    if any(k in base for k in ("transcript", "logs", "external")):
        return "external"
    if base.endswith(".py"):
        return "backend"

    return "backend"


def _extract_ast_summary_from_code(code: str, fname: str) -> Dict[str, Any]:
    """Extrai símbolos principais, linhas e imports de código fonte em memória via AST standard."""
    lines = code.splitlines()
    line_count = len(lines)
    symbols: List[str] = []
    imports: List[str] = []

    if fname.endswith(".py"):
        try:
            tree = ast.parse(code, filename=fname)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    symbols.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module.split(".")[0])
        except Exception:
            pass

    return {
        "lines": line_count,
        "symbols": sorted(list(set(symbols))),
        "imports": sorted(list(set(imports))),
    }


_SHARED_GRAPHIFY_INSTANCES: Dict[str, Any] = {}
_GIT_SHA_INVENTORY_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _get_shared_graphify(ws: str) -> Any:
    from graphify_engine import GraphifyEngine

    norm_ws = os.path.abspath(ws)
    inst = _SHARED_GRAPHIFY_INSTANCES.get(norm_ws)
    if inst is None:
        inst = GraphifyEngine(norm_ws)
        _SHARED_GRAPHIFY_INSTANCES[norm_ws] = inst
    return inst


class ArchifyEngine:
    """
    Motor determinístico Archify de Mapeamento Arquitetural, Delta Git, Foco de Alcance & Explainers.
    Zero dependências externas, zero consumo de tokens LLM.
    """

    def __init__(self, workspace_path: str = "") -> None:
        self.workspace_path = os.path.abspath(workspace_path or CURRENT_DIR)
        self.creationflags = 0x08000000 if os.name == "nt" else 0

    def _run_git(self, args: List[str], cwd: Optional[str] = None) -> Tuple[int, str]:
        target_dir = cwd or self.workspace_path
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=target_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=15,
                creationflags=self.creationflags,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            return proc.returncode, out.strip()
        except Exception as e:
            return 1, str(e)

    def _get_git_provenance(self) -> Dict[str, Any]:
        """Recupera proveniência git (SHA40, short SHA, branch, URL sanitizado sem credenciais)."""
        rc_sha, sha40 = self._run_git(["rev-parse", "HEAD"])
        rc_branch, branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        rc_url, remote_url = self._run_git(["remote", "get-url", "origin"])

        if rc_url != 0 or not remote_url:
            rc_url, remote_url = self._run_git(["config", "--get", "remote.origin.url"])

        clean_url = ""
        if remote_url and "unknown" not in remote_url.lower():
            # Strips any HTTP userinfo/credentials per Archify security guideline
            clean_url = re.sub(r"(https?://)[^/@]+@", r"\1", remote_url)

        sha = sha40.strip() if rc_sha == 0 and len(sha40.strip()) >= 7 else "unknown"
        return {
            "commit_sha": sha,
            "short_sha": sha[:7] if sha != "unknown" else "unknown",
            "branch": branch.strip() if rc_branch == 0 else "main",
            "remote_url": clean_url,
        }

    def build_archify_spec(self, workspace_path: str = "") -> Dict[str, Any]:
        """
        Gera a especificação canónica Archify (schema_version: 1, diagram_type: 'architecture').
        Organiza módulos em colunas estratificadas por fronteira semântica com coordenadas determinísticas sem sobreposição.
        """
        ws = os.path.abspath(workspace_path or self.workspace_path)
        ws_name = os.path.basename(ws) or "brain_mcp"
        provenance = self._get_git_provenance()

        # Obter grafo via GraphifyEngine partilhado em memória
        kg: Dict[str, Any] = {}
        try:
            kg = _get_shared_graphify(ws).build_codebase_knowledge_graph(workspace_path=ws, force_rebuild=False)
        except Exception:
            pass

        kg_nodes = kg.get("nodes", [])
        kg_edges = kg.get("edges", [])

        # Inventário de ficheiros do workspace
        file_inventory: Dict[str, Dict[str, Any]] = {}
        try:
            for entry in sorted(os.listdir(ws)):
                full_p = os.path.join(ws, entry)
                if os.path.isfile(full_p) and entry.endswith((".py", ".html", ".bat", ".json", ".md")):
                    if entry.startswith(".") or entry == "brain.db":
                        continue
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                            code_txt = fh.read()
                        ast_info = _extract_ast_summary_from_code(code_txt, entry)
                        file_inventory[entry] = ast_info
                    except Exception:
                        pass
        except Exception:
            pass

        # Associar símbolos do grafo aos ficheiros
        file_top_symbols: Dict[str, List[str]] = {}
        for n in kg_nodes:
            f = n.get("file")
            lbl = n.get("label", "")
            if f and f in file_inventory and lbl and lbl != f:
                file_top_symbols.setdefault(f, []).append(lbl)

        # Mapeamento de camadas para colunas
        layer_columns = {
            "frontend": 0,    # x = 40
            "messagebus": 1,  # x = 260
            "security": 2,    # x = 480
            "backend": 2,     # x = 480
            "database": 3,    # x = 700
            "cloud": 4,       # x = 920
            "external": 4,    # x = 920
        }

        layer_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        components: List[Dict[str, Any]] = []
        comp_id_map: Dict[str, str] = {}

        # Ordenar ficheiros para determinação consistente
        for fname in sorted(file_inventory.keys()):
            info = file_inventory[fname]
            sem_type = classify_semantic_type(fname)
            col_idx = layer_columns.get(sem_type, 2)
            row_idx = layer_counts[col_idx]
            layer_counts[col_idx] += 1

            cid = f"comp_{fname.replace('.', '_').replace('-', '_')}"
            comp_id_map[fname] = cid

            top_syms = file_top_symbols.get(fname, info.get("symbols", []))
            sublabel = f"{info['lines']}L · {len(top_syms)} símbolos"

            components.append({
                "id": cid,
                "type": sem_type,
                "label": fname,
                "sublabel": sublabel,
                "color": SEMANTIC_PALETTE.get(sem_type, {}).get("color", "#34D399"),
                "pos": [40 + col_idx * 220, 60 + row_idx * 86],
                "size": [165, 64],
                "sources": [{
                    "path": fname,
                    "start_line": 1,
                    "end_line": info["lines"],
                    "top_symbols": top_syms[:8],
                }],
            })

        # Adicionar cluster persistente SQLite/Pagoda
        sql_tables = [n["label"] for n in kg_nodes if n.get("node_type") == "SQL_TABLE"]
        if sql_tables:
            db_col = 3
            db_row = layer_counts[db_col]
            layer_counts[db_col] += 1
            components.append({
                "id": "comp_sqlite_pagoda_store",
                "type": "database",
                "label": "brain.db (SQLite WAL + Pagoda)",
                "sublabel": f"{len(sql_tables)} tabelas · LSM Folds",
                "color": SEMANTIC_PALETTE["database"]["color"],
                "pos": [40 + db_col * 220, 60 + db_row * 86],
                "size": [165, 64],
                "sources": [{
                    "path": "brain.db",
                    "start_line": 1,
                    "end_line": 1,
                    "top_symbols": sql_tables[:10],
                }],
            })
            comp_id_map["brain.db"] = "comp_sqlite_pagoda_store"

        # Fronteiras de Confiança / Zonas Lógicas
        boundaries = [
            {
                "id": "boundary_studio_frontend",
                "label": "Studio Frontend Surface",
                "component_ids": [c["id"] for c in components if c["type"] == "frontend"],
            },
            {
                "id": "boundary_hooks_mcp",
                "label": "Hooks & MCP Bus",
                "component_ids": [c["id"] for c in components if c["type"] == "messagebus"],
            },
            {
                "id": "boundary_cognitive_ast",
                "label": "Cognitive & AST Engines",
                "component_ids": [c["id"] for c in components if c["type"] in ("backend", "security")],
            },
            {
                "id": "boundary_persistence",
                "label": "Hybrid SQLite & Pagoda Store",
                "component_ids": [c["id"] for c in components if c["type"] == "database"],
            },
            {
                "id": "boundary_sync_cloud",
                "label": "Ecosystem & Sync",
                "component_ids": [c["id"] for c in components if c["type"] in ("cloud", "external")],
            },
        ]
        boundaries = [b for b in boundaries if b["component_ids"]]

        # Conexões Módulo-a-Módulo
        connections: List[Dict[str, Any]] = []
        seen_edges: Set[Tuple[str, str]] = set()

        # 1. Imports locais derivados do AST
        for fname, info in file_inventory.items():
            src_cid = comp_id_map.get(fname)
            if not src_cid:
                continue
            for imp in info.get("imports", []):
                target_fname = f"{imp}.py"
                tgt_cid = comp_id_map.get(target_fname)
                if tgt_cid and tgt_cid != src_cid:
                    edge_key = (src_cid, tgt_cid)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        connections.append({
                            "id": f"conn_{src_cid}_{tgt_cid}",
                            "from": src_cid,
                            "to": tgt_cid,
                            "label": f"import {imp}",
                            "confidence": "EXTRACTED",
                            "variant": "solid",
                        })

        # 2. Arestas do Grafo Knowledge Graph (HTTP, SQL, Chamadas)
        for e in kg_edges:
            s_node = e.get("source", "")
            t_node = e.get("target", "")
            e_type = e.get("edge_type", "CALLS")

            # Mapear nó fonte para componente
            src_f = s_node[5:] if s_node.startswith("file:") else ""
            if not src_f:
                for n in kg_nodes:
                    if n.get("id") == s_node:
                        src_f = n.get("file", "")
                        break

            tgt_f = t_node[5:] if t_node.startswith("file:") else ""
            if not tgt_f:
                if t_node.startswith("sql:"):
                    tgt_f = "brain.db"
                else:
                    for n in kg_nodes:
                        if n.get("id") == t_node:
                            tgt_f = n.get("file", "")
                            break

            src_cid = comp_id_map.get(src_f)
            tgt_cid = comp_id_map.get(tgt_f)

            if src_cid and tgt_cid and src_cid != tgt_cid:
                edge_key = (src_cid, tgt_cid)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    variant = "solid"
                    if "HTTP" in e_type:
                        variant = "dashed"
                    elif "SQL" in e_type:
                        variant = "accent"
                    connections.append({
                        "id": f"conn_{src_cid}_{tgt_cid}",
                        "from": src_cid,
                        "to": tgt_cid,
                        "label": e_type,
                        "confidence": str(e.get("confidence", "EXTRACTED")),
                        "variant": variant,
                    })

        return {
            "schema_version": 1,
            "diagram_type": "architecture",
            "meta": {
                "title": f"{ws_name} — Evidence Console",
                "visual_preset": "signal-flow",
                "repository": provenance,
                "generated_tokens_cost": 0,
                "components_count": len(components),
                "connections_count": len(connections),
            },
            "palette": SEMANTIC_PALETTE,
            "boundaries": boundaries,
            "components": components,
            "connections": connections,
        }

    def compute_architecture_delta(
        self,
        base_ref: str = "HEAD~1",
        head_ref: str = "WORKTREE",
        workspace_path: str = "",
    ) -> Dict[str, Any]:
        """
        Compara a arquitetura do repositório entre base_ref e head_ref em memória.
        Inspirado em tt-a1i/archify/delta/architecture-delta.mjs. Zero modificações no disco.
        """
        ws = os.path.abspath(workspace_path or self.workspace_path)
        provenance = self._get_git_provenance()

        # Resolução de base SHA
        rc_base, base_sha = self._run_git(["rev-parse", base_ref], cwd=ws)
        if rc_base != 0:
            # Fallback para HEAD se HEAD~1 falhar (ex: repo de 1 commit)
            rc_base, base_sha = self._run_git(["rev-parse", "HEAD"], cwd=ws)
            if rc_base != 0:
                base_sha = "empty"

        # Resolução de head SHA
        head_sha = "WORKTREE"
        if head_ref != "WORKTREE":
            rc_head, head_sha_val = self._run_git(["rev-parse", head_ref], cwd=ws)
            head_sha = head_sha_val.strip() if rc_head == 0 else "WORKTREE"

        # 1. Carregar inventário da base em memória (cacheado por commit SHA imutável!)
        base_files: Dict[str, Dict[str, Any]] = {}
        if base_sha != "empty":
            cached_base = _GIT_SHA_INVENTORY_CACHE.get(base_sha)
            if cached_base is not None:
                base_files = cached_base
            else:
                rc_tree, tree_out = self._run_git(["ls-tree", "-r", "--name-only", base_ref], cwd=ws)
                if rc_tree == 0:
                    for line in tree_out.splitlines():
                        f = line.strip()
                        if f.endswith((".py", ".html", ".bat", ".json", ".md")) and not f.startswith("."):
                            rc_show, content = self._run_git(["show", f"{base_ref}:{f}"], cwd=ws)
                            if rc_show == 0:
                                base_files[f] = _extract_ast_summary_from_code(content, f)
                _GIT_SHA_INVENTORY_CACHE[base_sha] = base_files

        # 2. Carregar inventário do head
        head_files: Dict[str, Dict[str, Any]] = {}
        if head_ref == "WORKTREE":
            for entry in sorted(os.listdir(ws)):
                full_p = os.path.join(ws, entry)
                if os.path.isfile(full_p) and entry.endswith((".py", ".html", ".bat", ".json", ".md")):
                    if entry.startswith(".") or entry == "brain.db":
                        continue
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                            code_txt = fh.read()
                        head_files[entry] = _extract_ast_summary_from_code(code_txt, entry)
                    except Exception:
                        pass
        else:
            rc_tree, tree_out = self._run_git(["ls-tree", "-r", "--name-only", head_ref], cwd=ws)
            if rc_tree == 0:
                for line in tree_out.splitlines():
                    f = line.strip()
                    if f.endswith((".py", ".html", ".bat", ".json", ".md")) and not f.startswith("."):
                        rc_show, content = self._run_git(["show", f"{head_ref}:{f}"], cwd=ws)
                        if rc_show == 0:
                            head_files[f] = _extract_ast_summary_from_code(content, f)

        # 3. Calcular Diferencial Canónico
        added_components: List[Dict[str, Any]] = []
        removed_components: List[Dict[str, Any]] = []
        modified_components: List[Dict[str, Any]] = []

        all_file_keys = sorted(list(set(base_files.keys()).union(head_files.keys())))

        for f in all_file_keys:
            in_base = f in base_files
            in_head = f in head_files
            sem_type = classify_semantic_type(f)
            color = SEMANTIC_PALETTE.get(sem_type, {}).get("color", "#34D399")

            if in_head and not in_base:
                added_components.append({
                    "file": f,
                    "semantic_type": sem_type,
                    "color": color,
                    "symbols_added": head_files[f]["symbols"],
                    "lines": head_files[f]["lines"],
                })
            elif in_base and not in_head:
                removed_components.append({
                    "file": f,
                    "semantic_type": sem_type,
                    "color": color,
                    "symbols_removed": base_files[f]["symbols"],
                })
            else:
                b_info = base_files[f]
                h_info = head_files[f]
                b_syms = set(b_info["symbols"])
                h_syms = set(h_info["symbols"])

                syms_added = sorted(list(h_syms - b_syms))
                syms_removed = sorted(list(b_syms - h_syms))
                line_delta = h_info["lines"] - b_info["lines"]

                if syms_added or syms_removed or line_delta != 0:
                    modified_components.append({
                        "file": f,
                        "semantic_type": sem_type,
                        "color": color,
                        "symbols_added": syms_added,
                        "symbols_removed": syms_removed,
                        "line_delta": line_delta,
                    })

        # 4. Diferencial de Conexões (Imports locais)
        def _build_connections(files_dict: Dict[str, Dict[str, Any]]) -> Set[Tuple[str, str]]:
            conns = set()
            for src, info in files_dict.items():
                for imp in info.get("imports", []):
                    tgt = f"{imp}.py"
                    if tgt in files_dict and tgt != src:
                        conns.add((src, tgt))
            return conns

        base_conns = _build_connections(base_files)
        head_conns = _build_connections(head_files)

        added_connections = [
            {"from": s, "to": t, "kind": "import"}
            for (s, t) in sorted(list(head_conns - base_conns))
        ]
        removed_connections = [
            {"from": s, "to": t, "kind": "import"}
            for (s, t) in sorted(list(base_conns - head_conns))
        ]

        counts = {
            "added": len(added_components),
            "removed": len(removed_components),
            "modified": len(modified_components),
            "edges_added": len(added_connections),
            "edges_removed": len(removed_connections),
        }

        summary_text = (
            f"Delta Arquitetural ({base_ref} ➔ {head_ref}): "
            f"{counts['added']} componentes adicionados, "
            f"{counts['modified']} modificados, "
            f"{counts['removed']} removidos; "
            f"{counts['edges_added']} conexões adicionadas, "
            f"{counts['edges_removed']} removidas."
        )

        return {
            "ok": True,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "provenance": {
                "base_sha": base_sha[:7] if base_sha != "empty" else "empty",
                "head_sha": head_sha[:7] if head_sha != "WORKTREE" else "WORKTREE",
                "current_remote": provenance.get("remote_url", ""),
            },
            "added_components": added_components,
            "removed_components": removed_components,
            "modified_components": modified_components,
            "added_connections": added_connections,
            "removed_connections": removed_connections,
            "counts": counts,
            "summary_text": summary_text,
        }

    def compute_reachability_focus(
        self,
        node_query: str,
        workspace_path: str = "",
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Isola a vizinhança navegável a montante (Upstream) e a jusante (Downstream) de um nó alvo.
        Elimina 90%+ do ruído do grafo, gerando foco de blast-radius determinístico com zero tokens.
        """
        ws = os.path.abspath(workspace_path or self.workspace_path)
        depth = max(1, min(max_depth, 5))

        kg = _get_shared_graphify(ws).build_codebase_knowledge_graph(workspace_path=ws, force_rebuild=False)
        nodes: List[Dict[str, Any]] = kg.get("nodes", [])
        edges: List[Dict[str, Any]] = kg.get("edges", [])

        # 1. Resolver nó alvo
        q_norm = (node_query or "").strip().lower()
        matched_node: Optional[Dict[str, Any]] = None

        for n in nodes:
            lbl = n.get("label", "").lower()
            nid = n.get("id", "").lower()
            if q_norm and (lbl == q_norm or nid == q_norm or q_norm in lbl):
                matched_node = n
                break

        if not matched_node and nodes:
            # Fallback para primeiro God Node ou primeiro nó do grafo
            god_nodes = kg.get("god_nodes", [])
            if god_nodes:
                matched_node = god_nodes[0]
            else:
                matched_node = nodes[0]

        if not matched_node:
            return {
                "ok": False,
                "error": f"Nó não encontrado para a query: '{node_query}'",
                "center_node": None,
                "upstream": [],
                "downstream": [],
                "edges": [],
                "noise_eliminated_pct": 100.0,
                "semantic_palette": SEMANTIC_PALETTE,
            }

        target_id = matched_node["id"]

        # Índices de arestas
        in_edges: Dict[str, List[Dict[str, Any]]] = {}
        out_edges: Dict[str, List[Dict[str, Any]]] = {}
        for e in edges:
            s = e.get("source", "")
            t = e.get("target", "")
            out_edges.setdefault(s, []).append(e)
            in_edges.setdefault(t, []).append(e)

        nodes_by_id = {n["id"]: n for n in nodes}

        # 2. Caminhar Upstream (quem chama / importa / alimenta o nó)
        upstream_visited: Dict[str, int] = {}
        queue: List[Tuple[str, int]] = [(target_id, 0)]
        while queue:
            cur_id, cur_d = queue.pop(0)
            if cur_d >= depth:
                continue
            for e in in_edges.get(cur_id, []):
                src = e.get("source", "")
                if src and src != target_id and src not in upstream_visited:
                    upstream_visited[src] = cur_d + 1
                    queue.append((src, cur_d + 1))

        # 3. Caminhar Downstream (o que o nó chama / grava / desencadeia)
        downstream_visited: Dict[str, int] = {}
        queue = [(target_id, 0)]
        while queue:
            cur_id, cur_d = queue.pop(0)
            if cur_d >= depth:
                continue
            for e in out_edges.get(cur_id, []):
                tgt = e.get("target", "")
                if tgt and tgt != target_id and tgt not in downstream_visited:
                    downstream_visited[tgt] = cur_d + 1
                    queue.append((tgt, cur_d + 1))

        def _format_reach_node(n_dict: Dict[str, Any], dist: int, direction: str) -> Dict[str, Any]:
            f = n_dict.get("file", "")
            ln = n_dict.get("line", 1)
            sem = classify_semantic_type(f or n_dict.get("label", ""), n_dict.get("node_type", ""))
            return {
                "id": n_dict.get("id"),
                "label": n_dict.get("label"),
                "node_type": n_dict.get("node_type"),
                "semantic_type": sem,
                "color": SEMANTIC_PALETTE.get(sem, {}).get("color", "#34D399"),
                "file": f,
                "line": ln,
                "line_pointer": f"{f}:L{ln}" if f else "N/A",
                "hop_distance": dist,
                "direction": direction,
                "pagerank": n_dict.get("pagerank", 1.0),
                "community": n_dict.get("community_name", "Core"),
            }

        center_formatted = _format_reach_node(matched_node, 0, "center")

        upstream_nodes = [
            _format_reach_node(nodes_by_id[nid], dist, "upstream")
            for nid, dist in sorted(upstream_visited.items(), key=lambda x: x[1])
            if nid in nodes_by_id
        ]

        downstream_nodes = [
            _format_reach_node(nodes_by_id[nid], dist, "downstream")
            for nid, dist in sorted(downstream_visited.items(), key=lambda x: x[1])
            if nid in nodes_by_id
        ]

        # Arestas no subgrafo focado
        focused_ids = {target_id}.union(upstream_visited.keys()).union(downstream_visited.keys())
        relevant_edges = [
            {
                "source": e.get("source"),
                "target": e.get("target"),
                "edge_type": e.get("edge_type"),
                "confidence": e.get("confidence", "EXTRACTED"),
                "direction": "upstream" if e.get("target") == target_id or e.get("target") in upstream_visited else "downstream",
            }
            for e in edges
            if e.get("source") in focused_ids and e.get("target") in focused_ids
        ]

        total_graph_nodes = max(1, len(nodes))
        retained_count = len(focused_ids)
        noise_eliminated = round((1.0 - (retained_count / total_graph_nodes)) * 100.0, 1)

        return {
            "ok": True,
            "center_node": center_formatted,
            "upstream": upstream_nodes,
            "downstream": downstream_nodes,
            "edges": relevant_edges,
            "retained_nodes_count": retained_count,
            "total_nodes_count": total_graph_nodes,
            "noise_eliminated_pct": noise_eliminated,
            "semantic_palette": SEMANTIC_PALETTE,
        }

    def build_explainer_walkthrough(
        self,
        source_query: str,
        target_query: str,
        workspace_path: str = "",
    ) -> Dict[str, Any]:
        """
        Gera um Explainer Conclusion-First determinístico mapeando o fluxo exato de execução entre dois nós.
        Inspirado no tt-a1i/archify explainer protocol.
        """
        ws = os.path.abspath(workspace_path or self.workspace_path)
        path_res = _get_shared_graphify(ws).find_graph_path(
            source_query=source_query,
            target_query=target_query,
            max_hops=7,
            workspace_path=ws,
        )

        if not path_res.get("found"):
            return {
                "ok": True,
                "found": False,
                "title": f"Fluxo não encontrado: {source_query} ➔ {target_query}",
                "conclusion_first": f"Não foi encontrado caminho determinístico até 7 saltos entre '{source_query}' e '{target_query}'.",
                "steps": [],
                "involved_files": [],
                "token_savings": path_res.get("token_savings", {}),
            }

        path_nodes: List[Dict[str, Any]] = path_res.get("path_nodes", [])
        path_edges: List[Dict[str, Any]] = path_res.get("path_edges", [])
        hops = path_res.get("hops_count", len(path_nodes) - 1)
        token_savings = path_res.get("token_savings", {})

        involved_layers = set()
        steps: List[Dict[str, Any]] = []

        for i, node in enumerate(path_nodes):
            f = node.get("file", "")
            ln = node.get("line", 1)
            sem_type = classify_semantic_type(f or node.get("label", ""), node.get("node_type", ""))
            color = SEMANTIC_PALETTE.get(sem_type, {}).get("color", "#34D399")
            involved_layers.add(SEMANTIC_PALETTE.get(sem_type, {}).get("label", sem_type))

            rel_to_next = None
            conf = "EXTRACTED"
            narrative = f"Ponto de contacto {i+1}: {node.get('label')}"

            if i < len(path_edges):
                e = path_edges[i]
                rel_to_next = e.get("edge_type")
                conf = e.get("confidence", "EXTRACTED")
                exp = e.get("explanation")
                if exp:
                    narrative = exp

            steps.append({
                "step": i + 1,
                "id": node.get("id"),
                "label": node.get("label"),
                "node_type": node.get("node_type"),
                "semantic_type": sem_type,
                "color": color,
                "evidence_beacon": f"{f}:L{ln}" if f else "N/A",
                "relation_to_next": rel_to_next,
                "confidence": conf,
                "narrative": narrative,
            })

        saved_k = round(token_savings.get("tokens_saved", 0) / 1000.0, 1)
        mult = token_savings.get("compression_multiplier", "1x")
        conclusion = (
            f"Fluxo comprovado em {hops} saltos cruzando {len(involved_layers)} fronteiras de confiança "
            f"({ ' ➔ '.join(list(involved_layers)[:3]) }). "
            f"Confiança determinística de 100% via AST com {saved_k}k tokens poupados ({mult} de compressão)."
        )

        return {
            "ok": True,
            "found": True,
            "title": f"Fluxo Verificado: {source_query} ➔ {target_query}",
            "conclusion_first": conclusion,
            "hops_count": hops,
            "latency_ms": path_res.get("latency_ms", 0),
            "steps": steps,
            "involved_files": path_res.get("involved_files", []),
            "token_savings": token_savings,
        }

    def export_standalone_html(
        self,
        workspace_path: str = "",
        output_path: Optional[str] = None,
        include_delta: bool = True,
    ) -> Dict[str, Any]:
        """
        Exporta a consola interactiva independente Archify ('The Evidence Console') num único ficheiro HTML autónomo.
        Zero CDNs, zero dependências de rede, paleta Midnight #020617, diagrama SVG estratificado e reachability interativo.
        """
        ws = os.path.abspath(workspace_path or self.workspace_path)
        spec = self.build_archify_spec(workspace_path=ws)
        delta = self.compute_architecture_delta(workspace_path=ws) if include_delta else {}

        spec_json = json.dumps(spec, ensure_ascii=False).replace("</script>", "<\\/script>")
        delta_json = json.dumps(delta, ensure_ascii=False).replace("</script>", "<\\/script>")

        repo_info = spec["meta"].get("repository", {})
        title = html.escape(spec["meta"].get("title", "Evidence Console"))
        commit_sha = html.escape(repo_info.get("short_sha", "HEAD"))
        branch = html.escape(repo_info.get("branch", "main"))

        # Gerar SVG dos Componentes e Conexões
        components = spec.get("components", [])
        connections = spec.get("connections", [])
        boundaries = spec.get("boundaries", [])

        # Calcular limites do canvas SVG
        max_x = max([c["pos"][0] + c["size"][0] for c in components] + [1000]) + 80
        max_y = max([c["pos"][1] + c["size"][1] for c in components] + [600]) + 80

        # SVG markup
        svg_parts: List[str] = []
        svg_parts.append(f'<svg id="archify-svg" width="{max_x}" height="{max_y}" viewBox="0 0 {max_x} {max_y}" xmlns="http://www.w3.org/2000/svg">')
        svg_parts.append('<defs>')
        svg_parts.append('  <marker id="arrow-solid" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">')
        svg_parts.append('    <path d="M 0 1 L 9 5 L 0 9 z" fill="#64748b"/>')
        svg_parts.append('  </marker>')
        svg_parts.append('  <marker id="arrow-accent" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">')
        svg_parts.append('    <path d="M 0 1 L 9 5 L 0 9 z" fill="#a78bfa"/>')
        svg_parts.append('  </marker>')
        svg_parts.append('</defs>')

        # 1. Zonas Lógicas (Boundaries)
        for b in boundaries:
            b_comps = [c for c in components if c["id"] in b.get("component_ids", [])]
            if not b_comps:
                continue
            bx_min = min(c["pos"][0] for c in b_comps) - 16
            by_min = min(c["pos"][1] for c in b_comps) - 30
            bx_max = max(c["pos"][0] + c["size"][0] for c in b_comps) + 16
            by_max = max(c["pos"][1] + c["size"][1] for c in b_comps) + 16
            bw = bx_max - bx_min
            bh = by_max - by_min
            b_label = html.escape(b.get("label", ""))

            svg_parts.append(f'<g class="boundary-zone" id="{b["id"]}">'
                             f'<rect x="{bx_min}" y="{by_min}" width="{bw}" height="{bh}" rx="10" '
                             f'fill="rgba(30, 41, 59, 0.25)" stroke="#334155" stroke-dasharray="4,4" stroke-width="1.2"/>'
                             f'<text x="{bx_min + 12}" y="{by_min + 18}" fill="#94a3b8" font-size="11" font-weight="600" letter-spacing="0.5">{b_label}</text>'
                             f'</g>')

        # 2. Conexões
        comp_centers = {c["id"]: (c["pos"][0] + c["size"][0] / 2, c["pos"][1] + c["size"][1] / 2) for c in components}
        for conn in connections:
            from_pt = comp_centers.get(conn["from"])
            to_pt = comp_centers.get(conn["to"])
            if not from_pt or not to_pt:
                continue
            x1, y1 = from_pt
            x2, y2 = to_pt
            # Curvatura Bézier simples
            cx = (x1 + x2) / 2
            variant = conn.get("variant", "solid")
            stroke = "#a78bfa" if variant == "accent" else ("#0284c7" if variant == "dashed" else "#475569")
            dash = 'stroke-dasharray="4,4"' if variant == "dashed" else ""
            marker = "arrow-accent" if variant == "accent" else "arrow-solid"

            svg_parts.append(
                f'<path class="arch-edge" data-from="{conn["from"]}" data-to="{conn["to"]}" '
                f'd="M {x1} {y1} C {cx} {y1}, {cx} {y2}, {x2} {y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="1.4" {dash} marker-end="url(#{marker})" opacity="0.6"/>'
            )

        # 3. Componentes
        for c in components:
            cx, cy = c["pos"]
            cw, ch = c["size"]
            c_color = c.get("color", "#34D399")
            c_label = html.escape(c.get("label", ""))
            c_sub = html.escape(c.get("sublabel", ""))
            c_type = html.escape(c.get("type", "backend"))

            svg_parts.append(
                f'<g class="arch-node" id="{c["id"]}" data-id="{c["id"]}" data-type="{c_type}" cursor="pointer" transform="translate({cx},{cy})">'
                f'<rect class="node-box" width="{cw}" height="{ch}" rx="8" fill="#0f172a" stroke="{c_color}" stroke-width="1.4"/>'
                f'<circle cx="14" cy="20" r="5" fill="{c_color}"/>'
                f'<text x="26" y="24" fill="#f8fafc" font-size="12" font-weight="600">{c_label}</text>'
                f'<text x="26" y="44" fill="#94a3b8" font-size="10">{c_sub}</text>'
                f'</g>'
            )

        svg_parts.append('</svg>')
        svg_content = "\n".join(svg_parts)

        # Template HTML Midnight Canvas
        html_content = f"""<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <title>{title} — The Evidence Console</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {{
      --bg: #020617;
      --card-bg: #0b0f19;
      --panel-bg: #0f172a;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --border: #1e293b;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    body.light-theme {{
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --panel-bg: #f1f5f9;
      --text: #0f172a;
      --text-muted: #64748b;
      --border: #cbd5e1;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-mono);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      transition: background 0.2s, color 0.2s;
    }}
    header {{
      height: 52px;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      font-size: 13px;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; }}
    .brand-badge {{
      background: #10b981;
      color: #020617;
      font-size: 10px;
      font-weight: 800;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
    }}
    .header-actions {{ display: flex; align-items: center; gap: 12px; }}
    .search-input {{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 5px 10px;
      border-radius: 6px;
      font-family: inherit;
      font-size: 12px;
      width: 220px;
    }}
    .btn {{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 5px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-family: inherit;
      font-size: 12px;
      font-weight: 600;
    }}
    .btn:hover {{ border-color: #38bdf8; }}
    .palette-legend {{
      display: flex;
      align-items: center;
      gap: 12px;
      background: var(--panel-bg);
      padding: 6px 16px;
      border-bottom: 1px solid var(--border);
      font-size: 11px;
      overflow-x: auto;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 5px; }}
    .legend-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
    main {{
      display: flex;
      flex: 1;
      height: calc(100vh - 84px);
      overflow: hidden;
    }}
    #canvas-container {{
      flex: 1;
      overflow: auto;
      background: radial-gradient(circle, var(--border) 1px, transparent 1px);
      background-size: 24px 24px;
      padding: 24px;
    }}
    aside {{
      width: 340px;
      background: var(--card-bg);
      border-left: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding: 16px;
      font-size: 12px;
    }}
    .panel-title {{
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .beacon-card {{
      background: var(--panel-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
    }}
    .beacon-title {{ font-weight: 700; color: #38bdf8; margin-bottom: 6px; }}
    .beacon-code {{
      background: #000;
      color: #34d399;
      padding: 4px 6px;
      border-radius: 4px;
      font-size: 11px;
      display: block;
      margin: 4px 0 8px 0;
    }}
    .symbols-list {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }}
    .sym-pill {{
      background: var(--border);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
    }}
    /* Interação nós */
    .arch-node:hover .node-box {{ stroke-width: 2.2px; filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.4)); }}
    .arch-node.active .node-box {{ stroke: #38bdf8 !important; stroke-width: 2.6px; }}
    .dimmed {{ opacity: 0.15 !important; }}
    .highlight-upstream {{ stroke: #22d3ee !important; stroke-width: 2.4px !important; opacity: 1 !important; }}
    .highlight-downstream {{ stroke: #fb923c !important; stroke-width: 2.4px !important; opacity: 1 !important; }}
    #delta-drawer {{
      position: absolute;
      bottom: 0;
      left: 0;
      right: 340px;
      height: 240px;
      background: var(--card-bg);
      border-top: 2px solid #38bdf8;
      transform: translateY(100%);
      transition: transform 0.25s ease-in-out;
      padding: 16px;
      overflow-y: auto;
      font-size: 12px;
      z-index: 100;
    }}
    #delta-drawer.open {{ transform: translateY(0); }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>🏛️ {title}</span>
      <span class="brand-badge">Zero-Token</span>
      <span style="color: var(--text-muted); font-size: 11px;">SHA: {commit_sha} ({branch})</span>
    </div>
    <div class="header-actions">
      <input type="text" id="search-box" class="search-input" placeholder="Pesquisar símbolo ou ficheiro...">
      <button class="btn" id="btn-delta">Delta ({commit_sha} vs Worktree)</button>
      <button class="btn" id="btn-theme">🌓 Tema</button>
    </div>
  </header>

  <div class="palette-legend">
    <span style="font-weight: 700; color: var(--text-muted);">Sinais:</span>
    {''.join([f'<div class="legend-item"><span class="legend-dot" style="background:{v["color"]}"></span><span>{v["label"]}</span></div>' for v in SEMANTIC_PALETTE.values()])}
  </div>

  <main>
    <div id="canvas-container">
      {svg_content}
    </div>
    <aside id="evidence-sidebar">
      <div class="panel-title">
        <span>📡 Evidence Beacon</span>
        <span id="beacon-status" style="font-size: 10px; color: #10b981;">Deterministic</span>
      </div>
      <div id="beacon-content">
        <p style="color: var(--text-muted);">Clica num componente ou aresta no canvas para focar alcance upstream/downstream imediato.</p>
      </div>
    </aside>
  </main>

  <div id="delta-drawer">
    <div class="panel-title">
      <span>📐 Architecture Delta (HEAD~1 ➔ Worktree)</span>
      <button class="btn" id="btn-close-delta">Fechar</button>
    </div>
    <div id="delta-content"></div>
  </div>

  <script>
    const SPEC = {spec_json};
    const DELTA = {delta_json};

    const nodes = document.querySelectorAll('.arch-node');
    const edges = document.querySelectorAll('.arch-edge');
    const beaconBox = document.getElementById('beacon-content');
    const searchBox = document.getElementById('search-box');
    const deltaDrawer = document.getElementById('delta-drawer');
    const deltaContent = document.getElementById('delta-content');

    // Mapeamento id -> componente
    const compMap = {{}};
    (SPEC.components || []).forEach(c => {{ compMap[c.id] = c; }});

    // Renderizar Delta
    if (DELTA && DELTA.ok) {{
      deltaContent.innerHTML = `
        <p style="margin-bottom: 8px; color: #38bdf8;"><strong>${{DELTA.summary_text || ''}}</strong></p>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 8px;">
          <div class="beacon-card">
            <strong style="color: #34d399;">+ Adicionados (${{(DELTA.added_components || []).length}})</strong>
            ${{(DELTA.added_components || []).map(a => `<div style="margin-top:4px;">${{a.file}} (+${{a.lines}}L)</div>`).join('') || '<div style="color:#64748b;">Nenhum</div>'}}
          </div>
          <div class="beacon-card">
            <strong style="color: #fbbf24;">⚡ Modificados (${{(DELTA.modified_components || []).length}})</strong>
            ${{(DELTA.modified_components || []).map(m => `<div style="margin-top:4px;">${{m.file}} (${{m.line_delta >= 0 ? '+' : ''}}${{m.line_delta}}L)</div>`).join('') || '<div style="color:#64748b;">Nenhum</div>'}}
          </div>
          <div class="beacon-card">
            <strong style="color: #fb7185;">- Removidos (${{(DELTA.removed_components || []).length}})</strong>
            ${{(DELTA.removed_components || []).map(r => `<div style="margin-top:4px;">${{r.file}}</div>`).join('') || '<div style="color:#64748b;">Nenhum</div>'}}
          </div>
        </div>
      `;
    }}

    // Reachability Focus ao Clicar
    nodes.forEach(node => {{
      node.addEventListener('click', (e) => {{
        e.stopPropagation();
        const cid = node.getAttribute('data-id');
        const comp = compMap[cid];
        if (!comp) return;

        // Limpar estados anteriores
        nodes.forEach(n => {{ n.classList.remove('active', 'dimmed'); }});
        edges.forEach(ed => {{ ed.classList.remove('highlight-upstream', 'highlight-downstream', 'dimmed'); }});

        node.classList.add('active');

        // Encontrar montante (upstream) e jusante (downstream)
        const upstreamNodes = new Set();
        const downstreamNodes = new Set();

        edges.forEach(ed => {{
          const from = ed.getAttribute('data-from');
          const to = ed.getAttribute('data-to');
          if (to === cid) {{
            upstreamNodes.add(from);
            ed.classList.add('highlight-upstream');
          }} else if (from === cid) {{
            downstreamNodes.add(to);
            ed.classList.add('highlight-downstream');
          }} else {{
            ed.classList.add('dimmed');
          }}
        }});

        nodes.forEach(n => {{
          const nid = n.getAttribute('data-id');
          if (nid !== cid && !upstreamNodes.has(nid) && !downstreamNodes.has(nid)) {{
            n.classList.add('dimmed');
          }}
        }});

        // Atualizar Evidence Sidebar
        const src = (comp.sources && comp.sources[0]) || {{}};
        const syms = src.top_symbols || [];
        beaconBox.innerHTML = `
          <div class="beacon-card">
            <div class="beacon-title">${{comp.label}}</div>
            <span class="beacon-code">${{src.path || comp.label}}:L${{src.start_line || 1}}-L${{src.end_line || 1}}</span>
            <div style="margin-bottom: 6px;"><strong>Camada:</strong> <span style="color:${{comp.color}}">${{comp.type}}</span></div>
            <div style="margin-bottom: 6px;"><strong>Alcance Local:</strong> Upstream: ${{upstreamNodes.size}} | Downstream: ${{downstreamNodes.size}}</div>
            <div><strong>Símbolos em Destaque (${{syms.length}}):</strong></div>
            <div class="symbols-list">
              ${{syms.map(s => `<span class="sym-pill">${{s}}</span>`).join('')}}
            </div>
          </div>
        `;
      }});
    }});

    // Clique fora limpa foco
    document.getElementById('canvas-container').addEventListener('click', () => {{
      nodes.forEach(n => n.classList.remove('active', 'dimmed'));
      edges.forEach(ed => ed.classList.remove('highlight-upstream', 'highlight-downstream', 'dimmed'));
      beaconBox.innerHTML = '<p style="color: var(--text-muted);">Clica num componente ou aresta no canvas para focar alcance upstream/downstream imediato.</p>';
    }});

    // Filtro de Pesquisa
    searchBox.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase().trim();
      if (!q) {{
        nodes.forEach(n => n.classList.remove('dimmed'));
        edges.forEach(ed => ed.classList.remove('dimmed'));
        return;
      }}
      nodes.forEach(n => {{
        const cid = n.getAttribute('data-id');
        const comp = compMap[cid];
        const match = comp && (comp.label.toLowerCase().includes(q) || (comp.sources[0]?.top_symbols || []).some(s => s.toLowerCase().includes(q)));
        if (match) {{
          n.classList.remove('dimmed');
        }} else {{
          n.classList.add('dimmed');
        }}
      }});
      edges.forEach(ed => ed.classList.add('dimmed'));
    }});

    // Delta Drawer Toggle
    document.getElementById('btn-delta').addEventListener('click', () => {{
      deltaDrawer.classList.toggle('open');
    }});
    document.getElementById('btn-close-delta').addEventListener('click', () => {{
      deltaDrawer.classList.remove('open');
    }});

    // Tema Claro / Escuro
    document.getElementById('btn-theme').addEventListener('click', () => {{
      document.body.classList.toggle('light-theme');
    }});
  </script>
</body>
</html>
"""
        if output_path:
            out_file = os.path.abspath(output_path)
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(html_content)

        return {
            "ok": True,
            "html": html_content,
            "bytes": len(html_content.encode("utf-8")),
            "output_path": output_path,
            "components_count": len(components),
            "connections_count": len(connections),
        }

# -*- coding: utf-8 -*-
"""
Pagoda LSM Memory Folding Engine (Billion-Context Architecture)
=============================================================
Inspirado na arquitetura Model-Driven Incremental Hierarchical Compression
do ranxianglei/billion-context (MIT).

Implementa um motor de memória em camadas (LSM Pagoda Fold) 100% determinístico,
com zero-LLM tokens, compressão zlib reversível sem perdas (lossless) e ordenação
estável para o KV-Cache do modelo.

Camadas:
  - Tier 1: Turn Episodes (Turnos individuais compactados em zlib)
  - Tier 2: Milestone Folds (Agregação de 5 turnos T1 em 1 marco persistente)
  - Tier 3: Architecture Epochs (Agregação de 5 marcos T2 em 1 época arquitetural)
"""

import datetime
import json
import os
import re
import sqlite3
import zlib
from typing import Any, Dict, List, Optional


class PagodaFoldEngine:
    def __init__(self, db: Optional[Any] = None) -> None:
        if db is not None:
            self.db = db
        else:
            from db_engine import BrainDB
            self.db = BrainDB()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Cria idempotentemente a tabela pagoda_folds e os índices de alta performance."""
        with self.db._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pagoda_folds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace TEXT NOT NULL DEFAULT 'brain_mcp',
                    tier INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL,
                    summary_telegraphic TEXT NOT NULL,
                    raw_payload_zlib BLOB,
                    raw_chars INTEGER NOT NULL DEFAULT 0,
                    folded_chars INTEGER NOT NULL DEFAULT 0,
                    parent_fold_id INTEGER DEFAULT NULL,
                    child_fold_ids TEXT NOT NULL DEFAULT '[]',
                    key_files TEXT NOT NULL DEFAULT '',
                    git_sha TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pagoda_ws_active 
                ON pagoda_folds(workspace, parent_fold_id, tier, id);
                """
            )

    def fold_turn_episode(
        self,
        workspace: str,
        title: str,
        summary: str,
        raw_payload: Any,
        key_files: str = "",
        git_sha: str = "",
        auto_rollup_threshold: int = 5,
    ) -> Dict[str, Any]:
        """
        Dobra um episódio de turno (Tier 1) de forma 100% lossless via zlib.
        Aplica guard de desduplicação e dispara Pagoda Roll-Up incremental se atingir o limiar.
        """
        ws = self.db.normalize_workspace(workspace)
        if isinstance(raw_payload, (dict, list)):
            raw_str = json.dumps(raw_payload, ensure_ascii=False, indent=2)
        else:
            raw_str = str(raw_payload or "")

        raw_bytes = raw_str.encode("utf-8")
        raw_payload_zlib = zlib.compress(raw_bytes, level=6)
        raw_chars = len(raw_str)
        folded_chars = len(raw_payload_zlib)

        clean_title = (title or "Turno").strip()[:65]
        clean_summary = (summary or "Memória colhida").strip()[:140]

        if not git_sha:
            try:
                from auto_updater import get_git_status
                git_sha = get_git_status().get("local_sha", "")
            except Exception:
                git_sha = ""

        with self.db._connect() as conn:
            # Deduplication Guard: se o último Tier-1 ativo tiver exatamente o mesmo título e sumário, atualiza
            latest = conn.execute(
                """
                SELECT id, title, summary_telegraphic FROM pagoda_folds
                WHERE workspace = ? AND tier = 1 AND parent_fold_id IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (ws,),
            ).fetchone()

            if (
                latest
                and latest["title"] == clean_title
                and latest["summary_telegraphic"] == clean_summary
            ):
                fold_id = latest["id"]
                conn.execute(
                    """
                    UPDATE pagoda_folds
                    SET raw_payload_zlib = ?, raw_chars = ?, folded_chars = ?, key_files = ?, git_sha = ?
                    WHERE id = ?
                    """,
                    (raw_payload_zlib, raw_chars, folded_chars, key_files, git_sha, fold_id),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO pagoda_folds (
                        workspace, tier, title, summary_telegraphic, raw_payload_zlib,
                        raw_chars, folded_chars, parent_fold_id, child_fold_ids, key_files, git_sha
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, NULL, '[]', ?, ?)
                    """,
                    (
                        ws,
                        clean_title,
                        clean_summary,
                        raw_payload_zlib,
                        raw_chars,
                        folded_chars,
                        key_files,
                        git_sha,
                    ),
                )
                fold_id = cur.lastrowid

        rollups = self._maybe_rollup_pagoda(ws, threshold=auto_rollup_threshold)
        return {
            "ok": True,
            "fold_id": fold_id,
            "tier": 1,
            "workspace": ws,
            "raw_chars": raw_chars,
            "folded_chars": folded_chars,
            "rollups_triggered": rollups,
        }

    def _maybe_rollup_pagoda(self, ws: str, threshold: int = 5) -> int:
        """
        Executa o roll-up hierárquico Pagoda:
        - Agrupa os 'threshold' mais antigos Tier-1 ativos num novo Tier-2 (Milestone)
        - Agrupa os 'threshold' mais antigos Tier-2 ativos num novo Tier-3 (Epoch)
        Preserva 100% dos dados originais para descompressão futura sem perdas.
        """
        rollups_count = 0
        with self.db._connect() as conn:
            while True:
                # 1. Avalia Roll-Up Tier 1 -> Tier 2
                t1_rows = conn.execute(
                    """
                    SELECT id, title, summary_telegraphic, key_files, git_sha, raw_chars, folded_chars, created_at
                    FROM pagoda_folds
                    WHERE workspace = ? AND parent_fold_id IS NULL AND tier = 1
                    ORDER BY id ASC
                    """,
                    (ws,),
                ).fetchall()

                if len(t1_rows) >= threshold:
                    batch = [dict(r) for r in t1_rows[:threshold]]
                    first_id = batch[0]["id"]
                    last_id = batch[-1]["id"]
                    first_title = batch[0]["title"]

                    t2_title = f"Marco T2 ({first_id}..{last_id}): {first_title[:36]}"
                    t2_summary = "; ".join(c["summary_telegraphic"] for c in batch)[:180]

                    # Desduplica key_files mantendo a ordem
                    files_seen = set()
                    combined_files = []
                    for c in batch:
                        for f in (c.get("key_files") or "").split(","):
                            f_clean = f.strip()
                            if f_clean and f_clean not in files_seen:
                                files_seen.add(f_clean)
                                combined_files.append(f_clean)
                    key_files_str = ", ".join(combined_files[:10])

                    child_ids = [c["id"] for c in batch]
                    child_ids_json = json.dumps(child_ids)

                    archived_payload = [
                        {
                            "id": c["id"],
                            "tier": 1,
                            "title": c["title"],
                            "summary": c["summary_telegraphic"],
                            "key_files": c.get("key_files", ""),
                            "raw_chars": c.get("raw_chars", 0),
                            "folded_chars": c.get("folded_chars", 0),
                            "created_at": str(c.get("created_at", "")),
                        }
                        for c in batch
                    ]
                    raw_json = json.dumps(archived_payload, ensure_ascii=False, indent=2)
                    raw_zlib = zlib.compress(raw_json.encode("utf-8"), level=6)
                    raw_chars = sum(c.get("raw_chars", 0) for c in batch) + len(raw_json)
                    folded_chars = len(raw_zlib)
                    git_sha = batch[-1].get("git_sha") or ""

                    cur = conn.execute(
                        """
                        INSERT INTO pagoda_folds (
                            workspace, tier, title, summary_telegraphic, raw_payload_zlib,
                            raw_chars, folded_chars, parent_fold_id, child_fold_ids, key_files, git_sha
                        ) VALUES (?, 2, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                        """,
                        (
                            ws,
                            t2_title,
                            t2_summary,
                            raw_zlib,
                            raw_chars,
                            folded_chars,
                            child_ids_json,
                            key_files_str,
                            git_sha,
                        ),
                    )
                    new_t2_id = cur.lastrowid

                    placeholders = ",".join("?" for _ in child_ids)
                    conn.execute(
                        f"UPDATE pagoda_folds SET parent_fold_id = ? WHERE id IN ({placeholders})",
                        [new_t2_id] + child_ids,
                    )
                    rollups_count += 1
                    continue

                # 2. Avalia Roll-Up Tier 2 -> Tier 3
                t2_rows = conn.execute(
                    """
                    SELECT id, title, summary_telegraphic, key_files, git_sha, raw_chars, folded_chars, created_at
                    FROM pagoda_folds
                    WHERE workspace = ? AND parent_fold_id IS NULL AND tier = 2
                    ORDER BY id ASC
                    """,
                    (ws,),
                ).fetchall()

                if len(t2_rows) >= threshold:
                    batch = [dict(r) for r in t2_rows[:threshold]]
                    first_id = batch[0]["id"]
                    last_id = batch[-1]["id"]
                    first_title = batch[0]["title"]

                    clean_t3_base = re.sub(r"^(?:Marco T2|Epoch T3)\s*\([^)]*\):\s*", "", first_title).strip()
                    t3_title = f"Época T3 ({first_id}..{last_id}): {(key_files_str or clean_t3_base)[:36]}"
                    t3_summary = "; ".join(c["summary_telegraphic"] for c in batch)[:180]

                    files_seen = set()
                    combined_files = []
                    for c in batch:
                        for f in (c.get("key_files") or "").split(","):
                            f_clean = f.strip()
                            if f_clean and f_clean not in files_seen:
                                files_seen.add(f_clean)
                                combined_files.append(f_clean)
                    key_files_str = ", ".join(combined_files[:12])

                    child_ids = [c["id"] for c in batch]
                    child_ids_json = json.dumps(child_ids)

                    archived_payload = [
                        {
                            "id": c["id"],
                            "tier": 2,
                            "title": c["title"],
                            "summary": c["summary_telegraphic"],
                            "key_files": c.get("key_files", ""),
                            "raw_chars": c.get("raw_chars", 0),
                            "folded_chars": c.get("folded_chars", 0),
                            "created_at": str(c.get("created_at", "")),
                        }
                        for c in batch
                    ]
                    raw_json = json.dumps(archived_payload, ensure_ascii=False, indent=2)
                    raw_zlib = zlib.compress(raw_json.encode("utf-8"), level=6)
                    raw_chars = sum(c.get("raw_chars", 0) for c in batch) + len(raw_json)
                    folded_chars = len(raw_zlib)
                    git_sha = batch[-1].get("git_sha") or ""

                    cur = conn.execute(
                        """
                        INSERT INTO pagoda_folds (
                            workspace, tier, title, summary_telegraphic, raw_payload_zlib,
                            raw_chars, folded_chars, parent_fold_id, child_fold_ids, key_files, git_sha
                        ) VALUES (?, 3, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                        """,
                        (
                            ws,
                            t3_title,
                            t3_summary,
                            raw_zlib,
                            raw_chars,
                            folded_chars,
                            child_ids_json,
                            key_files_str,
                            git_sha,
                        ),
                    )
                    new_t3_id = cur.lastrowid

                    placeholders = ",".join("?" for _ in child_ids)
                    conn.execute(
                        f"UPDATE pagoda_folds SET parent_fold_id = ? WHERE id IN ({placeholders})",
                        [new_t3_id] + child_ids,
                    )
                    rollups_count += 1
                    continue

                break

        return rollups_count

    def decompress_fold(self, fold_id: int) -> Dict[str, Any]:
        """
        Restaura de forma 100% lossless o payload bruto comprimido em zlib
        e a árvore de filhos se for um marco agrupado (Tier 2 ou 3).
        """
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pagoda_folds WHERE id = ?", (fold_id,)
            ).fetchone()
            if not row:
                return {"ok": False, "error": f"Fold #{fold_id} not found"}

            row_dict = dict(row)
            raw_blob = row_dict.get("raw_payload_zlib")
            raw_text = ""
            parsed_payload = None

            if raw_blob:
                try:
                    decompressed = zlib.decompress(raw_blob)
                    raw_text = decompressed.decode("utf-8", errors="replace")
                    try:
                        parsed_payload = json.loads(raw_text)
                    except Exception:
                        parsed_payload = None
                except Exception as e:
                    raw_text = f"[Decompression Error: {e}]"
                    parsed_payload = None

            children: List[Dict[str, Any]] = []
            child_ids_raw = row_dict.get("child_fold_ids") or "[]"
            try:
                child_ids = (
                    json.loads(child_ids_raw)
                    if isinstance(child_ids_raw, str)
                    else list(child_ids_raw)
                )
                if child_ids:
                    placeholders = ",".join("?" for _ in child_ids)
                    ch_rows = conn.execute(
                        f"""
                        SELECT id, tier, title, summary_telegraphic, key_files, created_at 
                        FROM pagoda_folds 
                        WHERE id IN ({placeholders}) 
                        ORDER BY id ASC
                        """,
                        child_ids,
                    ).fetchall()
                    children = [dict(cr) for cr in ch_rows]
            except Exception:
                children = []

            return {
                "ok": True,
                "id": row_dict["id"],
                "workspace": row_dict["workspace"],
                "tier": row_dict["tier"],
                "title": row_dict["title"],
                "summary_telegraphic": row_dict["summary_telegraphic"],
                "key_files": row_dict.get("key_files", ""),
                "git_sha": row_dict.get("git_sha", ""),
                "raw_chars": row_dict.get("raw_chars", 0),
                "folded_chars": row_dict.get("folded_chars", 0),
                "created_at": str(row_dict.get("created_at", "")),
                "raw_text": raw_text,
                "parsed_payload": parsed_payload,
                "children": children,
            }

    def get_active_pagoda_timeline(
        self, workspace: str = "brain_mcp", max_chars: int = 320
    ) -> Dict[str, Any]:
        """
        Retorna a timeline compacta de folds ativos não agrupados na ordem canónica
        append-only (T3 -> T2 -> T1, IDs mais antigos primeiro) para estabilidade do KV-Cache.
        Calcula o rácio real de compressão em relação a todos os caracteres históricos.
        """
        ws = self.db.normalize_workspace(workspace)
        with self.db._connect() as conn:
            active_rows = conn.execute(
                """
                SELECT id, workspace, tier, title, summary_telegraphic, raw_chars, folded_chars, key_files, git_sha, created_at
                FROM pagoda_folds
                WHERE workspace = ? AND parent_fold_id IS NULL
                ORDER BY tier DESC, id ASC
                """,
                (ws,),
            ).fetchall()
            active = [dict(r) for r in active_rows]

            stats_row = conn.execute(
                """
                SELECT count(*) as total_cnt, COALESCE(SUM(raw_chars), 0) as total_raw, COALESCE(SUM(folded_chars), 0) as total_folded
                FROM pagoda_folds
                WHERE workspace = ?
                """,
                (ws,),
            ).fetchone()
            total_cnt = stats_row["total_cnt"] if stats_row else 0
            total_raw = stats_row["total_raw"] if stats_row else 0
            total_folded = stats_row["total_folded"] if stats_row else 0

        c1 = sum(1 for f in active if f["tier"] == 1)
        c2 = sum(1 for f in active if f["tier"] == 2)
        c3 = sum(1 for f in active if f["tier"] == 3)
        tier_counts = {1: c1, 2: c2, 3: c3}

        if not active:
            return {
                "ok": True,
                "workspace": ws,
                "tier_counts": tier_counts,
                "active_count": 0,
                "total_historical_folds": total_cnt,
                "total_raw_tokens": 0,
                "active_tokens": 0,
                "compression_ratio": 1.0,
                "pagoda_line": "",
                "active_folds": [],
            }

        item_tokens: List[str] = []
        for f in active:
            clean_short_title = re.sub(r"[\r\n|:]+", " ", f.get("title", "")).strip()
            clean_short_title = re.sub(r"\s+", "", clean_short_title)[:22]
            item_tokens.append(f"#{f['id']}(T{f['tier']}:{clean_short_title})")

        items_joined = "|".join(item_tokens)
        suffix = "[use brain_decompress_fold(id)]"

        # Estima rácio preliminar baseado no total histórico
        prelim_line = f"🏯[PAGODA|T3:{c3}|T2:{c2}|T1:{c1}|10x]:{items_joined}{suffix}"
        prelim_len = max(1, len(prelim_line))
        ratio = max(1.0, round(total_raw / prelim_len, 1)) if total_raw > 0 else 1.0
        ratio_str = f"{round(ratio)}x" if ratio >= 10 else f"{ratio:.1f}x"

        pagoda_line = f"🏯[PAGODA|T3:{c3}|T2:{c2}|T1:{c1}|{ratio_str}]:{items_joined}{suffix}"
        if len(pagoda_line) > max_chars:
            pagoda_line = f"🏯[PAGODA|T3:{c3}|T2:{c2}|T1:{c1}|{ratio_str}]:{items_joined}"
            if len(pagoda_line) > max_chars:
                pagoda_line = pagoda_line[: max_chars - 3] + "..."

        raw_tok = max(1, total_raw // 4)
        act_tok = max(1, len(pagoda_line) // 4)
        final_ratio = max(1.0, round(total_raw / max(1, len(pagoda_line)), 1)) if total_raw > 0 else 1.0

        return {
            "ok": True,
            "workspace": ws,
            "tier_counts": tier_counts,
            "active_count": len(active),
            "total_historical_folds": total_cnt,
            "total_raw_tokens": raw_tok,
            "active_tokens": act_tok,
            "compression_ratio": final_ratio,
            "pagoda_line": pagoda_line,
            "active_folds": active,
        }

    def get_pagoda_overview(self, workspace: str = "brain_mcp") -> Dict[str, Any]:
        """
        Retorna visão holística para o Web Dashboard, incluindo a timeline ativa
        e os últimos 15 folds históricos com estado de roll-up.
        """
        ws = self.db.normalize_workspace(workspace)
        timeline = self.get_active_pagoda_timeline(workspace=ws, max_chars=360)
        with self.db._connect() as conn:
            recent_rows = conn.execute(
                """
                SELECT id, workspace, tier, title, summary_telegraphic, raw_chars, folded_chars,
                       parent_fold_id, child_fold_ids, key_files, git_sha, created_at
                FROM pagoda_folds
                WHERE workspace = ?
                ORDER BY id DESC
                LIMIT 15
                """,
                (ws,),
            ).fetchall()
            recent: List[Dict[str, Any]] = []
            for r in recent_rows:
                d = dict(r)
                d["is_rolled_up"] = bool(d.get("parent_fold_id"))
                recent.append(d)

        timeline["recent_folds"] = recent
        return timeline

    def fold_current_checkpoint(self, workspace: str = "brain_mcp") -> Dict[str, Any]:
        """
        Auxiliar para dobrar o checkpoint atual e memórias recentes como um episódio Tier-1.
        Utilizado pelo Web Dashboard e hooks de sincronização.
        """
        ws = self.db.normalize_workspace(workspace)
        checkpoint = self.db.get_checkpoint(ws)
        with self.db._connect() as conn:
            m_rows = conn.execute(
                """
                SELECT id, topic, fact, category, tags, created_at
                FROM memories
                WHERE workspace = ?
                ORDER BY id DESC
                LIMIT 5
                """,
                (ws,),
            ).fetchall()
            recent_memories = [dict(m) for m in m_rows]

        if not checkpoint and not recent_memories:
            return {"ok": False, "message": "Nenhum checkpoint ou memória para dobrar"}

        title = (checkpoint.get("goal") if checkpoint else None) or (
            recent_memories[0]["topic"] if recent_memories else f"Checkpoint {ws}"
        )
        summary = (checkpoint.get("last_completed") if checkpoint else None) or (
            recent_memories[0]["fact"] if recent_memories else f"Estado atual do workspace {ws}"
        )
        raw_payload = {
            "checkpoint": checkpoint,
            "recent_memories": recent_memories,
            "folded_at": datetime.datetime.now().isoformat(),
        }
        key_files = (checkpoint.get("key_files") if checkpoint else "") or ""
        return self.fold_turn_episode(
            workspace=ws,
            title=title,
            summary=summary,
            raw_payload=raw_payload,
            key_files=key_files,
        )

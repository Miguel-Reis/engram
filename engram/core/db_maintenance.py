"""Deep SQLite maintenance, orphan vector cleanup, and cross-workspace deduplication."""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Dict, List, Tuple

from engram.core.logging import log_error

# Heuristics for assigning canonical ownership when an identical memory topic was
# cloned across multiple workspaces (pre-v9.2 workspace drift cleanup).
_OWNER_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "brain_mcp",
        (
            "engram",
            "antigravity brain",
            "vault & defuddle",
            "studio os",
            "ui studio",
            "ui architecture",
            "v2.6",
            "v2.7",
            "v2.8",
            "v4.",
            "v5.",
            "v6.",
            "v7.",
            "v8.",
            "v9.",
            "v10.",
            "v11.",
            "token diet",
            "quota 5h",
            "5h quota",
            "hipporag",
            "pagoda",
            "archify",
            "graphify",
            "scout",
            "swarm",
            "brain_mcp",
            "brain_inject",
            "brain_harvest",
            "db_engine",
            "orbit",
            "office 3d",
            "neural cortex",
            "workspace consolidation",
        ),
    ),
    ("jarvis-cortex-os", ("jarvis", "vierisid")),
    ("mike-gsp", ("mike-gsp", "mike_gsp", "daemon go", "panel auth", "panel_auth")),
    ("mt2", ("n2play", "metin2", "mt2", "m2ui")),
    ("shadowmeter2", ("shadowmeter", "shadowhub", "meter.v2")),
    ("aion2", ("aion2", "aion 2")),
    ("cgclima-site", ("cgclima",)),
    ("roblox", ("roblox",)),
)

# Workspaces that frequently received accidental cross-project copies in early builds
_DRIFT_PRONE_WORKSPACES = frozenset({"app", "anti", "global", "brain_mcp", "shadowmeter2"})


def _choose_canonical_owner(topic: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Select the single canonical memory row to keep across a multi-workspace clone group."""
    t_low = str(topic or "").lower()
    fact_sample = " ".join(str(r.get("fact") or "")[:240].lower() for r in rows[:2])
    haystack = f"{t_low} {fact_sample}"

    # 1. Explicit project keyword match
    preferred_ws = None
    for ws_key, keywords in _OWNER_KEYWORDS:
        if any(k in haystack for k in keywords):
            preferred_ws = ws_key
            break

    def _rank_key(r: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
        ws = str(r.get("workspace") or "").lower()
        matches_pref = 1 if (preferred_ws and ws == preferred_ws) else 0
        non_drift = 1 if ws not in _DRIFT_PRONE_WORKSPACES else 0
        is_pinned = 1 if int(r.get("pinned") or 0) else 0
        imp = int(r.get("importance") or 0)
        rid = int(r.get("id") or 0)
        return (matches_pref, non_drift, is_pinned, imp, rid)

    return max(rows, key=_rank_key)


def count_vector_orphans(conn: sqlite3.Connection, table_exists_fn: Any) -> Dict[str, int]:
    """Count orphan rows in vector/revision/edge tables pointing to deleted memories."""
    counts = {
        "memory_neural_embeddings": 0,
        "neural_onnx_vectors": 0,
        "memory_revisions": 0,
        "memory_edges": 0,
    }
    try:
        if table_exists_fn(conn, "memory_neural_embeddings"):
            row = conn.execute(
                "SELECT COUNT(*) FROM memory_neural_embeddings WHERE memory_id NOT IN (SELECT id FROM memories);"
            ).fetchone()
            counts["memory_neural_embeddings"] = int(row[0]) if row else 0
        if table_exists_fn(conn, "neural_onnx_vectors"):
            row = conn.execute(
                "SELECT COUNT(*) FROM neural_onnx_vectors WHERE memory_id NOT IN (SELECT id FROM memories);"
            ).fetchone()
            counts["neural_onnx_vectors"] = int(row[0]) if row else 0
        if table_exists_fn(conn, "memory_revisions"):
            row = conn.execute(
                "SELECT COUNT(*) FROM memory_revisions WHERE memory_id NOT IN (SELECT id FROM memories);"
            ).fetchone()
            counts["memory_revisions"] = int(row[0]) if row else 0
        if table_exists_fn(conn, "memory_edges"):
            row = conn.execute(
                "SELECT COUNT(*) FROM memory_edges WHERE source_id NOT IN (SELECT id FROM memories) OR target_id NOT IN (SELECT id FROM memories);"
            ).fetchone()
            counts["memory_edges"] = int(row[0]) if row else 0
    except Exception as exc:
        log_error("db_maintenance", "count_vector_orphans failed", exc)
    return counts


def cleanup_vector_orphans(conn: sqlite3.Connection, table_exists_fn: Any) -> Dict[str, int]:
    """Delete orphan rows from v10/v11 vector, revision, and edge tables."""
    pruned: Dict[str, int] = {}
    for vtbl in ("memory_neural_embeddings", "neural_onnx_vectors", "neural_feedback_log", "memory_revisions"):
        if table_exists_fn(conn, vtbl):
            try:
                cur = conn.execute(
                    f'DELETE FROM "{vtbl}" WHERE memory_id NOT IN (SELECT id FROM memories);'
                )
                pruned[vtbl] = max(0, int(cur.rowcount or 0))
            except Exception as exc:
                log_error("db_maintenance", f"orphan cleanup failed for {vtbl}", exc)
                pruned[vtbl] = 0
    if table_exists_fn(conn, "memory_edges"):
        try:
            cur_e = conn.execute(
                "DELETE FROM memory_edges WHERE source_id NOT IN (SELECT id FROM memories) OR target_id NOT IN (SELECT id FROM memories);"
            )
            pruned["memory_edges_post"] = max(0, int(cur_e.rowcount or 0))
        except Exception as exc:
            log_error("db_maintenance", "post orphan cleanup failed for memory_edges", exc)
    # Clean vec_memories virtual table if sqlite_vec extension is loadable on this connection
    if table_exists_fn(conn, "vec_memories"):
        try:
            import sqlite_vec  # type: ignore

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            cur_v = conn.execute(
                "DELETE FROM vec_memories WHERE memory_id NOT IN (SELECT id FROM memories);"
            )
            pruned["vec_memories"] = max(0, int(cur_v.rowcount or 0))
        except Exception:
            # Extension unavailable or already pruned; safe to skip
            pass
    return pruned


def deduplicate_cross_workspace_clones(
    conn: sqlite3.Connection,
    table_exists_fn: Any,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Remove cross-workspace duplicate clones caused by pre-v9.2 workspace drift while
    preserving unique per-workspace facts and legitimate per-project learned rules.
    Re-points any memory_edges from removed duplicate IDs to the kept canonical ID.
    """
    mem_cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(memories);").fetchall()}
    pin_expr = "is_pinned" if "is_pinned" in mem_cols else ("pinned" if "pinned" in mem_cols else "0")
    acc_expr = "access_count" if "access_count" in mem_cols else "0"
    valid_clause = "WHERE valid_to IS NULL" if "valid_to" in mem_cols else ""
    rows = conn.execute(
        f"""
        SELECT id, workspace, category, topic, fact, importance, {pin_expr} AS pinned, {acc_expr} AS access_count
        FROM memories
        {valid_clause}
        ORDER BY id ASC;
        """
    ).fetchall()

    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        d = dict(r)
        topic_key = re.sub(r"\s+", " ", str(d.get("topic") or "").strip().lower())
        if not topic_key:
            continue
        # Preserve per-workspace synthesized meta-rules (each workspace has its own pattern summary)
        if topic_key.startswith("🧬 meta-regra aprendida") or topic_key.startswith("meta-regra aprendida"):
            continue
        by_topic.setdefault(topic_key, []).append(d)

    duplicate_ids: List[Tuple[int, int]] = []  # (removed_id, kept_id)
    groups_cleaned = 0

    for topic_key, group in by_topic.items():
        distinct_ws = {str(g.get("workspace") or "").lower() for g in group}
        if len(distinct_ws) < 2:
            continue
        # Only deduplicate when the fact payload itself is substantially identical
        # (first 120 normalized chars match) so genuinely distinct project notes sharing a generic title survive!
        by_sig: Dict[str, List[Dict[str, Any]]] = {}
        for g in group:
            f_sig = re.sub(r"\s+", " ", str(g.get("fact") or "").strip().lower())[:120]
            by_sig.setdefault(f_sig, []).append(g)

        for _sig, clones in by_sig.items():
            clone_wss = {str(c.get("workspace") or "").lower() for c in clones}
            if len(clone_wss) < 2:
                continue
            keeper = _choose_canonical_owner(topic_key, clones)
            keep_id = int(keeper["id"])
            groups_cleaned += 1
            for c in clones:
                cid = int(c["id"])
                if cid != keep_id:
                    duplicate_ids.append((cid, keep_id))

    if dry_run or not duplicate_ids:
        return {
            "dry_run": bool(dry_run),
            "groups_cleaned": groups_cleaned,
            "clones_removed": len(duplicate_ids),
        }

    # Re-point edges cleanly before deleting cloned rows
    has_edges = table_exists_fn(conn, "memory_edges")
    for rem_id, keep_id in duplicate_ids:
        if has_edges:
            try:
                conn.execute(
                    "UPDATE OR IGNORE memory_edges SET source_id = ? WHERE source_id = ? AND target_id != ?;",
                    (keep_id, rem_id, keep_id),
                )
                conn.execute(
                    "UPDATE OR IGNORE memory_edges SET target_id = ? WHERE target_id = ? AND source_id != ?;",
                    (keep_id, rem_id, keep_id),
                )
                conn.execute(
                    "DELETE FROM memory_edges WHERE source_id = ? OR target_id = ?;",
                    (rem_id, rem_id),
                )
            except Exception as exc:
                log_error("db_maintenance", f"repoint edges {rem_id}->{keep_id}", exc)
        conn.execute("DELETE FROM memories WHERE id = ?;", (rem_id,))

    if table_exists_fn(conn, "memories_fts"):
        conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild');")

    return {
        "dry_run": False,
        "groups_cleaned": groups_cleaned,
        "clones_removed": len(duplicate_ids),
    }


def compact_sqlite_database(abs_path: str) -> Dict[str, Any]:
    """
    Run coordinated WAL checkpoint + VACUUM + truncate checkpoint safely.
    On Windows NTFS, disables mmap (`PRAGMA mmap_size=0`), loads `sqlite_vec` if present,
    and if NTFS keeps a dead trailing tail larger than logical pages, rewrites cleanly
    via `VACUUM INTO` + atomic `os.replace()`.
    """
    result = {"vacuumed": False, "wal_checkpoint_busy": 0, "tail_truncated": False}
    if not os.path.isfile(abs_path):
        return result
    vac_conn = sqlite3.connect(abs_path, timeout=30.0, isolation_level=None)
    try:
        vac_conn.execute("PRAGMA busy_timeout = 30000;")
        vac_conn.execute("PRAGMA mmap_size = 0;")
        try:
            import sqlite_vec  # type: ignore

            vac_conn.enable_load_extension(True)
            sqlite_vec.load(vac_conn)
            vac_conn.enable_load_extension(False)
        except Exception:
            pass
        vac_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        vac_conn.execute("VACUUM;")
        ck = vac_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
        result["vacuumed"] = True
        result["wal_checkpoint_busy"] = int(ck[0]) if ck else 0

        # Check for Windows NTFS dead tail (file size >> logical page_count * page_size)
        pc = int((vac_conn.execute("PRAGMA page_count;").fetchone() or [0])[0])
        ps = int((vac_conn.execute("PRAGMA page_size;").fetchone() or [4096])[0])
        logical_bytes = pc * ps
        disk_bytes = os.path.getsize(abs_path)
        if logical_bytes > 0 and disk_bytes > logical_bytes + (2 * 1024 * 1024):
            tmp_compact = f"{abs_path}.compact.tmp"
            if os.path.exists(tmp_compact):
                try:
                    os.remove(tmp_compact)
                except OSError:
                    pass
            try:
                esc_tmp = tmp_compact.replace("'", "''")
                vac_conn.execute(f"VACUUM INTO '{esc_tmp}';")
                vac_conn.close()
                vac_conn = None  # type: ignore[assignment]
                if os.path.isfile(tmp_compact) and os.path.getsize(tmp_compact) < disk_bytes:
                    os.replace(tmp_compact, abs_path)
                    for suffix in ("-wal", "-shm"):
                        side = f"{abs_path}{suffix}"
                        if os.path.isfile(side):
                            try:
                                os.remove(side)
                            except OSError:
                                pass
                    result["tail_truncated"] = True
            except Exception as exc_tail:
                log_error("db_maintenance", "VACUUM INTO tail truncation skipped (busy)", exc_tail)
                if os.path.isfile(tmp_compact):
                    try:
                        os.remove(tmp_compact)
                    except OSError:
                        pass
    except Exception as exc:
        log_error("db_maintenance", "compact_sqlite_database failed", exc)
    finally:
        if vac_conn is not None:
            vac_conn.close()
    return result

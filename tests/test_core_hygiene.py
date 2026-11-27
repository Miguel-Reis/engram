"""Hermetic tests for core DB isolation, workspace normalization, orphan cleanup & dedup."""

from __future__ import annotations

from engram.core.db_maintenance import (
    cleanup_vector_orphans,
    count_vector_orphans,
    deduplicate_cross_workspace_clones,
)
from engram.core.logging import get_recent_errors, log_error
from engram.core.utils import canonical_workspace_alias, normalize_workspace_slug, utc_now_iso


def test_engram_db_path_env_isolation(isolated_db) -> None:
    from db_engine import BrainDB

    second = BrainDB()
    assert second.db_path == isolated_db.db_path
    mid, created = isolated_db.store_fact(
        topic="Hermetic Test Fact",
        fact="Stored exclusively inside temporary ENGRAM_DB_PATH database.",
        workspace="test_iso",
        category="architecture",
    )
    assert created is True and mid > 0


def test_workspace_slug_and_alias_normalization() -> None:
    from db_engine import BrainDB

    assert canonical_workspace_alias("jarvis_cortex_os") == "jarvis-cortex-os"
    assert normalize_workspace_slug("  Jarvis_Cortex_OS ") == "jarvis-cortex-os"
    assert BrainDB.normalize_workspace("C:/Users/dev/projects/jarvis_cortex_os") == "jarvis-cortex-os"
    assert utc_now_iso().endswith("Z")


def test_orphan_vector_cleanup_and_cross_workspace_dedup(isolated_db) -> None:
    # Seed cloned memories across drift-prone workspaces + a distinct per-workspace meta-rule
    id_keep, _ = isolated_db.store_fact(
        topic="UI Studio OS v7.0",
        fact="Engram Web Studio OS carbon obsidian architecture with 60 FPS tactical 3D cortex.",
        workspace="brain_mcp",
        category="architecture",
        importance=5,
    )
    id_clone, _ = isolated_db.store_fact(
        topic="UI Studio OS v7.0",
        fact="Engram Web Studio OS carbon obsidian architecture with 60 FPS tactical 3D cortex.",
        workspace="shadowmeter2",
        category="architecture",
        importance=3,
    )
    # Meta-rules per workspace must NOT be deduplicated away
    isolated_db.store_fact(
        topic="🧬 Meta-Regra Aprendida [explicit_note]",
        fact="Padrao especifico do projeto brain_mcp.",
        workspace="brain_mcp",
        category="learned_rule",
    )
    isolated_db.store_fact(
        topic="🧬 Meta-Regra Aprendida [explicit_note]",
        fact="Padrao especifico do projeto brain_mcp.",
        workspace="shadowmeter2",
        category="learned_rule",
    )

    with isolated_db._connect() as conn:
        # Insert an orphan v10 embedding pointing to non-existent memory ID 999999
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_neural_embeddings (
                memory_id INTEGER PRIMARY KEY,
                backend TEXT,
                dims INTEGER,
                vector_json TEXT,
                content_hash TEXT,
                updated_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO memory_neural_embeddings (memory_id, backend, dims, vector_json) VALUES (999999, 'test', 4, '[0,0,0,0]');"
        )
        orph_before = count_vector_orphans(conn, isolated_db._table_exists)
        assert orph_before["memory_neural_embeddings"] == 1

        dedup = deduplicate_cross_workspace_clones(conn, isolated_db._table_exists, dry_run=False)
        assert dedup["groups_cleaned"] == 1
        assert dedup["clones_removed"] == 1

        remaining_ids = [
            int(r[0]) for r in conn.execute("SELECT id FROM memories WHERE topic = 'UI Studio OS v7.0';").fetchall()
        ]
        assert remaining_ids == [id_keep]
        assert id_clone not in remaining_ids

        # Meta-rules preserved in both workspaces
        meta_cnt = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE topic = '🧬 Meta-Regra Aprendida [explicit_note]';"
        ).fetchone()[0]
        assert meta_cnt == 2

        pruned = cleanup_vector_orphans(conn, isolated_db._table_exists)
        assert pruned["memory_neural_embeddings"] == 1
        orph_after = count_vector_orphans(conn, isolated_db._table_exists)
        assert orph_after["memory_neural_embeddings"] == 0


def test_structured_error_logger_ring_buffer() -> None:
    log_error("test_suite", "simulated non-fatal error", RuntimeError("boom"))
    snap = get_recent_errors(limit=5)
    assert snap["total_logged_errors"] >= 1
    assert any(item["component"] == "test_suite" and item["error_type"] == "RuntimeError" for item in snap["recent"])

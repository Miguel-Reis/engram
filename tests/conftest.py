"""Shared hermetic pytest fixtures — guarantees tests NEVER touch production brain.db."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """Yield a fresh BrainDB backed by a temporary SQLite file via ENGRAM_DB_PATH."""
    from db_engine import BrainDB

    db_file = str(tmp_path / "engram_test.db")
    monkeypatch.setenv("ENGRAM_DB_PATH", db_file)
    monkeypatch.setenv("BRAIN_TEST_MODE", "1")
    db = BrainDB()
    assert os.path.abspath(db.db_path) == os.path.abspath(db_file)
    try:
        yield db
    finally:
        BrainDB.close_thread_connections(db_file)

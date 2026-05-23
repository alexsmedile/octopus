"""Shared fixtures for db/ tests.

`temp_db` returns a fresh in-file SQLite DB (not :memory:, so multiple
connections in a test can see the same data) under a tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from octopus.db.connection import get_db


@pytest.fixture
def temp_db(tmp_path: Path):
    db_path = tmp_path / "index.db"
    conn = get_db(db_path)
    try:
        yield conn
    finally:
        conn.close()

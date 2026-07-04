"""Shared fixtures for db/ tests.

`temp_db` returns a fresh in-file SQLite DB (not :memory:, so multiple
connections in a test can see the same data) under a tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from octopus.db.connection import get_db


@pytest.fixture(autouse=True, scope="session")
def _isolate_octopus_data(tmp_path_factory):
    """Redirect the real user index/logs/sync into a throwaway dir.

    CLI-level tests call get_db() with no path → default_db_path() →
    ~/.local/share/octopus/index.db, polluting the developer's live index.
    default_db_path() (and the logs/journal paths) honor $XDG_DATA_HOME, so
    pointing it at a tmp dir for the whole session isolates every write.
    """
    data_home = tmp_path_factory.mktemp("xdg_data")
    import os

    prev = os.environ.get("XDG_DATA_HOME")
    os.environ["XDG_DATA_HOME"] = str(data_home)
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = prev


@pytest.fixture
def temp_db(tmp_path: Path):
    db_path = tmp_path / "index.db"
    conn = get_db(db_path)
    try:
        yield conn
    finally:
        conn.close()

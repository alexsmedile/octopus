"""SQLite connection management.

Schema v2 (D46/D48): adds `kind` and `promoted_to` columns + their indexes.
Migration runs in-place via ALTER TABLE when an existing v1 DB is opened.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

SCHEMA_VERSION = 2
SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


# Python 3.12+ deprecated the default date/datetime adapter/converter pair.
# Register explicit ISO 8601 ones for our DATE / TIMESTAMP / DATETIME columns.
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat(timespec="seconds"))
sqlite3.register_converter("DATE", lambda b: date.fromisoformat(b.decode("ascii")))
sqlite3.register_converter("TIMESTAMP", lambda b: datetime.fromisoformat(b.decode("ascii")))
sqlite3.register_converter("DATETIME", lambda b: datetime.fromisoformat(b.decode("ascii")))


def default_db_path() -> Path:
    """Return ~/.local/share/octopus/index.db (XDG-aware)."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return base / "octopus" / "index.db"


def get_db(path: Path | None = None) -> sqlite3.Connection:
    """Open (or create) the index DB. Applies pragmas. Creates schema if absent.

    The caller is responsible for closing the connection (use a context manager).
    """
    path = path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables / indexes; migrate v1 → v2 in-place if needed."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current == 0:
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return
    if current == 1:
        # Migrate to v2: add kind + promoted_to columns and their indexes.
        # ALTER TABLE ADD COLUMN is the only safe in-place option in SQLite.
        conn.executescript(
            """
            ALTER TABLE tasks ADD COLUMN kind TEXT;
            ALTER TABLE tasks ADD COLUMN promoted_to TEXT;
            CREATE INDEX IF NOT EXISTS idx_tasks_kind        ON tasks(kind);
            CREATE INDEX IF NOT EXISTS idx_tasks_promoted_to ON tasks(promoted_to);
            """
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"index.db schema version {current} > supported {SCHEMA_VERSION}; "
            "upgrade octopus-cli"
        )
    # current == SCHEMA_VERSION: no-op


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Wrap a write in a transaction. Commits on success, rolls back on error."""
    conn.execute("BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

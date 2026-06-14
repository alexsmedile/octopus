"""SQLite connection management.

Schema v6: adds subtasks/blocked_by/waiting_for columns; composite + partial indexes.
Schema v5 (D104): adds `parent` column on tasks for subtask graph.
Schema v4 (D87/D88): activity priority + last_touched_at columns.
Schema v3 (D63): adds `task_external_refs` join table for adapter dedup.
v2 (D46/D48): adds `kind` and `promoted_to` columns + their indexes.
Migrations run in-place via ALTER TABLE / CREATE TABLE on connection open.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

SCHEMA_VERSION = 6
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
    """Create tables / indexes; migrate forward to SCHEMA_VERSION as needed."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current == 0:
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return
    # Forward-chained migrations: each block bumps user_version by one.
    if current == 1:
        # v1 → v2 (D46/D48): kind + promoted_to columns on tasks.
        conn.executescript(
            """
            ALTER TABLE tasks ADD COLUMN kind TEXT;
            ALTER TABLE tasks ADD COLUMN promoted_to TEXT;
            CREATE INDEX IF NOT EXISTS idx_tasks_kind        ON tasks(kind);
            CREATE INDEX IF NOT EXISTS idx_tasks_promoted_to ON tasks(promoted_to);
            """
        )
        conn.execute("PRAGMA user_version = 2")
        current = 2
    if current == 2:
        # v2 → v3 (D63): task_external_refs join table for adapter dedup.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS task_external_refs (
              task_id     TEXT     NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
              adapter     TEXT     NOT NULL,
              external_id TEXT     NOT NULL,
              PRIMARY KEY (adapter, external_id)
            );
            CREATE INDEX IF NOT EXISTS idx_task_external_refs_task
              ON task_external_refs(task_id);
            """
        )
        # Backfill from existing tasks' raw_frontmatter.external_refs.
        _backfill_external_refs(conn)
        conn.execute("PRAGMA user_version = 3")
        current = 3
    if current == 3:
        # v3 → v4 (D87/D88): activity priority + last_touched_at columns.
        conn.executescript(
            """
            ALTER TABLE activities ADD COLUMN priority TEXT;
            ALTER TABLE activities ADD COLUMN last_touched_at DATETIME;
            CREATE INDEX IF NOT EXISTS idx_activities_priority    ON activities(priority);
            CREATE INDEX IF NOT EXISTS idx_activities_last_touch  ON activities(last_touched_at);
            """
        )
        conn.execute("PRAGMA user_version = 4")
        current = 4
    if current == 4:
        # v4 → v5 (D104): parent column on tasks for subtask graph.
        conn.executescript(
            """
            ALTER TABLE tasks ADD COLUMN parent TEXT;
            CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent);
            """
        )
        # Backfill from existing tasks' raw_frontmatter.parent.
        _backfill_parent(conn)
        conn.execute("PRAGMA user_version = 5")
        current = 5
    if current == 5:
        # v5 → v6: subtasks/blocked_by/waiting_for columns + composite + partial indexes.
        conn.executescript(
            """
            ALTER TABLE tasks ADD COLUMN subtasks   TEXT;
            ALTER TABLE tasks ADD COLUMN blocked_by TEXT;
            ALTER TABLE tasks ADD COLUMN waiting_for TEXT;
            CREATE INDEX IF NOT EXISTS idx_tasks_activity_bucket
              ON tasks(activity_id, bucket, archived, pinned DESC, due, slug);
            CREATE INDEX IF NOT EXISTS idx_tasks_open
              ON tasks(bucket, activity_id, pinned DESC, due, slug)
              WHERE bucket NOT IN ('done', 'dropped')
                AND (archived IS NULL OR archived = 0);
            """
        )
        _backfill_v6(conn)
        conn.execute("PRAGMA user_version = 6")
        current = 6
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"index.db schema version {current} > supported {SCHEMA_VERSION}; "
            "upgrade octopus-cli"
        )
    # current == SCHEMA_VERSION: no-op


def _backfill_external_refs(conn: sqlite3.Connection) -> None:
    """v2 → v3 migration: scan existing tasks and populate task_external_refs.

    Reads `raw_frontmatter` JSON, looks for `external_refs` dict, inserts
    one row per (adapter, external_id) pair. Idempotent (uses INSERT OR IGNORE).
    """
    import json

    rows = conn.execute("SELECT id, raw_frontmatter FROM tasks").fetchall()
    for row in rows:
        raw = row["raw_frontmatter"]
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        refs = data.get("external_refs") if isinstance(data, dict) else None
        if not isinstance(refs, dict):
            continue
        for adapter, external_id in refs.items():
            if not adapter or not external_id:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO task_external_refs "
                "(task_id, adapter, external_id) VALUES (?, ?, ?)",
                (row["id"], str(adapter), str(external_id)),
            )


def _backfill_parent(conn: sqlite3.Connection) -> None:
    """v4 → v5 migration: populate tasks.parent from raw_frontmatter."""
    import json

    rows = conn.execute("SELECT id, raw_frontmatter FROM tasks").fetchall()
    for row in rows:
        raw = row["raw_frontmatter"]
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        parent = data.get("parent") if isinstance(data, dict) else None
        if parent:
            conn.execute(
                "UPDATE tasks SET parent = ? WHERE id = ?",
                (str(parent), row["id"]),
            )


def _backfill_v6(conn: sqlite3.Connection) -> None:
    """v5 → v6 migration: populate subtasks, blocked_by, waiting_for from raw_frontmatter."""
    import json

    rows = conn.execute("SELECT id, raw_frontmatter FROM tasks WHERE raw_frontmatter IS NOT NULL").fetchall()
    for row in rows:
        try:
            data = json.loads(row["raw_frontmatter"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        subtasks = data.get("subtasks")
        blocked_by = data.get("blocked_by")
        waiting_for = data.get("waiting_for")
        if subtasks is not None or blocked_by is not None or waiting_for is not None:
            conn.execute(
                "UPDATE tasks SET subtasks = ?, blocked_by = ?, waiting_for = ? WHERE id = ?",
                (
                    json.dumps(subtasks) if isinstance(subtasks, list) else None,
                    str(blocked_by) if blocked_by else None,
                    str(waiting_for) if waiting_for else None,
                    row["id"],
                ),
            )


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

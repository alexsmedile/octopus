"""Stale-check on read.

Compares row `indexed_at` against file `mtime`. Re-parses + upserts stale rows
inline so read commands return fresh data. See SCHEMA-INDEX.md §4.2.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from octopus.db.upsert import (
    delete_by_path, upsert_activity, upsert_session, upsert_task,
)
from octopus.fs.io import read_activity, read_task

# Stderr warning is emitted by the CLI layer, not here.
StaleWarning = tuple[str, str]  # (kind, message)


def _row_indexed_at(row: sqlite3.Row) -> datetime:
    raw = row["indexed_at"]
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(raw)


def is_stale(row: sqlite3.Row) -> bool:
    """True if file mtime > row indexed_at, OR file missing."""
    path = Path(row["path"])
    if not path.exists():
        return True
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return mtime > _row_indexed_at(row)


def refresh_task_row(
    conn: sqlite3.Connection, row: sqlite3.Row
) -> StaleWarning | None:
    """Re-parse the file at row['path'] and upsert; warn if file is gone.

    Returns a StaleWarning if the file is missing (row is left in place per rule R).
    """
    path = Path(row["path"])
    if not path.exists():
        return (
            "missing-source",
            f"task {row['slug']!r}: source file missing at {path} — "
            "run `octopus reindex --prune` to clean up",
        )
    task, _ = read_task(path)
    upsert_task(conn, row["activity_id"], task)
    return None


def refresh_activity_row(
    conn: sqlite3.Connection, row: sqlite3.Row
) -> StaleWarning | None:
    """Re-parse activity.md and upsert; warn if missing."""
    path = Path(row["path"])
    activity_md = path / ".octopus" / "activity.md"
    if not activity_md.is_file():
        return (
            "missing-source",
            f"activity {row['id']!r}: file missing at {activity_md} — "
            "run `octopus reindex --prune` to clean up",
        )
    activity, _ = read_activity(activity_md)
    upsert_activity(conn, activity)
    return None


def refresh_rows(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    kind: str,  # 'task' or 'activity'
) -> list[StaleWarning]:
    """Apply stale-check + refresh to a list of rows. Returns any warnings."""
    warnings: list[StaleWarning] = []
    for row in rows:
        if not is_stale(row):
            continue
        if kind == "task":
            w = refresh_task_row(conn, row)
        elif kind == "activity":
            w = refresh_activity_row(conn, row)
        else:
            raise ValueError(f"unknown kind {kind!r}")
        if w is not None:
            warnings.append(w)
    return warnings


def prune_missing(conn: sqlite3.Connection) -> dict[str, int]:
    """Delete rows whose source files no longer exist. Returns counts per table."""
    counts: dict[str, int] = {"activities": 0, "tasks": 0, "sessions": 0}
    for table in counts:
        # Activities: path is the activity folder; check for .octopus/activity.md inside it
        # Tasks/sessions: path is the file itself
        rows = conn.execute(f"SELECT id, path FROM {table}").fetchall()
        for row in rows:
            path = Path(row["path"])
            exists = (
                (path / ".octopus" / "activity.md").is_file()
                if table == "activities"
                else path.is_file()
            )
            if not exists:
                conn.execute(f"DELETE FROM {table} WHERE id = ?", (row["id"],))
                counts[table] += 1
    return counts

"""Read-shaped queries for index-backed commands."""

from __future__ import annotations

import sqlite3
from typing import Any


def list_activities(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    type_: str | None = None,
    area: str | None = None,
) -> list[sqlite3.Row]:
    """Backing query for `octopus list` (cross-activity mode)."""
    sql = "SELECT * FROM activities WHERE 1=1"
    args: list[Any] = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if type_:
        sql += " AND type = ?"
        args.append(type_)
    if area:
        sql += " AND area = ?"
        args.append(area)
    sql += " ORDER BY status, title"
    return conn.execute(sql, args).fetchall()


def get_activity_by_id_or_prefix(
    conn: sqlite3.Connection, query: str
) -> list[sqlite3.Row]:
    """Resolve an activity ID by exact match or unambiguous prefix."""
    exact = conn.execute(
        "SELECT * FROM activities WHERE id = ?", (query,)
    ).fetchall()
    if exact:
        return exact
    # Prefix on slug portion (before the '-hash')
    return conn.execute(
        "SELECT * FROM activities WHERE id LIKE ?",
        (f"{query}-%",),
    ).fetchall()


def _apply_promotion_filters(
    sql: str,
    args: list[Any],
    *,
    kinds: list[str] | None,
    promoted: bool,
    spec: str | None,
) -> tuple[str, list[Any]]:
    """Append --kind / --promoted / --spec filter clauses (D52)."""
    if kinds:
        placeholders = ",".join("?" * len(kinds))
        sql += f" AND kind IN ({placeholders})"
        args.extend(kinds)
    if spec:
        # --spec is a scope override: implies --promoted to that target.
        sql += " AND promoted_to = ?"
        args.append(f"spectacular:{spec}")
    elif promoted:
        sql += " AND promoted_to IS NOT NULL"
    return sql, args


def tasks_for_activity(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    bucket: str | None = None,
    include_archived: bool = False,
    kinds: list[str] | None = None,
    promoted: bool = False,
    spec: str | None = None,
) -> list[sqlite3.Row]:
    """Tasks for one activity, sorted pinned-first / priority / due / slug.

    --kind / --promoted / --spec filter args follow D52 scope rules. When
    `promoted=True` or `spec` is set, this overrides the default scope
    implicitly (callers don't need to lift `include_archived`).
    """
    sql = "SELECT * FROM tasks WHERE activity_id = ?"
    args: list[Any] = [activity_id]
    if bucket:
        sql += " AND bucket = ?"
        args.append(bucket)
    if not include_archived:
        sql += " AND (archived IS NULL OR archived = 0)"
    sql, args = _apply_promotion_filters(
        sql, args, kinds=kinds, promoted=promoted, spec=spec
    )
    sql += """
        ORDER BY
          CASE WHEN pinned = 1 THEN 0 ELSE 1 END,
          CASE priority
            WHEN 'urgent' THEN 0
            WHEN 'high' THEN 1
            WHEN 'low' THEN 3
            ELSE 2
          END,
          due IS NULL, due,
          slug
    """
    return conn.execute(sql, args).fetchall()


def tasks_all(
    conn: sqlite3.Connection,
    *,
    bucket: str | None = None,
    include_archived: bool = False,
    kinds: list[str] | None = None,
    promoted: bool = False,
    spec: str | None = None,
) -> list[sqlite3.Row]:
    """Tasks across ALL activities — backing `--all` flag and `octopus loops`."""
    sql = "SELECT * FROM tasks WHERE 1=1"
    args: list[Any] = []
    if bucket:
        sql += " AND bucket = ?"
        args.append(bucket)
    if not include_archived:
        sql += " AND (archived IS NULL OR archived = 0)"
    sql, args = _apply_promotion_filters(
        sql, args, kinds=kinds, promoted=promoted, spec=spec
    )
    sql += """
        ORDER BY
          CASE WHEN pinned = 1 THEN 0 ELSE 1 END,
          CASE priority
            WHEN 'urgent' THEN 0
            WHEN 'high' THEN 1
            WHEN 'low' THEN 3
            ELSE 2
          END,
          activity_id,
          due IS NULL, due,
          slug
    """
    return conn.execute(sql, args).fetchall()


def loops(
    conn: sqlite3.Connection,
    *,
    activity_id: str | None = None,
) -> list[sqlite3.Row]:
    """Open loops: bucket NOT IN (done, dropped) AND NOT archived.

    Scoped to one activity if given; else cross-activity.
    """
    sql = """
        SELECT * FROM tasks
        WHERE bucket NOT IN ('done', 'dropped')
          AND (archived IS NULL OR archived = 0)
    """
    args: list[Any] = []
    if activity_id:
        sql += " AND activity_id = ?"
        args.append(activity_id)
    sql += """
        ORDER BY
          CASE WHEN pinned = 1 THEN 0 ELSE 1 END,
          activity_id,
          CASE bucket
            WHEN 'now' THEN 0
            WHEN 'next' THEN 1
            WHEN 'backlog' THEN 2
            ELSE 3
          END,
          slug
    """
    return conn.execute(sql, args).fetchall()


def count_by_bucket(
    conn: sqlite3.Connection, activity_id: str
) -> dict[str, int]:
    """Task counts per bucket for one activity."""
    rows = conn.execute(
        """
        SELECT bucket, COUNT(*) as n FROM tasks
        WHERE activity_id = ?
          AND (archived IS NULL OR archived = 0)
        GROUP BY bucket
        """,
        (activity_id,),
    ).fetchall()
    return {row["bucket"]: row["n"] for row in rows}


def find_task_by_slug(
    conn: sqlite3.Connection,
    slug: str,
    *,
    activity_id: str | None = None,
) -> list[sqlite3.Row]:
    """Resolve a task by exact slug. If activity_id is given, scoped to it."""
    if activity_id:
        return conn.execute(
            "SELECT * FROM tasks WHERE activity_id = ? AND slug = ?",
            (activity_id, slug),
        ).fetchall()
    return conn.execute("SELECT * FROM tasks WHERE slug = ?", (slug,)).fetchall()


def total_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Total rows per table (used by empty-index detection)."""
    return {
        "activities": conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0],
        "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        "sessions": conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
    }

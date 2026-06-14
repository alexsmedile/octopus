"""Read-shaped queries for index-backed commands."""

from __future__ import annotations

import sqlite3
from typing import Any

# Columns returned by list-style task queries (tasks_for_activity, tasks_all, loops).
# Excludes raw_frontmatter — callers use the promoted columns (subtasks, blocked_by,
# waiting_for) instead of JSON-parsing the blob at render time.
_TASK_LIST_COLS = """
    id, activity_id, path, slug, title,
    bucket, stage, run_state, pinned, issue, archived,
    due, scheduled, start_date, end_date,
    priority, energy, actor, owner,
    kind, promoted_to, parent, subtasks, blocked_by, waiting_for,
    indexed_at
""".strip()


def list_activities(
    conn: sqlite3.Connection,
    *,
    statuses: list[str] | None = None,
    priorities: list[str] | None = None,
    types: list[str] | None = None,
    areas: list[str] | None = None,
    has_pinned: bool = False,
    has_overdue: bool = False,
    has_now: bool = False,
    touched_within_days: int | None = None,
    include_archived: bool = False,
    # legacy single-value params (kept for back-compat with #30 callers)
    status: str | None = None,
    type_: str | None = None,
    area: str | None = None,
) -> list[sqlite3.Row]:
    """Backing query for `octopus list` (cross-activity mode).

    D83: archived hidden by default. D27: rich filter flags.
    Multi-value filters (statuses/priorities/types/areas) accept lists;
    legacy singular params still work for older callers (#30 forget tests).
    """
    # Coerce singular legacy params into list form.
    if status and not statuses:
        statuses = [status]
    if type_ and not types:
        types = [type_]
    if area and not areas:
        areas = [area]

    sql = "SELECT a.* FROM activities a WHERE 1=1"
    args: list[Any] = []

    if statuses:
        placeholders = ",".join("?" * len(statuses))
        sql += f" AND a.status IN ({placeholders})"
        args.extend(statuses)
    elif not include_archived:
        # D83 — hide archived by default unless an explicit status filter overrides
        sql += " AND (a.status IS NULL OR a.status != 'archived')"

    if priorities:
        placeholders = ",".join("?" * len(priorities))
        sql += f" AND a.priority IN ({placeholders})"
        args.extend(priorities)

    if types:
        placeholders = ",".join("?" * len(types))
        sql += f" AND a.type IN ({placeholders})"
        args.extend(types)

    if areas:
        placeholders = ",".join("?" * len(areas))
        sql += f" AND a.area IN ({placeholders})"
        args.extend(areas)

    if has_pinned:
        sql += (
            " AND EXISTS (SELECT 1 FROM tasks t WHERE t.activity_id = a.id "
            "AND t.pinned = 1 AND (t.archived IS NULL OR t.archived = 0) "
            "AND t.bucket NOT IN ('done', 'dropped'))"
        )

    if has_overdue:
        sql += (
            " AND EXISTS (SELECT 1 FROM tasks t WHERE t.activity_id = a.id "
            "AND t.due IS NOT NULL AND t.due < date('now') "
            "AND (t.archived IS NULL OR t.archived = 0) "
            "AND t.bucket NOT IN ('done', 'dropped'))"
        )

    if has_now:
        sql += (
            " AND EXISTS (SELECT 1 FROM tasks t WHERE t.activity_id = a.id "
            "AND t.bucket = 'now' AND (t.archived IS NULL OR t.archived = 0))"
        )

    if touched_within_days is not None:
        sql += (
            " AND a.last_touched_at IS NOT NULL "
            "AND a.last_touched_at >= datetime('now', ?)"
        )
        args.append(f"-{int(touched_within_days)} days")

    sql += """
        ORDER BY
          CASE a.priority
            WHEN 'urgent' THEN 0
            WHEN 'high'   THEN 1
            WHEN 'low'    THEN 3
            ELSE 2
          END,
          a.last_touched_at IS NULL,
          a.last_touched_at DESC,
          a.title
    """
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

    Uses idx_tasks_activity_bucket to avoid a temp B-tree sort on every call.
    Excludes raw_frontmatter — callers use promoted columns (subtasks, blocked_by, waiting_for).
    """
    sql = f"SELECT {_TASK_LIST_COLS} FROM tasks WHERE activity_id = ?"
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
    """Tasks across ALL activities — backing `--all` flag and `octopus loops`.

    Uses idx_tasks_open partial index when no bucket filter or include_archived
    is set (the common case), avoiding a full table scan.
    """
    sql = f"SELECT {_TASK_LIST_COLS} FROM tasks WHERE 1=1"
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

    Uses idx_tasks_open partial index — no full table scan.
    Scoped to one activity if given; else cross-activity.
    """
    sql = f"""
        SELECT {_TASK_LIST_COLS} FROM tasks
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


def find_by_external_ref(
    conn: sqlite3.Connection, adapter: str, external_id: str
) -> str | None:
    """Look up a task by (adapter, external_id) via task_external_refs (D63).

    Returns the task_id or None. Fast indexed lookup — backs the pull
    pipeline's dedup check.
    """
    row = conn.execute(
        "SELECT task_id FROM task_external_refs WHERE adapter = ? AND external_id = ?",
        (adapter, external_id),
    ).fetchone()
    return row["task_id"] if row else None

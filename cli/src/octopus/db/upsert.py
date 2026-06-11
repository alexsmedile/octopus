"""Upsert / delete operations for the index.

Mutation verbs call these after a successful file write.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from datetime import date, datetime
from pathlib import Path
from typing import Any

from octopus.core.models import Activity, Task


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _to_jsonable(value: Any) -> Any:
    """Convert dataclass-friendly values into JSON primitives."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(x) for x in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def _activity_raw_frontmatter(activity: Activity) -> str:
    """Serialize the activity's frontmatter-bearing fields as JSON.

    Excludes runtime-only fields (folder_path, extra is merged in).
    """
    exclude = {"folder_path", "extra"}
    data: dict[str, Any] = {}
    for f in fields(activity):
        if f.name in exclude:
            continue
        value = getattr(activity, f.name)
        if value is None or value == [] or value == {}:
            continue
        data[f.name] = _to_jsonable(value)
    # Merge unknown frontmatter fields preserved on read
    for k, v in activity.extra.items():
        if k not in data:
            data[k] = _to_jsonable(v)
    return json.dumps(data, sort_keys=True)


def _task_raw_frontmatter(task: Task) -> str:
    """Serialize the task's frontmatter-bearing fields as JSON."""
    exclude = {"slug", "path", "extra"}
    data: dict[str, Any] = {}
    for f in fields(task):
        if f.name in exclude:
            continue
        value = getattr(task, f.name)
        if value is None or value is False or value == [] or value == {}:
            continue
        data[f.name] = _to_jsonable(value)
    for k, v in task.extra.items():
        if k not in data:
            data[k] = _to_jsonable(v)
    return json.dumps(data, sort_keys=True)


def upsert_activity(
    conn: sqlite3.Connection, activity: Activity, *, touch: bool = False,
) -> None:
    """Insert or update the activity row in the index.

    D88: pass `touch=True` to also bump `last_touched_at` to now. Used by
    `sync_task_after_write` and `sync_activity_after_write` to mark the
    activity as recently active. Plain reindex passes touch=False so it
    doesn't artificially refresh every row.
    """
    now = _now()
    conn.execute(
        """
        INSERT INTO activities (
            id, path, title, type, status, area, priority,
            created, last_reviewed, last_touched_at,
            raw_frontmatter, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            path = excluded.path,
            title = excluded.title,
            type = excluded.type,
            status = excluded.status,
            area = excluded.area,
            priority = excluded.priority,
            created = excluded.created,
            last_reviewed = excluded.last_reviewed,
            last_touched_at = COALESCE(excluded.last_touched_at, activities.last_touched_at),
            raw_frontmatter = excluded.raw_frontmatter,
            indexed_at = excluded.indexed_at
        """,
        (
            activity.id,
            activity.last_known_path,
            activity.title,
            activity.type,
            activity.status,
            activity.area,
            activity.priority,
            activity.created.isoformat() if activity.created else None,
            activity.last_reviewed.isoformat() if activity.last_reviewed else None,
            now if touch else None,
            _activity_raw_frontmatter(activity),
            now,
        ),
    )


def upsert_task(conn: sqlite3.Connection, activity_id: str, task: Task) -> None:
    """Insert or update the task row in the index."""
    if not task.slug:
        raise ValueError(f"task has empty slug: {task.title!r}")
    if not task.path:
        raise ValueError(f"task has no path: {task.slug!r}")

    task_id = f"{activity_id}/{task.slug}"
    conn.execute(
        """
        INSERT INTO tasks (
            id, activity_id, path, slug, title,
            bucket, stage, run_state, pinned, issue, archived,
            due, scheduled, start_date, end_date,
            priority, energy, actor, owner,
            kind, promoted_to, parent,
            raw_frontmatter, indexed_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            path = excluded.path,
            slug = excluded.slug,
            title = excluded.title,
            bucket = excluded.bucket,
            stage = excluded.stage,
            run_state = excluded.run_state,
            pinned = excluded.pinned,
            issue = excluded.issue,
            archived = excluded.archived,
            due = excluded.due,
            scheduled = excluded.scheduled,
            start_date = excluded.start_date,
            end_date = excluded.end_date,
            priority = excluded.priority,
            energy = excluded.energy,
            actor = excluded.actor,
            owner = excluded.owner,
            kind = excluded.kind,
            promoted_to = excluded.promoted_to,
            parent = excluded.parent,
            raw_frontmatter = excluded.raw_frontmatter,
            indexed_at = excluded.indexed_at
        """,
        (
            task_id,
            activity_id,
            str(task.path),
            task.slug,
            task.title,
            task.bucket,
            task.stage,
            task.run_state,
            1 if task.pinned else None,
            task.issue,
            1 if task.archived else None,
            task.due.isoformat() if task.due else None,
            task.scheduled.isoformat() if task.scheduled else None,
            task.start_date.isoformat() if task.start_date else None,
            task.end_date.isoformat() if task.end_date else None,
            task.priority,
            task.energy,
            task.actor,
            task.owner,
            task.kind,
            task.promoted_to,
            task.parent or None,
            _task_raw_frontmatter(task),
            _now(),
        ),
    )
    # D63: keep task_external_refs in sync. Delete all rows for this task,
    # then re-insert from the current frontmatter (handles add/remove/update).
    conn.execute("DELETE FROM task_external_refs WHERE task_id = ?", (task_id,))
    for adapter_name, external_id in (task.external_refs or {}).items():
        if not adapter_name or not external_id:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO task_external_refs "
            "(task_id, adapter, external_id) VALUES (?, ?, ?)",
            (task_id, str(adapter_name), str(external_id)),
        )


def upsert_session(
    conn: sqlite3.Connection,
    activity_id: str,
    *,
    filename: str,
    path: Path,
    title: str | None,
    started: datetime | None,
    ended: datetime | None,
    raw_frontmatter: dict[str, Any] | None = None,
) -> None:
    """Insert or update a session row. Sessions are read-only in v1 (request 04 adds verbs)."""
    session_id = f"{activity_id}/{filename}"
    conn.execute(
        """
        INSERT INTO sessions (
            id, activity_id, path, title, started, ended,
            raw_frontmatter, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            path = excluded.path,
            title = excluded.title,
            started = excluded.started,
            ended = excluded.ended,
            raw_frontmatter = excluded.raw_frontmatter,
            indexed_at = excluded.indexed_at
        """,
        (
            session_id,
            activity_id,
            str(path),
            title,
            started.isoformat(timespec="seconds") if started else None,
            ended.isoformat(timespec="seconds") if ended else None,
            json.dumps(_to_jsonable(raw_frontmatter or {}), sort_keys=True),
            _now(),
        ),
    )


def delete_by_path(conn: sqlite3.Connection, table: str, path: Path | str) -> int:
    """Delete row(s) whose `path` column equals the given path. Returns row count."""
    if table not in {"activities", "tasks", "sessions"}:
        raise ValueError(f"unknown table {table!r}")
    cur = conn.execute(f"DELETE FROM {table} WHERE path = ?", (str(path),))
    return cur.rowcount


def delete_task(conn: sqlite3.Connection, activity_id: str, slug: str) -> int:
    """Delete a task row by activity+slug. Returns row count."""
    cur = conn.execute(
        "DELETE FROM tasks WHERE activity_id = ? AND slug = ?", (activity_id, slug)
    )
    return cur.rowcount

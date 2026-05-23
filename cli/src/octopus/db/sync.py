"""High-level sync helpers used by the CLI verbs.

Centralizes the "after-mutation upsert" pattern so each verb doesn't have to
reach into db internals.
"""

from __future__ import annotations

from pathlib import Path

from octopus.core.models import Task
from octopus.db.connection import get_db
from octopus.db.upsert import (
    delete_by_path,
    upsert_activity,
    upsert_task,
)
from octopus.fs.io import read_activity


def sync_activity_after_write(folder: Path) -> str | None:
    """Upsert the activity row after a file write. Returns error message or None."""
    try:
        activity, _ = read_activity(folder / ".octopus" / "activity.md")
        conn = get_db()
        try:
            upsert_activity(conn, activity)
        finally:
            conn.close()
    except Exception as e:
        return f"index update failed: {e}"
    return None


def sync_task_after_write(activity_folder: Path, task: Task) -> str | None:
    """Upsert the task row after a file write. Returns error message or None."""
    try:
        activity, _ = read_activity(activity_folder / ".octopus" / "activity.md")
        conn = get_db()
        try:
            upsert_task(conn, activity.id, task)
        finally:
            conn.close()
    except Exception as e:
        return f"index update failed: {e}"
    return None


def sync_delete_task(task_path: Path) -> str | None:
    """Remove a task row when its file is gone (e.g. after archive-to-trash)."""
    try:
        conn = get_db()
        try:
            delete_by_path(conn, "tasks", task_path)
        finally:
            conn.close()
    except Exception as e:
        return f"index update failed: {e}"
    return None

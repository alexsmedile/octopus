"""Stale-check: file mtime > row indexed_at triggers refresh."""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

from octopus.core.models import Task
from octopus.db.stale import is_stale, prune_missing, refresh_rows
from octopus.db.upsert import upsert_activity, upsert_task
from octopus.fs.io import write_task
from octopus.fs.scaffold import init_activity


def _bump_mtime(path: Path, seconds: int = 5) -> None:
    future = time.time() + seconds
    os.utime(path, (future, future))


def test_is_stale_false_when_indexed_after_write(temp_db, tmp_path):
    """Writing the file *before* upsert means indexed_at >= mtime → not stale.

    We back-date the file mtime to make the assertion robust against
    indexed_at being second-truncated by `_now()` in upsert.
    """
    folder = tmp_path / "proj"
    folder.mkdir()
    activity = init_activity(folder, activity_type="code")
    upsert_activity(temp_db, activity)
    task_path = folder / ".octopus" / "tasks" / "backlog" / "a.md"
    t = Task(title="A", created=date(2026, 5, 1), bucket="backlog", slug="a", path=task_path)
    write_task(task_path, t, "")
    # Back-date the file so it is definitively older than indexed_at.
    past = time.time() - 60
    os.utime(task_path, (past, past))
    upsert_task(temp_db, activity.id, t)
    row = temp_db.execute("SELECT * FROM tasks").fetchone()
    assert is_stale(row) is False


def test_is_stale_true_after_touch(temp_db, tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    activity = init_activity(folder, activity_type="code")
    upsert_activity(temp_db, activity)
    task_path = folder / ".octopus" / "tasks" / "backlog" / "a.md"
    t = Task(title="A", created=date(2026, 5, 1), bucket="backlog", slug="a", path=task_path)
    write_task(task_path, t, "")
    upsert_task(temp_db, activity.id, t)

    _bump_mtime(task_path, seconds=60)
    row = temp_db.execute("SELECT * FROM tasks").fetchone()
    assert is_stale(row) is True


def test_refresh_rows_picks_up_hand_edit(temp_db, tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    activity = init_activity(folder, activity_type="code")
    upsert_activity(temp_db, activity)
    task_path = folder / ".octopus" / "tasks" / "backlog" / "a.md"
    t = Task(title="Original", created=date(2026, 5, 1), bucket="backlog", slug="a", path=task_path)
    write_task(task_path, t, "")
    upsert_task(temp_db, activity.id, t)

    # Hand-edit: change the title on disk
    t2 = Task(title="Hand-edited", created=date(2026, 5, 1), bucket="backlog", slug="a", path=task_path)
    write_task(task_path, t2, "")
    _bump_mtime(task_path, seconds=60)

    rows = temp_db.execute("SELECT * FROM tasks").fetchall()
    warnings = refresh_rows(temp_db, rows, kind="task")
    assert warnings == []
    row = temp_db.execute("SELECT title FROM tasks").fetchone()
    assert row["title"] == "Hand-edited"


def test_is_stale_true_when_file_missing(temp_db, tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    activity = init_activity(folder, activity_type="code")
    upsert_activity(temp_db, activity)
    task_path = folder / ".octopus" / "tasks" / "backlog" / "a.md"
    t = Task(title="A", created=date(2026, 5, 1), bucket="backlog", slug="a", path=task_path)
    write_task(task_path, t, "")
    upsert_task(temp_db, activity.id, t)

    task_path.unlink()
    row = temp_db.execute("SELECT * FROM tasks").fetchone()
    assert is_stale(row) is True

    warnings = refresh_rows(temp_db, [row], kind="task")
    assert len(warnings) == 1
    assert warnings[0][0] == "missing-source"
    # Row preserved (rule R) — not auto-deleted
    assert temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1


def test_prune_missing_removes_orphans(temp_db, tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    activity = init_activity(folder, activity_type="code")
    upsert_activity(temp_db, activity)
    task_path = folder / ".octopus" / "tasks" / "backlog" / "a.md"
    t = Task(title="A", created=date(2026, 5, 1), bucket="backlog", slug="a", path=task_path)
    write_task(task_path, t, "")
    upsert_task(temp_db, activity.id, t)

    task_path.unlink()
    counts = prune_missing(temp_db)
    assert counts["tasks"] == 1
    assert temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0

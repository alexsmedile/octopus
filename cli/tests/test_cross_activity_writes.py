"""Tests for #26 — cross-activity write verbs.

Covers:
- `octopus add task` and `add activity`
- `set` with --task and --activity multi-target + mutex rules (D84)
- `--activity` flag on write verbs (D86)
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from octopus.cli import app
from octopus.fs.io import read_task
from octopus.fs.scaffold import init_activity

runner = CliRunner()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "config"))
    import octopus.config
    import octopus.db.connection
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)
    yield tmp_path
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)


@pytest.fixture
def two_activities(isolated):
    a = isolated / "alpha"
    a.mkdir()
    init_activity(a, activity_type="code")
    b = isolated / "beta"
    b.mkdir()
    init_activity(b, activity_type="code")
    from octopus.db.connection import get_db
    from octopus.db.reindex import reindex_all
    conn = get_db()
    try:
        reindex_all(conn, [isolated])
    finally:
        conn.close()
    return a, b


def _ids(a: Path, b: Path) -> tuple[str, str]:
    from octopus.core.identify import resolve_activity
    return resolve_activity(str(a))["id"], resolve_activity(str(b))["id"]


# ── add task ──────────────────────────────────────────────────────────


def test_add_task_with_activity_targets_named_activity(two_activities, monkeypatch):
    a, b = two_activities
    a_id, b_id = _ids(a, b)
    monkeypatch.chdir(b)  # cwd is in beta, but we target alpha
    res = runner.invoke(app, ["add", "task", "from anywhere", "--activity", a_id])
    assert res.exit_code == 0, res.output
    # The new task should land in alpha's tasks/, not beta's.
    a_tasks = list((a / ".octopus" / "tasks").rglob("*.md"))
    b_tasks = list((b / ".octopus" / "tasks").rglob("*.md"))
    assert len(a_tasks) == 1
    assert len(b_tasks) == 0


def test_add_task_without_activity_uses_cwd(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["add", "task", "local capture"])
    assert res.exit_code == 0, res.output
    a_tasks = list((a / ".octopus" / "tasks").rglob("*.md"))
    assert len(a_tasks) == 1


def test_add_task_unknown_activity_errors(two_activities, monkeypatch, tmp_path):
    a, _b = two_activities
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["add", "task", "x", "--activity", "no-such-activity"])
    assert res.exit_code != 0
    assert "no activity matches" in res.output


def test_add_task_with_priority_and_now(two_activities, monkeypatch):
    a, _b = two_activities
    a_id, _ = _ids(a, _b)
    monkeypatch.chdir(_b)
    res = runner.invoke(
        app, ["add", "task", "urgent thing", "--activity", a_id, "--now", "--priority", "urgent"]
    )
    assert res.exit_code == 0, res.output
    files = list((a / ".octopus" / "tasks" / "now").glob("*.md"))
    assert len(files) == 1
    task, _ = read_task(files[0])
    assert task.bucket == "now"
    assert task.priority == "urgent"


# ── add activity ──────────────────────────────────────────────────────


def test_add_activity_creates_new_folder(isolated, monkeypatch):
    monkeypatch.chdir(isolated)
    res = runner.invoke(app, ["add", "activity", "fresh project"])
    assert res.exit_code == 0, res.output
    folder = isolated / "fresh-project"
    assert (folder / ".octopus" / "activity.md").is_file()


def test_add_activity_with_path(isolated, monkeypatch):
    target = isolated / "subdir" / "deep" / "myproj"
    monkeypatch.chdir(isolated)
    res = runner.invoke(app, ["add", "activity", "deep proj", "--path", str(target)])
    assert res.exit_code == 0, res.output
    assert (target / ".octopus" / "activity.md").is_file()


def test_add_activity_with_priority(isolated, monkeypatch):
    """D87: --priority is now valid on add activity (was stub-rejected in #26)."""
    from octopus.fs.io import read_activity
    monkeypatch.chdir(isolated)
    res = runner.invoke(app, ["add", "activity", "p1", "--priority", "high"])
    assert res.exit_code == 0, res.output
    act, _ = read_activity(isolated / "p1" / ".octopus" / "activity.md")
    assert act.priority == "high"


def test_add_activity_priority_invalid(isolated, monkeypatch):
    monkeypatch.chdir(isolated)
    res = runner.invoke(app, ["add", "activity", "x", "--priority", "medium"])
    assert res.exit_code != 0
    assert "low" in res.output


def test_add_activity_rejects_nested(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["add", "activity", "nested"])
    assert res.exit_code != 0
    assert "nested" in res.output.lower()


# ── set mutex rules (D84) ─────────────────────────────────────────────


def test_set_positional_plus_task_rejected(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["set", "slug1", "--task", "other", "--priority", "high"])
    assert res.exit_code != 0
    assert "mutually exclusive" in res.output


def test_set_positional_plus_activity_rejected(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["set", "slug1", "--activity", "a1", "--priority", "high"])
    assert res.exit_code != 0
    assert "mutually exclusive" in res.output


def test_set_task_plus_activity_rejected(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["set", "--task", "t1", "--activity", "a1", "--priority", "high"])
    assert res.exit_code != 0
    assert "mutually exclusive" in res.output


def test_set_no_target_rejected(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["set", "--priority", "high"])
    assert res.exit_code != 0
    assert "no target" in res.output


def test_set_multiple_positionals_rejected(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["set", "s1", "s2", "--priority", "high"])
    assert res.exit_code != 0
    assert "multiple positional" in res.output


def test_set_activity_rejects_task_only_flags(two_activities, monkeypatch):
    a, _b = two_activities
    a_id, _ = _ids(a, _b)
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["set", "--activity", a_id, "--bucket", "next"])
    assert res.exit_code != 0
    assert "task-only flag" in res.output
    assert "--bucket" in res.output


def test_set_task_level_rejects_activity_flags(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    # Create a task first so the slug resolves
    runner.invoke(app, ["add", "task", "demo"])
    res = runner.invoke(app, ["set", "demo", "--status", "on_hold"])
    assert res.exit_code != 0
    assert "activity-only" in res.output


# ── set --task multi-target ───────────────────────────────────────────


def test_set_task_multi_target_within_cwd(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    runner.invoke(app, ["add", "task", "first"])
    runner.invoke(app, ["add", "task", "second"])
    res = runner.invoke(app, ["set", "--task", "first", "--task", "second", "--priority", "high"])
    assert res.exit_code == 0, res.output
    files = list((a / ".octopus" / "tasks").rglob("*.md"))
    assert len(files) == 2
    for f in files:
        task, _ = read_task(f)
        assert task.priority == "high"


def test_set_task_multi_unknown_slug_partial_fail(two_activities, monkeypatch):
    a, _b = two_activities
    monkeypatch.chdir(a)
    runner.invoke(app, ["add", "task", "exists"])
    res = runner.invoke(app, ["set", "--task", "exists", "--task", "does-not-exist", "--priority", "high"])
    # Exits non-zero overall, but the valid target still gets updated.
    assert res.exit_code != 0
    f = next((a / ".octopus" / "tasks").rglob("exists.md"))
    task, _ = read_task(f)
    assert task.priority == "high"


def test_set_positional_outside_activity_errors(isolated, monkeypatch):
    monkeypatch.chdir(isolated)
    res = runner.invoke(app, ["set", "some-slug", "--priority", "high"])
    assert res.exit_code != 0
    assert "not inside" in res.output


# ── set --activity multi-target ───────────────────────────────────────


def test_set_activity_multi_target_status(two_activities, monkeypatch, tmp_path):
    a, b = two_activities
    a_id, b_id = _ids(a, b)
    monkeypatch.chdir(tmp_path)  # outside both
    res = runner.invoke(
        app, ["set", "--activity", a_id, "--activity", b_id, "--status", "paused"]
    )
    assert res.exit_code == 0, res.output
    from octopus.fs.io import read_activity
    for root in (a, b):
        act, _ = read_activity(root / ".octopus" / "activity.md")
        assert act.status == "paused"


def test_set_activity_priority_now_works(two_activities, monkeypatch):
    """D87: --priority on set --activity is implemented (was stubbed in #26)."""
    from octopus.fs.io import read_activity
    a, _b = two_activities
    a_id, _ = _ids(a, _b)
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["set", "--activity", a_id, "--priority", "high"])
    assert res.exit_code == 0, res.output
    act, _ = read_activity(a / ".octopus" / "activity.md")
    assert act.priority == "high"

    # Clear it via explicit-default
    res = runner.invoke(app, ["set", "--activity", a_id, "--priority", "normal"])
    assert res.exit_code == 0, res.output
    act, _ = read_activity(a / ".octopus" / "activity.md")
    assert act.priority is None


# ── --activity flag on other write verbs (D86) ────────────────────────


def test_pin_with_activity_from_outside(two_activities, monkeypatch, tmp_path):
    a, _b = two_activities
    a_id, _ = _ids(a, _b)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["add", "task", "pinme", "--activity", a_id])
    res = runner.invoke(app, ["pin", "pinme", "--activity", a_id])
    assert res.exit_code == 0, res.output
    f = next((a / ".octopus" / "tasks").rglob("pinme.md"))
    task, _ = read_task(f)
    assert task.pinned is True


def test_finish_with_activity(two_activities, monkeypatch, tmp_path):
    a, _b = two_activities
    a_id, _ = _ids(a, _b)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["add", "task", "ship-it", "--activity", a_id])
    res = runner.invoke(app, ["finish", "ship-it", "--activity", a_id])
    assert res.exit_code == 0, res.output
    f = next((a / ".octopus" / "tasks").rglob("ship-it.md"))
    task, _ = read_task(f)
    assert task.bucket == "done"
    assert task.end_date is not None


def test_plan_with_activity(two_activities, monkeypatch, tmp_path):
    a, _b = two_activities
    a_id, _ = _ids(a, _b)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["add", "task", "doit", "--activity", a_id])
    res = runner.invoke(app, ["plan", "doit", "--activity", a_id])
    assert res.exit_code == 0, res.output
    f = next((a / ".octopus" / "tasks").rglob("doit.md"))
    task, _ = read_task(f)
    assert task.bucket == "next"

"""Tests for octopus.actions — the shared mutation layer for CLI + TUI."""

from __future__ import annotations

from pathlib import Path

import pytest

from octopus import actions
from octopus.actions import ActionError
from octopus.fs.io import read_task
from octopus.fs.scaffold import init_activity


@pytest.fixture
def activity(tmp_path: Path) -> Path:
    init_activity(tmp_path, title="test", activity_type="other")
    return tmp_path


def test_capture_creates_task_in_backlog_by_default(activity: Path) -> None:
    r = actions.capture_task(activity, "Ship the TUI")
    assert r.bucket == "backlog"
    assert r.path.is_file()
    task, _ = read_task(r.path)
    assert task.title == "Ship the TUI"
    assert task.bucket == "backlog"


def test_capture_now_does_not_auto_pin(activity: Path) -> None:
    """Capture into NOW must not pin — pin is a separate axis (AXIS-MODEL §ATTENTION)."""
    r = actions.capture_task(activity, "Right now thing", bucket="now")
    task, _ = read_task(r.path)
    assert task.bucket == "now"
    assert task.pinned is None


def test_capture_rejects_empty_title(activity: Path) -> None:
    with pytest.raises(ActionError, match="title is required"):
        actions.capture_task(activity, "   ")


def test_capture_handles_slug_collision(activity: Path) -> None:
    r1 = actions.capture_task(activity, "alpha")
    r2 = actions.capture_task(activity, "alpha")
    assert r1.slug != r2.slug
    assert r1.path.is_file() and r2.path.is_file()


def test_start_task(activity: Path) -> None:
    cap = actions.capture_task(activity, "go", bucket="now")
    res = actions.start_task(activity, cap.slug)
    assert res.message == "started"
    task, _ = read_task(actions.find_task_file(activity / ".octopus", "folders", cap.slug))
    assert task.start_date is not None


def test_start_idempotent(activity: Path) -> None:
    cap = actions.capture_task(activity, "go", bucket="now")
    actions.start_task(activity, cap.slug)
    res2 = actions.start_task(activity, cap.slug)
    assert "already started" in res2.message


def test_start_resumes_terminal(activity: Path) -> None:
    cap = actions.capture_task(activity, "go", bucket="now")
    actions.finish_task(activity, cap.slug)
    res = actions.start_task(activity, cap.slug)
    assert res.message == "resumed"
    assert res.bucket == "now"


def test_finish_clears_axes(activity: Path) -> None:
    cap = actions.capture_task(activity, "go", bucket="now")
    actions.start_task(activity, cap.slug)
    actions.finish_task(activity, cap.slug)
    path = actions.find_task_file(activity / ".octopus", "folders", cap.slug)
    task, _ = read_task(path)
    assert task.bucket == "done"
    assert task.pinned is None
    assert task.end_date is not None


def test_drop(activity: Path) -> None:
    cap = actions.capture_task(activity, "doomed")
    actions.drop_task(activity, cap.slug)
    path = actions.find_task_file(activity / ".octopus", "folders", cap.slug)
    task, _ = read_task(path)
    assert task.bucket == "dropped"
    assert task.end_date is not None


def test_move_task(activity: Path) -> None:
    cap = actions.capture_task(activity, "thing")  # backlog
    res = actions.move_task(activity, cap.slug, "next")
    assert res.bucket == "next"
    path = actions.find_task_file(activity / ".octopus", "folders", cap.slug)
    task, _ = read_task(path)
    assert task.bucket == "next"


def test_move_next_pipeline(activity: Path) -> None:
    cap = actions.capture_task(activity, "thing")
    actions.move_next(activity, cap.slug)  # backlog → next
    actions.move_next(activity, cap.slug)  # next → now
    path = actions.find_task_file(activity / ".octopus", "folders", cap.slug)
    task, _ = read_task(path)
    assert task.bucket == "now"


def test_move_next_terminal_raises(activity: Path) -> None:
    cap = actions.capture_task(activity, "thing", bucket="now")
    actions.finish_task(activity, cap.slug)
    with pytest.raises(ActionError, match="cannot advance"):
        actions.move_next(activity, cap.slug)


def test_toggle_pin(activity: Path) -> None:
    cap = actions.capture_task(activity, "thing")
    actions.toggle_pin(activity, cap.slug)
    path = actions.find_task_file(activity / ".octopus", "folders", cap.slug)
    assert read_task(path)[0].pinned is True
    actions.toggle_pin(activity, cap.slug)
    assert read_task(path)[0].pinned is None


def test_pin_terminal_raises(activity: Path) -> None:
    cap = actions.capture_task(activity, "thing", bucket="now")
    actions.finish_task(activity, cap.slug)
    with pytest.raises(ActionError, match="cannot pin"):
        actions.pin_task(activity, cap.slug)


def test_missing_task_raises(activity: Path) -> None:
    with pytest.raises(ActionError, match="task not found"):
        actions.start_task(activity, "nope")

"""Round-trip + default-omission tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from octopus.core.models import Task
from octopus.fs.io import read_task, write_task
from octopus.fs.scaffold import init_activity


def test_init_creates_valid_activity(tmp_path: Path):
    folder = tmp_path / "proj"
    folder.mkdir()
    activity = init_activity(folder, title="Test Project", activity_type="code")
    assert (folder / ".octopus" / "activity.md").is_file()
    assert (folder / ".octopus" / "tasks" / "backlog").is_dir()
    assert (folder / ".octopus" / "tasks" / "done").is_dir()
    assert (folder / ".octopus" / "tasks" / "dropped").is_dir()
    # ID slug derives from folder name, not title
    assert activity.id.startswith("proj-")


def test_task_roundtrip(tmp_path: Path):
    folder = tmp_path / "proj"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    task = Task(
        title="Fix the bug",
        created=date(2026, 5, 22),
        bucket="next",
        priority="urgent",
        tags=["urgent", "auth"],
    )
    task_path = folder / ".octopus" / "tasks" / "next" / "fix-the-bug.md"
    body = "\nSome body content.\n\n## References\n"
    write_task(task_path, task, body)
    loaded, _ = read_task(task_path)
    assert loaded.title == task.title
    assert loaded.created == task.created
    assert loaded.bucket == task.bucket
    assert loaded.priority == task.priority
    assert loaded.tags == task.tags


def test_default_omission_minimal_capture(tmp_path: Path):
    """A capture with all defaults produces 3-line frontmatter (title, created, bucket)."""
    folder = tmp_path / "proj"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    task = Task(title="Minimal", created=date(2026, 5, 23))
    task_path = folder / ".octopus" / "tasks" / "backlog" / "minimal.md"
    write_task(task_path, task, "\n")
    content = task_path.read_text(encoding="utf-8")
    # Required: title, created, bucket
    assert "title: Minimal" in content
    assert "created:" in content
    assert "bucket: backlog" in content
    # Default-omitted: actor, priority, tags, pinned, archived
    assert "actor:" not in content
    assert "priority:" not in content
    assert "tags:" not in content
    assert "pinned:" not in content
    assert "archived:" not in content


def test_actor_written_when_not_human(tmp_path: Path):
    folder = tmp_path / "proj"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    task = Task(title="Bot task", created=date(2026, 5, 23), actor="ai")
    task_path = folder / ".octopus" / "tasks" / "backlog" / "bot.md"
    write_task(task_path, task, "\n")
    assert "actor: ai" in task_path.read_text(encoding="utf-8")


def test_pinned_only_when_true(tmp_path: Path):
    folder = tmp_path / "proj"
    folder.mkdir()
    init_activity(folder, activity_type="code")

    # pinned: True written
    t1 = Task(title="Pinned task", created=date(2026, 5, 23), bucket="now", pinned=True)
    p1 = folder / ".octopus" / "tasks" / "now" / "pinned.md"
    write_task(p1, t1, "\n")
    assert "pinned: true" in p1.read_text(encoding="utf-8")

    # pinned: None omitted (use a title that doesn't contain "pinned")
    t2 = Task(title="Just a task", created=date(2026, 5, 23), bucket="now", pinned=None)
    p2 = folder / ".octopus" / "tasks" / "now" / "just-a-task.md"
    write_task(p2, t2, "\n")
    assert "pinned" not in p2.read_text(encoding="utf-8")


def test_unknown_frontmatter_preserved(tmp_path: Path):
    """Unknown keys round-trip; legacy keys get stripped."""
    folder = tmp_path / "proj"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    task_path = folder / ".octopus" / "tasks" / "backlog" / "test.md"
    task_path.write_text(
        "---\n"
        "title: Test\n"
        "created: 2026-05-22\n"
        "bucket: backlog\n"
        "future_field: future_value\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    task, body = read_task(task_path)
    assert "future_field" in task.extra
    write_task(task_path, task, body)
    content = task_path.read_text(encoding="utf-8")
    assert "future_field: future_value" in content


def test_legacy_status_field_in_file_surfaces_error(tmp_path: Path):
    folder = tmp_path / "proj"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    task_path = folder / ".octopus" / "tasks" / "backlog" / "legacy.md"
    task_path.write_text(
        "---\n"
        "title: Legacy\n"
        "created: 2026-05-22\n"
        "bucket: backlog\n"
        "status: doing\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    task, _ = read_task(task_path)
    errors = task.validate()
    assert any("legacy field 'status'" in e for e in errors)

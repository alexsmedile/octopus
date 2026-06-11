"""Tests for the subtask feature (D104).

Covers:
- capture --parent: attach on creation, depth guard, parent-not-found
- set --parent <slug>: attach
- set --parent "": detach
- subtasks <slug>: list children
- finish --force / --cascade: open-children guard
- drop --force / --cascade: open-children guard
- actions: attach_subtask, detach_subtask, list_subtasks, _sync_subtasks_list
- model validation: depth limit, cross-activity, parent+subtasks conflict
- lint rules: subtask-depth, subtask-orphan, subtask-cross-activity
- TODO.md adapter: indented checkbox → suggested_parent
"""

from __future__ import annotations

from pathlib import Path

import pytest

import importlib

from typer.testing import CliRunner

from octopus.cli import app
from octopus.core.models import Task
from octopus.fs.io import read_task
from octopus.fs.scaffold import init_activity

runner = CliRunner()

# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated DB + config environment."""
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
def act(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Single activity scaffold; chdir so --activity is not needed."""
    root = isolated / "alpha"
    root.mkdir()
    init_activity(root, activity_type="code")
    from octopus.db.connection import get_db
    from octopus.db.reindex import reindex_all
    conn = get_db()
    try:
        reindex_all(conn, [isolated])
    finally:
        conn.close()
    monkeypatch.chdir(root)
    return root


def _slug_path(act: Path, slug: str) -> Path | None:
    from octopus.actions import find_task_file
    from octopus.fs.scaffold import read_storage_mode
    octopus_dir = act / ".octopus"
    mode = read_storage_mode(octopus_dir)
    return find_task_file(octopus_dir, mode, slug)


def _read(act: Path, slug: str) -> Task:
    p = _slug_path(act, slug)
    assert p is not None, f"task not found: {slug}"
    task, _ = read_task(p)
    return task


# ── capture --parent ──────────────────────────────────────────────────


def test_capture_with_parent_sets_field(act: Path) -> None:
    runner.invoke(app, ["add", "task", "parent-task"])
    res = runner.invoke(app, ["add", "task", "child-task", "--parent", "parent-task"])
    assert res.exit_code == 0, res.output

    child = _read(act, "child-task")
    assert child.parent == "parent-task"

    parent = _read(act, "parent-task")
    assert "child-task" in parent.subtasks


def test_capture_parent_not_found_exits(act: Path) -> None:
    res = runner.invoke(app, ["add", "task", "orphan", "--parent", "nonexistent"])
    assert res.exit_code != 0


def test_capture_depth_guard_rejects_grandchild(act: Path) -> None:
    runner.invoke(app, ["add", "task", "grandparent"])
    runner.invoke(app, ["add", "task", "child", "--parent", "grandparent"])
    res = runner.invoke(app, ["add", "task", "grandchild", "--parent", "child"])
    assert res.exit_code != 0


def test_capture_multiple_children(act: Path) -> None:
    runner.invoke(app, ["add", "task", "parent"])
    runner.invoke(app, ["add", "task", "first-child", "--parent", "parent"])
    runner.invoke(app, ["add", "task", "second-child", "--parent", "parent"])
    parent = _read(act, "parent")
    assert set(parent.subtasks) == {"first-child", "second-child"}


# ── set --parent attach ───────────────────────────────────────────────


def test_set_parent_attaches(act: Path) -> None:
    runner.invoke(app, ["add", "task", "base-parent"])
    runner.invoke(app, ["add", "task", "base-child"])
    res = runner.invoke(app, ["set", "base-child", "--parent", "base-parent"])
    assert res.exit_code == 0, res.output

    child = _read(act, "base-child")
    assert child.parent == "base-parent"

    parent = _read(act, "base-parent")
    assert "base-child" in parent.subtasks


def test_set_parent_rejects_cross_activity_slash(act: Path) -> None:
    runner.invoke(app, ["add", "task", "task-a"])
    res = runner.invoke(app, ["set", "task-a", "--parent", "other/task"])
    assert res.exit_code != 0


def test_set_parent_rejects_depth_exceeded(act: Path) -> None:
    runner.invoke(app, ["add", "task", "gp"])
    runner.invoke(app, ["add", "task", "child", "--parent", "gp"])
    runner.invoke(app, ["add", "task", "new-task"])
    res = runner.invoke(app, ["set", "new-task", "--parent", "child"])
    assert res.exit_code != 0


# ── set --parent "" detach ────────────────────────────────────────────


def test_set_parent_empty_detaches(act: Path) -> None:
    runner.invoke(app, ["add", "task", "base"])
    runner.invoke(app, ["add", "task", "attached", "--parent", "base"])

    res = runner.invoke(app, ["set", "attached", "--parent", ""])
    assert res.exit_code == 0, res.output

    child = _read(act, "attached")
    assert child.parent is None

    parent = _read(act, "base")
    assert "attached" not in parent.subtasks


def test_detach_idempotent(act: Path) -> None:
    runner.invoke(app, ["add", "task", "solo"])
    res = runner.invoke(app, ["set", "solo", "--parent", ""])
    assert res.exit_code == 0, res.output


# ── subtasks list ─────────────────────────────────────────────────────


def test_subtasks_command_lists_children(act: Path) -> None:
    runner.invoke(app, ["add", "task", "hub"])
    runner.invoke(app, ["add", "task", "spoke-one", "--parent", "hub"])
    runner.invoke(app, ["add", "task", "spoke-two", "--parent", "hub"])

    res = runner.invoke(app, ["subtasks", "hub"])
    assert res.exit_code == 0, res.output
    assert "spoke-one" in res.output
    assert "spoke-two" in res.output


def test_subtasks_command_no_children_message(act: Path) -> None:
    runner.invoke(app, ["add", "task", "lone"])
    res = runner.invoke(app, ["subtasks", "lone"])
    assert res.exit_code == 0
    assert "no subtasks" in res.output


def test_subtasks_command_nonexistent_parent(act: Path) -> None:
    res = runner.invoke(app, ["subtasks", "ghost"])
    assert res.exit_code != 0


# ── finish guard ──────────────────────────────────────────────────────


def test_finish_blocked_by_open_children(act: Path) -> None:
    runner.invoke(app, ["add", "task", "epic"])
    runner.invoke(app, ["add", "task", "story", "--parent", "epic"])

    res = runner.invoke(app, ["finish", "epic"])
    assert res.exit_code != 0
    assert "story" in res.output or "subtask" in res.output.lower()


def test_finish_force_ignores_open_children(act: Path) -> None:
    runner.invoke(app, ["add", "task", "big"])
    runner.invoke(app, ["add", "task", "small", "--parent", "big"])

    res = runner.invoke(app, ["finish", "big", "--force"])
    assert res.exit_code == 0, res.output

    parent = _read(act, "big")
    assert parent.bucket == "done"
    # child is untouched
    child = _read(act, "small")
    assert child.bucket != "done"


def test_finish_cascade_finishes_children_first(act: Path) -> None:
    runner.invoke(app, ["add", "task", "feature"])
    runner.invoke(app, ["add", "task", "task-1", "--parent", "feature"])
    runner.invoke(app, ["add", "task", "task-2", "--parent", "feature"])

    res = runner.invoke(app, ["finish", "feature", "--cascade"])
    assert res.exit_code == 0, res.output

    assert _read(act, "task-1").bucket == "done"
    assert _read(act, "task-2").bucket == "done"
    assert _read(act, "feature").bucket == "done"


def test_finish_no_guard_when_no_children(act: Path) -> None:
    runner.invoke(app, ["add", "task", "standalone"])
    res = runner.invoke(app, ["finish", "standalone"])
    assert res.exit_code == 0, res.output


# ── drop guard ────────────────────────────────────────────────────────


def test_drop_blocked_by_open_children(act: Path) -> None:
    runner.invoke(app, ["add", "task", "project"])
    runner.invoke(app, ["add", "task", "sub", "--parent", "project"])

    res = runner.invoke(app, ["drop", "project"])
    assert res.exit_code != 0


def test_drop_force_drops_parent_only(act: Path) -> None:
    runner.invoke(app, ["add", "task", "parent"])
    runner.invoke(app, ["add", "task", "kid", "--parent", "parent"])

    res = runner.invoke(app, ["drop", "parent", "--force"])
    assert res.exit_code == 0, res.output

    assert _read(act, "parent").bucket == "dropped"
    assert _read(act, "kid").bucket != "dropped"


def test_drop_cascade_drops_children_first(act: Path) -> None:
    runner.invoke(app, ["add", "task", "initiative"])
    runner.invoke(app, ["add", "task", "sub-one", "--parent", "initiative"])
    runner.invoke(app, ["add", "task", "sub-two", "--parent", "initiative"])

    res = runner.invoke(app, ["drop", "initiative", "--cascade"])
    assert res.exit_code == 0, res.output

    assert _read(act, "sub-one").bucket == "dropped"
    assert _read(act, "sub-two").bucket == "dropped"
    assert _read(act, "initiative").bucket == "dropped"


# ── end alias ─────────────────────────────────────────────────────────


def test_end_alias_respects_cascade(act: Path) -> None:
    runner.invoke(app, ["add", "task", "epic2"])
    runner.invoke(app, ["add", "task", "story2", "--parent", "epic2"])

    res = runner.invoke(app, ["end", "epic2", "--cascade"])
    assert res.exit_code == 0, res.output
    assert _read(act, "story2").bucket == "done"
    assert _read(act, "epic2").bucket == "done"


# ── actions unit tests ────────────────────────────────────────────────


def test_actions_attach_detach_roundtrip(act: Path) -> None:
    from octopus import actions

    runner.invoke(app, ["add", "task", "p"])
    runner.invoke(app, ["add", "task", "c"])

    actions.attach_subtask(act, "c", "p")
    assert _read(act, "c").parent == "p"
    assert "c" in _read(act, "p").subtasks

    actions.detach_subtask(act, "c")
    assert _read(act, "c").parent is None
    assert "c" not in _read(act, "p").subtasks


def test_actions_attach_parent_not_found(act: Path) -> None:
    from octopus import actions
    runner.invoke(app, ["add", "task", "orphan-c"])
    with pytest.raises(actions.ActionError, match="parent task not found"):
        actions.attach_subtask(act, "orphan-c", "ghost-p")


def test_actions_attach_parent_itself_a_child(act: Path) -> None:
    from octopus import actions
    runner.invoke(app, ["add", "task", "root"])
    runner.invoke(app, ["add", "task", "mid", "--parent", "root"])
    runner.invoke(app, ["add", "task", "leaf"])
    with pytest.raises(actions.ActionError, match="nesting depth"):
        actions.attach_subtask(act, "leaf", "mid")


def test_actions_attach_child_already_has_subtasks(act: Path) -> None:
    from octopus import actions
    runner.invoke(app, ["add", "task", "a"])
    runner.invoke(app, ["add", "task", "b"])
    runner.invoke(app, ["add", "task", "c", "--parent", "b"])
    with pytest.raises(actions.ActionError, match="already has subtasks"):
        actions.attach_subtask(act, "b", "a")


def test_actions_list_subtasks(act: Path) -> None:
    from octopus import actions
    runner.invoke(app, ["add", "task", "hub2"])
    runner.invoke(app, ["add", "task", "arm-1", "--parent", "hub2"])
    runner.invoke(app, ["add", "task", "arm-2", "--parent", "hub2"])

    children = actions.list_subtasks(act, "hub2")
    slugs = {c.slug for c in children}
    assert slugs == {"arm-1", "arm-2"}


def test_actions_open_subtasks_warning_message(act: Path) -> None:
    from octopus import actions
    runner.invoke(app, ["add", "task", "p2"])
    runner.invoke(app, ["add", "task", "c2", "--parent", "p2"])

    result = actions.finish_task(act, "p2")
    assert isinstance(result, actions.OpenSubtasksWarning)
    assert "c2" in result.message
    assert "--force" in result.message or "--cascade" in result.message


# ── model validation ──────────────────────────────────────────────────


def test_model_parent_with_slash_is_invalid() -> None:
    t = Task(title="t", created=__import__("datetime").date.today(), bucket="backlog",
             parent="other-activity/task")
    errors = t.validate()
    assert any("cross-activity" in e for e in errors)


def test_model_parent_empty_string_is_invalid() -> None:
    t = Task(title="t", created=__import__("datetime").date.today(), bucket="backlog",
             parent="")
    errors = t.validate()
    assert any("empty" in e for e in errors)


def test_model_parent_and_subtasks_conflict() -> None:
    t = Task(title="t", created=__import__("datetime").date.today(), bucket="backlog",
             parent="some-parent", subtasks=["child-a"])
    errors = t.validate()
    assert any("cannot be both" in e for e in errors)


# ── lint rules ────────────────────────────────────────────────────────


def test_lint_subtask_depth_fires_when_both_set(tmp_path: Path) -> None:
    from octopus.lint import lint_activity
    from octopus.lint.findings import Severity

    act = _build_lint_activity(tmp_path)
    _write_lint_task(act, "backlog", "bad-task", {
        "parent": "some-parent",
        "subtasks": ["child-x"],
    })
    report = lint_activity(act, rule_codes=["subtask-depth"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.ERROR


def test_lint_subtask_depth_clean(tmp_path: Path) -> None:
    from octopus.lint import lint_activity

    act = _build_lint_activity(tmp_path)
    _write_lint_task(act, "backlog", "parent-only", {"subtasks": ["c1"]})
    _write_lint_task(act, "backlog", "child-only", {"parent": "parent-only"})
    report = lint_activity(act, rule_codes=["subtask-depth"])
    assert report.findings == []


def test_lint_subtask_orphan_fires_for_missing_parent(tmp_path: Path) -> None:
    from octopus.lint import lint_activity
    from octopus.lint.findings import Severity

    act = _build_lint_activity(tmp_path)
    _write_lint_task(act, "backlog", "orphan", {"parent": "ghost-parent"})
    report = lint_activity(act, rule_codes=["subtask-orphan"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.WARN


def test_lint_subtask_orphan_clean_when_parent_exists(tmp_path: Path) -> None:
    from octopus.lint import lint_activity

    act = _build_lint_activity(tmp_path)
    _write_lint_task(act, "backlog", "real-parent", {})
    _write_lint_task(act, "backlog", "real-child", {"parent": "real-parent"})
    report = lint_activity(act, rule_codes=["subtask-orphan"])
    assert report.findings == []


def test_lint_subtask_cross_activity_fires_for_slash(tmp_path: Path) -> None:
    from octopus.lint import lint_activity
    from octopus.lint.findings import Severity

    act = _build_lint_activity(tmp_path)
    _write_lint_task(act, "backlog", "cross", {"parent": "other-act/some-task"})
    report = lint_activity(act, rule_codes=["subtask-cross-activity"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.ERROR


def test_lint_subtask_cross_activity_clean_for_normal(tmp_path: Path) -> None:
    from octopus.lint import lint_activity

    act = _build_lint_activity(tmp_path)
    _write_lint_task(act, "backlog", "normal", {"parent": "sibling-task"})
    report = lint_activity(act, rule_codes=["subtask-cross-activity"])
    assert report.findings == []


def _build_lint_activity(tmp_path: Path) -> Path:
    """Minimal activity scaffold for lint tests."""
    root = tmp_path / "lint-act"
    octo = root / ".octopus"
    octo.mkdir(parents=True)
    (octo / "activity.md").write_text(
        "---\nid: lint-aaaa\ntitle: lint\ntype: other\nstatus: active\n"
        "spec_version: 1\nlast_known_path: /tmp/lint\n---\n",
        encoding="utf-8",
    )
    tasks = octo / "tasks"
    for b in ("now", "next", "backlog", "done", "dropped"):
        (tasks / b).mkdir(parents=True)
    return root


def _write_lint_task(
    activity_root: Path,
    bucket: str,
    slug: str,
    extra: dict | None = None,
) -> Path:
    """Write a minimal task file for lint tests."""
    import yaml as _yaml  # noqa: PLC0415 — local import for test helper

    path = activity_root / ".octopus" / "tasks" / bucket / f"{slug}.md"
    fm: dict = {"title": slug, "created": "2026-05-26", "bucket": bucket}
    fm.update(extra or {})
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines += ["---", ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── TODO.md adapter: indented checkboxes → suggested_parent ──────────


def test_todo_md_indented_checkbox_gets_suggested_parent() -> None:
    from octopus.adapters.todo_md import _parse_todo_md as parse_todo_md

    content = """\
- [ ] parent task
  - [ ] child task a
  - [ ] child task b
"""
    tasks = parse_todo_md(content)
    assert len(tasks) == 3

    parent_et = tasks[0]
    child_a = tasks[1]
    child_b = tasks[2]

    assert parent_et.suggested_parent is None
    assert child_a.suggested_parent == parent_et.external_id.split("#")[-1]
    assert child_b.suggested_parent == parent_et.external_id.split("#")[-1]


def test_todo_md_top_level_items_no_parent() -> None:
    from octopus.adapters.todo_md import _parse_todo_md as parse_todo_md

    content = """\
- [ ] task one
- [ ] task two
- [ ] task three
"""
    tasks = parse_todo_md(content)
    assert all(t.suggested_parent is None for t in tasks)


def test_todo_md_indented_after_section_heading_resets_parent() -> None:
    from octopus.adapters.todo_md import _parse_todo_md as parse_todo_md

    content = """\
## Section A

- [ ] parent a

## Section B

  - [ ] this looks indented but parent reset at heading
"""
    tasks = parse_todo_md(content)
    # The indented item under Section B has no parent (heading reset tracking)
    indented = next(t for t in tasks if "looks indented" in t.title)
    assert indented.suggested_parent is None


def test_todo_md_deeper_indent_treated_as_child_of_last_top_level() -> None:
    from octopus.adapters.todo_md import _parse_todo_md as parse_todo_md

    content = """\
- [ ] top
  - [ ] nested one level
    - [ ] nested two levels (treated as child of top)
"""
    tasks = parse_todo_md(content)
    # Both indented items get suggested_parent = slug of "top"
    top_slug = tasks[0].external_id.split("#")[-1]
    assert tasks[1].suggested_parent == top_slug
    # Deeper nesting also links to the last top-level (depth limit 1)
    assert tasks[2].suggested_parent == top_slug


def test_todo_md_mixed_top_and_child_items() -> None:
    from octopus.adapters.todo_md import _parse_todo_md as parse_todo_md

    content = """\
- [ ] project alpha
  - [ ] alpha sub 1
  - [ ] alpha sub 2
- [ ] project beta
  - [ ] beta sub 1
"""
    tasks = parse_todo_md(content)
    assert len(tasks) == 5

    alpha_slug = tasks[0].external_id.split("#")[-1]
    beta_slug = tasks[3].external_id.split("#")[-1]

    assert tasks[1].suggested_parent == alpha_slug
    assert tasks[2].suggested_parent == alpha_slug
    assert tasks[4].suggested_parent == beta_slug

"""Tests for #24 (capture/edit polish) CLI behavior end-to-end.

Covers:
- D76 tag flag matrix on capture + set
- D77 set --bucket is frontmatter-only; mv moves the file
- D78 set --slug cascading rename
- D79 octopus refs find
- D80 explicit-default values clear instead of reject
- D81 capture --now no longer auto-pins
- D82 empty body on capture
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from octopus.cli import app
from octopus.fs.io import read_task
from octopus.fs.scaffold import init_activity


runner = CliRunner()


@pytest.fixture
def activity(tmp_path: Path, monkeypatch):
    """Activity with isolated config + data dirs, cwd inside it."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "config"))
    import importlib

    import octopus.config
    import octopus.db.connection

    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)

    act = tmp_path / "act"
    act.mkdir()
    init_activity(act, activity_type="code")
    monkeypatch.chdir(act)
    yield act
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)


# ── D82: empty body on capture ────────────────────────────────────────


def test_capture_default_body_is_empty(activity: Path):
    result = runner.invoke(app, ["capture", "foo bar"])
    assert result.exit_code == 0
    task, body = read_task(activity / ".octopus" / "tasks" / "backlog" / "foo-bar.md")
    assert body == ""


def test_capture_no_references_heading(activity: Path):
    """D82: no more hardcoded `## References` heading."""
    runner.invoke(app, ["capture", "foo"])
    text = (activity / ".octopus" / "tasks" / "backlog" / "foo.md").read_text()
    assert "## References" not in text


# ── D81: --now does not auto-pin ──────────────────────────────────────


def test_capture_now_does_not_auto_pin(activity: Path):
    result = runner.invoke(app, ["capture", "fire", "--now"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "now" / "fire.md")
    assert task.bucket == "now"
    assert task.pinned is None or task.pinned is False


# ── D80: explicit-default values clear, don't reject ──────────────────


def test_capture_priority_normal_accepted(activity: Path):
    """D80: --priority normal should clear, not reject."""
    result = runner.invoke(app, ["capture", "task", "--priority", "normal"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.priority is None


def test_capture_priority_none_accepted(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--priority", "none"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.priority is None


def test_capture_priority_empty_accepted(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--priority", ""])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.priority is None


def test_capture_priority_invalid_rejected(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--priority", "weird"])
    assert result.exit_code != 0


def test_capture_actor_human_clears(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--actor", "human"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.actor is None


def test_capture_actor_ai_accepted(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--actor", "ai"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.actor == "ai"


# ── Capture date flags ────────────────────────────────────────────────


def test_capture_with_due_date(activity: Path):
    from datetime import date
    result = runner.invoke(app, ["capture", "task", "--due", "2026-07-01"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.due == date(2026, 7, 1)


def test_capture_with_due_and_scheduled(activity: Path):
    """--due + --scheduled flow through (no end_date — would fail validation)."""
    from datetime import date
    result = runner.invoke(
        app, ["capture", "epic",
              "--due", "2026-12-01",
              "--scheduled", "2026-11-15"],
    )
    assert result.exit_code == 0, result.output
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "epic.md")
    assert task.due == date(2026, 12, 1)
    assert task.scheduled == date(2026, 11, 15)


def test_capture_end_date_without_terminal_bucket_rejected(activity: Path):
    """Schema rule: end_date requires done/dropped — capture validation catches it."""
    result = runner.invoke(
        app, ["capture", "task", "--end-date", "2026-12-15"],
    )
    assert result.exit_code != 0


def test_capture_invalid_date_rejected(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--due", "not-a-date"])
    assert result.exit_code != 0


# ── D76: tag flag matrix on capture ──────────────────────────────────


def test_capture_with_tag_single(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--tag", "bug"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#bug"]


def test_capture_with_tags_comma_separated(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--tags", "bug,tui,release"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#bug", "#tui", "#release"]


def test_capture_with_tag_space_separated(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--tag", "bug tui release"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#bug", "#tui", "#release"]


def test_capture_with_tag_repeated(activity: Path):
    result = runner.invoke(app, ["capture", "task", "--tag", "bug", "--tag", "tui"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#bug", "#tui"]


def test_capture_nested_tag(activity: Path):
    """Obsidian-style nested tags work."""
    result = runner.invoke(app, ["capture", "task", "--tag", "tui/marquee"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#tui/marquee"]


def test_capture_tag_normalizes_hash(activity: Path):
    """Flag values with or without # produce same result."""
    runner.invoke(app, ["capture", "alpha", "--tag", "#bug"])
    runner.invoke(app, ["capture", "beta", "--tag", "bug"])
    t1, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "alpha.md")
    t2, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "beta.md")
    assert t1.tags == t2.tags == ["#bug"]


def test_capture_tag_mutex_replace_with_add_rejected(activity: Path):
    """D76: --tag (replace) + --add-tag (incremental) is mutex."""
    result = runner.invoke(
        app, ["capture", "task", "--tag", "X", "--add-tag", "Y"],
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower() or "cannot be combined" in result.output.lower()


# ── D76: tag flag matrix on set ──────────────────────────────────────


def test_set_replaces_tags(activity: Path):
    runner.invoke(app, ["capture", "task", "--tag", "old1,old2"])
    result = runner.invoke(app, ["set", "task", "--tags", "new1,new2"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#new1", "#new2"]


def test_set_add_tag_appends(activity: Path):
    runner.invoke(app, ["capture", "task", "--tag", "existing"])
    result = runner.invoke(app, ["set", "task", "--add-tag", "added"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#existing", "#added"]


def test_set_remove_tag_drops(activity: Path):
    runner.invoke(app, ["capture", "task", "--tag", "a,b,c"])
    result = runner.invoke(app, ["set", "task", "--remove-tag", "b"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#a", "#c"]


def test_set_clear_tags_empties(activity: Path):
    runner.invoke(app, ["capture", "task", "--tag", "a,b,c"])
    result = runner.invoke(app, ["set", "task", "--clear-tags"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == []


def test_set_clear_then_add_starts_fresh(activity: Path):
    runner.invoke(app, ["capture", "task", "--tag", "old"])
    result = runner.invoke(app, ["set", "task", "--clear-tags", "--add-tag", "new"])
    assert result.exit_code == 0
    task, _ = read_task(activity / ".octopus" / "tasks" / "backlog" / "task.md")
    assert task.tags == ["#new"]


# ── D77: set --bucket is frontmatter-only ────────────────────────────


def test_set_bucket_changes_frontmatter_only(activity: Path):
    """D77: --bucket changes the field but does NOT move the file."""
    runner.invoke(app, ["capture", "task"])  # → backlog/task.md
    result = runner.invoke(app, ["set", "task", "--bucket", "next"])
    assert result.exit_code == 0

    backlog_path = activity / ".octopus" / "tasks" / "backlog" / "task.md"
    next_path = activity / ".octopus" / "tasks" / "next" / "task.md"
    # File stayed in backlog
    assert backlog_path.exists()
    assert not next_path.exists()
    # Frontmatter says next
    task, _ = read_task(backlog_path)
    assert task.bucket == "next"


def test_set_bucket_emits_mismatch_warning(activity: Path):
    """D77: warning surfaces when bucket and folder disagree."""
    runner.invoke(app, ["capture", "task"])
    result = runner.invoke(app, ["set", "task", "--bucket", "next"])
    # Warnings go to stderr in our CLI but Typer's CliRunner mixes them by default.
    assert "octopus mv task next" in result.output or "octopus mv" in result.output


# ── D77: mv moves the file ────────────────────────────────────────────


def test_mv_moves_file_in_folder_mode(activity: Path):
    runner.invoke(app, ["capture", "task"])
    result = runner.invoke(app, ["mv", "task", "next"])
    assert result.exit_code == 0

    assert not (activity / ".octopus" / "tasks" / "backlog" / "task.md").exists()
    new_path = activity / ".octopus" / "tasks" / "next" / "task.md"
    assert new_path.exists()
    task, _ = read_task(new_path)
    assert task.bucket == "next"


def test_mv_to_done_without_dates_rejected(activity: Path):
    """mv enforces validation — rejects bad terminal states with a useful hint."""
    runner.invoke(app, ["capture", "task"])
    result = runner.invoke(app, ["mv", "task", "done"])
    assert result.exit_code != 0
    # Output mentions finish/drop as the correct path.
    assert "finish" in result.output.lower() or "drop" in result.output.lower()


def test_mv_alias_works(activity: Path):
    """`move` is the canonical name; `mv` is the alias."""
    runner.invoke(app, ["capture", "task"])
    result = runner.invoke(app, ["move", "task", "next"])
    assert result.exit_code == 0


# ── D78: set --slug cascading rename ─────────────────────────────────


def test_slug_rename_with_yes(activity: Path):
    """-y skips the prompt and applies the cascade."""
    runner.invoke(app, ["capture", "old-name"])
    result = runner.invoke(app, ["set", "old-name", "--slug", "new-name", "-y"])
    assert result.exit_code == 0, result.output
    assert not (activity / ".octopus" / "tasks" / "backlog" / "old-name.md").exists()
    assert (activity / ".octopus" / "tasks" / "backlog" / "new-name.md").exists()


def test_slug_rename_invalid_slug_rejected(activity: Path):
    runner.invoke(app, ["capture", "old"])
    result = runner.invoke(app, ["set", "old", "--slug", "Bad Slug!", "-y"])
    assert result.exit_code != 0


def test_slug_rename_target_already_exists_rejected(activity: Path):
    runner.invoke(app, ["capture", "a"])
    runner.invoke(app, ["capture", "b"])
    result = runner.invoke(app, ["set", "a", "--slug", "b", "-y"])
    assert result.exit_code != 0


def test_slug_rename_identical_rejected(activity: Path):
    runner.invoke(app, ["capture", "same"])
    result = runner.invoke(app, ["set", "same", "--slug", "same", "-y"])
    assert result.exit_code != 0


def test_slug_rename_updates_waiting_for(activity: Path):
    """Cascading: waiting_for in other tasks gets rewritten."""
    runner.invoke(app, ["capture", "blocker"])
    runner.invoke(app, ["capture", "blocked"])
    runner.invoke(app, ["wait", "blocked", "--for", "blocker"])
    result = runner.invoke(app, ["set", "blocker", "--slug", "the-blocker", "-y"])
    assert result.exit_code == 0, result.output
    blocked_text = (activity / ".octopus" / "tasks" / "backlog" / "blocked.md").read_text()
    assert "waiting_for: the-blocker" in blocked_text
    assert "waiting_for: blocker\n" not in blocked_text


def test_slug_rename_updates_todo_md_arrow(activity: Path):
    """Cascading: → octopus:<old-slug> arrows in TODO.md get rewritten."""
    runner.invoke(app, ["capture", "thing"])
    todo = activity / "TODO.md"
    todo.write_text("# t\n\n- [x] thing → octopus:thing\n", encoding="utf-8")
    result = runner.invoke(app, ["set", "thing", "--slug", "renamed", "-y"])
    assert result.exit_code == 0, result.output
    assert "→ octopus:renamed" in todo.read_text()
    assert "→ octopus:thing\n" not in todo.read_text()


# ── D79: refs find ───────────────────────────────────────────────────


def test_refs_find_shows_managed_and_warnings(activity: Path):
    runner.invoke(app, ["capture", "target"])
    # Create a session log referencing target by name
    runner.invoke(app, ["session", "start", "--title", "work"])
    runner.invoke(app, ["session", "log", "blocked on target"])
    result = runner.invoke(app, ["refs", "find", "target"])
    assert result.exit_code == 0
    assert "target" in result.output
    # Should split into managed + warning sections
    assert "managed" in result.output.lower() or "Managed" in result.output
    assert "prose" in result.output.lower() or "user" in result.output.lower()


def test_refs_find_no_matches(activity: Path):
    result = runner.invoke(app, ["refs", "find", "nonexistent-slug"])
    assert result.exit_code == 0
    assert "no references" in result.output.lower() or "no refs" in result.output.lower()


def test_refs_find_word_boundary(activity: Path):
    """Should NOT match substrings — `foo` doesn't match `foobar`."""
    runner.invoke(app, ["capture", "foobar"])
    result = runner.invoke(app, ["refs", "find", "foo"])
    # `foo` is not present as a whole-word anywhere.
    assert "no references" in result.output.lower() or "(0)" in result.output

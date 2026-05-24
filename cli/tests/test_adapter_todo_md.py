"""Tests for the TODO.md adapter (#21)."""

from __future__ import annotations

from pathlib import Path

import pytest

from octopus.adapters.todo_md import (
    TodoMdAdapter,
    _extract_title_meta,
    _parse_checkbox,
    _parse_todo_md,
    _slugify_heading,
)


# ── pure parser unit tests ────────────────────────────────────────────


def test_checkbox_unchecked():
    assert _parse_checkbox("- [ ] hello").state == "unchecked"


def test_checkbox_checked_both_cases():
    assert _parse_checkbox("- [x] done").state == "checked"
    assert _parse_checkbox("- [X] done caps").state == "checked"


def test_checkbox_in_progress_markers():
    assert _parse_checkbox("- [-] doing").state == "in-progress"
    assert _parse_checkbox("- [/] doing slash").state == "in-progress"


def test_checkbox_other_marker_treated_as_unchecked():
    assert _parse_checkbox("- [?] huh").state == "unchecked"


def test_checkbox_alt_bullet_chars():
    assert _parse_checkbox("* [ ] asterisk").state == "unchecked"
    assert _parse_checkbox("+ [ ] plus").state == "unchecked"


def test_checkbox_indent_allowed():
    assert _parse_checkbox("    - [ ] indented").state == "unchecked"


def test_checkbox_rejects_heading_and_prose():
    assert _parse_checkbox("## Heading") is None
    assert _parse_checkbox("just text") is None
    assert _parse_checkbox("- regular bullet") is None


def test_title_cleanup_no_prefix():
    assert _extract_title_meta("plain title") == ("plain title", None, False)


def test_title_cleanup_known_prefixes():
    assert _extract_title_meta("TODO: fix bug") == ("fix bug", None, False)
    assert _extract_title_meta("FIXME: improve errors") == ("improve errors", None, False)
    assert _extract_title_meta("BUG: crash") == ("crash", "bug", False)
    assert _extract_title_meta("HACK: workaround") == ("workaround", "chore", False)


def test_title_cleanup_note_is_skipped():
    _, _, skip = _extract_title_meta("NOTE: just info")
    assert skip is True


def test_title_cleanup_unknown_prefix_kept_verbatim():
    """Random ALLCAPS prefixes aren't recognized — no false positives."""
    assert _extract_title_meta("XYZ: kept verbatim") == ("XYZ: kept verbatim", None, False)
    assert _extract_title_meta("RANDOM: keeps the prefix") == (
        "RANDOM: keeps the prefix", None, False,
    )


def test_slugify_heading():
    assert _slugify_heading("Backlog") == "backlog"
    assert _slugify_heading("To Do") == "to-do"
    assert _slugify_heading("v0.4 Release Notes!") == "v0-4-release-notes"
    assert _slugify_heading("   spaces  ") == "spaces"


# ── _parse_todo_md (full content) ─────────────────────────────────────


SAMPLE = """\
# Project notes

## Backlog
- [ ] TODO: wire database
- [ ] FIXME: improve error messages
- [x] BUG: crash on save
- [-] HACK: temp workaround
- [ ] NOTE: this is just info

## Done
- [x] something finished

regular paragraph

- not a checkbox
"""


def test_parse_default_skips_checked_and_notes():
    tasks = _parse_todo_md(SAMPLE)
    titles = [t.title for t in tasks]
    assert "wire database" in titles
    assert "improve error messages" in titles
    assert "temp workaround" in titles  # [-] is in-progress, kept
    # Skipped: [x] BUG, NOTE, and the Done-section [x]
    assert "crash on save" not in titles
    assert "this is just info" not in titles
    assert "something finished" not in titles


def test_parse_include_checked_pulls_done_items():
    tasks = _parse_todo_md(SAMPLE, include_checked=True)
    titles = [t.title for t in tasks]
    assert "crash on save" in titles
    assert "something finished" in titles


def test_parse_section_filter_keeps_only_matching():
    tasks = _parse_todo_md(SAMPLE, section_filter=["backlog"])
    sections = {t.source_group for t in tasks}
    assert sections == {"backlog"}


def test_parse_section_filter_empty_means_all():
    tasks_with_filter = _parse_todo_md(SAMPLE, section_filter=[])
    tasks_without = _parse_todo_md(SAMPLE, section_filter=None)
    assert len(tasks_with_filter) == len(tasks_without)


def test_parse_assigns_correct_buckets_and_kinds():
    tasks = _parse_todo_md(SAMPLE)
    by_title = {t.title: t for t in tasks}
    assert by_title["wire database"].suggested_bucket == "backlog"
    assert by_title["temp workaround"].suggested_bucket == "now"
    assert by_title["temp workaround"].suggested_kind == "chore"
    assert by_title["wire database"].suggested_kind is None


def test_parse_external_id_is_slug_based():
    """external_id uses slug-of-title, not line numbers (Q6 — survives drift)."""
    tasks = _parse_todo_md(SAMPLE)
    by_title = {t.title: t.external_id for t in tasks}
    assert by_title["wire database"] == "TODO.md#wire-database"
    assert by_title["improve error messages"] == "TODO.md#improve-error-messages"


def test_parse_duplicate_titles_get_counter_suffix():
    content = """
- [ ] same thing
- [ ] same thing
"""
    tasks = _parse_todo_md(content)
    ids = [t.external_id for t in tasks]
    assert ids == ["TODO.md#same-thing", "TODO.md#same-thing-2"]


def test_parse_empty_file_returns_empty():
    assert _parse_todo_md("") == []
    assert _parse_todo_md("\n\n") == []


def test_parse_no_checkboxes_returns_empty():
    content = "# heading\n\nprose only\n\n- regular bullet\n"
    assert _parse_todo_md(content) == []


# ── adapter behavior ──────────────────────────────────────────────────


def test_adapter_status_healthy():
    """Real adapter is healthy (unlike the stubs for Obsidian/Reminders)."""
    s = TodoMdAdapter().status()
    assert s.healthy is True
    assert s.error is None


def test_adapter_list_groups_returns_empty():
    """Single-file source — no concept of groups (Q1)."""
    assert TodoMdAdapter().list_groups() == []


def test_adapter_validate_config_ok():
    a = TodoMdAdapter()
    assert a.validate_config({}) == []
    assert a.validate_config({"path": "TODO.md", "include_checked": False}) == []
    assert a.validate_config({"section_filter": ["backlog"]}) == []


def test_adapter_validate_config_rejects_bad_types():
    a = TodoMdAdapter()
    assert a.validate_config({"path": ""}) != []
    assert a.validate_config({"path": 42}) != []
    assert a.validate_config({"include_checked": "yes"}) != []
    assert a.validate_config({"section_filter": "not-a-list"}) != []
    assert a.validate_config({"section_filter": [1, 2, 3]}) != []


def test_adapter_push_is_pull_only():
    r = TodoMdAdapter().push(None)
    assert r.ref is None
    assert "pull-only" in (r.error or "").lower()


# ── end-to-end with real file ─────────────────────────────────────────


@pytest.fixture
def activity_with_todo(tmp_path: Path, monkeypatch):
    """Build an activity with a TODO.md and isolated config/data dirs."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "config"))
    import importlib

    import octopus.config
    import octopus.db.connection

    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)

    from octopus.fs.scaffold import init_activity

    act = tmp_path / "proj"
    act.mkdir()
    init_activity(act, activity_type="code")
    (act / "TODO.md").write_text(SAMPLE, encoding="utf-8")
    # Switch cwd so find_activity_root works
    monkeypatch.chdir(act)
    yield act
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)


def test_adapter_peek_real_file(activity_with_todo: Path):
    a = TodoMdAdapter()
    result = a.peek()
    assert result.errors == []
    titles = [t.title for t in result.tasks]
    assert "wire database" in titles
    assert "crash on save" not in titles  # default skips checked


def test_adapter_pull_same_as_peek(activity_with_todo: Path):
    """pull() is read-only at the adapter level — pipeline does materialization."""
    a = TodoMdAdapter()
    peek_titles = [t.title for t in a.peek().tasks]
    pull_titles = [t.title for t in a.pull().tasks]
    assert peek_titles == pull_titles


def test_adapter_search_filters_by_substring(activity_with_todo: Path):
    a = TodoMdAdapter()
    r = a.search("database")
    titles = [t.title for t in r.tasks]
    assert titles == ["wire database"]


def test_adapter_missing_file_is_no_op(tmp_path: Path, monkeypatch):
    """No TODO.md at activity root → soft no-op (Q4)."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "config"))
    import importlib

    import octopus.config
    import octopus.db.connection

    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)

    from octopus.fs.scaffold import init_activity

    act = tmp_path / "proj"
    act.mkdir()
    init_activity(act, activity_type="code")
    monkeypatch.chdir(act)

    # No TODO.md file at all
    r = TodoMdAdapter().peek()
    assert r.tasks == []
    assert r.errors == []
    assert len(r.skipped) == 1  # one (path, reason) entry

    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)

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


# ── #22 / v0.5.0: inline metadata, arrow exclusion, mark_pulled, mutation verbs ──


from datetime import date as _date
from octopus.adapters.base import Capability
from octopus.adapters.todo_md import (
    InlineMetadata,
    _annotate_pulled_line,
    _flip_marker,
    _insert_under_section,
    _parse_inline_metadata,
)


# Inline metadata parser ──


def test_inline_meta_extracts_priority_emoji():
    m = _parse_inline_metadata("urgent thing ⏫")
    assert m.title == "urgent thing"
    assert m.priority == "urgent"


def test_inline_meta_high_priority_triangle():
    assert _parse_inline_metadata("X 🔺").priority == "urgent"


def test_inline_meta_low_priorities():
    assert _parse_inline_metadata("X 🔽").priority == "low"
    assert _parse_inline_metadata("X ⏬").priority == "low"


def test_inline_meta_medium_dropped():
    assert _parse_inline_metadata("X 🔼").priority is None


def test_inline_meta_extracts_due_date():
    m = _parse_inline_metadata("fix bug 📅 2026-06-15")
    assert m.title == "fix bug"
    assert m.due == _date(2026, 6, 15)


def test_inline_meta_extracts_scheduled_and_start():
    m = _parse_inline_metadata("X ⏳ 2026-07-01 🛫 2026-06-25")
    assert m.scheduled == _date(2026, 7, 1)
    assert m.start_date == _date(2026, 6, 25)


def test_inline_meta_extracts_tags():
    m = _parse_inline_metadata("call mom #personal #weekly")
    assert m.title == "call mom"
    assert set(m.tags) == {"personal", "weekly"}


def test_inline_meta_extracts_arrow():
    m = _parse_inline_metadata("wire bridge → octopus:wire-obsidian-bridge")
    assert m.has_arrow is True
    assert m.arrow_target == "octopus:wire-obsidian-bridge"
    assert "→" not in m.title
    assert "octopus" not in m.title


def test_inline_meta_arrow_with_spectacular_target():
    m = _parse_inline_metadata("plan adapter → spectacular:06-adapter-framework")
    assert m.arrow_target == "spectacular:06-adapter-framework"


def test_inline_meta_combined_fields():
    m = _parse_inline_metadata("ship it ⏫ 📅 2026-06-15 #urgent #release")
    assert m.title == "ship it"
    assert m.priority == "urgent"
    assert m.due == _date(2026, 6, 15)
    assert set(m.tags) == {"urgent", "release"}


def test_inline_meta_no_metadata():
    m = _parse_inline_metadata("plain title")
    assert m.title == "plain title"
    assert m.priority is None
    assert m.due is None
    assert m.tags == ()
    assert m.has_arrow is False


def test_inline_meta_strips_noop_emoji():
    m = _parse_inline_metadata("done thing ✅ 2024-01-01 ➕ 2023-12-01")
    assert m.title == "done thing"


# Parser integration with metadata ──


def test_parse_emoji_metadata_flows_to_external_task():
    content = "## Friction\n- [ ] urgent fix ⏫ 📅 2026-06-15 #release #p0\n"
    tasks = _parse_todo_md(content)
    assert len(tasks) == 1
    t = tasks[0]
    assert t.title == "urgent fix"
    assert t.suggested_priority == "urgent"
    assert t.suggested_due == _date(2026, 6, 15)
    assert set(t.suggested_tags) == {"release", "p0"}


def test_parse_arrow_items_skipped():
    content = """
- [ ] new item
- [x] already in octopus → octopus:foo
- [x] in spectacular → spectacular:06-thing
- [ ] also new
"""
    tasks = _parse_todo_md(content)
    titles = [t.title for t in tasks]
    assert titles == ["new item", "also new"]


def test_parse_cancelled_marker_skipped():
    content = "- [!] cancelled item\n- [ ] live item\n"
    tasks = _parse_todo_md(content)
    assert [t.title for t in tasks] == ["live item"]


def test_parse_in_progress_marker_maps_to_now():
    content = "- [/] slash marker\n- [-] dash marker\n"
    tasks = _parse_todo_md(content)
    assert all(t.suggested_bucket == "now" for t in tasks)


def test_parse_prefix_and_emoji_combine():
    content = "- [ ] BUG: marquee thing ⏫ 📅 2026-06-30 #tui\n"
    tasks = _parse_todo_md(content)
    assert len(tasks) == 1
    t = tasks[0]
    assert t.title == "marquee thing"
    assert t.suggested_kind == "bug"
    assert t.suggested_priority == "urgent"
    assert t.suggested_due == _date(2026, 6, 30)
    assert "tui" in t.suggested_tags


# Annotation primitives ──


def test_annotate_pulled_line_basic():
    line = "- [ ] simple item"
    out = _annotate_pulled_line(line, "simple-item")
    assert out == "- [x] simple item → octopus:simple-item"


def test_annotate_pulled_line_preserves_indent_and_bullet():
    line = "  * [ ] indented asterisk"
    out = _annotate_pulled_line(line, "indented-asterisk")
    assert out == "  * [x] indented asterisk → octopus:indented-asterisk"


def test_annotate_pulled_line_preserves_inline_metadata():
    line = "- [ ] ship it ⏫ 📅 2026-06-15 #release"
    out = _annotate_pulled_line(line, "ship-it")
    assert "⏫" in out and "📅 2026-06-15" in out and "#release" in out
    assert out.endswith("→ octopus:ship-it")


def test_annotate_pulled_line_idempotent():
    """Running mark_pulled twice on the same line must not double-annotate."""
    line = "- [ ] thing"
    once = _annotate_pulled_line(line, "thing")
    twice = _annotate_pulled_line(once, "thing")
    assert once == twice


# Helper: _flip_marker, _insert_under_section ──


def test_flip_marker_to_checked():
    assert _flip_marker("- [ ] thing", "checked") == "- [x] thing"


def test_flip_marker_to_unchecked_strips_arrow():
    assert _flip_marker(
        "- [x] thing → octopus:thing", "unchecked"
    ) == "- [ ] thing"


def test_insert_under_section_existing():
    content = "# T\n\n## Friction\n\n- [ ] a\n\n## Done\n"
    out, where = _insert_under_section(content, "friction", "- [ ] new")
    assert "- [ ] new" in out
    assert "Done" in out  # heading still present
    assert "friction" in where


def test_insert_under_section_creates_when_missing():
    content = "# T\n\n## Existing\n- [ ] a\n"
    out, where = _insert_under_section(content, "newsection", "- [ ] new")
    assert "## newsection" in out
    assert "- [ ] new" in out
    assert "heading not found" in where


def test_insert_under_section_none_appends_to_end():
    content = "# T\n\n## Friction\n- [ ] a\n"
    out, where = _insert_under_section(content, None, "- [ ] tail")
    assert out.endswith("- [ ] tail")
    assert "no section" in where


# End-to-end: pull + mark_pulled rewrites the file ──


def test_mark_pulled_rewrites_source(activity_with_todo: Path):
    """After a pull, the source TODO.md must show `→ octopus:<slug>` on imported lines."""
    adapter = TodoMdAdapter()
    pr = adapter.pull()
    # Build the {external_id → slug} mapping the pipeline would build.
    mapping = {t.external_id: _slugify_heading(t.title) for t in pr.tasks}
    adapter.mark_pulled(mapping)

    content = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    # The three import-eligible items got arrows
    assert "→ octopus:wire-database" in content
    assert "→ octopus:improve-error-messages" in content
    # The skipped NOTE: line did NOT get an arrow
    assert "→ octopus:this-is-just-info" not in content


def test_mark_pulled_leaves_unmapped_lines_alone(activity_with_todo: Path):
    """Lines whose external_id isn't in the mapping must not be modified."""
    adapter = TodoMdAdapter()
    before = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    adapter.mark_pulled({})  # empty mapping → no-op
    after = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    assert before == after


# Mutation verbs ──


def test_add_item_appends_to_section(activity_with_todo: Path):
    adapter = TodoMdAdapter()
    msg = adapter.add_item("brand new task", section="backlog")
    assert "backlog" in msg.lower()
    content = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    assert "- [ ] brand new task" in content


def test_add_item_with_metadata(activity_with_todo: Path):
    adapter = TodoMdAdapter()
    adapter.add_item(
        "high prio",
        section="backlog",
        priority="urgent",
        due="2026-07-01",
        tags=["release"],
    )
    content = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    assert "- [ ] high prio ⏫ 📅 2026-07-01 #release" in content


def test_add_item_in_progress_marker(activity_with_todo: Path):
    TodoMdAdapter().add_item("working on", section="backlog", state="in-progress")
    content = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    assert "- [/] working on" in content


def test_add_item_invalid_due_raises(activity_with_todo: Path):
    with pytest.raises(ValueError):
        TodoMdAdapter().add_item("x", section="backlog", due="nope")


def test_add_item_unknown_section_creates_it(activity_with_todo: Path):
    TodoMdAdapter().add_item("new", section="completely-new-section")
    content = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    assert "## completely-new-section" in content
    assert "- [ ] new" in content


def test_mark_complete_toggles_in_place(activity_with_todo: Path):
    adapter = TodoMdAdapter()
    adapter.add_item("smoke item", section="backlog")
    msg = adapter.mark_complete("smoke item")
    assert "smoke item" in msg
    content = (activity_with_todo / "TODO.md").read_text(encoding="utf-8")
    assert "- [x] smoke item" in content


def test_mark_complete_no_match_raises(activity_with_todo: Path):
    with pytest.raises(ValueError, match="no matching"):
        TodoMdAdapter().mark_complete("nothing matches this")


def test_mark_complete_ambiguous_raises_without_first(activity_with_todo: Path):
    adapter = TodoMdAdapter()
    adapter.add_item("dup one", section="backlog")
    adapter.add_item("dup two", section="backlog")
    with pytest.raises(ValueError, match="matches"):
        adapter.mark_complete("dup")


def test_mark_complete_first_picks_top(activity_with_todo: Path):
    adapter = TodoMdAdapter()
    adapter.add_item("alpha first", section="backlog")
    adapter.add_item("alpha second", section="backlog")
    msg = adapter.mark_complete("alpha", first=True)
    assert "alpha first" in msg


def test_mark_open_reverts_and_strips_arrow(activity_with_todo: Path):
    """Reopening a previously-pulled item must drop the → arrow."""
    adapter = TodoMdAdapter()
    # Seed a fully-annotated line
    path = activity_with_todo / "TODO.md"
    path.write_text(
        "## backlog\n\n- [x] previously pulled → octopus:previously-pulled\n",
        encoding="utf-8",
    )
    adapter.mark_open("previously pulled")
    content = path.read_text(encoding="utf-8")
    assert "- [ ] previously pulled" in content
    assert "→ octopus:" not in content


# Capability declaration ──


def test_todo_md_declares_mark_pulled():
    """TODO.md adapter must declare MARK_PULLED so the pipeline calls it."""
    assert Capability.MARK_PULLED in TodoMdAdapter().capabilities


def test_other_stub_adapters_do_not_declare_mark_pulled():
    """Obsidian/Reminders stubs should NOT declare MARK_PULLED (they don't rewrite sources)."""
    from octopus.adapters.obsidian import ObsidianAdapter
    from octopus.adapters.reminders import RemindersAdapter
    assert Capability.MARK_PULLED not in ObsidianAdapter().capabilities
    assert Capability.MARK_PULLED not in RemindersAdapter().capabilities

"""Memory append: scaffold, lazy section, marker preservation, default → Notes."""

from __future__ import annotations

from datetime import datetime

import pytest

from octopus.fs.scaffold import init_activity
from octopus.memory import (
    MARKER,
    append_entry,
    memory_path,
    read_memory,
    section_entries,
)
from octopus.memory.io import _split_on_marker


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_default_target_is_notes(activity):
    folder, aid = activity
    _, canon = append_entry(folder, aid, "a thought")
    assert canon == "Notes"
    _, body = read_memory(memory_path(folder))
    _, below, ok = _split_on_marker(body)
    assert ok
    assert "## Notes" in below
    assert "## Log" not in below  # Schema change: Log was dropped.


def test_explicit_state_section(activity):
    folder, aid = activity
    _, canon = append_entry(folder, aid, "paused for legal review", section="state")
    assert canon == "State"
    _, body = read_memory(memory_path(folder))
    _, below, _ = _split_on_marker(body)
    assert "## State" in below
    entries = section_entries(below, "State")
    assert len(entries) == 1
    assert entries[0][1] == "paused for legal review"


def test_append_empty_note_raises(activity):
    folder, aid = activity
    with pytest.raises(ValueError, match="non-empty"):
        append_entry(folder, aid, "   ")


def test_scaffold_created_on_first_append(activity):
    folder, aid = activity
    assert not memory_path(folder).is_file()
    append_entry(folder, aid, "first")
    assert memory_path(folder).is_file()


def test_lazy_section_creation(activity):
    folder, aid = activity
    append_entry(folder, aid, "decision a", section="decisions")
    _, body = read_memory(memory_path(folder))
    _, below, _ = _split_on_marker(body)
    # Only the targeted section exists (lazy)
    assert "## Decisions" in below
    assert "## State" not in below
    assert "## Notes" not in below


def test_multiple_appends_to_same_section_chronological(activity):
    folder, aid = activity
    append_entry(folder, aid, "first", when=datetime(2026, 5, 1, 9, 0))
    append_entry(folder, aid, "second", when=datetime(2026, 5, 2, 10, 0))
    _, body = read_memory(memory_path(folder))
    _, below, _ = _split_on_marker(body)
    entries = section_entries(below, "Notes")
    assert [e[1] for e in entries] == ["first", "second"]
    assert entries[0][0].startswith("2026-05-01")
    assert entries[1][0].startswith("2026-05-02")


def test_canonical_order_preserved_across_appends(activity):
    folder, aid = activity
    # Append in non-canonical order: Notes → Decisions → State.
    append_entry(folder, aid, "n", section="notes")
    append_entry(folder, aid, "d", section="decisions")
    append_entry(folder, aid, "s", section="state")
    _, body = read_memory(memory_path(folder))
    _, below, _ = _split_on_marker(body)
    # Heading order in `below` should be Decisions, Notes, State (canonical positions).
    headings = [
        line.lstrip("# ").strip()
        for line in below.splitlines()
        if line.startswith("## ")
    ]
    assert headings == ["Decisions", "Notes", "State"]


def test_marker_reinserted_when_deleted(activity, capsys):
    folder, aid = activity
    # Create initial file then strip the marker by hand.
    append_entry(folder, aid, "first")
    p = memory_path(folder)
    text = p.read_text(encoding="utf-8").replace(MARKER + "\n", "").replace(MARKER, "")
    p.write_text(text, encoding="utf-8")
    append_entry(folder, aid, "second")
    captured = capsys.readouterr()
    assert "marker missing" in captured.err
    assert MARKER in p.read_text(encoding="utf-8")


def test_unknown_section_raises(activity):
    folder, aid = activity
    with pytest.raises(Exception):  # UnknownSectionError extends ValueError
        append_entry(folder, aid, "x", section="nonsense")


def test_last_updated_bumped(activity):
    folder, aid = activity
    when = datetime(2026, 5, 23, 12, 0, 0)
    memory, _ = append_entry(folder, aid, "x", when=when)
    assert memory.last_updated.isoformat() == "2026-05-23"

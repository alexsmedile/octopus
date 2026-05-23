"""Hand-edit safety: user-added sections preserved, byte-for-byte body invariant."""

from __future__ import annotations

import pytest

from octopus.fs.scaffold import init_activity
from octopus.memory import append_entry, memory_path, read_memory, section_entries
from octopus.memory.io import _split_on_marker


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_user_added_section_preserved(activity):
    folder, aid = activity
    append_entry(folder, aid, "first decision", section="decisions")
    # Hand-insert a non-canonical section below the marker.
    p = memory_path(folder)
    text = p.read_text(encoding="utf-8")
    text = text + "\n## Risks\n\n### 2026-05-23 14:00\nrisk #1\n"
    p.write_text(text, encoding="utf-8")

    append_entry(folder, aid, "second decision", section="decisions")
    after = p.read_text(encoding="utf-8")
    assert "## Risks" in after
    assert "risk #1" in after


def test_existing_entries_not_reformatted(activity):
    folder, aid = activity
    # First append.
    append_entry(folder, aid, "the original text — with em-dash & punctuation", section="notes")
    p = memory_path(folder)
    before = p.read_text(encoding="utf-8")
    # Append a second entry.
    append_entry(folder, aid, "another note", section="notes")
    after = p.read_text(encoding="utf-8")
    # Original entry must appear verbatim in the new file.
    assert "the original text — with em-dash & punctuation" in after
    # And the original block (everything up to the second `### `) must be a prefix
    # of the new content — guarantee: no reformatting of existing entries.
    prefix_end = before.rfind("\n")
    assert before[:prefix_end] in after


def test_marker_position_preserved(activity):
    folder, aid = activity
    append_entry(folder, aid, "a", section="notes")
    p = memory_path(folder)
    text = p.read_text(encoding="utf-8")
    above, below, ok = _split_on_marker(text)
    assert ok
    # The marker should sit between the user intro (above) and managed (below).
    assert "# Memory:" in above
    assert "## Notes" in below


def test_unknown_frontmatter_round_trips(activity):
    folder, aid = activity
    append_entry(folder, aid, "a", section="notes")
    p = memory_path(folder)
    # Hand-insert unknown frontmatter key.
    text = p.read_text(encoding="utf-8")
    text = text.replace("activity:", "owner: alex\nactivity:")
    p.write_text(text, encoding="utf-8")
    # Append again; unknown key must survive.
    append_entry(folder, aid, "b", section="notes")
    after = p.read_text(encoding="utf-8")
    assert "owner: alex" in after

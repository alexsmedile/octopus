"""Default `memory show`: preview with `(showing latest 3 of N)` + footer."""

from __future__ import annotations

from datetime import datetime

import pytest

from octopus.fs.scaffold import init_activity
from octopus.memory import append_entry, set_summary, show_default


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_show_default_on_missing_memory(activity):
    folder, _ = activity
    out = show_default(folder)
    assert "no memory.md" in out


def test_show_default_with_summary_only(activity):
    folder, aid = activity
    set_summary(folder, aid, "the project tagline")
    out = show_default(folder)
    assert "summary: the project tagline" in out
    # No sections yet → no preview blocks
    assert "showing latest" not in out


def test_show_default_includes_state_decisions_open(activity):
    folder, aid = activity
    append_entry(folder, aid, "decision one", section="decisions")
    append_entry(folder, aid, "question one", section="open")
    append_entry(folder, aid, "state one", section="state")
    out = show_default(folder)
    # All three preview sections show up with `(showing latest 1 of 1)`
    assert "## State (showing latest 1 of 1)" in out
    assert "## Open Questions (showing latest 1 of 1)" in out
    assert "## Decisions (showing latest 1 of 1)" in out
    # No "X more" footers when N <= 3
    assert "more — run" not in out


def test_show_default_truncates_with_footer_when_more_than_three(activity):
    folder, aid = activity
    for i in range(5):
        append_entry(
            folder, aid, f"decision {i}",
            section="decisions",
            when=datetime(2026, 5, 1 + i, 9, 0),
        )
    out = show_default(folder)
    assert "## Decisions (showing latest 3 of 5)" in out
    # Earliest 2 not in preview
    assert "decision 0" not in out
    assert "decision 1" not in out
    # Latest 3 in preview
    assert "decision 2" in out
    assert "decision 3" in out
    assert "decision 4" in out
    # Footer present with correct count + cli hint
    assert "[2 more — run `octopus memory show --section decisions` for all]" in out


def test_show_default_state_truncation_uses_correct_section_arg(activity):
    folder, aid = activity
    for i in range(4):
        append_entry(
            folder, aid, f"state {i}",
            section="state",
            when=datetime(2026, 5, 1 + i, 9, 0),
        )
    out = show_default(folder)
    assert "## State (showing latest 3 of 4)" in out
    assert "[1 more — run `octopus memory show --section state` for all]" in out


def test_show_default_omits_empty_sections(activity):
    folder, aid = activity
    append_entry(folder, aid, "d", section="decisions")
    out = show_default(folder)
    # Only Decisions has entries; State/Open headings should be absent.
    assert "## Decisions" in out
    assert "## State (" not in out
    assert "## Open Questions (" not in out


def test_show_default_open_questions_uses_short_arg(activity):
    folder, aid = activity
    for i in range(5):
        append_entry(
            folder, aid, f"q {i}",
            section="open",
            when=datetime(2026, 5, 1 + i, 9, 0),
        )
    out = show_default(folder)
    assert "## Open Questions (showing latest 3 of 5)" in out
    # Section arg uses "open" (first word lowercased)
    assert "[2 more — run `octopus memory show --section open` for all]" in out

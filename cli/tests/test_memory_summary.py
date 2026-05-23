"""Memory summary: set via text, preserve unknown frontmatter."""

from __future__ import annotations

import pytest

from octopus.fs.scaffold import init_activity
from octopus.memory import memory_path, read_memory, set_summary


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_set_summary_creates_memory(activity):
    folder, aid = activity
    assert not memory_path(folder).is_file()
    set_summary(folder, aid, "a one-line summary")
    assert memory_path(folder).is_file()
    memory, _ = read_memory(memory_path(folder))
    assert memory.summary == "a one-line summary"


def test_set_summary_updates_existing(activity):
    folder, aid = activity
    set_summary(folder, aid, "first")
    set_summary(folder, aid, "second")
    memory, _ = read_memory(memory_path(folder))
    assert memory.summary == "second"


def test_set_summary_preserves_unknown_frontmatter(activity):
    folder, aid = activity
    set_summary(folder, aid, "the summary")
    # Inject a hand-edited unknown key.
    p = memory_path(folder)
    text = p.read_text(encoding="utf-8")
    text = text.replace("activity:", "custom_key: custom_value\nactivity:")
    p.write_text(text, encoding="utf-8")
    # Re-set summary; custom key must survive.
    set_summary(folder, aid, "new summary")
    after = p.read_text(encoding="utf-8")
    assert "custom_key" in after
    assert "custom_value" in after

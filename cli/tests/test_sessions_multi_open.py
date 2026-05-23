"""Multi-open prompt outcomes: [c]ontinue, [n]ew, [e]nd-previous, [a]bort."""

from __future__ import annotations

from datetime import datetime

import pytest

from octopus.fs.scaffold import init_activity
from octopus.sessions import (
    list_sessions,
    read_session,
    start_session,
)
from octopus.sessions.cache import get_active


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / ".cache" / "octopus"))


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_continue_returns_active_session(activity):
    folder, aid = activity
    first = start_session(folder, aid, title="t1")
    same = start_session(folder, aid, title="t2", on_open_sessions=lambda opens: "c")
    assert same.filename == first.filename
    # Only one session file written
    assert len(list_sessions(folder)) == 1


def test_new_starts_second_session(activity):
    folder, aid = activity
    first = start_session(folder, aid, title="t1", when=datetime(2026, 5, 23, 9, 0, 0))
    second = start_session(
        folder, aid, title="t2",
        on_open_sessions=lambda opens: "n",
        when=datetime(2026, 5, 23, 10, 0, 0),
    )
    assert second.filename != first.filename
    # Active flipped to the new one
    assert get_active(aid) == second.filename
    # Both files exist; first is still open
    sessions = list_sessions(folder)
    assert len(sessions) == 2
    assert all(s.is_open() for s in sessions)


def test_end_previous_marks_dropped_with_note(activity):
    folder, aid = activity
    first = start_session(folder, aid, title="t1", when=datetime(2026, 5, 23, 9, 0, 0))
    second = start_session(
        folder, aid, title="t2",
        on_open_sessions=lambda opens: "e",
        when=datetime(2026, 5, 23, 10, 0, 0),
    )
    # First should be closed with status=dropped + auto-note in body
    on_first, body = read_session(first.path)
    assert on_first.ended is not None
    assert on_first.status == "dropped"
    assert on_first.active is None
    assert "ended by `session start --replace`" in body
    # Active now points at second
    assert get_active(aid) == second.filename


def test_abort_raises_and_writes_nothing(activity):
    folder, aid = activity
    first = start_session(folder, aid, title="t1")
    with pytest.raises(RuntimeError, match="aborted"):
        start_session(folder, aid, title="t2", on_open_sessions=lambda opens: "a")
    # Only the first session file exists
    assert len(list_sessions(folder)) == 1
    assert get_active(aid) == first.filename

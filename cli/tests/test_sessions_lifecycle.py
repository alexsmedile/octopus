"""Session lifecycle happy paths: start / log / end / switch."""

from __future__ import annotations

from datetime import datetime

import pytest

from octopus.fs.scaffold import init_activity
from octopus.sessions import (
    end_session,
    list_sessions,
    log_session,
    read_session,
    start_session,
    switch_session,
)
from octopus.sessions.cache import get_active


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Redirect ~/.cache/octopus to tmp for every test."""
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / ".cache" / "octopus"))


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_start_session_creates_file_and_sets_active(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="warm-up")
    assert s.is_open()
    assert s.active is True
    assert s.path is not None and s.path.is_file()
    assert get_active(aid) == s.filename
    # Filename shape: YYYY-MM-DD-<slug>
    assert s.filename.startswith(datetime.now().strftime("%Y-%m-%d"))
    assert "warm-up" in s.filename


def test_log_appends_entry_to_active(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    log_session(folder, aid, "first note")
    log_session(folder, aid, "second note")
    body = s.path.read_text().split("---", 2)[-1]
    assert "first note" in body
    assert "second note" in body
    # Second-precision header
    assert "### " in body
    headers = [line for line in body.splitlines() if line.startswith("### ")]
    assert all(len(h.split()[2]) == 8 for h in headers)  # HH:MM:SS


def test_end_session_clears_active_and_marks_done(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    ended = end_session(folder, aid, summary="all good")
    assert ended.ended is not None
    assert ended.status == "done"
    assert ended.summary == "all good"
    assert get_active(aid) is None
    # On disk, active is gone
    on_disk, _ = read_session(s.path)
    assert on_disk.active is None
    assert on_disk.status == "done"


def test_end_session_dropped_status(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    ended = end_session(folder, aid, status="dropped")
    assert ended.status == "dropped"


def test_switch_session_flips_active_pointer(activity):
    folder, aid = activity
    s1 = start_session(folder, aid, title="first")
    # Start a second session: choose [n] via fallback (no callback → defaults to "n")
    s2 = start_session(folder, aid, title="second")
    assert get_active(aid) == s2.filename

    switch_session(folder, aid, s1.filename)
    assert get_active(aid) == s1.filename
    # Frontmatter mirrors flipped
    on_s1, _ = read_session(s1.path)
    on_s2, _ = read_session(s2.path)
    assert on_s1.active is True
    assert on_s2.active is None


def test_switch_rejects_closed_session(activity):
    folder, aid = activity
    s1 = start_session(folder, aid, title="first")
    end_session(folder, aid)
    s2 = start_session(folder, aid, title="second")
    with pytest.raises(ValueError):
        switch_session(folder, aid, s1.filename)


def test_list_sessions_returns_chronological(activity):
    folder, aid = activity
    s1 = start_session(folder, aid, title="a", when=datetime(2026, 5, 1, 9, 0, 0))
    # End to avoid the open-sessions branch; start_session no-callback defaults to "n"
    end_session(folder, aid)
    s2 = start_session(folder, aid, title="b", when=datetime(2026, 5, 2, 9, 0, 0))
    rows = list_sessions(folder)
    assert [r.filename for r in rows] == [s1.filename, s2.filename]

"""`session show` precedence: active → most-recent → error-if-zero."""

from __future__ import annotations

from datetime import datetime

import pytest

from octopus.fs.scaffold import init_activity
from octopus.sessions import end_session, show_session, start_session


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / ".cache" / "octopus"))


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_no_sessions_raises(activity):
    folder, aid = activity
    with pytest.raises(FileNotFoundError, match="no sessions"):
        show_session(folder, aid)


def test_active_takes_precedence(activity):
    folder, aid = activity
    first = start_session(folder, aid, title="a", when=datetime(2026, 5, 1, 9, 0, 0))
    end_session(folder, aid, when=datetime(2026, 5, 1, 10, 0, 0))
    second = start_session(folder, aid, title="b", when=datetime(2026, 5, 2, 9, 0, 0))
    # Active is `second`; show should return it.
    got = show_session(folder, aid)
    assert got.filename == second.filename


def test_fallback_to_most_recent_when_no_active(activity):
    folder, aid = activity
    first = start_session(folder, aid, title="a", when=datetime(2026, 5, 1, 9, 0, 0))
    end_session(folder, aid, when=datetime(2026, 5, 1, 10, 0, 0))
    second = start_session(folder, aid, title="b", when=datetime(2026, 5, 2, 9, 0, 0))
    end_session(folder, aid, when=datetime(2026, 5, 2, 11, 0, 0))
    # No active; latest-ended wins
    got = show_session(folder, aid)
    assert got.filename == second.filename


def test_explicit_slug_overrides(activity):
    folder, aid = activity
    first = start_session(folder, aid, title="a", when=datetime(2026, 5, 1, 9, 0, 0))
    end_session(folder, aid)
    second = start_session(folder, aid, title="b", when=datetime(2026, 5, 2, 9, 0, 0))
    got = show_session(folder, aid, slug=first.filename)
    assert got.filename == first.filename


def test_unknown_slug_raises(activity):
    folder, aid = activity
    start_session(folder, aid, title="a")
    with pytest.raises(FileNotFoundError):
        show_session(folder, aid, slug="2099-01-01-nope")

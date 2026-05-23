"""`session log` with no active session must error with NoActiveSessionError."""

from __future__ import annotations

import pytest

from octopus.fs.scaffold import init_activity
from octopus.sessions import NoActiveSessionError, log_session, start_session
from octopus.sessions.cache import clear_active, get_active


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / ".cache" / "octopus"))


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_log_with_no_session_raises(activity):
    folder, aid = activity
    with pytest.raises(NoActiveSessionError, match="no active session"):
        log_session(folder, aid, "anything")


def test_log_after_cache_cleared_raises(activity):
    folder, aid = activity
    start_session(folder, aid, title="t")
    clear_active(aid)
    with pytest.raises(NoActiveSessionError):
        log_session(folder, aid, "anything")


def test_log_with_empty_note_raises(activity):
    folder, aid = activity
    start_session(folder, aid, title="t")
    with pytest.raises(ValueError, match="non-empty"):
        log_session(folder, aid, "   ")


def test_log_clears_cache_when_file_missing(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    s.path.unlink()
    with pytest.raises(NoActiveSessionError, match="missing"):
        log_session(folder, aid, "x")
    # Cache pointer cleaned up
    assert get_active(aid) is None

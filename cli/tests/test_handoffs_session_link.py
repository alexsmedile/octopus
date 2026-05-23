"""`session end --handoff` flow: symmetric from_session ↔ related_handoff link."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from octopus.cli import app
from octopus.fs.scaffold import init_activity
from octopus.handoffs.io import list_handoffs
from octopus.sessions.io import list_sessions

runner = CliRunner()


@pytest.fixture
def activity(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / ".cache"))
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    monkeypatch.chdir(folder)
    return folder, a.id


def test_session_end_handoff_non_interactive_requires_title(activity):
    folder, _ = activity
    runner.invoke(app, ["session", "start", "--title", "work block"])
    result = runner.invoke(
        app,
        ["session", "end", "--handoff", "--non-interactive"],
    )
    assert result.exit_code != 0
    assert "handoff-title" in result.output.lower() or "handoff-title" in (result.stderr or "").lower()


def test_session_end_handoff_creates_symmetric_link(activity):
    folder, _ = activity
    runner.invoke(app, ["session", "start", "--title", "work block"])
    result = runner.invoke(
        app,
        [
            "session", "end",
            "--handoff",
            "--non-interactive",
            "--handoff-title", "Pick up here",
            "--handoff-to-actor", "ai",
            "--handoff-summary", "where we stopped",
        ],
    )
    assert result.exit_code == 0, result.output
    sessions = list_sessions(folder)
    handoffs = list_handoffs(folder)
    assert len(sessions) == 1
    assert len(handoffs) == 1
    s = sessions[0]
    h = handoffs[0]
    # Symmetric backlink.
    assert s.related_handoff == h.slug
    assert h.from_session == s.filename
    # Body template was used.
    assert h.path is not None
    body = h.path.read_text(encoding="utf-8")
    assert "## TL;DR" in body
    assert h.summary == "where we stopped"
    assert h.to_actor == "ai"


def test_handoff_new_requires_activity(tmp_path, monkeypatch):
    """`handoff new` outside an activity exits non-zero."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["handoff", "new", "orphan"])
    assert result.exit_code != 0


def test_handoff_list_and_show_via_cli(activity):
    folder, _ = activity
    result = runner.invoke(app, ["handoff", "new", "first one", "--priority", "high"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["handoff", "list"])
    assert result.exit_code == 0
    assert "first one" in result.output
    assert "high" in result.output

    # Grab slug from list (the last column is the slug — read it from disk).
    handoffs = list_handoffs(folder)
    slug = handoffs[0].slug
    result = runner.invoke(app, ["handoff", "show", slug])
    assert result.exit_code == 0
    assert "first one" in result.output
    assert "## TL;DR" in result.output  # body is rendered


def test_handoff_list_status_filter(activity):
    folder, _ = activity
    runner.invoke(app, ["handoff", "new", "a"])
    runner.invoke(app, ["handoff", "new", "b"])
    result = runner.invoke(app, ["handoff", "list", "--status", "resolved"])
    assert result.exit_code == 0
    assert "no handoffs" in result.output

"""Tests for #30 — index hygiene: forget activity + archived-by-default filter."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from octopus.cli import app
from octopus.core.identify import (
    ActivityAmbiguous,
    ActivityNotFound,
    resolve_activity,
)
from octopus.fs.scaffold import init_activity

runner = CliRunner()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch):
    """Isolate index + config to a fresh temp dir for each test."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "config"))
    import importlib

    import octopus.config
    import octopus.db.connection

    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)
    yield tmp_path
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)


@pytest.fixture
def two_activities(isolated, monkeypatch):
    """Create two indexed activities; return their roots."""
    a = isolated / "alpha"
    a.mkdir()
    init_activity(a, activity_type="code")
    b = isolated / "beta"
    b.mkdir()
    init_activity(b, activity_type="code")

    # Reindex to populate the SQLite rows.
    from octopus.db.connection import get_db
    from octopus.db.reindex import reindex_all

    conn = get_db()
    try:
        reindex_all(conn, [isolated])
    finally:
        conn.close()
    return a, b


# ── core/identify ─────────────────────────────────────────────────────


def test_resolve_by_path(two_activities):
    a, _b = two_activities
    row = resolve_activity(str(a))
    assert row["path"] == str(a)


def test_resolve_by_path_with_tilde(two_activities):
    a, _b = two_activities
    # Path-like detection trips on `/` even without tilde
    row = resolve_activity(str(a.resolve()))
    assert row["path"] == str(a)


def test_resolve_by_id_exact(two_activities):
    a, _b = two_activities
    # Get the id by walking up the path first
    full_row = resolve_activity(str(a))
    row = resolve_activity(full_row["id"])
    assert row["id"] == full_row["id"]


def test_resolve_by_prefix(two_activities):
    a, _b = two_activities
    full_row = resolve_activity(str(a))
    # The slug portion should match
    prefix = full_row["id"].split("-")[0]
    row = resolve_activity(prefix)
    assert row["id"] == full_row["id"]


def test_resolve_unknown_token(two_activities):
    with pytest.raises(ActivityNotFound):
        resolve_activity("nonexistent-token")


def test_resolve_empty_token(two_activities):
    with pytest.raises(ActivityNotFound):
        resolve_activity("")


def test_resolve_path_not_in_index(isolated):
    """A path with .octopus/ on disk but not in the index → ActivityNotFound."""
    folder = isolated / "unindexed"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    # Don't reindex — the activity exists on disk but the index doesn't know.
    with pytest.raises(ActivityNotFound):
        resolve_activity(str(folder))


def test_resolve_path_no_octopus(isolated):
    """A path with no .octopus/ → ActivityNotFound."""
    plain = isolated / "plain-folder"
    plain.mkdir()
    with pytest.raises(ActivityNotFound):
        resolve_activity(str(plain))


def test_resolve_ambiguous_prefix(isolated):
    """Two activities with the same slug prefix → ActivityAmbiguous."""
    # Manually craft two activities with overlapping slug.
    # init_activity uses the folder name for the slug, so we need different
    # folder names that share a prefix.
    one = isolated / "shared-name-one"
    one.mkdir()
    init_activity(one, activity_type="code")
    two = isolated / "shared-name-two"
    two.mkdir()
    init_activity(two, activity_type="code")

    from octopus.db.connection import get_db
    from octopus.db.reindex import reindex_all

    conn = get_db()
    try:
        reindex_all(conn, [isolated])
    finally:
        conn.close()

    with pytest.raises(ActivityAmbiguous):
        resolve_activity("shared-name")


# ── forget activity CLI ───────────────────────────────────────────────


def test_forget_activity_by_path_y_no_archive(two_activities):
    """`-y` alone forgets but does NOT archive (D83)."""
    a, _b = two_activities
    result = runner.invoke(app, ["forget", "activity", str(a), "-y"])
    assert result.exit_code == 0, result.output
    # Files remain at original location
    assert (a / ".octopus" / "activity.md").exists()
    # No _archive folder created
    assert not (a.parent / "_archive").exists()
    # Activity is gone from the index
    with pytest.raises(ActivityNotFound):
        resolve_activity(str(a))


def test_forget_activity_with_archive(two_activities):
    """`--archive` moves files to <parent>/_archive/<name>/."""
    a, _b = two_activities
    result = runner.invoke(app, ["forget", "activity", str(a), "--archive", "-y"])
    assert result.exit_code == 0, result.output
    # Original location is gone
    assert not a.exists()
    # Archive destination exists
    archive_dest = a.parent / "_archive" / a.name
    assert archive_dest.is_dir()
    assert (archive_dest / ".octopus" / "activity.md").exists()


def test_forget_activity_by_id_prefix(two_activities):
    a, _b = two_activities
    full_row = resolve_activity(str(a))
    prefix = full_row["id"].split("-")[0]
    result = runner.invoke(app, ["forget", "activity", prefix, "-y"])
    assert result.exit_code == 0, result.output


def test_forget_unknown_activity(isolated):
    result = runner.invoke(app, ["forget", "activity", "nonexistent", "-y"])
    assert result.exit_code != 0
    assert "no activity matches" in result.output.lower()


def test_forget_already_forgotten(two_activities):
    a, _b = two_activities
    runner.invoke(app, ["forget", "activity", str(a), "-y"])
    result = runner.invoke(app, ["forget", "activity", str(a), "-y"])
    assert result.exit_code != 0


def test_forget_only_targeted_activity(two_activities):
    """Forgetting alpha must NOT touch beta."""
    a, b = two_activities
    runner.invoke(app, ["forget", "activity", str(a), "-y"])
    # Beta still resolvable
    row = resolve_activity(str(b))
    assert row["path"] == str(b)


def test_forget_archive_destination_collision(two_activities):
    """If <parent>/_archive/<name>/ already exists, archive fails clean."""
    a, _b = two_activities
    # Pre-create the archive destination
    archive_dest = a.parent / "_archive" / a.name
    archive_dest.mkdir(parents=True)
    result = runner.invoke(app, ["forget", "activity", str(a), "--archive", "-y"])
    assert result.exit_code != 0
    assert "already exists" in result.output.lower() or "destination" in result.output.lower()


# ── archived-by-default in list_activities ────────────────────────────


def test_list_activities_hides_archived_by_default(isolated, two_activities):
    """An activity with status='archived' is hidden from list_activities by default."""
    a, _b = two_activities

    # Manually flip alpha to archived
    from octopus.db.connection import get_db
    from octopus.db.queries import list_activities

    conn = get_db()
    try:
        # We need to find alpha's id
        row = resolve_activity(str(a))
        conn.execute(
            "UPDATE activities SET status = 'archived' WHERE id = ?", (row["id"],)
        )

        # Default: archived hidden
        rows = list_activities(conn)
        titles = {r["title"] for r in rows}
        assert a.name not in titles
        assert "beta" in titles

        # include_archived=True: archived surfaces
        rows = list_activities(conn, include_archived=True)
        titles = {r["title"] for r in rows}
        assert a.name in titles
    finally:
        conn.close()


def test_list_activities_explicit_status_archived_shows_archived(isolated, two_activities):
    """`--status archived` overrides the default-hide."""
    a, _b = two_activities

    from octopus.db.connection import get_db
    from octopus.db.queries import list_activities

    conn = get_db()
    try:
        row = resolve_activity(str(a))
        conn.execute(
            "UPDATE activities SET status = 'archived' WHERE id = ?", (row["id"],)
        )
        rows = list_activities(conn, status="archived")
        titles = {r["title"] for r in rows}
        assert a.name in titles
        assert "beta" not in titles
    finally:
        conn.close()


# ── CLI flag --include-archived ───────────────────────────────────────


def test_list_cmd_include_archived_flag(isolated, two_activities, monkeypatch):
    """The CLI --include-archived flag flips the default."""
    a, _b = two_activities

    # Flip alpha to archived
    from octopus.db.connection import get_db

    conn = get_db()
    try:
        row = resolve_activity(str(a))
        conn.execute(
            "UPDATE activities SET status = 'archived' WHERE id = ?", (row["id"],)
        )
    finally:
        conn.close()

    # Cwd must be outside both activities so list --all gets the activity view
    monkeypatch.chdir(isolated)
    result = runner.invoke(app, ["list", "--all"])
    assert "alpha" not in result.output
    assert "beta" in result.output

    result = runner.invoke(app, ["list", "--all", "--include-archived"])
    assert "alpha" in result.output
    assert "beta" in result.output

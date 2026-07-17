"""`--glyphs` on `octopus list` / `octopus task show` (G3, request 49-tui-glyph-parity).

Default off (no output change for scripts); opt-in prefixes each task row
with its slot-1 status glyph, reusing `octopus.tui.icons`."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from octopus.cli import app
from octopus.fs.scaffold import init_activity

runner = CliRunner()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "config"))
    import octopus.config
    import octopus.db.connection
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)
    yield tmp_path
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)


@pytest.fixture
def activity(isolated, monkeypatch):
    a = isolated / "alpha"
    a.mkdir()
    init_activity(a, activity_type="code")

    from octopus.db.connection import get_db
    from octopus.db.reindex import reindex_all
    conn = get_db()
    try:
        reindex_all(conn, [isolated])
    finally:
        conn.close()

    monkeypatch.chdir(a)
    runner.invoke(app, ["add", "task", "backlog-task"])
    runner.invoke(app, ["add", "task", "next-task", "--next"])
    return a


def test_list_without_glyphs_flag_has_no_glyph_prefix(activity):
    result = runner.invoke(app, ["list", "tasks"])
    assert result.exit_code == 0
    assert "□" not in result.output
    assert "·" not in result.output


def test_list_with_glyphs_flag_shows_bucket_idle_glyphs(activity):
    result = runner.invoke(app, ["list", "tasks", "--glyphs"])
    assert result.exit_code == 0
    # next-task sits in NEXT (idle, no progress, no exception) → □
    assert "□" in result.output
    # backlog-task sits in BACKLOG (idle) → ·
    assert "·" in result.output


def test_task_show_with_glyphs_flag_prefixes_title(activity):
    result = runner.invoke(app, ["task", "show", "next-task", "--glyphs"])
    assert result.exit_code == 0
    assert result.output.startswith("□ next-task")


def test_task_show_without_glyphs_flag_has_no_prefix(activity):
    result = runner.invoke(app, ["task", "show", "next-task"])
    assert result.exit_code == 0
    assert not result.output.startswith("□")

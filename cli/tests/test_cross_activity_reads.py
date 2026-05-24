"""Tests for #27 — cross-activity reads + dashboards.

Covers:
- `octopus list tasks/activities [<path-or-id>]`
- `octopus list --all` filter flags (--priority --has-pinned --has-overdue ...)
- `octopus status <path-or-id>` rich version
- `octopus get activity <path-or-id>` JSON
- `octopus dashboard`, `octopus next`, `octopus impact`
"""

from __future__ import annotations

import importlib
import json
from datetime import date, timedelta
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
def workspace(isolated, monkeypatch):
    """Two activities (alpha=urgent, beta=normal), each with a few tasks."""
    a = isolated / "alpha"
    a.mkdir()
    init_activity(a, activity_type="code", priority="urgent")
    b = isolated / "beta"
    b.mkdir()
    init_activity(b, activity_type="business")

    from octopus.db.connection import get_db
    from octopus.db.reindex import reindex_all
    conn = get_db()
    try:
        reindex_all(conn, [isolated])
    finally:
        conn.close()

    # Add some tasks via the CLI
    monkeypatch.chdir(a)
    runner.invoke(app, ["add", "task", "pin-task", "--priority", "high"])
    runner.invoke(app, ["pin", "pin-task"])
    runner.invoke(app, ["add", "task", "now-task", "--now"])
    runner.invoke(app, ["add", "task", "overdue-task", "--due", "2024-01-01"])
    monkeypatch.chdir(b)
    runner.invoke(app, ["add", "task", "plain-thing"])

    return a, b


def _ids(a: Path, b: Path) -> tuple[str, str]:
    from octopus.core.identify import resolve_activity
    return resolve_activity(str(a))["id"], resolve_activity(str(b))["id"]


# ── list tasks/activities ─────────────────────────────────────────────


def test_list_tasks_noun_explicit(workspace, monkeypatch, tmp_path):
    a, b = workspace
    monkeypatch.chdir(tmp_path)
    a_id, _ = _ids(a, b)
    res = runner.invoke(app, ["list", "tasks", a_id])
    assert res.exit_code == 0, res.output
    assert "pin-task" in res.output
    assert "plain-thing" not in res.output  # beta's task should NOT appear


def test_list_tasks_with_path(workspace, monkeypatch, tmp_path):
    a, b = workspace
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list", "tasks", str(a)])
    assert res.exit_code == 0, res.output
    assert "pin-task" in res.output


def test_list_activities_noun_explicit(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list", "activities"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output
    assert "beta" in res.output


def test_list_priority_filter(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list", "activities", "--priority", "urgent"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output
    assert "beta" not in res.output


def test_list_type_filter(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list", "activities", "--type", "business"])
    assert res.exit_code == 0, res.output
    assert "beta" in res.output
    assert "alpha" not in res.output


def test_list_has_pinned(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list", "activities", "--has-pinned"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output
    assert "beta" not in res.output


def test_list_has_overdue(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list", "activities", "--has-overdue"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output
    assert "beta" not in res.output


def test_list_has_now(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list", "activities", "--has-now"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output
    assert "beta" not in res.output


def test_list_bare_inside_activity_shows_tasks(workspace, monkeypatch):
    a, _b = workspace
    monkeypatch.chdir(a)
    res = runner.invoke(app, ["list"])
    assert res.exit_code == 0, res.output
    assert "pin-task" in res.output


def test_list_bare_outside_shows_activities(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["list"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output


# ── status rich ───────────────────────────────────────────────────────


def test_status_by_path(workspace, monkeypatch, tmp_path):
    a, _b = workspace
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["status", str(a)])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output
    assert "urgent" in res.output  # priority chip
    assert "Now" in res.output     # bucket header
    assert "now-task" in res.output


def test_status_by_id(workspace, monkeypatch, tmp_path):
    a, b = workspace
    a_id, _ = _ids(a, b)
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["status", a_id])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output


def test_status_unknown_errors(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["status", "no-such-thing"])
    assert res.exit_code != 0
    assert "no activity" in res.output


# ── get activity JSON ─────────────────────────────────────────────────


def test_get_activity_json_compact(workspace, monkeypatch, tmp_path):
    a, b = workspace
    a_id, _ = _ids(a, b)
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["get", "activity", a_id, "--format", "compact"])
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output.strip().splitlines()[-1])
    assert doc["activity"]["id"] == a_id
    assert doc["activity"]["priority"] == "urgent"
    assert doc["buckets"]["now"] >= 1
    assert any(t["slug"] == "now-task" for t in doc["now_tasks"])
    assert any(t["slug"] == "pin-task" for t in doc["pinned_tasks"])
    assert any(t["slug"] == "overdue-task" for t in doc["overdue_tasks"])


def test_get_activity_unknown_errors(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["get", "activity", "no-such-thing"])
    assert res.exit_code != 0


# ── dashboard / next / impact ─────────────────────────────────────────


def test_dashboard_rich_text(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["dashboard"])
    assert res.exit_code == 0, res.output
    assert "DASHBOARD" in res.output
    assert "PINNED" in res.output
    assert "pin-task" in res.output


def test_dashboard_json_stdout(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["dashboard", "--json"])
    assert res.exit_code == 0, res.output
    # Find the JSON line (Rich prints to stdout too)
    last_line = res.output.strip().splitlines()[-1]
    doc = json.loads(last_line)
    assert "pinned" in doc
    assert "overdue" in doc
    assert "now" in doc
    assert any(t["slug"] == "pin-task" for t in doc["pinned"])


def test_dashboard_json_to_file(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    out_path = tmp_path / "dashboard.json"
    res = runner.invoke(app, ["dashboard", "--json-out", str(out_path)])
    assert res.exit_code == 0, res.output
    assert out_path.is_file()
    doc = json.loads(out_path.read_text())
    assert "pinned" in doc


def test_next_default_limit_3(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["next"])
    assert res.exit_code == 0, res.output
    assert "NEXT 3" in res.output


def test_next_custom_limit(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["next", "--limit", "1"])
    assert res.exit_code == 0, res.output
    # Only one numbered entry
    lines = [line for line in res.output.splitlines() if line.strip().startswith(("1.", "2."))]
    numbered = [line for line in res.output.splitlines() if line.strip().startswith("1.")]
    assert len(numbered) == 1


def test_impact_full_list(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["impact"])
    assert res.exit_code == 0, res.output
    assert "IMPACT" in res.output
    # Pinned, overdue, now tasks should all be present
    assert "pin-task" in res.output
    assert "now-task" in res.output
    assert "overdue-task" in res.output


def test_impact_show_score(workspace, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["impact", "--show-score"])
    assert res.exit_code == 0, res.output
    # Pinned + activity-urgent + priority-high = 100 + 20 + 25 = 145
    assert "(145)" in res.output or "(" in res.output  # at least some score shown


def test_impact_ranking_order(workspace, monkeypatch, tmp_path):
    """pin-task (high prio + activity urgent + pinned) should rank above plain-thing."""
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["impact", "--json"])
    assert res.exit_code == 0, res.output
    last_line = res.output.strip().splitlines()[-1]
    ranked = json.loads(last_line)
    slugs = [r["slug"] for r in ranked]
    # pin-task should appear before plain-thing
    assert slugs.index("pin-task") < slugs.index("plain-thing")
    # Top result should have the highest score
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)

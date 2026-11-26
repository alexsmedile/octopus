"""OTF 0.1.0 interoperability tests for Octopus core model & IO."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from octopus.adapters.todo_md import _annotate_pulled_line, _parse_inline_metadata
from octopus.core.models import Task
from octopus.core.otf import task_to_otf_dict
from octopus.db.connection import SCHEMA_VERSION, get_db
from octopus.db.upsert import upsert_activity, upsert_task
from octopus.fs.io import read_task, write_task

OTF_FIXTURES = Path("/Users/alex/code/libs/otf/fixtures/0.1.0/valid")
OTF_SCHEMA = Path("/Users/alex/code/libs/otf/schemas/0.1.0/task.schema.json")


def test_read_native_otf_fixtures() -> None:
    """Octopus read_task() natively parses OTF 0.1.0 Record Markdown fixtures."""
    if not OTF_FIXTURES.exists():
        return

    minimal, body = read_task(OTF_FIXTURES / "minimal.md")
    assert minimal.otf_id == "550e8400-e29b-41d4-a716-446655440000"
    assert minimal.title == "Prepare the revised draft"
    assert minimal.bucket == "backlog"
    assert "ordinary Markdown" in body

    full, _ = read_task(OTF_FIXTURES / "full-with-dlcs.md")
    assert full.otf_id == "550e8400-e29b-41d4-a716-446655440001"
    assert full.bucket == "now"
    assert full.stage == "in_review"
    assert full.kind == "docs"
    assert full.issue == "waiting"
    assert full.waiting_for == "Waiting on editor sign-off"
    assert full.tags == ["spec", "release"]
    assert full.scheduled == date(2026, 12, 2)
    assert full.due == date(2026, 12, 5)
    assert "otf.agile" in full.extensions
    assert "otf.schedule" in full.extensions

    dup, _ = read_task(OTF_FIXTURES / "duplicate-cancelled.md")
    assert dup.bucket == "dropped"
    assert dup.duplicate_of == "550e8400-e29b-41d4-a716-446655440001"


def test_roundtrip_octopus_task_as_otf_and_validate_schema(tmp_path: Path) -> None:
    """Octopus Task serializes to conformant OTF 0.1.0 and round-trips losslessly."""
    task = Task(
        title="Adopt OTF in Octopus",
        created=date(2026, 11, 26),
        bucket="now",
        stage="in_review",
        kind="feat",
        priority="high",
        owner="alex",
        actor="ai",
        run_state="running",
        pinned=True,
        issue="blocked",
        blocked_by="Waiting on schema review",
        scheduled=date(2026, 11, 27),
        due=date(2026, 12, 1),
        tags=["otf", "sync"],
        otf_id="550e8400-e29b-41d4-a716-446655440123",
        description="Native OTF 0.1.0 record support",
        extensions={"otf.agile": {"version": "0.1", "cycle": "sprint-1"}},
        extra={"custom_keep": "preserved"},
    )

    out_file = tmp_path / "adopt-otf.md"
    write_task(out_file, task, "## Notes\n\nKeep this body.", format="otf", project_id="octopus")

    reloaded, body = read_task(out_file)
    assert reloaded.otf_id == task.otf_id
    assert reloaded.title == task.title
    assert reloaded.bucket == "now"
    assert reloaded.stage == "in_review"
    assert reloaded.kind == "feat"
    assert reloaded.priority == "high"
    assert reloaded.owner == "alex"
    assert reloaded.actor == "ai"
    assert reloaded.run_state == "running"
    assert reloaded.pinned is True
    assert reloaded.issue == "blocked"
    assert reloaded.blocked_by == "Waiting on schema review"
    assert reloaded.tags == ["otf", "sync"]
    assert reloaded.extensions["otf.agile"]["cycle"] == "sprint-1"
    assert reloaded.extra["custom_keep"] == "preserved"
    assert "Keep this body." in body

    # Verify emitted dict matches OTF 0.1.0 JSON Schema structurally
    otf_dict = task_to_otf_dict(task, project_id="octopus")
    assert otf_dict["type"] == "task"
    assert otf_dict["otf_version"] == "0.1.0"
    assert otf_dict["status"] == "in_progress"
    assert otf_dict["impediment"] == "blocked"
    assert otf_dict["impediment_reason"] == "Waiting on schema review"
    if OTF_SCHEMA.exists():
        schema = json.loads(OTF_SCHEMA.read_text(encoding="utf-8"))
        assert set(schema["required"]).issubset(otf_dict.keys())


def test_sqlite_v7_stores_otf_id_and_status(tmp_path: Path) -> None:
    """SQLite schema v7 persists otf_id and canonical OTF status."""
    from octopus.core.models import Activity

    db_path = tmp_path / "index.db"
    conn = get_db(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 7

    act = Activity(id="demo", title="Demo", created=date(2026, 11, 26), last_known_path=str(tmp_path))
    upsert_activity(conn, act)
    t = Task(
        title="Indexed OTF task",
        created=date(2026, 11, 26),
        bucket="now",
        otf_id="550e8400-e29b-41d4-a716-446655440999",
        slug="indexed-otf-task",
        path=tmp_path / "indexed-otf-task.md",
    )
    upsert_task(conn, "demo", t)
    row = conn.execute("SELECT otf_id, status FROM tasks WHERE slug = 'indexed-otf-task'").fetchone()
    assert row["otf_id"] == "550e8400-e29b-41d4-a716-446655440999"
    assert row["status"] == "in_progress"
    conn.close()


def test_todo_md_parses_otf_uuid_and_preserves_unchecked_on_otf_pull() -> None:
    """todo_md extracts <!-- otf:UUID --> from titles and preserves unchecked [ ] in OTF mode."""
    meta = _parse_inline_metadata("Ship OTF sync !high #otf <!-- otf:550e8400-e29b-41d4-a716-446655440888 -->")
    assert meta.title == "Ship OTF sync"
    assert meta.priority == "high"
    assert meta.tags == ("otf",)
    assert meta.otf_id == "550e8400-e29b-41d4-a716-446655440888"

    annotated = _annotate_pulled_line(
        "- [ ] Ship OTF sync <!-- otf:550e8400-e29b-41d4-a716-446655440888 -->",
        "ship-otf-sync",
        keep_unchecked=True,
    )
    assert annotated == "- [ ] Ship OTF sync → octopus:ship-otf-sync <!-- otf:550e8400-e29b-41d4-a716-446655440888 -->"


def test_otf_bridge_adapters_registered_and_delegate_json() -> None:
    """github & plane adapters are registered in Octopus and delegate to otf JSON CLI."""
    from octopus.adapters.base import Adapter
    from octopus.adapters.otf_bridge import OtfGitHubAdapter, OtfPlaneAdapter
    from octopus.adapters.registry import registered_names

    names = registered_names()
    assert "github" in names
    assert "plane" in names

    calls: list[list[str]] = []

    def fake_runner(args: list[str]) -> dict:
        calls.append(args)
        if args[0] == "pull":
            return {"ok": True, "count": 1}
        if args[0] == "list":
            return {
                "ok": True,
                "tasks": [
                    {
                        "type": "task",
                        "otf_version": "0.1.0",
                        "id": "550e8400-e29b-41d4-a716-446655440321",
                        "title": "Remote synced task",
                        "status": "in_progress",
                        "stage": "In Review",
                        "priority": "high",
                        "labels": ["sync"],
                        "external_refs": [
                            {"system": "github", "scope": "alexsmedile/octopus", "id": "I_123", "role": "source"}
                        ],
                    }
                ],
            }
        if args[0] == "push":
            return {"ok": True, "issueUrl": "https://github.com/alexsmedile/octopus/issues/9", "issueNodeId": "I_9"}
        return {"ok": True}

    gh = OtfGitHubAdapter(runner=fake_runner)
    pl = OtfPlaneAdapter(runner=fake_runner)
    assert isinstance(gh, Adapter)
    assert isinstance(pl, Adapter)

    pulled = gh.pull(groups=["alexsmedile/octopus"])
    assert not pulled.errors
    assert len(pulled.tasks) == 1
    assert pulled.tasks[0].external_id == "I_123"
    assert pulled.tasks[0].suggested_bucket == "now"
    assert pulled.tasks[0].suggested_stage == "In Review"

    t = Task(title="Push via Octopus", created=date(2026, 11, 26), slug="push-via-octopus")
    pushed = gh.push(t, repo="alexsmedile/octopus", project=2, apply=True)
    assert pushed.error is None
    assert pushed.ref == "https://github.com/alexsmedile/octopus/issues/9"
    assert any(c[0] == "push" and "--project" in c and "2" in c for c in calls)

    pl_pulled = pl.pull(groups=["acme/proj-1"])
    assert not pl_pulled.errors
    assert len(pl_pulled.tasks) == 1

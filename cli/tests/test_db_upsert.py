"""Upsert layer: idempotency, default-omission, JSON blob shape."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from octopus.core.models import Activity, Task
from octopus.db.upsert import (
    delete_by_path,
    delete_task,
    upsert_activity,
    upsert_session,
    upsert_task,
)


def _make_activity(folder: Path, slug: str = "demo") -> Activity:
    return Activity(
        id=f"{slug}-a1b2",
        title="Demo",
        created=date(2026, 5, 1),
        type="code",
        status="active",
        last_known_path=str(folder),
    )


def _make_task(slug: str, path: Path, **overrides) -> Task:
    return Task(
        title=overrides.pop("title", "A task"),
        created=date(2026, 5, 1),
        bucket=overrides.pop("bucket", "backlog"),
        slug=slug,
        path=path,
        **overrides,
    )


def test_upsert_activity_inserts_then_updates(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    upsert_activity(temp_db, a)  # idempotent
    rows = temp_db.execute("SELECT * FROM activities").fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == a.id
    assert rows[0]["title"] == "Demo"


def test_upsert_activity_updates_fields(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    a.title = "Renamed"
    a.status = "paused"
    upsert_activity(temp_db, a)
    row = temp_db.execute("SELECT title, status FROM activities").fetchone()
    assert row["title"] == "Renamed"
    assert row["status"] == "paused"


def test_upsert_task_idempotent(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    t = _make_task("fix-bug", tmp_path / "fix-bug.md")
    upsert_task(temp_db, a.id, t)
    upsert_task(temp_db, a.id, t)
    rows = temp_db.execute("SELECT * FROM tasks").fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == f"{a.id}/fix-bug"
    assert rows[0]["bucket"] == "backlog"
    # pinned/archived absent → stored as NULL, not 0
    assert rows[0]["pinned"] is None
    assert rows[0]["archived"] is None


def test_upsert_task_raw_frontmatter_is_json(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    t = _make_task("x", tmp_path / "x.md", priority="urgent", tags=["a", "b"])
    upsert_task(temp_db, a.id, t)
    row = temp_db.execute("SELECT raw_frontmatter FROM tasks").fetchone()
    payload = json.loads(row["raw_frontmatter"])
    assert payload["priority"] == "urgent"
    assert payload["tags"] == ["a", "b"]
    # default-omission: pinned False / archived False should NOT appear
    assert "pinned" not in payload
    assert "archived" not in payload


def test_upsert_task_pinned_stored_as_one(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    t = _make_task("pin", tmp_path / "pin.md", pinned=True)
    upsert_task(temp_db, a.id, t)
    row = temp_db.execute("SELECT pinned FROM tasks").fetchone()
    assert row["pinned"] == 1


def test_upsert_task_requires_slug_and_path(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    t = Task(title="no slug", created=date(2026, 5, 1), bucket="backlog")
    try:
        upsert_task(temp_db, a.id, t)
    except ValueError as e:
        assert "slug" in str(e)
    else:
        raise AssertionError("expected ValueError for empty slug")


def test_upsert_session_and_delete(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    sess_path = tmp_path / "2026-05-23.md"
    upsert_session(
        temp_db, a.id,
        filename="2026-05-23", path=sess_path,
        title="Day log", started=None, ended=None,
        raw_frontmatter={"tags": ["x"]},
    )
    rows = temp_db.execute("SELECT * FROM sessions").fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == f"{a.id}/2026-05-23"
    n = delete_by_path(temp_db, "sessions", sess_path)
    assert n == 1
    assert temp_db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_delete_task_by_activity_and_slug(temp_db, tmp_path):
    a = _make_activity(tmp_path)
    upsert_activity(temp_db, a)
    t = _make_task("gone", tmp_path / "gone.md")
    upsert_task(temp_db, a.id, t)
    assert delete_task(temp_db, a.id, "gone") == 1
    assert temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_user_version_set_to_supported(temp_db):
    """Schema v4 via D88 (activity priority + last_touched_at)."""
    from octopus.db.connection import SCHEMA_VERSION

    v = temp_db.execute("PRAGMA user_version").fetchone()[0]
    assert v == SCHEMA_VERSION == 6


def test_foreign_keys_enforced(temp_db, tmp_path):
    """Cannot insert a task referencing an unknown activity_id."""
    t = _make_task("orphan", tmp_path / "orphan.md")
    try:
        upsert_task(temp_db, "ghost-0000", t)
    except Exception:
        return
    raise AssertionError("expected foreign-key violation for missing activity")

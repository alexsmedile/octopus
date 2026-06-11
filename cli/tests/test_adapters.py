"""Tests for the adapter framework (#06).

Covers:
- adapters.base: protocol + dataclasses sanity
- adapters.registry: built-in + entry-point + conflict resolution
- adapters.journal: read/write + sentinel cursor + corrupt-file recovery
- adapters.pipeline: resolve_groups (D59 matrix), materialize_pull_result,
  resolve_target_activity
- db schema v3: task_external_refs table + find_by_external_ref + backfill
- config: adapter config split (main + bridges/<name>.toml)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from octopus.adapters import (
    Adapter,
    AdapterStatus,
    Capability,
    ExternalRef,
    ExternalTask,
    PullResult,
)

# ── adapters.base ─────────────────────────────────────────────────────


def test_capability_enum_has_five_values():
    """v0.4.x shipped four; D74 (#22) added MARK_PULLED for source-annotating adapters."""
    assert {c.value for c in Capability} == {
        "pull", "push", "notify", "reconcile", "mark_pulled",
    }


def test_external_ref_is_str():
    assert ExternalRef is str


def test_dataclass_defaults():
    t = ExternalTask(external_id="x", title="t")
    assert t.suggested_bucket is None
    assert t.suggested_tags == []

    p = PullResult()
    assert p.tasks == [] and p.errors == [] and p.cursor is None

    s = AdapterStatus(name="foo", healthy=False)
    assert s.capabilities == set()


def test_stub_adapters_satisfy_protocol():
    """All built-in adapters implement the Adapter Protocol surface.

    Obsidian remains a stub as of v0.4.2. TODO.md (v0.4.1) and Reminders
    (v0.4.2) are real implementations.
    """
    from octopus.adapters.obsidian import ObsidianAdapter
    from octopus.adapters.reminders import RemindersAdapter
    from octopus.adapters.todo_md import TodoMdAdapter

    for cls in (ObsidianAdapter, RemindersAdapter, TodoMdAdapter):
        adapter = cls()
        assert isinstance(adapter, Adapter)
        assert Capability.PULL in adapter.capabilities

    # Only Obsidian is still a stub.
    obs_status = ObsidianAdapter().status()
    assert obs_status.healthy is False
    assert "not implemented" in obs_status.error.lower()

    # TodoMd is real (file-based — always healthy).
    todo_status = TodoMdAdapter().status()
    assert todo_status.healthy is True

    # Reminders is real but depends on remindctl + auth. On the dev box
    # both are present so it'll typically be healthy; on CI it won't be.
    # Either way the protocol shape is what we're checking here.
    rem_status = RemindersAdapter().status()
    assert isinstance(rem_status.healthy, bool)


# ── adapters.registry ─────────────────────────────────────────────────


def test_registry_contains_builtins():
    from octopus.adapters.registry import load_registry, registered_names

    reg = load_registry()
    assert set(reg.keys()) >= {"obsidian", "reminders", "todo-md"}
    assert registered_names() == sorted(reg.keys())


def test_registry_get_unknown_returns_none():
    from octopus.adapters.registry import get_adapter_class

    assert get_adapter_class("nope") is None


# ── adapters.journal ──────────────────────────────────────────────────


@pytest.fixture
def isolated_journal(monkeypatch, tmp_path: Path):
    """Sandbox XDG_DATA_HOME so journal tests don't touch the real home."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    yield tmp_path


def test_journal_missing_returns_defaults(isolated_journal):
    from octopus.adapters.journal import read_journal

    j = read_journal("reminders")
    assert j.adapter == "reminders"
    assert j.last_pull is None
    assert j.pull_count == 0
    assert j.cursor is None


def test_journal_write_then_read(isolated_journal):
    from octopus.adapters.journal import read_journal, update_journal

    j1 = update_journal("reminders", pulled=True, cursor="abc")
    assert j1.pull_count == 1
    assert j1.last_pull is not None
    assert j1.cursor == "abc"

    j2 = read_journal("reminders")
    assert j2.pull_count == 1
    assert j2.cursor == "abc"


def test_journal_cursor_sentinel_preserves(isolated_journal):
    """Omitting `cursor` should NOT clear it (sentinel behavior)."""
    from octopus.adapters.journal import update_journal

    update_journal("reminders", pulled=True, cursor="first")
    j = update_journal("reminders", pulled=True)  # no cursor kwarg
    assert j.cursor == "first"


def test_journal_explicit_none_cursor_clears(isolated_journal):
    from octopus.adapters.journal import update_journal

    update_journal("reminders", pulled=True, cursor="first")
    j = update_journal("reminders", cursor=None)
    assert j.cursor is None


def test_journal_corrupt_file_recovers(isolated_journal):
    from octopus.adapters.journal import journal_path, read_journal

    path = journal_path("reminders")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json {", encoding="utf-8")
    j = read_journal("reminders")
    assert j.pull_count == 0  # defaults


# ── adapters.pipeline (resolve_groups — D59 flag matrix) ─────────────


def test_resolve_groups_configured_only():
    from octopus.adapters.pipeline import resolve_groups

    assert resolve_groups(
        configured_lists=["A"], flag_list=None, flag_capture_all=False
    ) == ["A"]
    assert resolve_groups(
        configured_lists=["A", "B"], flag_list=None, flag_capture_all=False
    ) == ["A", "B"]


def test_resolve_groups_flag_overrides():
    from octopus.adapters.pipeline import resolve_groups

    assert resolve_groups(
        configured_lists=["A"], flag_list="X", flag_capture_all=False
    ) == ["X"]
    assert resolve_groups(
        configured_lists=None, flag_list="X,Y", flag_capture_all=False
    ) == ["X", "Y"]


def test_resolve_groups_capture_all():
    from octopus.adapters.pipeline import resolve_groups

    assert resolve_groups(
        configured_lists=None,
        flag_list=None,
        flag_capture_all=True,
        adapter_list_groups=["L1", "L2"],
    ) == ["L1", "L2"]


def test_resolve_groups_mutual_exclusion_exit_1():
    from octopus.adapters.pipeline import PipelineError, resolve_groups

    with pytest.raises(PipelineError) as exc:
        resolve_groups(configured_lists=None, flag_list="X", flag_capture_all=True)
    assert exc.value.exit_code == 1


def test_resolve_groups_pull_no_config_no_flag_exit_3():
    from octopus.adapters.pipeline import PipelineError, resolve_groups

    with pytest.raises(PipelineError) as exc:
        resolve_groups(configured_lists=None, flag_list=None, flag_capture_all=False, verb="pull")
    assert exc.value.exit_code == 3


def test_resolve_groups_peek_no_config_no_flag_returns_none():
    """peek with nothing → discovery mode (returns None, no exception)."""
    from octopus.adapters.pipeline import resolve_groups

    assert resolve_groups(
        configured_lists=None, flag_list=None, flag_capture_all=False, verb="peek"
    ) is None


# ── config: adapter helpers ───────────────────────────────────────────


@pytest.fixture
def isolated_config(monkeypatch, tmp_path: Path):
    """Sandbox OCTOPUS_CONFIG_HOME."""
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path))
    # Force reimport so SYSTEM_CONFIG_DIR picks up the new env var.
    import importlib

    import octopus.config

    importlib.reload(octopus.config)
    yield tmp_path
    # Clean up: reload again so subsequent tests get a fresh module
    importlib.reload(octopus.config)


def test_adapter_config_enable_disable_cycle(isolated_config):
    from octopus.config import (
        is_adapter_enabled,
        list_enabled_adapters,
        load_adapter_config,
        set_adapter_enabled,
        write_adapter_config,
    )

    assert not is_adapter_enabled("reminders")
    set_adapter_enabled("reminders", True)
    write_adapter_config("reminders", {"lists": ["Inbox"]})

    assert is_adapter_enabled("reminders")
    assert "reminders" in list_enabled_adapters()
    assert load_adapter_config("reminders")["lists"] == ["Inbox"]

    set_adapter_enabled("reminders", False)
    assert not is_adapter_enabled("reminders")
    # Disable MUST preserve bridges file
    assert load_adapter_config("reminders")["lists"] == ["Inbox"]


def test_adapter_config_write_handles_all_types(isolated_config):
    from octopus.config import load_adapter_config, write_adapter_config

    write_adapter_config(
        "test",
        {"name": "hello", "count": 42, "enabled": True, "items": ["a", "b"]},
    )
    data = load_adapter_config("test")
    assert data == {"name": "hello", "count": 42, "enabled": True, "items": ["a", "b"]}


# ── db: schema v3 + task_external_refs ────────────────────────────────


def test_schema_version_is_current(temp_db):
    from octopus.db.connection import SCHEMA_VERSION

    v = temp_db.execute("PRAGMA user_version").fetchone()[0]
    assert v == SCHEMA_VERSION == 5


def test_task_external_refs_table_exists(temp_db):
    rows = temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_external_refs'"
    ).fetchall()
    assert len(rows) == 1


def test_find_by_external_ref_returns_none_when_absent(temp_db):
    from octopus.db.queries import find_by_external_ref

    assert find_by_external_ref(temp_db, "reminders", "nope") is None


def test_upsert_task_populates_external_refs(temp_db, tmp_path: Path):
    from datetime import date

    from octopus.core.models import Task
    from octopus.db.queries import find_by_external_ref
    from octopus.db.upsert import upsert_activity, upsert_task
    from octopus.fs.scaffold import init_activity

    folder = tmp_path / "alpha"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    upsert_activity(temp_db, a)

    path = folder / ".octopus" / "tasks" / "backlog" / "foo.md"
    t = Task(
        title="Foo",
        created=date(2026, 5, 1),
        bucket="backlog",
        slug="foo",
        path=path,
        external_refs={"reminders": "uuid-123"},
    )
    upsert_task(temp_db, a.id, t)

    task_id = find_by_external_ref(temp_db, "reminders", "uuid-123")
    assert task_id == f"{a.id}/foo"


def test_upsert_task_updates_external_refs_on_change(temp_db, tmp_path: Path):
    """Re-upserting a task with different external_refs must clear stale entries."""
    from datetime import date

    from octopus.core.models import Task
    from octopus.db.queries import find_by_external_ref
    from octopus.db.upsert import upsert_activity, upsert_task
    from octopus.fs.scaffold import init_activity

    folder = tmp_path / "alpha"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    upsert_activity(temp_db, a)

    path = folder / ".octopus" / "tasks" / "backlog" / "foo.md"
    t = Task(
        title="Foo",
        created=date(2026, 5, 1),
        bucket="backlog",
        slug="foo",
        path=path,
        external_refs={"reminders": "uuid-old"},
    )
    upsert_task(temp_db, a.id, t)
    assert find_by_external_ref(temp_db, "reminders", "uuid-old") is not None

    # Change the ref
    t.external_refs = {"reminders": "uuid-new"}
    upsert_task(temp_db, a.id, t)
    assert find_by_external_ref(temp_db, "reminders", "uuid-old") is None
    assert find_by_external_ref(temp_db, "reminders", "uuid-new") == f"{a.id}/foo"


# ── pipeline: materialize_pull_result end-to-end ──────────────────────


@pytest.fixture
def activity_with_db(tmp_path: Path, monkeypatch):
    """Build a fresh activity and point the index at a fresh DB."""
    from octopus.fs.scaffold import init_activity

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "config"))
    # Force reimport so paths pick up env
    import importlib

    import octopus.config
    import octopus.db.connection

    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)

    folder = tmp_path / "act"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    yield folder
    importlib.reload(octopus.config)
    importlib.reload(octopus.db.connection)


def test_materialize_creates_new_task(activity_with_db: Path):
    from octopus.adapters.base import ExternalTask, PullResult
    from octopus.adapters.pipeline import materialize_pull_result
    from octopus.fs.io import read_task

    pr = PullResult(tasks=[ExternalTask(external_id="ex-1", title="buy milk")])
    result = materialize_pull_result(activity_with_db, "reminders", pr)

    assert result.new_count == 1
    assert result.skipped_count == 0
    assert result.error_count == 0

    # Task file exists
    slug = result.new_slugs[0]
    task_path = activity_with_db / ".octopus" / "tasks" / "backlog" / f"{slug}.md"
    assert task_path.exists()

    task, body = read_task(task_path)
    assert task.imported_from == "reminders"
    assert task.import_date == date.today()
    assert task.actor in (None, "human")  # human is default; either is correct
    assert task.external_refs["reminders"] == "ex-1"
    assert "Imported from reminders" in body


def test_materialize_dedups_on_rerun(activity_with_db: Path):
    """Second materialize of the same external_id must skip, not create."""
    from octopus.adapters.base import ExternalTask, PullResult
    from octopus.adapters.pipeline import materialize_pull_result

    et = ExternalTask(external_id="ex-1", title="buy milk")
    pr = PullResult(tasks=[et])

    r1 = materialize_pull_result(activity_with_db, "reminders", pr)
    assert r1.new_count == 1

    # Second run with same ExternalTask
    r2 = materialize_pull_result(activity_with_db, "reminders", PullResult(tasks=[et]))
    assert r2.new_count == 0
    assert r2.skipped_count == 1


def test_materialize_mixed_batch(activity_with_db: Path):
    """Batch with one known + one new → split correctly."""
    from octopus.adapters.base import ExternalTask, PullResult
    from octopus.adapters.pipeline import materialize_pull_result

    # Seed one
    materialize_pull_result(
        activity_with_db,
        "reminders",
        PullResult(tasks=[ExternalTask(external_id="known", title="A")]),
    )

    # Run with mixed batch
    pr = PullResult(
        tasks=[
            ExternalTask(external_id="known", title="A (already)"),  # dedupe
            ExternalTask(external_id="brand-new", title="B"),  # new
        ]
    )
    r = materialize_pull_result(activity_with_db, "reminders", pr)
    assert r.new_count == 1
    assert r.skipped_count == 1


def test_materialize_uses_suggested_bucket_and_kind(activity_with_db: Path):
    from octopus.adapters.base import ExternalTask, PullResult
    from octopus.adapters.pipeline import materialize_pull_result
    from octopus.fs.io import read_task

    pr = PullResult(
        tasks=[
            ExternalTask(
                external_id="ex",
                title="urgent thing",
                suggested_bucket="next",
                suggested_kind="bug",
                suggested_tags=["billing", "p0"],
            )
        ]
    )
    r = materialize_pull_result(activity_with_db, "reminders", pr)
    slug = r.new_slugs[0]
    task_path = activity_with_db / ".octopus" / "tasks" / "next" / f"{slug}.md"
    assert task_path.exists()
    task, _ = read_task(task_path)
    assert task.bucket == "next"
    assert task.kind == "bug"
    assert set(task.tags) == {"billing", "p0"}

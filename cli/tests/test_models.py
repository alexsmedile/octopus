"""Task validation tests — CRITICAL-DEPENDENCIES rule A (v1 schema).

Schema has no status/kind. Lifecycle is encoded via bucket + dates.
"""

from __future__ import annotations

from datetime import date

from octopus.core.models import Task


def _task(**kw) -> Task:
    defaults = {"title": "test", "created": date(2026, 5, 22)}
    defaults.update(kw)
    return Task(**defaults)


def test_minimal_task_is_valid():
    t = _task()
    assert t.validate() == []


def test_bucket_done_requires_both_dates():
    t = _task(bucket="done")
    errors = t.validate()
    assert any("requires start_date" in e for e in errors)
    assert any("requires end_date" in e for e in errors)


def test_bucket_done_with_dates_is_valid():
    t = _task(bucket="done", start_date=date(2026, 5, 20), end_date=date(2026, 5, 22))
    assert t.validate() == []


def test_bucket_dropped_requires_end_date_only():
    t = _task(bucket="dropped")
    assert any("bucket: dropped requires end_date" in e for e in t.validate())


def test_dropped_without_start_date_is_valid():
    t = _task(bucket="dropped", end_date=date(2026, 5, 22))
    assert t.validate() == []


def test_end_date_before_start_date_rejected():
    t = _task(bucket="done", start_date=date(2026, 5, 22), end_date=date(2026, 5, 20))
    assert any(">= start_date" in e for e in t.validate())


def test_terminal_bucket_cannot_have_issue():
    t = _task(
        bucket="done", start_date=date(2026, 5, 20), end_date=date(2026, 5, 22),
        issue="blocked", blocked_by="x",
    )
    assert any("cannot have issue" in e for e in t.validate())


def test_terminal_bucket_cannot_be_pinned():
    t = _task(
        bucket="done", start_date=date(2026, 5, 20), end_date=date(2026, 5, 22),
        pinned=True,
    )
    assert any("cannot have pinned" in e for e in t.validate())


def test_end_date_requires_terminal_bucket():
    t = _task(bucket="now", end_date=date(2026, 5, 22))
    assert any("end_date present requires bucket: done or dropped" in e for e in t.validate())


def test_blocked_requires_blocked_by():
    t = _task(issue="blocked")
    assert any("issue: blocked requires blocked_by" in e for e in t.validate())


def test_waiting_requires_waiting_for():
    t = _task(issue="waiting")
    assert any("issue: waiting requires waiting_for" in e for e in t.validate())


def test_invalid_bucket_rejected():
    t = _task(bucket="urgent")
    assert any("task.bucket='urgent'" in e for e in t.validate())


def test_run_state_validation():
    t = _task(run_state="bogus")
    assert any("task.run_state='bogus'" in e for e in t.validate())
    assert _task(run_state="running").validate() == []
    assert _task(run_state="failed").validate() == []


def test_priority_validation():
    assert _task(priority="urgent").validate() == []
    assert _task(priority="low").validate() == []
    # `medium` no longer valid in v1 — normal is absent
    t = _task(priority="medium")
    assert any("task.priority='medium'" in e for e in t.validate())


def test_actor_includes_automation():
    assert _task(actor="automation").validate() == []
    assert _task(actor="ai").validate() == []
    assert _task(actor="human").validate() == []


def test_legacy_status_field_rejected():
    t = _task()
    t.extra["status"] = "doing"
    assert any("legacy field 'status'" in e for e in t.validate())


def test_kind_field_accepted():
    """D46 — kind is no longer legacy; it's a v1 work-classification enum."""
    t = _task(kind="bug")
    errors = t.validate()
    assert not any("legacy field 'kind'" in e for e in errors)


def test_unknown_kind_warns_not_rejected():
    """D46 — unknown kind values warn (via smells), don't reject."""
    t = _task(kind="weirdkind")
    assert t.validate() == [] or "legacy" not in " ".join(t.validate())
    assert any("weirdkind" in w for w in t.smells())


def test_legacy_open_field_rejected():
    t = _task()
    t.extra["open"] = True
    assert any("legacy field 'open'" in e for e in t.validate())


def test_is_terminal():
    assert _task(bucket="done", start_date=date(2026, 5, 20), end_date=date(2026, 5, 21)).is_terminal()
    assert _task(bucket="dropped", end_date=date(2026, 5, 21)).is_terminal()
    assert not _task(bucket="now").is_terminal()
    assert not _task(bucket="backlog").is_terminal()

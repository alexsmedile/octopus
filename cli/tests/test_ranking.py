"""Unit tests for the R1 ranking heuristic (D89)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from octopus.core.ranking import (
    W_ACTIVITY_PRIORITY_HIGH,
    W_ACTIVITY_PRIORITY_URGENT,
    W_BLOCKED,
    W_DUE_SOON_BASE,
    W_NOW_BUCKET,
    W_OVERDUE_BASE,
    W_OVERDUE_DAY_CAP,
    W_PINNED,
    W_PRIORITY_HIGH,
    W_PRIORITY_URGENT,
    score_task,
)


@dataclass
class T:
    """Minimal duck-typed task for the ranker."""
    bucket: str = "backlog"
    pinned: bool | None = None
    archived: bool | None = None
    due: date | None = None
    priority: str | None = None
    issue: str | None = None


TODAY = date(2026, 5, 24)


def test_archived_excluded():
    assert score_task(T(archived=True), today=TODAY) is None


def test_done_bucket_excluded():
    assert score_task(T(bucket="done"), today=TODAY) is None


def test_dropped_bucket_excluded():
    assert score_task(T(bucket="dropped"), today=TODAY) is None


def test_empty_task_scores_zero():
    s = score_task(T(), today=TODAY)
    assert s is not None
    assert s.total == 0


def test_pinned():
    s = score_task(T(pinned=True), today=TODAY)
    assert s.pinned == W_PINNED


def test_now_bucket():
    s = score_task(T(bucket="now"), today=TODAY)
    assert s.now_bucket == W_NOW_BUCKET


def test_priority_urgent():
    s = score_task(T(priority="urgent"), today=TODAY)
    assert s.priority == W_PRIORITY_URGENT


def test_priority_high():
    s = score_task(T(priority="high"), today=TODAY)
    assert s.priority == W_PRIORITY_HIGH


def test_priority_low_no_contribution():
    s = score_task(T(priority="low"), today=TODAY)
    assert s.priority == 0


def test_overdue_one_day():
    s = score_task(T(due=TODAY - timedelta(days=1)), today=TODAY)
    assert s.overdue == W_OVERDUE_BASE + 1


def test_overdue_caps_at_30_days():
    s = score_task(T(due=TODAY - timedelta(days=100)), today=TODAY)
    assert s.overdue == W_OVERDUE_BASE + W_OVERDUE_DAY_CAP


def test_due_today_treated_as_due_soon():
    s = score_task(T(due=TODAY), today=TODAY)
    assert s.due_soon == W_DUE_SOON_BASE


def test_due_soon_decays():
    s = score_task(T(due=TODAY + timedelta(days=3)), today=TODAY)
    assert s.due_soon == W_DUE_SOON_BASE - 3


def test_due_past_seven_days_no_due_soon():
    s = score_task(T(due=TODAY + timedelta(days=8)), today=TODAY)
    assert s.due_soon == 0
    assert s.overdue == 0


def test_blocked_negative():
    s = score_task(T(issue="blocked"), today=TODAY)
    assert s.blocked == W_BLOCKED


def test_waiting_also_blocked():
    s = score_task(T(issue="waiting"), today=TODAY)
    assert s.blocked == W_BLOCKED


def test_activity_priority_urgent():
    s = score_task(T(), activity_priority="urgent", today=TODAY)
    assert s.activity_priority == W_ACTIVITY_PRIORITY_URGENT


def test_activity_priority_high():
    s = score_task(T(), activity_priority="high", today=TODAY)
    assert s.activity_priority == W_ACTIVITY_PRIORITY_HIGH


def test_composite_pinned_urgent_now():
    s = score_task(T(bucket="now", pinned=True, priority="urgent"), today=TODAY)
    assert s.total == W_PINNED + W_NOW_BUCKET + W_PRIORITY_URGENT
    assert s.total == 100 + 40 + 50  # 190


def test_composite_overdue_blocked():
    """Overdue + blocked: overdue contributes positively, blocked penalizes."""
    s = score_task(
        T(due=TODAY - timedelta(days=5), issue="blocked", priority="high"),
        activity_priority="urgent",
        today=TODAY,
    )
    expected = (
        W_OVERDUE_BASE + 5
        + W_PRIORITY_HIGH
        + W_ACTIVITY_PRIORITY_URGENT
        + W_BLOCKED
    )
    assert s.total == expected


def test_total_is_sum_of_breakdown():
    s = score_task(
        T(bucket="now", pinned=True, priority="urgent", due=TODAY + timedelta(days=2)),
        activity_priority="high",
        today=TODAY,
    )
    assert s.total == (
        s.pinned + s.overdue + s.now_bucket + s.due_soon
        + s.priority + s.activity_priority + s.blocked
    )

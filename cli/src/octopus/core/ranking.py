"""Ranking heuristic R1 (D89) for `next` / `impact` views.

Single-pass numeric score per task. Higher = more impact. The algorithm
is locked for v1; weights may become configurable in a later request, but
the call sites stay stable.

Weights:

| Signal                          | Weight                       |
|---------------------------------|------------------------------|
| pinned: true                    | +100                         |
| overdue                         | +80 + days_overdue (cap +30) |
| bucket: now                     | +40                          |
| due soon (<= 7 days)            | +30 − days_until_due         |
| priority: urgent (task)         | +50                          |
| priority: high   (task)         | +25                          |
| activity priority: urgent       | +20                          |
| activity priority: high         | +10                          |
| issue: blocked / waiting        | −30                          |

Excluded entirely (returns None): archived tasks, done bucket, dropped bucket.

Ties broken by `last_touched_at` ascending (older = stale = bubbles up); the
ranker leaves that to the caller — it just returns the numeric score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

W_PINNED = 100
W_OVERDUE_BASE = 80
W_OVERDUE_DAY_CAP = 30
W_NOW_BUCKET = 40
W_DUE_SOON_BASE = 30
W_DUE_SOON_WINDOW = 7
W_PRIORITY_URGENT = 50
W_PRIORITY_HIGH = 25
W_ACTIVITY_PRIORITY_URGENT = 20
W_ACTIVITY_PRIORITY_HIGH = 10
W_BLOCKED = -30


@dataclass
class ScoreBreakdown:
    """Per-signal contribution; sum() == total."""

    pinned: int = 0
    overdue: int = 0
    now_bucket: int = 0
    due_soon: int = 0
    priority: int = 0
    activity_priority: int = 0
    blocked: int = 0

    @property
    def total(self) -> int:
        return (
            self.pinned + self.overdue + self.now_bucket + self.due_soon
            + self.priority + self.activity_priority + self.blocked
        )


def score_task(
    task: Any,
    *,
    activity_priority: str | None = None,
    today: date | None = None,
) -> ScoreBreakdown | None:
    """Return the score breakdown for a task. Returns None if excluded.

    `task` is duck-typed for any object with the Task fields used here:
    `archived`, `bucket`, `pinned`, `due`, `priority`, `issue`.
    `today` defaults to date.today() — overridable for deterministic tests.
    """
    today = today or date.today()

    if getattr(task, "archived", None):
        return None
    bucket = getattr(task, "bucket", None)
    if bucket in {"done", "dropped"}:
        return None

    score = ScoreBreakdown()

    if getattr(task, "pinned", None):
        score.pinned = W_PINNED

    due = getattr(task, "due", None)
    if due is not None:
        delta_days = (due - today).days
        if delta_days < 0:
            days_overdue = min(-delta_days, W_OVERDUE_DAY_CAP)
            score.overdue = W_OVERDUE_BASE + days_overdue
        elif 0 <= delta_days <= W_DUE_SOON_WINDOW:
            score.due_soon = W_DUE_SOON_BASE - delta_days

    if bucket == "now":
        score.now_bucket = W_NOW_BUCKET

    priority = getattr(task, "priority", None)
    if priority == "urgent":
        score.priority = W_PRIORITY_URGENT
    elif priority == "high":
        score.priority = W_PRIORITY_HIGH

    if activity_priority == "urgent":
        score.activity_priority = W_ACTIVITY_PRIORITY_URGENT
    elif activity_priority == "high":
        score.activity_priority = W_ACTIVITY_PRIORITY_HIGH

    if getattr(task, "issue", None) in {"blocked", "waiting"}:
        score.blocked = W_BLOCKED

    return score

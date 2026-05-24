"""Domain models: Activity and Task.

Lightweight dataclasses backed by frontmatter. Mirrors the v1 schema:
- Five-value bucket (pipeline absorbs lifecycle terminal states).
- No `status` or `kind` field.
- `pinned` (not `open`) for attention axis.
- `stage` (free-form) for domain workflow.
- `run_state` for machine execution axis.
- Default-omission: defaults aren't stored in frontmatter on write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ── Enums (matching SPEC) ────────────────────────────────────────────

ACTIVITY_TYPES = {
    "code", "business", "content", "skill",
    "automation", "research", "personal", "other",
}
ACTIVITY_STATUSES = {
    "active", "next", "paused", "planning",
    "maintenance", "reference", "archive", "unknown",
}

# Pipeline axis — five values now (backlog/next/now + terminal done/dropped).
TASK_BUCKETS = {"backlog", "next", "now", "done", "dropped"}
TERMINAL_BUCKETS = {"done", "dropped"}

# Runtime axis.
TASK_RUN_STATES = {"queued", "running", "finished", "failed"}

# Impediment axis.
TASK_ISSUES = {"blocked", "waiting"}

# Prioritization.
# Absent = normal. Explicit values are escalations or de-escalations.
TASK_PRIORITIES = {"low", "high", "urgent"}
TASK_ENERGIES = {"low", "mid", "high"}

# Actor — added `automation` for deterministic scripts (distinct from `ai`).
TASK_ACTORS = {"human", "ai", "automation"}

# Taxonomy (D46) — work-classification, optional. Soft validation v1.
TASK_KINDS = {"feat", "bug", "spec", "polish", "test", "chore"}

# Defaults that should be omitted from written frontmatter.
DEFAULT_ACTOR = "human"
DEFAULT_BUCKET = "backlog"


@dataclass
class Activity:
    """activity.md frontmatter — unchanged by 02b."""

    id: str
    title: str
    created: date
    kind: str = "activity"
    spec_version: int = 1
    type: str = "other"
    status: str = "active"
    area: str | None = None
    priority: str | None = None         # D87 — low|high|urgent; None = normal
    last_reviewed: date | None = None
    last_known_path: str = ""
    source_of_truth: str = "."
    locations: list[str] = field(default_factory=list)
    linked_activities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    folder_path: Path | None = field(default=None, repr=False)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.id:
            errors.append("activity.id is required")
        if not self.title:
            errors.append("activity.title is required")
        if self.type not in ACTIVITY_TYPES:
            errors.append(f"activity.type={self.type!r} not in {sorted(ACTIVITY_TYPES)}")
        if self.status not in ACTIVITY_STATUSES:
            errors.append(f"activity.status={self.status!r} not in {sorted(ACTIVITY_STATUSES)}")
        if self.kind != "activity":
            errors.append(f"activity.kind={self.kind!r} must be 'activity' in v1")
        if not self.last_known_path:
            errors.append("activity.last_known_path is required")
        if self.spec_version != 1:
            errors.append(f"activity.spec_version={self.spec_version} not supported")
        # D87 — strict enum on activity priority (same set as tasks, None = normal)
        if self.priority is not None and self.priority not in {"low", "high", "urgent"}:
            errors.append(
                f"activity.priority={self.priority!r} not in [low, high, urgent] (or omit for normal)"
            )
        return errors


@dataclass
class Task:
    """tasks/<slug>.md frontmatter — v1 schema (02b collapse + D46/D48).

    Notable changes from pre-02b:
    - bucket is 5-valued (added done, dropped).
    - status, open fields removed.
    - pinned, stage, run_state added.
    - actor includes 'automation'.
    - priority normal is absent (no 'medium' value).
    - kind added back as work-classification (feat/bug/spec/polish/test/chore) — D46.
    - promoted_to added as <provider>:<id> promotion marker — D48.
    """

    title: str
    created: date

    # Workflow
    bucket: str = DEFAULT_BUCKET
    stage: str | None = None

    # Runtime
    run_state: str | None = None

    # Attention / impediment / visibility
    pinned: bool | None = None  # absent = not pinned
    issue: str | None = None
    blocked_by: str | None = None
    waiting_for: str | None = None
    archived: bool | None = None  # absent = visible

    # Dates
    due: date | None = None
    scheduled: date | None = None
    start_date: date | None = None
    end_date: date | None = None

    # Prioritization
    priority: str | None = None  # absent = normal
    energy: str | None = None

    # Actors
    actor: str | None = None  # absent = human
    owner: str | None = None

    # Taxonomy
    kind: str | None = None  # D46 — soft enum; unknown values warn but don't reject
    tags: list[str] = field(default_factory=list)

    # Integrations & provenance
    external_refs: dict[str, str] = field(default_factory=dict)
    import_date: date | None = None
    imported_from: str | None = None
    promoted_to: str | None = None  # D48 — "<provider>:<identifier>"

    # Not serialized:
    slug: str = field(default="", repr=False)
    path: Path | None = field(default=None, repr=False)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def is_terminal(self) -> bool:
        return self.bucket in TERMINAL_BUCKETS

    def effective_actor(self) -> str:
        return self.actor if self.actor is not None else DEFAULT_ACTOR

    def validate(self) -> list[str]:
        """Validation per CRITICAL-DEPENDENCIES.md rule A."""
        errors: list[str] = []

        # Required
        if not self.title:
            errors.append("task.title is required")
        if self.bucket not in TASK_BUCKETS:
            errors.append(f"task.bucket={self.bucket!r} not in {sorted(TASK_BUCKETS)}")

        # Enum validation for optional fields when present
        if self.run_state is not None and self.run_state not in TASK_RUN_STATES:
            errors.append(f"task.run_state={self.run_state!r} not in {sorted(TASK_RUN_STATES)}")
        if self.issue is not None and self.issue not in TASK_ISSUES:
            errors.append(f"task.issue={self.issue!r} not in {sorted(TASK_ISSUES)}")
        if self.priority is not None and self.priority not in TASK_PRIORITIES:
            errors.append(f"task.priority={self.priority!r} not in {sorted(TASK_PRIORITIES)}")
        if self.energy is not None and self.energy not in TASK_ENERGIES:
            errors.append(f"task.energy={self.energy!r} not in {sorted(TASK_ENERGIES)}")
        if self.actor is not None and self.actor not in TASK_ACTORS:
            errors.append(f"task.actor={self.actor!r} not in {sorted(TASK_ACTORS)}")

        # Cross-field rules (CRITICAL-DEPENDENCIES.md rule A)
        if self.bucket == "done":
            if self.start_date is None:
                errors.append("bucket: done requires start_date")
            if self.end_date is None:
                errors.append("bucket: done requires end_date")
        if self.bucket == "dropped" and self.end_date is None:
            errors.append("bucket: dropped requires end_date")
        if self.is_terminal() and self.issue is not None:
            errors.append(f"bucket: {self.bucket} cannot have issue set")
        if self.is_terminal() and self.pinned:
            errors.append(f"bucket: {self.bucket} cannot have pinned: true")
        if self.end_date is not None and not self.is_terminal():
            errors.append("end_date present requires bucket: done or dropped")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            errors.append("end_date must be >= start_date")
        if self.issue == "blocked" and not self.blocked_by:
            errors.append("issue: blocked requires blocked_by")
        if self.issue == "waiting" and not self.waiting_for:
            errors.append("issue: waiting requires waiting_for")

        # Forbidden legacy fields surfaced via `extra`
        # NOTE: `kind` was previously forbidden but is now a v1 work-classification
        # field (D46). It's parsed into self.kind, not self.extra. If something
        # ended up in extra under "kind" it's a parser bug.
        for forbidden in ("status", "open"):
            if forbidden in self.extra:
                errors.append(
                    f"legacy field {forbidden!r} is not allowed in v1 (see DECISIONS D32/D33/D34)"
                )

        # promoted_to format check (D48): "<provider>:<identifier>"
        if self.promoted_to is not None:
            if ":" not in self.promoted_to:
                errors.append(
                    f"promoted_to={self.promoted_to!r} must be '<provider>:<identifier>'"
                )
            else:
                provider, _, identifier = self.promoted_to.partition(":")
                if not provider or not identifier:
                    errors.append(
                        f"promoted_to={self.promoted_to!r} has empty provider or identifier"
                    )

        return errors

    def smells(self) -> list[str]:
        """SHOULD-warn smells per CRITICAL-DEPENDENCIES.md rule E."""
        warnings: list[str] = []
        # `bucket: backlog + pinned + old` warning is created/now-based;
        # the CLI computes it at write time (we don't have "now" here).
        if (
            self.start_date is not None
            and not self.is_terminal()
            and self.pinned is not True
            and self.bucket in {"next", "backlog"}
        ):
            warnings.append(
                "started but not pinned and not in 'now' — stalled?"
            )
        if self.issue == "waiting" and not self.waiting_for:
            warnings.append("issue: waiting without waiting_for")
        # Soft kind validation (D46): unknown values warn but don't reject.
        if self.kind is not None and self.kind not in TASK_KINDS:
            warnings.append(
                f"kind={self.kind!r} not in v1 enum {sorted(TASK_KINDS)} — proceeding anyway"
            )
        return warnings


# ── Session / Memory / Handoff (request 04) ──────────────────────────

SESSION_STATUSES = {"doing", "done", "dropped"}
HANDOFF_STATUSES = {"open", "received", "resolved", "stale"}
HANDOFF_ACTORS = {"human", "ai", "both"}
HANDOFF_PRIORITIES = {"high", "medium", "low"}

DEFAULT_HANDOFF_ACTOR = "human"
DEFAULT_HANDOFF_STATUS = "open"
DEFAULT_HANDOFF_PRIORITY = "medium"


@dataclass
class Session:
    """sessions/<filename>.md frontmatter — SCHEMA-SESSION.md v1.

    Filename is `YYYY-MM-DD-<slug>.md`. `active` is mirrored from the
    runtime cache file (`~/.cache/octopus/active-sessions.json`); cache wins
    on mismatch.
    """

    title: str
    started: datetime
    ended: datetime | None = None
    active: bool | None = None  # cache-mirrored; absent in frontmatter unless True
    status: str | None = None  # doing | done | dropped (absent = open)
    related_tasks: list[str] = field(default_factory=list)
    related_handoff: str | None = None
    summary: str | None = None

    # Not serialized
    filename: str = field(default="", repr=False)
    path: Path | None = field(default=None, repr=False)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def is_open(self) -> bool:
        return self.ended is None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.title:
            errors.append("session.title is required")
        if self.started is None:
            errors.append("session.started is required")
        if (
            self.ended is not None
            and self.started is not None
            and self.ended < self.started
        ):
            errors.append("session.ended must be >= started")
        if self.status is not None and self.status not in SESSION_STATUSES:
            errors.append(
                f"session.status={self.status!r} not in {sorted(SESSION_STATUSES)}"
            )
        # Cross-field invariants (SCHEMA-SESSION.md "MUST clear")
        if self.status == "dropped" and self.active is True:
            errors.append("session.status=dropped requires active=false")
        if self.ended is not None and self.active is True:
            errors.append("session.ended set requires active=false")
        if self.status == "done" and self.ended is None:
            errors.append("session.status=done requires ended")
        return errors


@dataclass
class Memory:
    """memory.md frontmatter — SCHEMA-MEMORY.md v1.

    The body is opaque to this dataclass — `memory/io.py` manages the
    two-zone split (marker `<!-- octopus-managed-below -->`).
    """

    activity: str
    last_updated: date
    summary: str | None = None
    tags: list[str] = field(default_factory=list)

    path: Path | None = field(default=None, repr=False)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.activity:
            errors.append("memory.activity is required")
        if self.last_updated is None:
            errors.append("memory.last_updated is required")
        return errors


@dataclass
class Handoff:
    """handoffs/<slug>.md frontmatter — SCHEMA-HANDOFF.md v1."""

    title: str
    created: date
    from_actor: str = DEFAULT_HANDOFF_ACTOR
    status: str = DEFAULT_HANDOFF_STATUS

    from_session: str | None = None
    to_actor: str | None = None
    to_owner: str | None = None
    related_tasks: list[str] = field(default_factory=list)
    related_activities: list[str] = field(default_factory=list)
    received_at: date | None = None
    resolved_at: date | None = None
    summary: str | None = None
    priority: str = DEFAULT_HANDOFF_PRIORITY
    tags: list[str] = field(default_factory=list)

    slug: str = field(default="", repr=False)
    path: Path | None = field(default=None, repr=False)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.title:
            errors.append("handoff.title is required")
        if self.created is None:
            errors.append("handoff.created is required")
        if self.from_actor not in HANDOFF_ACTORS:
            errors.append(
                f"handoff.from_actor={self.from_actor!r} not in {sorted(HANDOFF_ACTORS)}"
            )
        if self.to_actor is not None and self.to_actor not in HANDOFF_ACTORS:
            errors.append(
                f"handoff.to_actor={self.to_actor!r} not in {sorted(HANDOFF_ACTORS)}"
            )
        if self.status not in HANDOFF_STATUSES:
            errors.append(
                f"handoff.status={self.status!r} not in {sorted(HANDOFF_STATUSES)}"
            )
        if self.priority not in HANDOFF_PRIORITIES:
            errors.append(
                f"handoff.priority={self.priority!r} not in {sorted(HANDOFF_PRIORITIES)}"
            )
        if self.received_at is not None and self.status not in {"received", "resolved"}:
            errors.append("handoff.received_at requires status in {received, resolved}")
        if self.resolved_at is not None and self.status != "resolved":
            errors.append("handoff.resolved_at requires status=resolved")
        if (
            self.received_at is not None
            and self.resolved_at is not None
            and self.resolved_at < self.received_at
        ):
            errors.append("handoff.resolved_at must be >= received_at")
        if (
            self.resolved_at is not None
            and self.created is not None
            and self.resolved_at < self.created
        ):
            errors.append("handoff.resolved_at must be >= created")
        return errors

"""Adapter framework — protocol and data types.

The shared contract every external integration implements. See:
- `.spectacular/specs/SCHEMA-ADAPTER.md` — formal spec
- `.spectacular/DECISIONS.md D56–D66` — locked design

v1 ships only `PULL` adapters (Obsidian/Reminders/TODO.md). `PUSH`,
`NOTIFY`, `RECONCILE` are forward-stable capability flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Protocol, runtime_checkable

# ── capability enum (D56) ─────────────────────────────────────────────


class Capability(Enum):
    """Atomic adapter capability verbs. No meta-capabilities (D56)."""

    PULL = "pull"            # adapter.pull() works
    PUSH = "push"            # adapter.push() works
    NOTIFY = "notify"        # external change events (flag only in v1; method ships with #12)
    RECONCILE = "reconcile"  # has a conflict-resolution policy (flag only in v1; method ships with #10)
    MARK_PULLED = "mark_pulled"  # adapter annotates its source after successful pull (D74)


# ── data types ────────────────────────────────────────────────────────


# Opaque, adapter-defined. Apple Reminders uses x-apple-reminderkit URIs,
# GitHub uses owner/repo#N, TODO.md uses path#L<line>. The framework
# stores it verbatim into task frontmatter's external_refs.<adapter>.
ExternalRef = str


@dataclass
class ExternalTask:
    """An item the adapter wants to surface (peek) or import (pull).

    The framework never mutates the external system in response to these
    fields — adapters provide *suggestions* (suggested_*) and the pipeline
    materializes Octopus tasks using sensible defaults (see SCHEMA-ADAPTER §7.3).

    suggested_* fields mirror Task frontmatter 1-to-1 (D103). All optional;
    absent means "use the Task default." The pipeline applies them in the
    re-open pass after capture_task().
    """

    external_id: str                              # becomes external_refs.<adapter>
    title: str
    body: str | None = None

    # ── workflow ──────────────────────────────────────────────────────
    suggested_bucket: str | None = None           # backlog | next | now | done | dropped
    suggested_stage: str | None = None            # free-form domain workflow marker

    # ── attention / impediment ────────────────────────────────────────
    suggested_pinned: bool | None = None          # True → pinned: true
    suggested_issue: str | None = None            # blocked | waiting
    suggested_blocked_by: str | None = None
    suggested_waiting_for: str | None = None

    # ── dates ─────────────────────────────────────────────────────────
    suggested_due: date | None = None
    suggested_scheduled: date | None = None

    # ── prioritization ────────────────────────────────────────────────
    suggested_priority: str | None = None         # low | high | urgent (absent = normal)
    suggested_energy: str | None = None           # low | mid | high

    # ── actors ────────────────────────────────────────────────────────
    suggested_actor: str | None = None            # human | ai | automation (absent = human)
    suggested_owner: str | None = None

    # ── taxonomy ──────────────────────────────────────────────────────
    suggested_kind: str | None = None             # feat | bug | spec | polish | test | chore
    suggested_tags: list[str] = field(default_factory=list)

    # ── subtask graph (D104/D105) ─────────────────────────────────────
    suggested_parent: str | None = None            # parent slug (activity-scoped)

    # ── provenance ────────────────────────────────────────────────────
    created_external: datetime | None = None
    source_group: str | None = None               # which list/section/repo this came from


@dataclass
class PullResult:
    """Returned by `pull()`, `peek()`, and `search()`. Same shape; the
    framework decides whether to materialize based on which verb was invoked.
    """

    tasks: list[ExternalTask] = field(default_factory=list)
    cursor: str | None = None                                       # opaque resume token
    skipped: list[tuple[str, str]] = field(default_factory=list)    # (external_id, reason)
    errors: list[str] = field(default_factory=list)


@dataclass
class PushResult:
    """Returned by `push()`. ref is None on failure; error is non-None then."""

    ref: ExternalRef | None = None
    error: str | None = None


@dataclass
class AdapterStatus:
    """Health-check return shape. Populated from sync journal + adapter probe."""

    name: str
    healthy: bool
    last_pull: datetime | None = None
    last_push: datetime | None = None
    error: str | None = None
    capabilities: set[Capability] = field(default_factory=set)


# ── the protocol (D57) ────────────────────────────────────────────────


@runtime_checkable
class Adapter(Protocol):
    """The seven-method contract every adapter implements.

    `link()` from PRD §7.1 is intentionally absent — that was pipeline glue,
    not adapter behavior. The framework writes external_refs to task
    frontmatter after a successful pull/push.

    `groups` is opaque to the framework. Each adapter interprets it:
      - Reminders: list names
      - GitHub: repo specs (`owner/repo`)
      - ICS: calendar names
      - TODO.md: ignored (single file)
    """

    name: str
    capabilities: set[Capability]

    def status(self) -> AdapterStatus:
        """Health check + provenance metadata.

        MUST NOT touch the external system if known-unhealthy (e.g.
        Reminders adapter on a non-macOS host should return healthy=False
        without calling osascript).
        """
        ...

    def validate_config(self, data: dict) -> list[str]:
        """Return a list of error messages for the given config dict.

        Empty list = valid. Called by `octopus bridge enable` BEFORE
        persisting any state.
        """
        ...

    def list_groups(self) -> list[str]:
        """Discover available groups (lists, repos, calendars) the
        external system currently offers.

        Used by `peek` discovery mode (no default group, no flag) and
        `--capture-all` resolution.
        """
        ...

    def peek(self, groups: list[str] | None = None) -> PullResult:
        """READ-ONLY display. MUST NOT create files or modify external state.

        `groups=None` means "use configured defaults" (see SCHEMA-ADAPTER §4.3).
        """
        ...

    def pull(self, groups: list[str] | None = None) -> PullResult:
        """Fetch items for import. The adapter does NOT write Octopus
        files — it returns data; the framework's pipeline materializes
        tasks with provenance fields.
        """
        ...

    def push(self, task) -> PushResult:
        """Write a single Octopus task to the external system. v1 adapters
        return PushResult(error="not supported").
        """
        ...

    def search(self, query: str, groups: list[str] | None = None) -> PullResult:
        """Adapter-side search. Same shape as pull() but the framework
        treats results as display-only (no materialization).

        Adapters with native search APIs use them. Adapters without
        (TODO.md, basic Reminders) may implement as `peek(groups) + filter`.
        """
        ...

"""Task promotion — Octopus → Spectacular and other external targets.

Implements `octopus promote` semantics per D47–D54:

- one-way, task → request
- namespaced `promoted_to: <provider>:<identifier>` marker
- hard-coded 3-line stub body replacement
- multi-task atomic pre-flight
- `--force` repoints, `--revert` soft-clears
- reindex derives `related_tasks` on the request PLAN.md side

All helpers here are pure / file-local — the orchestration verb in
`actions.promote_task` wires them up with the existing read/write/sync helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from octopus.config import REGISTERED_PROVIDERS, Config

# ── target parsing ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class PromoteTarget:
    """Resolved promotion target. `canonical` is what gets written to frontmatter."""

    provider: str  # canonical provider name (e.g. "spectacular")
    identifier: str  # slug or external id
    create_new: bool  # True when an explicit ":new" was requested
    explicit_slug: bool  # True when the user typed an identifier (vs. shorthand)

    @property
    def canonical(self) -> str:
        return f"{self.provider}:{self.identifier}"


class PromotionError(Exception):
    """User-facing promotion error. Carries an exit-code hint."""

    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _resolve_chip(token: str, cfg: Config) -> str:
    """Resolve a chip alias to its canonical provider name, or return token unchanged."""
    for provider, chip in cfg.provider_chips.items():
        if chip == token:
            return provider
    return token


def parse_target(
    raw: str,
    *,
    task_slugs: list[str],
    cfg: Config,
) -> PromoteTarget:
    """Parse the `--to` argument into a canonical PromoteTarget.

    Input shapes:
      <provider>:<id>           explicit
      <chip>:<id>               chip alias accepted
      <id>                      uses cfg.provider_default
      <provider>                shorthand: <provider>:<task-slug> (single-task only)
      <provider>:new            requires --slug; create_new=True

    Raises PromotionError(exit_code=3) on invalid input.
    """
    if not raw:
        raise PromotionError("--to is required")

    if ":" in raw:
        provider, _, identifier = raw.partition(":")
        provider = _resolve_chip(provider, cfg)
        if provider not in REGISTERED_PROVIDERS:
            raise PromotionError(
                f"unknown provider {provider!r}; registered: {sorted(REGISTERED_PROVIDERS)}"
            )
        if not identifier:
            raise PromotionError(f"--to {raw!r} has empty identifier")
        if identifier == "new":
            return PromoteTarget(
                provider=provider, identifier="", create_new=True, explicit_slug=False
            )
        return PromoteTarget(
            provider=provider, identifier=identifier, create_new=False, explicit_slug=True
        )

    # No colon: either a bare provider or a bare identifier.
    resolved = _resolve_chip(raw, cfg)
    if resolved in REGISTERED_PROVIDERS:
        # Provider-only shorthand: use task slug as identifier (single-task only).
        if len(task_slugs) != 1:
            raise PromotionError(
                f"provider-only shorthand --to {raw!r} is ambiguous with "
                f"{len(task_slugs)} tasks; specify an explicit slug"
            )
        return PromoteTarget(
            provider=resolved,
            identifier=task_slugs[0],
            create_new=False,
            explicit_slug=False,
        )
    # Bare identifier — use default provider.
    return PromoteTarget(
        provider=cfg.provider_default,
        identifier=raw,
        create_new=False,
        explicit_slug=True,
    )


# ── spectacular layout ─────────────────────────────────────────────────


def spectacular_requests_dir(activity_root: Path) -> Path:
    return activity_root / ".spectacular" / "requests"


def spectacular_archive_dir(activity_root: Path) -> Path:
    return spectacular_requests_dir(activity_root) / "_archive"


def find_spectacular_request(activity_root: Path, slug: str) -> Path | None:
    """Locate an existing request directory (live or archived). None if absent."""
    requests = spectacular_requests_dir(activity_root)
    live = requests / slug
    if live.is_dir():
        return live
    archived = spectacular_archive_dir(activity_root) / slug
    if archived.is_dir():
        return archived
    return None


NUMBER_PREFIX_RE = re.compile(r"^\d+-")


def next_request_number(activity_root: Path) -> int:
    """Scan requests/ + _archive/ for NN- prefixes; return next free integer."""
    used: set[int] = set()
    for d in (spectacular_requests_dir(activity_root), spectacular_archive_dir(activity_root)):
        if not d.is_dir():
            continue
        for entry in d.iterdir():
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            m = NUMBER_PREFIX_RE.match(entry.name)
            if m:
                try:
                    used.add(int(m.group().rstrip("-")))
                except ValueError:
                    pass
    n = 1
    while n in used:
        n += 1
    return n


def apply_auto_number(slug: str, activity_root: Path, cfg: Config) -> str:
    """Prepend `NN-` if config says so and the slug doesn't already have one."""
    if not cfg.spectacular_auto_number:
        return slug
    if NUMBER_PREFIX_RE.match(slug):
        return slug
    return f"{next_request_number(activity_root):02d}-{slug}"


# ── PLAN.md scaffolding ────────────────────────────────────────────────


PLAN_TEMPLATE = """\
---
status: backlog
priority: medium
owner: alex
updated: {today}
summary: "{summary}"
related: []
gates: []
promoted_from: {promoted_from}
---

# {title}

## Goal

(TODO: write the goal — what does this request build, lock, or change?)

## Why

(TODO: explain the motivation — what makes this worth a full request?)

## Approach

(TODO: outline the implementation plan.)

## Deliverables

- [ ] (TODO)

## Out of scope (this request)

- (TODO)
"""


def scaffold_request(
    activity_root: Path,
    *,
    slug: str,
    title: str,
    promoted_from: str,
) -> Path:
    """Create a fresh request directory with a starter PLAN.md.

    Returns the path to the PLAN.md. Raises PromotionError if the directory
    already exists (caller should have smart-resolved before calling).
    """
    request_dir = spectacular_requests_dir(activity_root) / slug
    if request_dir.exists():
        raise PromotionError(f"request {slug!r} already exists", exit_code=3)
    request_dir.mkdir(parents=True, exist_ok=True)
    plan_path = request_dir / "PLAN.md"
    plan_path.write_text(
        PLAN_TEMPLATE.format(
            today=date.today().isoformat(),
            summary=f"Promoted from Octopus task '{promoted_from}'.",
            promoted_from=promoted_from,
            title=title,
        ),
        encoding="utf-8",
    )
    return plan_path


# ── stub body ──────────────────────────────────────────────────────────


STUB_TEMPLATE = """\
# {title}

Promoted to **[{canonical}](../../.spectacular/requests/{slug}/PLAN.md)** on {today}.

The request PLAN.md is the source of truth from here on.
"""


def render_stub(*, title: str, canonical: str, identifier: str) -> str:
    """Build the body that replaces a promoted task's original content."""
    return STUB_TEMPLATE.format(
        title=title,
        canonical=canonical,
        slug=identifier,
        today=date.today().isoformat(),
    )


# ── reindex helper ─────────────────────────────────────────────────────


def derive_related_tasks(promoted_to_values: list[str]) -> dict[str, list[str]]:
    """Build a `{spec-slug: [task-slugs]}` map from a flat list of promoted_to values.

    Input shape: each item is `(task_slug, promoted_to_value_or_None)` pair —
    callers pass that as a list of two-tuples encoded as ``"<slug>\\t<value>"``
    so this helper stays a pure function over strings (testable in isolation).

    Each entry like ``"task-a\\tspectacular:20-task-promotion"`` produces
    a key ``"20-task-promotion"`` in the returned map with ``"task-a"`` appended.
    Malformed values, non-spectacular providers, and empty rows are ignored.
    """
    result: dict[str, list[str]] = {}
    for entry in promoted_to_values:
        if "\t" not in entry:
            continue
        task_slug, value = entry.split("\t", 1)
        if not value or ":" not in value:
            continue
        provider, _, identifier = value.partition(":")
        if provider != "spectacular" or not identifier:
            continue
        result.setdefault(identifier, []).append(task_slug)
    for k in result:
        result[k] = sorted(set(result[k]))
    return result

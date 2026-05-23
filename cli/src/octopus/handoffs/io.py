"""Handoff frontmatter read/write + filesystem operations.

Body MUST be preserved byte-for-byte across CLI writes. v1 is filesystem-only
— no SQLite mirror. See `.spectacular/specs/SCHEMA-HANDOFF.md`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

from octopus.core.models import (
    DEFAULT_HANDOFF_ACTOR,
    DEFAULT_HANDOFF_PRIORITY,
    DEFAULT_HANDOFF_STATUS,
    Handoff,
)
from octopus.core.slug import slugify

HANDOFF_FIELDS = {
    "title", "created",
    "from_session", "from_actor", "to_actor", "to_owner",
    "related_tasks", "related_activities",
    "status", "received_at", "resolved_at",
    "summary", "priority", "tags",
}

FILENAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>.+)$")


class HandoffNotFoundError(FileNotFoundError):
    """Raised when a handoff slug doesn't resolve."""


# ── Path helpers ─────────────────────────────────────────────────────


def handoffs_dir(activity_root: Path) -> Path:
    """Return `<activity>/.octopus/handoffs/` (created on demand)."""
    return activity_root / ".octopus" / "handoffs"


def ensure_handoffs_dir(activity_root: Path) -> Path:
    d = handoffs_dir(activity_root)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Filename generation ──────────────────────────────────────────────


def generate_filename(
    title: str,
    *,
    when: date | None = None,
    existing: list[str] | None = None,
) -> str:
    """Return `YYYY-MM-DD-<slug>` (no extension). Collision-suffixed."""
    when = when or date.today()
    try:
        base_slug = slugify(title) if title and title.strip() else "handoff"
    except ValueError:
        base_slug = "handoff"
    candidate = f"{when.isoformat()}-{base_slug}"
    existing = existing or []
    if candidate not in existing:
        return candidate
    n = 2
    while f"{candidate}-{n}" in existing:
        n += 1
    return f"{candidate}-{n}"


# ── Date coercion ────────────────────────────────────────────────────


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to date")


# ── Read / write ─────────────────────────────────────────────────────


def read_handoff(path: Path) -> tuple[Handoff, str]:
    post = frontmatter.load(path)
    data = post.metadata
    extra = {k: v for k, v in data.items() if k not in HANDOFF_FIELDS}

    created = _coerce_date(data.get("created"))
    if created is None:
        raise ValueError(f"handoff {path} missing required 'created'")

    handoff = Handoff(
        title=str(data.get("title", "")),
        created=created,
        from_actor=str(data.get("from_actor", DEFAULT_HANDOFF_ACTOR)),
        status=str(data.get("status", DEFAULT_HANDOFF_STATUS)),
        from_session=data.get("from_session"),
        to_actor=data.get("to_actor"),
        to_owner=data.get("to_owner"),
        related_tasks=list(data.get("related_tasks") or []),
        related_activities=list(data.get("related_activities") or []),
        received_at=_coerce_date(data.get("received_at")),
        resolved_at=_coerce_date(data.get("resolved_at")),
        summary=data.get("summary"),
        priority=str(data.get("priority", DEFAULT_HANDOFF_PRIORITY)),
        tags=list(data.get("tags") or []),
        slug=path.stem,
        path=path,
        extra=extra,
    )
    return handoff, post.content


def write_handoff(path: Path, handoff: Handoff, body: str) -> None:
    """Write a handoff. Default-omission for from_actor/status/priority/lists."""
    data: dict[str, Any] = {
        "title": handoff.title,
        "created": handoff.created.isoformat(),
    }
    if handoff.from_session is not None:
        data["from_session"] = handoff.from_session
    if handoff.from_actor != DEFAULT_HANDOFF_ACTOR:
        data["from_actor"] = handoff.from_actor
    else:
        # `from_actor` is required by schema — always write it, even if default.
        data["from_actor"] = DEFAULT_HANDOFF_ACTOR
    if handoff.to_actor is not None:
        data["to_actor"] = handoff.to_actor
    if handoff.to_owner is not None:
        data["to_owner"] = handoff.to_owner
    if handoff.related_tasks:
        data["related_tasks"] = handoff.related_tasks
    if handoff.related_activities:
        data["related_activities"] = handoff.related_activities
    # `status` required — always emit.
    data["status"] = handoff.status
    if handoff.received_at is not None:
        data["received_at"] = handoff.received_at.isoformat()
    if handoff.resolved_at is not None:
        data["resolved_at"] = handoff.resolved_at.isoformat()
    if handoff.summary is not None:
        data["summary"] = handoff.summary
    if handoff.priority != DEFAULT_HANDOFF_PRIORITY:
        data["priority"] = handoff.priority
    if handoff.tags:
        data["tags"] = handoff.tags

    for k, v in handoff.extra.items():
        if k not in data:
            data[k] = v

    post = frontmatter.Post(body, **data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


# ── Body template ────────────────────────────────────────────────────


def default_body(title: str) -> str:
    """Recommended body template from SCHEMA-HANDOFF.md.

    Principle: handoffs are routers, not duplicates. Reference other artifacts
    (tasks, sessions, PRDs) by path; don't restate them here.
    """
    return (
        f"# {title}\n"
        "\n"
        "## TL;DR\n"
        "_One paragraph: where we are, where to go next._\n"
        "\n"
        "## What's done\n"
        "- \n"
        "\n"
        "## What's next\n"
        "- [ ] \n"
        "\n"
        "## Suggested next actions\n"
        "_Machine-actionable. Pick one and run it._\n"
        "- [ ] `octopus task list --pinned`\n"
        "- [ ] `octopus memory show --section open`\n"
        "- [ ] `octopus session start --title \"<resume>\"`\n"
        "\n"
        "## Open questions\n"
        "- \n"
        "\n"
        "## References\n"
        "_Link, don't restate. Use `[[task-slug]]`, `sessions/<filename>`, paths, URLs._\n"
        "- \n"
    )


# ── Listing ──────────────────────────────────────────────────────────


def list_handoffs(
    activity_root: Path, *, status: str | None = None
) -> list[Handoff]:
    """List handoffs for an activity, sorted by `created` ascending.

    Optional status filter.
    """
    d = handoffs_dir(activity_root)
    if not d.is_dir():
        return []
    handoffs: list[Handoff] = []
    for p in sorted(d.glob("*.md")):
        try:
            h, _ = read_handoff(p)
            handoffs.append(h)
        except (ValueError, OSError):
            continue
    if status:
        handoffs = [h for h in handoffs if h.status == status]
    handoffs.sort(key=lambda h: h.created)
    return handoffs


# ── new ──────────────────────────────────────────────────────────────


def new_handoff(
    activity_root: Path,
    title: str,
    *,
    from_session: str | None = None,
    from_actor: str = DEFAULT_HANDOFF_ACTOR,
    to_actor: str | None = None,
    to_owner: str | None = None,
    priority: str = DEFAULT_HANDOFF_PRIORITY,
    summary: str | None = None,
    related_tasks: list[str] | None = None,
    related_activities: list[str] | None = None,
    tags: list[str] | None = None,
    when: date | None = None,
    body: str | None = None,
) -> Handoff:
    """Create a new handoff file under `<activity>/.octopus/handoffs/`.

    Returns the created Handoff (with .path and .slug populated).
    """
    if not title or not title.strip():
        raise ValueError("handoff title is required")
    ensure_handoffs_dir(activity_root)
    existing = [p.stem for p in handoffs_dir(activity_root).glob("*.md")]
    filename = generate_filename(title, when=when, existing=existing)
    path = handoffs_dir(activity_root) / f"{filename}.md"

    handoff = Handoff(
        title=title.strip(),
        created=when or date.today(),
        from_actor=from_actor,
        status=DEFAULT_HANDOFF_STATUS,
        from_session=from_session,
        to_actor=to_actor,
        to_owner=to_owner,
        related_tasks=related_tasks or [],
        related_activities=related_activities or [],
        summary=summary,
        priority=priority,
        tags=tags or [],
        slug=filename,
        path=path,
    )
    errors = handoff.validate()
    if errors:
        raise ValueError("invalid handoff: " + "; ".join(errors))

    write_handoff(path, handoff, body if body is not None else default_body(title.strip()))
    return handoff


# ── show ─────────────────────────────────────────────────────────────


def show_handoff(activity_root: Path, slug: str) -> Handoff:
    """Resolve a slug to a Handoff. Raises HandoffNotFoundError."""
    path = handoffs_dir(activity_root) / f"{slug}.md"
    if not path.is_file():
        raise HandoffNotFoundError(f"handoff not found: {slug}")
    h, _ = read_handoff(path)
    return h

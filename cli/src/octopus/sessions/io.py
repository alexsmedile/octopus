"""Session frontmatter read/write + body manipulation.

Body MUST be preserved byte-for-byte across CLI writes except for the
documented `session log` append (a `### YYYY-MM-DD HH:MM:SS\\n<note>` block
at the bottom).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import frontmatter

from octopus.core.models import Session
from octopus.core.slug import slugify

SESSION_FIELDS = {
    "title", "started", "ended", "active", "status",
    "related_tasks", "related_handoff", "summary",
}

FILENAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>.+)$")


# ── Path helpers ─────────────────────────────────────────────────────


def sessions_dir(activity_root: Path) -> Path:
    """Return `<activity>/.octopus/sessions/` (created on demand)."""
    d = activity_root / ".octopus" / "sessions"
    return d


def ensure_sessions_dir(activity_root: Path) -> Path:
    d = sessions_dir(activity_root)
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
        base_slug = slugify(title) if title and title.strip() else "session"
    except ValueError:
        base_slug = "session"
    candidate = f"{when.isoformat()}-{base_slug}"
    existing = existing or []
    if candidate not in existing:
        return candidate
    n = 2
    while f"{candidate}-{n}" in existing:
        n += 1
    return f"{candidate}-{n}"


# ── Datetime coercion ────────────────────────────────────────────────


def _coerce_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # ISO 8601 with or without seconds
        return datetime.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to datetime")


# ── Read / write ─────────────────────────────────────────────────────


def read_session(path: Path) -> tuple[Session, str]:
    post = frontmatter.load(path)
    data = post.metadata
    extra = {k: v for k, v in data.items() if k not in SESSION_FIELDS}

    started = _coerce_dt(data.get("started"))
    if started is None:
        raise ValueError(f"session {path} missing required 'started'")

    session = Session(
        title=str(data.get("title", "")),
        started=started,
        ended=_coerce_dt(data.get("ended")),
        active=data.get("active") if isinstance(data.get("active"), bool) else None,
        status=data.get("status"),
        related_tasks=list(data.get("related_tasks") or []),
        related_handoff=data.get("related_handoff"),
        summary=data.get("summary"),
        filename=path.stem,
        path=path,
        extra=extra,
    )
    return session, post.content


def write_session(path: Path, session: Session, body: str) -> None:
    """Write a session file. Default-omission for `active`, `status`, lists."""
    data: dict[str, Any] = {
        "title": session.title,
        "started": session.started.isoformat(timespec="seconds"),
    }
    if session.ended is not None:
        data["ended"] = session.ended.isoformat(timespec="seconds")
    if session.active is True:
        data["active"] = True
    if session.status is not None:
        data["status"] = session.status
    if session.related_tasks:
        data["related_tasks"] = session.related_tasks
    if session.related_handoff is not None:
        data["related_handoff"] = session.related_handoff
    if session.summary is not None:
        data["summary"] = session.summary

    for k, v in session.extra.items():
        if k not in data:
            data[k] = v

    post = frontmatter.Post(body, **data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


# ── Body manipulation ────────────────────────────────────────────────


def append_log_entry(
    path: Path,
    note: str,
    *,
    when: datetime | None = None,
) -> None:
    """Append `### YYYY-MM-DD HH:MM:SS\\n<note>\\n` to the session body.

    Second precision per request 04 decision D41 Q2.
    """
    if not note.strip():
        raise ValueError("note must be non-empty")
    when = when or datetime.now()
    session, body = read_session(path)
    stamp = when.strftime("%Y-%m-%d %H:%M:%S")
    # Normalize trailing whitespace: ensure exactly one blank line before the heading.
    suffix = f"\n### {stamp}\n{note.rstrip()}\n"
    new_body = body.rstrip() + "\n" + suffix if body.strip() else suffix.lstrip("\n")
    write_session(path, session, new_body)


# ── Listing ──────────────────────────────────────────────────────────


def list_sessions(activity_root: Path) -> list[Session]:
    """List sessions for an activity, sorted by `started` ascending."""
    d = sessions_dir(activity_root)
    if not d.is_dir():
        return []
    sessions: list[Session] = []
    for p in sorted(d.glob("*.md")):
        try:
            s, _ = read_session(p)
            sessions.append(s)
        except (ValueError, OSError):
            continue
    sessions.sort(key=lambda s: s.started)
    return sessions

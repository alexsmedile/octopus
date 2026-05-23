"""Session lifecycle verbs: start / log / end / switch / prune / show / list.

Pure-Python semantics. The CLI layer wires these to typer commands +
typer.Exit codes + interactive prompts. Splitting keeps lifecycle
testable without touching stdin or the typer runner.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from octopus.core.models import Session
from octopus.sessions.cache import (
    clear_active,
    get_active,
    set_active,
)
from octopus.sessions.io import (
    append_log_entry,
    ensure_sessions_dir,
    generate_filename,
    list_sessions,
    read_session,
    sessions_dir,
    write_session,
)


class NoActiveSessionError(Exception):
    """Raised when a verb requires an active session and none is set."""


# ── helpers ──────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _open_sessions(activity_root: Path) -> list[Session]:
    return [s for s in list_sessions(activity_root) if s.is_open()]


def _existing_filenames(activity_root: Path) -> list[str]:
    return [s.filename for s in list_sessions(activity_root)]


def _path_for(activity_root: Path, filename: str) -> Path:
    return sessions_dir(activity_root) / f"{filename}.md"


def _append_auto_note(path: Path, message: str, *, when: datetime | None = None) -> None:
    """Append a dated note to the session body without bumping anything else."""
    append_log_entry(path, message, when=when)


# ── start ────────────────────────────────────────────────────────────


def start_session(
    activity_root: Path,
    activity_id: str,
    *,
    title: str | None = None,
    on_open_sessions: Callable[[list[Session]], str] | None = None,
    when: datetime | None = None,
) -> Session:
    """Start a new session in an activity.

    If any sessions are open, `on_open_sessions(opens) -> choice` is invoked
    where `choice` is one of `c|n|e|a`:
        c — continue the current active one (no new session created; returns it).
        n — start a new one anyway (multi-open allowed; D13.2).
        e — end the previous active session as `dropped` + auto-note, then start new.
        a — abort (raises RuntimeError("aborted")).

    If no callback is provided and there are open sessions, default behavior
    is `n` (start new).
    """
    when = when or _now()
    ensure_sessions_dir(activity_root)

    opens = _open_sessions(activity_root)
    if opens:
        choice = on_open_sessions(opens) if on_open_sessions else "n"
        choice = (choice or "").strip().lower()[:1]
        if choice == "a":
            raise RuntimeError("aborted")
        if choice == "c":
            # Return the active session (or first open if none active).
            active_name = get_active(activity_id)
            for s in opens:
                if s.filename == active_name:
                    return s
            return opens[0]
        if choice == "e":
            _end_previous_for_replace(activity_root, activity_id, when=when)
        # else choice == "n" → fall through

    # Generate filename + write file.
    title_resolved = title or f"session-{when.strftime('%H%M%S')}"
    filename = generate_filename(
        title_resolved, when=when.date(), existing=_existing_filenames(activity_root)
    )
    path = _path_for(activity_root, filename)
    session = Session(
        title=title_resolved,
        started=when,
        active=True,
        filename=filename,
        path=path,
    )
    write_session(path, session, "")
    set_active(activity_id, filename)
    return session


def _end_previous_for_replace(
    activity_root: Path, activity_id: str, *, when: datetime
) -> None:
    """For the `[e]` choice: mark the previously-active session as dropped + note."""
    active_name = get_active(activity_id)
    if active_name is None:
        # No active pointer — pick the most-recently-started open session.
        opens = _open_sessions(activity_root)
        if not opens:
            return
        target = max(opens, key=lambda s: s.started)
    else:
        target_path = _path_for(activity_root, active_name)
        if not target_path.is_file():
            clear_active(activity_id)
            return
        target, _ = read_session(target_path)

    # Append the auto-note BEFORE flipping ended/status, since append re-reads + re-writes.
    if target.path is not None:
        _append_auto_note(target.path, "ended by `session start --replace`", when=when)
        target, body = read_session(target.path)
        target.ended = when
        target.status = "dropped"
        target.active = None
        write_session(target.path, target, body)
    clear_active(activity_id)


# ── log ──────────────────────────────────────────────────────────────


def log_session(
    activity_root: Path,
    activity_id: str,
    note: str,
    *,
    when: datetime | None = None,
) -> Session:
    """Append a log entry to the active session. Raises if none active."""
    if not note or not note.strip():
        raise ValueError("note must be non-empty")
    active_name = get_active(activity_id)
    if active_name is None:
        raise NoActiveSessionError(
            f"no active session in {activity_id} — run `octopus session start` first"
        )
    path = _path_for(activity_root, active_name)
    if not path.is_file():
        # Cache pointer is stale (file deleted/renamed). Clean up.
        clear_active(activity_id)
        raise NoActiveSessionError(
            f"active session file missing: {path} — cache cleared"
        )
    append_log_entry(path, note, when=when)
    session, _ = read_session(path)
    return session


# ── end ──────────────────────────────────────────────────────────────


def end_session(
    activity_root: Path,
    activity_id: str,
    *,
    slug: str | None = None,
    summary: str | None = None,
    status: str = "done",
    when: datetime | None = None,
) -> Session:
    """End a session. Defaults to the active one if no slug given."""
    when = when or _now()
    if status not in {"done", "dropped"}:
        raise ValueError(f"status must be 'done' or 'dropped', got {status!r}")

    target_name = slug or get_active(activity_id)
    if target_name is None:
        raise NoActiveSessionError(
            f"no active session in {activity_id} and no slug given"
        )
    path = _path_for(activity_root, target_name)
    if not path.is_file():
        raise FileNotFoundError(f"session not found: {path}")

    session, body = read_session(path)
    if session.ended is not None:
        raise ValueError(f"session already ended: {target_name}")
    session.ended = when
    session.status = status
    session.active = None
    if summary is not None:
        session.summary = summary
    write_session(path, session, body)
    # Clear cache if this was the active session
    if get_active(activity_id) == target_name:
        clear_active(activity_id)
    return session


# ── switch ───────────────────────────────────────────────────────────


def switch_session(
    activity_root: Path, activity_id: str, slug: str
) -> Session:
    """Switch the active pointer to a different open session in the activity."""
    path = _path_for(activity_root, slug)
    if not path.is_file():
        raise FileNotFoundError(f"session not found: {path}")
    session, body = read_session(path)
    if not session.is_open():
        raise ValueError(f"cannot switch to a closed session: {slug}")

    # Demote previous active (frontmatter mirror only — cache will be overwritten).
    prev_name = get_active(activity_id)
    if prev_name and prev_name != slug:
        prev_path = _path_for(activity_root, prev_name)
        if prev_path.is_file():
            prev, prev_body = read_session(prev_path)
            if prev.active is True:
                prev.active = None
                write_session(prev_path, prev, prev_body)

    session.active = True
    write_session(path, session, body)
    set_active(activity_id, slug)
    return session


# ── prune ────────────────────────────────────────────────────────────


def prune_sessions(
    activity_root: Path,
    activity_id: str | None = None,
    *,
    days: int = 14,
    dry_run: bool = False,
    when: datetime | None = None,
) -> list[Session]:
    """Close sessions with no append activity for > `days` days.

    Returns the list of sessions that were (or would be) pruned. Reads
    `mtime` of the session file as the activity proxy.
    """
    when = when or _now()
    threshold = when - timedelta(days=days)
    pruned: list[Session] = []
    for s in _open_sessions(activity_root):
        if s.path is None:
            continue
        try:
            mtime = datetime.fromtimestamp(s.path.stat().st_mtime).replace(microsecond=0)
        except OSError:
            continue
        if mtime > threshold:
            continue
        pruned.append(s)
        if dry_run:
            continue
        # Close at the last log time (mtime is the best proxy we have).
        _append_auto_note(
            s.path, f"auto-closed by `session prune --days {days}`", when=when
        )
        s2, body = read_session(s.path)
        s2.ended = mtime
        s2.status = "dropped"
        s2.active = None
        write_session(s.path, s2, body)
        if activity_id and get_active(activity_id) == s.filename:
            clear_active(activity_id)
    return pruned


# ── show ─────────────────────────────────────────────────────────────


def show_session(
    activity_root: Path,
    activity_id: str,
    slug: str | None = None,
) -> Session:
    """Return the requested session.

    Precedence when no slug:
      1. Active session (per cache).
      2. Most-recent session (ended desc, then started desc).
      3. Error if zero sessions exist.
    """
    if slug is not None:
        path = _path_for(activity_root, slug)
        if not path.is_file():
            raise FileNotFoundError(f"session not found: {path}")
        session, _ = read_session(path)
        return session

    active_name = get_active(activity_id)
    if active_name:
        path = _path_for(activity_root, active_name)
        if path.is_file():
            session, _ = read_session(path)
            return session
        clear_active(activity_id)  # stale pointer

    sessions = list_sessions(activity_root)
    if not sessions:
        raise FileNotFoundError(f"no sessions in {activity_root}")

    # Most-recent: prefer the one with the latest `ended`, then `started`.
    def _recency(s: Session) -> tuple[datetime, datetime]:
        return (s.ended or s.started, s.started)

    sessions.sort(key=_recency, reverse=True)
    return sessions[0]

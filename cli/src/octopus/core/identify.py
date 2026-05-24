"""Path-or-id resolution for activity-targeting verbs (D83).

Used by:
  - octopus forget activity <path-or-id>   (#30)
  - octopus list tasks <path-or-id>        (#27, future)
  - octopus status <path-or-id>            (#27, future)
  - octopus get activity <path-or-id>      (#27, future)
  - octopus add task --activity <id>       (#26, future)

A single token is interpreted in one of two ways:

  Looks like a path (starts with `/`, `~`, or contains `/`)
    → resolve as a filesystem path, walk up to find .octopus/activity.md
  Looks like a bare token
    → match against `activities.id` in the index, by exact match or
      unambiguous prefix.

Ambiguity (a prefix matches multiple ids) lists candidates and raises.
"""

from __future__ import annotations

from pathlib import Path

from octopus.db.connection import get_db
from octopus.fs.discover import find_activity_root


class ActivityNotFound(Exception):
    """Token did not resolve to any activity."""


class ActivityAmbiguous(Exception):
    """Token (used as prefix) matched multiple activities."""

    def __init__(self, token: str, candidates: list[str]) -> None:
        super().__init__(
            f"ambiguous activity token {token!r}; matches: {', '.join(candidates)}"
        )
        self.token = token
        self.candidates = candidates


def _looks_like_path(token: str) -> bool:
    """Heuristic per D83: starts with `/`, `~`, or contains `/`."""
    if not token:
        return False
    return token.startswith("/") or token.startswith("~") or "/" in token


def resolve_activity(token: str) -> dict:
    """Resolve a token to an activity row from the index.

    Returns a dict with `id`, `path`, `title`, `type`, `status`, etc.
    (whatever columns the activities table carries).

    Raises ActivityNotFound or ActivityAmbiguous.
    """
    if not token or not token.strip():
        raise ActivityNotFound("empty activity token")

    if _looks_like_path(token):
        return _resolve_by_path(token)
    return _resolve_by_id_or_prefix(token)


def _resolve_by_path(token: str) -> dict:
    """Walk up from the path until .octopus/activity.md is found, then
    look up the matching row by path.
    """
    candidate = Path(token).expanduser().resolve()
    root = find_activity_root(candidate)
    if root is None:
        raise ActivityNotFound(
            f"no .octopus/ found at or above {token!r}"
        )
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM activities WHERE path = ?", (str(root),)
        ).fetchone()
        if row is None:
            raise ActivityNotFound(
                f"activity at {root} is not indexed; run `octopus reindex`"
            )
        return dict(row)
    finally:
        conn.close()


def _resolve_by_id_or_prefix(token: str) -> dict:
    """Match against `activities.id`. Exact match wins; else unambiguous prefix."""
    conn = get_db()
    try:
        # Exact match first
        row = conn.execute(
            "SELECT * FROM activities WHERE id = ?", (token,)
        ).fetchone()
        if row is not None:
            return dict(row)
        # Prefix match against the slug portion of the id (which is
        # "<slug>-<4hex>" per D1).
        rows = conn.execute(
            "SELECT * FROM activities WHERE id LIKE ? ORDER BY id",
            (f"{token}%",),
        ).fetchall()
        if not rows:
            # Also try matching just the slug prefix (before the -hex)
            rows = conn.execute(
                "SELECT * FROM activities WHERE id LIKE ? ORDER BY id",
                (f"{token}-%",),
            ).fetchall()
        if not rows:
            raise ActivityNotFound(f"no activity matches {token!r}")
        if len(rows) > 1:
            raise ActivityAmbiguous(token, [r["id"] for r in rows])
        return dict(rows[0])
    finally:
        conn.close()

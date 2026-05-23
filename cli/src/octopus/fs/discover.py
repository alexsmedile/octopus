"""Activity discovery per SPEC.md §8.1.

Walk-up: from cwd find the nearest `.octopus/activity.md`.
Walk-down: from configured roots find all `.octopus/activity.md`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

# Directories never recursed into during walk-down (SPEC.md §8.1).
SKIP_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "_archive", "_archived", "_backup", "_backups",
    "dist", "build", ".tox", ".pytest_cache", ".mypy_cache",
})


def find_activity_root(start: Path) -> Path | None:
    """Walk up from `start` to find the nearest activity folder.

    Returns the *parent* of `.octopus/` (the activity folder itself), not
    `.octopus/` itself. Returns None if no activity is found before the
    filesystem root.
    """
    current = start.resolve()
    if current.is_file():
        current = current.parent

    while True:
        candidate = current / ".octopus" / "activity.md"
        if candidate.is_file():
            return current
        if current.parent == current:  # filesystem root
            return None
        current = current.parent


def find_all_activities(roots: Iterable[Path]) -> list[Path]:
    """Walk down from each root, returning every activity folder found."""
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root = root.expanduser().resolve()
        if not root.is_dir():
            continue
        for activity_md in _walk_for_activity_md(root):
            activity_root = activity_md.parent.parent
            if activity_root not in seen:
                seen.add(activity_root)
                found.append(activity_root)
    return found


def _walk_for_activity_md(root: Path):
    """Yield paths to every .octopus/activity.md under root."""
    try:
        for entry in root.iterdir():
            if entry.name in SKIP_DIRS:
                continue
            if entry.is_symlink():
                continue
            if entry.name == ".octopus" and entry.is_dir():
                activity_md = entry / "activity.md"
                if activity_md.is_file():
                    yield activity_md
                # Do NOT recurse into .octopus/
                continue
            if entry.is_dir():
                yield from _walk_for_activity_md(entry)
    except PermissionError:
        return

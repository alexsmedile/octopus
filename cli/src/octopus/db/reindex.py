"""Full reindex: walk configured roots, upsert everything, detect drift.

See SCHEMA-INDEX.md §4.3 and CRITICAL-DEPENDENCIES.md rules P + Q.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import frontmatter

from octopus.db.stale import prune_missing
from octopus.db.upsert import upsert_activity, upsert_session, upsert_task
from octopus.fs.discover import SKIP_DIRS, find_all_activities
from octopus.fs.io import read_activity, read_task


@dataclass
class ReindexResult:
    activities_seen: int = 0
    tasks_seen: int = 0
    sessions_seen: int = 0
    pruned_activities: int = 0
    pruned_tasks: int = 0
    pruned_sessions: int = 0
    collisions: list[tuple[str, list[Path]]] = field(default_factory=list)
    renames: list[tuple[str, Path, Path]] = field(default_factory=list)
    missing_roots: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def reindex_all(
    conn: sqlite3.Connection,
    roots: list[Path],
    *,
    prune: bool = False,
    accept_renames: bool = False,
) -> ReindexResult:
    """Walk roots, upsert everything, return a summary.

    Args:
        roots: directories to scan (already expanded/resolved).
        prune: delete rows whose source files are missing AND auto-accept renames.
        accept_renames: when True (set by --prune or by interactive y), apply rename
            updates (path = current_path); when False, just record them.
    """
    result = ReindexResult()
    by_id: dict[str, list[Path]] = {}

    for root in roots:
        if not root.exists():
            result.missing_roots.append(root)
            continue
        for activity_folder in find_all_activities([root]):
            _process_activity(conn, activity_folder, result, by_id, accept_renames=accept_renames)

    # Collisions: same activity ID from multiple paths
    for activity_id, paths in by_id.items():
        if len(paths) > 1:
            result.collisions.append((activity_id, paths))

    # Optional prune of dangling rows
    if prune:
        pruned = prune_missing(conn)
        result.pruned_activities = pruned["activities"]
        result.pruned_tasks = pruned["tasks"]
        result.pruned_sessions = pruned["sessions"]

    return result


def _process_activity(
    conn: sqlite3.Connection,
    folder: Path,
    result: ReindexResult,
    by_id: dict[str, list[Path]],
    *,
    accept_renames: bool,
) -> None:
    """Upsert one activity + all its tasks + all its sessions."""
    activity_md = folder / ".octopus" / "activity.md"
    try:
        activity, _ = read_activity(activity_md)
    except Exception as e:
        result.errors.append(f"{activity_md}: {e}")
        return

    by_id.setdefault(activity.id, []).append(folder)

    # Rename detection
    if activity.last_known_path and activity.last_known_path != str(folder):
        result.renames.append((activity.id, Path(activity.last_known_path), folder))
        if accept_renames:
            activity.last_known_path = str(folder)

    upsert_activity(conn, activity)
    result.activities_seen += 1

    # Tasks
    tasks_dir = folder / ".octopus" / "tasks"
    if tasks_dir.is_dir():
        for task_file in _walk_task_files(tasks_dir):
            try:
                task, _ = read_task(task_file)
                upsert_task(conn, activity.id, task)
                result.tasks_seen += 1
            except Exception as e:
                result.errors.append(f"{task_file}: {e}")

    # Sessions
    sessions_dir = folder / ".octopus" / "sessions"
    if sessions_dir.is_dir():
        for session_file in sorted(sessions_dir.glob("*.md")):
            try:
                _index_session(conn, activity.id, session_file)
                result.sessions_seen += 1
            except Exception as e:
                result.errors.append(f"{session_file}: {e}")


def _walk_task_files(tasks_dir: Path):
    """Yield every .md file under tasks/, skipping `.trash/`."""
    if not tasks_dir.is_dir():
        return
    # Folder mode: iterate bucket subdirs. Field mode: tasks_dir directly.
    for entry in tasks_dir.iterdir():
        if entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        if entry.is_dir():
            for f in sorted(entry.glob("*.md")):
                yield f
        elif entry.suffix == ".md":
            yield entry


def _index_session(conn: sqlite3.Connection, activity_id: str, path: Path) -> None:
    """Read a session file's frontmatter and upsert the row."""
    post = frontmatter.load(path)
    data = post.metadata
    started = _coerce_datetime(data.get("started"))
    ended = _coerce_datetime(data.get("ended"))
    upsert_session(
        conn, activity_id,
        filename=path.stem,
        path=path,
        title=data.get("title"),
        started=started,
        ended=ended,
        raw_frontmatter=dict(data),
    )


def _coerce_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.combine(date.fromisoformat(value), datetime.min.time())
            except ValueError:
                return None
    return None

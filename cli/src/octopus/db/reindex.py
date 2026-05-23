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
    # D54: count of request PLAN.md files whose `related_tasks` was rewritten.
    related_tasks_propagated: int = 0
    # D48: malformed promoted_to values seen (slug → value).
    promoted_to_warnings: list[tuple[str, str]] = field(default_factory=list)


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

    # Tasks — collect promoted_to values as we go for the propagation pass.
    promoted_pairs: list[tuple[str, str]] = []  # (task_slug, promoted_to_value)
    tasks_dir = folder / ".octopus" / "tasks"
    if tasks_dir.is_dir():
        for task_file in _walk_task_files(tasks_dir):
            try:
                task, _ = read_task(task_file)
                upsert_task(conn, activity.id, task)
                result.tasks_seen += 1
                if task.promoted_to:
                    promoted_pairs.append((task.slug, task.promoted_to))
            except Exception as e:
                result.errors.append(f"{task_file}: {e}")

    # D54: propagate `related_tasks` to .spectacular/requests/<slug>/PLAN.md.
    # This makes the request side a derived mirror of the task scan.
    try:
        propagated, warnings = _propagate_related_tasks(folder, promoted_pairs)
        result.related_tasks_propagated += propagated
        result.promoted_to_warnings.extend(warnings)
    except Exception as e:
        result.errors.append(f"{folder}/.spectacular: related_tasks propagation failed: {e}")

    # Sessions
    sessions_dir = folder / ".octopus" / "sessions"
    if sessions_dir.is_dir():
        for session_file in sorted(sessions_dir.glob("*.md")):
            try:
                _index_session(conn, activity.id, session_file)
                result.sessions_seen += 1
            except Exception as e:
                result.errors.append(f"{session_file}: {e}")


def _propagate_related_tasks(
    activity_folder: Path,
    promoted_pairs: list[tuple[str, str]],
) -> tuple[int, list[tuple[str, str]]]:
    """Rewrite `related_tasks:` on every Spectacular request PLAN.md in this activity.

    Returns:
        (count of PLAN.md files written, list of (task_slug, malformed_value) warnings)

    Behavior per D54:
    - Parse each `promoted_to: <provider>:<id>` value.
    - Only `spectacular:` entries flow into related_tasks regeneration.
    - For each spectacular slug, derived list is sorted + deduped.
    - If no tasks reference a given live request, `related_tasks` is removed
      (default-omission). Archived requests are left alone (we don't touch
      _archive/).
    - Malformed values produce warnings but never abort.
    """
    requests_dir = activity_folder / ".spectacular" / "requests"
    if not requests_dir.is_dir():
        return (0, [])

    warnings: list[tuple[str, str]] = []
    by_slug: dict[str, list[str]] = {}
    for task_slug, value in promoted_pairs:
        if ":" not in value:
            warnings.append((task_slug, value))
            continue
        provider, _, identifier = value.partition(":")
        if not provider or not identifier:
            warnings.append((task_slug, value))
            continue
        if provider != "spectacular":
            # Non-spectacular providers are no-op for related_tasks (D54).
            continue
        by_slug.setdefault(identifier, []).append(task_slug)
    for k in by_slug:
        by_slug[k] = sorted(set(by_slug[k]))

    written = 0
    # Walk only live requests (skip _archive/ and dotfiles).
    for entry in requests_dir.iterdir():
        if not entry.is_dir() or entry.name.startswith("_") or entry.name.startswith("."):
            continue
        plan_path = entry / "PLAN.md"
        if not plan_path.is_file():
            continue
        slug = entry.name
        derived = by_slug.get(slug)
        if _rewrite_related_tasks(plan_path, derived):
            written += 1
    return (written, warnings)


def _rewrite_related_tasks(plan_path: Path, derived: list[str] | None) -> bool:
    """Rewrite `related_tasks:` in PLAN.md frontmatter. Returns True if changed.

    `derived=None` → field removed (default-omission). Otherwise → set to list.
    """
    try:
        post = frontmatter.load(plan_path)
    except Exception:
        return False
    current = post.metadata.get("related_tasks")
    # Normalize current to a comparable list for change detection.
    normalized_current = list(current) if isinstance(current, list) else None
    if derived is None or len(derived) == 0:
        if normalized_current is None:
            return False  # already absent
        del post.metadata["related_tasks"]
    else:
        if normalized_current == derived:
            return False
        post.metadata["related_tasks"] = list(derived)
    plan_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    return True


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

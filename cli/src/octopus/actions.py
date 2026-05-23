"""Shared action layer — used by both `octopus.cli` Typer commands and `octopus.tui`.

Goal: keep mutation logic in one place. Each function:
  - takes an activity_root: Path + named args
  - returns a small result dataclass (no printing, no Typer.Exit)
  - raises ActionError on validation/not-found/conflict errors

CLI commands today don't yet call into this layer — they're the source. Group 5
ports only the verbs the TUI needs (start, finish, drop, move, pin, unpin,
capture, start_session). Wider CLI ports are a follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from octopus.config import load_config
from octopus.core.models import (
    DEFAULT_BUCKET,
    TASK_BUCKETS,
    TASK_PRIORITIES,
    Task,
)
from octopus.core.slug import collision_suffix, slugify
from octopus.db.sync import sync_delete_task, sync_task_after_write
from octopus.fs.io import read_activity, read_task, write_task
from octopus.fs.scaffold import BUCKET_FOLDERS, read_storage_mode


# ── errors ─────────────────────────────────────────────────────────────


class ActionError(Exception):
    """Any user-facing error from an action. Carries a short message."""


# ── helpers ────────────────────────────────────────────────────────────


def find_task_file(octopus_dir: Path, storage_mode: str, slug: str) -> Path | None:
    """Locate tasks/<slug>.md across flat and bucket-folder layouts."""
    tasks_dir = octopus_dir / "tasks"
    if storage_mode == "folders":
        for bucket in BUCKET_FOLDERS:
            candidate = tasks_dir / bucket / f"{slug}.md"
            if candidate.is_file():
                return candidate
        return None
    candidate = tasks_dir / f"{slug}.md"
    return candidate if candidate.is_file() else None


def _load(activity_root: Path, slug: str) -> tuple[Path, Task, str, Path, str]:
    octopus_dir = activity_root / ".octopus"
    storage_mode = read_storage_mode(octopus_dir)
    task_path = find_task_file(octopus_dir, storage_mode, slug)
    if task_path is None:
        raise ActionError(f"task not found: {slug}")
    task, body = read_task(task_path)
    return task_path, task, body, octopus_dir, storage_mode


def _save(
    task: Task,
    body: str,
    current_path: Path,
    octopus_dir: Path,
    storage_mode: str,
    activity_root: Path,
) -> Path:
    if storage_mode == "folders":
        expected_dir = octopus_dir / "tasks" / task.bucket
        expected_dir.mkdir(parents=True, exist_ok=True)
        new_path = expected_dir / current_path.name
    else:
        new_path = current_path
    write_task(new_path, task, body)
    if new_path != current_path:
        sync_delete_task(current_path)
        try:
            current_path.unlink()
        except FileNotFoundError:
            pass
    task.path = new_path
    sync_task_after_write(activity_root, task)
    return new_path


def _validate(task: Task) -> None:
    errors = task.validate()
    if errors:
        raise ActionError("validation failed: " + "; ".join(errors))


# ── result types ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class TaskResult:
    slug: str
    bucket: str
    message: str


@dataclass(frozen=True)
class CaptureResult:
    slug: str
    bucket: str
    path: Path


@dataclass(frozen=True)
class SessionResult:
    filename: str
    title: str | None
    message: str


# ── task verbs ─────────────────────────────────────────────────────────


def start_task(activity_root: Path, slug: str) -> TaskResult:
    """Mark work begun. Idempotent. On done/dropped, resumes (bucket → now)."""
    path, task, body, octopus_dir, storage_mode = _load(activity_root, slug)
    today = date.today()
    if task.is_terminal():
        task.end_date = None
        task.bucket = "now"
        if task.start_date is None:
            task.start_date = today
        msg = "resumed"
    elif task.start_date is not None:
        return TaskResult(slug, task.bucket, f"already started ({task.start_date})")
    else:
        task.start_date = today
        msg = "started"
    _validate(task)
    _save(task, body, path, octopus_dir, storage_mode, activity_root)
    return TaskResult(slug, task.bucket, msg)


def finish_task(activity_root: Path, slug: str) -> TaskResult:
    """Mark complete: bucket → done, end_date set, clear pinned/issue/run_state."""
    path, task, body, octopus_dir, storage_mode = _load(activity_root, slug)
    today = date.today()
    if task.start_date is None:
        task.start_date = today
    if task.end_date is None:
        task.end_date = today
    task.bucket = "done"
    task.pinned = None
    task.issue = None
    task.blocked_by = None
    task.waiting_for = None
    task.run_state = None
    _validate(task)
    _save(task, body, path, octopus_dir, storage_mode, activity_root)
    return TaskResult(slug, "done", "finished")


def drop_task(activity_root: Path, slug: str) -> TaskResult:
    """Mark dropped: bucket → dropped, end_date set, clear pinned/issue/run_state."""
    path, task, body, octopus_dir, storage_mode = _load(activity_root, slug)
    today = date.today()
    if task.end_date is None:
        task.end_date = today
    task.bucket = "dropped"
    task.pinned = None
    task.issue = None
    task.blocked_by = None
    task.waiting_for = None
    task.run_state = None
    _validate(task)
    _save(task, body, path, octopus_dir, storage_mode, activity_root)
    return TaskResult(slug, "dropped", "dropped")


def move_task(
    activity_root: Path,
    slug: str,
    new_bucket: str,
    *,
    set_pinned: bool | None = None,
) -> TaskResult:
    """Move to a different bucket. set_pinned=True/False overrides pin state."""
    if new_bucket not in TASK_BUCKETS:
        raise ActionError(f"invalid bucket {new_bucket!r}; valid: {sorted(TASK_BUCKETS)}")
    path, task, body, octopus_dir, storage_mode = _load(activity_root, slug)
    old = task.bucket
    task.bucket = new_bucket
    if set_pinned is True:
        task.pinned = True
    elif set_pinned is False:
        task.pinned = None
    _validate(task)
    _save(task, body, path, octopus_dir, storage_mode, activity_root)
    return TaskResult(slug, new_bucket, f"moved {old} → {new_bucket}")


PIPELINE_FORWARD = {"backlog": "next", "next": "now", "now": "done"}


def move_next(activity_root: Path, slug: str) -> TaskResult:
    """Quick move: advance one step along the pipeline."""
    path, task, _, _, _ = _load(activity_root, slug)
    target = PIPELINE_FORWARD.get(task.bucket)
    if target is None:
        raise ActionError(f"cannot advance from {task.bucket!r}")
    return move_task(activity_root, slug, target)


def pin_task(activity_root: Path, slug: str) -> TaskResult:
    """Toggle: set pinned=True (mirrors `octopus pin`)."""
    path, task, body, octopus_dir, storage_mode = _load(activity_root, slug)
    if task.is_terminal():
        raise ActionError(f"cannot pin terminal task (bucket={task.bucket})")
    task.pinned = True
    _save(task, body, path, octopus_dir, storage_mode, activity_root)
    return TaskResult(slug, task.bucket, "pinned")


def unpin_task(activity_root: Path, slug: str) -> TaskResult:
    """Clear pinned flag (mirrors `octopus unpin`)."""
    path, task, body, octopus_dir, storage_mode = _load(activity_root, slug)
    task.pinned = None
    _save(task, body, path, octopus_dir, storage_mode, activity_root)
    return TaskResult(slug, task.bucket, "unpinned")


def toggle_pin(activity_root: Path, slug: str) -> TaskResult:
    """Pin if not pinned, unpin if pinned. Convenience for the TUI `p` key."""
    _, task, _, _, _ = _load(activity_root, slug)
    if task.pinned:
        return unpin_task(activity_root, slug)
    return pin_task(activity_root, slug)


# ── capture ────────────────────────────────────────────────────────────


def _resolve_slug_collision(target_dir: Path, base_slug: str, max_length: int) -> str:
    if not (target_dir / f"{base_slug}.md").exists():
        return base_slug
    counter = 2
    while True:
        candidate = collision_suffix(base_slug, counter, max_length=max_length)
        if not (target_dir / f"{candidate}.md").exists():
            return candidate
        counter += 1
        if counter > 999:
            raise ActionError(f"too many collisions on slug {base_slug!r}")


def capture_task(
    activity_root: Path,
    title: str,
    *,
    bucket: str = DEFAULT_BUCKET,
    priority: str | None = None,
    slug: str | None = None,
    body: str | None = None,
) -> CaptureResult:
    """Create a new task. Default bucket: backlog. --now also pins."""
    if not title or not title.strip():
        raise ActionError("title is required")
    if bucket not in TASK_BUCKETS:
        raise ActionError(f"invalid bucket {bucket!r}; valid: {sorted(TASK_BUCKETS)}")
    if priority is not None and priority not in TASK_PRIORITIES:
        raise ActionError(f"invalid priority {priority!r}; valid: {sorted(TASK_PRIORITIES)}")

    octopus_dir = activity_root / ".octopus"
    cfg = load_config(octopus_dir)
    storage_mode = read_storage_mode(octopus_dir)

    if slug:
        base_slug = slug.lower().strip().strip("-")
        if not base_slug or not all(c.isalnum() or c == "-" for c in base_slug):
            raise ActionError(f"invalid slug {slug!r} (lowercase alnum + hyphen only)")
    else:
        try:
            base_slug = slugify(title, noise_words=cfg.noise_words, max_length=cfg.max_length)
        except ValueError as exc:
            raise ActionError(f"cannot slugify title: {exc}") from exc

    target_dir = octopus_dir / "tasks" / (bucket if storage_mode == "folders" else "")
    target_dir.mkdir(parents=True, exist_ok=True)

    final_slug = _resolve_slug_collision(target_dir, base_slug, cfg.max_length)
    task_path = target_dir / f"{final_slug}.md"

    task = Task(
        title=title.strip(),
        created=date.today(),
        bucket=bucket,
        priority=priority,
        # Pin is a separate axis (AXIS-MODEL §ATTENTION) — capture does not pin.
        # Callers that want a pinned task should call pin_task() after capture.
        pinned=None,
    )
    task.slug = final_slug
    task.path = task_path
    _validate(task)

    write_task(task_path, task, body or "\n## References\n")
    sync_task_after_write(activity_root, task)

    return CaptureResult(slug=final_slug, bucket=bucket, path=task_path)


# ── session ────────────────────────────────────────────────────────────


def start_session_for(
    activity_root: Path,
    *,
    title: str | None = None,
) -> SessionResult:
    """Start a new session. If sessions are already open, default behavior
    (per session lifecycle) starts a new one anyway (multi-open allowed)."""
    # Deferred import — sessions module isn't free.
    from octopus.db.upsert import upsert_session
    from octopus.sessions import start_session

    activity, _ = read_activity(activity_root / ".octopus" / "activity.md")
    try:
        session = start_session(activity_root, activity.id, title=title)
    except RuntimeError as exc:
        raise ActionError(str(exc)) from exc

    # Index sync — best-effort, like the CLI verb.
    try:
        from octopus.db.connection import get_db
        conn = get_db()
        try:
            upsert_session(conn, activity.id, session)
        finally:
            conn.close()
    except Exception:
        pass

    return SessionResult(
        filename=session.filename,
        title=getattr(session, "title", None),
        message=f"started session {session.filename}",
    )

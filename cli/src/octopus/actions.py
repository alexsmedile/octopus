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


@dataclass(frozen=True)
class PromoteResult:
    promoted: list[str]  # task slugs that were promoted
    repointed: list[str]  # task slugs that were repointed via --force
    reverted: list[str]  # task slugs that were soft-cleared via --revert
    target: str | None  # canonical "<provider>:<identifier>" or None on revert
    scaffolded: bool  # True when a new request directory was created
    request_path: Path | None  # PLAN.md path when scaffolded or linked


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


# ── promotion ──────────────────────────────────────────────────────────


def promote_task(
    activity_root: Path,
    slugs: list[str],
    *,
    to: str | None = None,
    explicit_slug: str | None = None,
    force: bool = False,
    revert: bool = False,
) -> PromoteResult:
    """Promote one or more tasks to a Spectacular request (or other target).

    Semantics per D47–D51. See `promotion.py` for parsing + scaffolding helpers.

    Args:
        slugs: task slugs to promote (must be non-empty).
        to: `--to <provider>[:<id>]` raw value. Required unless `revert=True`.
        explicit_slug: when `to == "<provider>:new"`, the slug to use.
        force: repoint already-promoted tasks instead of rejecting.
        revert: soft-clear `promoted_to` + `end_date`; body stays stub.
    """
    from octopus.promotion import (
        PromotionError,
        apply_auto_number,
        find_spectacular_request,
        parse_target,
        render_stub,
        scaffold_request,
    )

    if not slugs:
        raise ActionError("at least one task slug required")

    octopus_dir = activity_root / ".octopus"
    cfg = load_config(octopus_dir)

    # ── revert path ───────────────────────────────────────────────────
    if revert:
        reverted: list[str] = []
        # Pre-flight: every task must exist.
        loaded: list[tuple[Path, Task, str, Path, str]] = []
        for slug in slugs:
            loaded.append(_load(activity_root, slug))
        for slug, (path, task, body, octo, storage) in zip(slugs, loaded):
            if task.promoted_to is None:
                # Idempotent revert — nothing to clear, skip quietly.
                continue
            # Soft revert (D49): clear promoted_to + end_date. Because
            # bucket=done requires end_date, also move the task back to
            # backlog/. Body stays as the stub (full restore is via git).
            task.promoted_to = None
            task.end_date = None
            task.bucket = "backlog"
            _validate(task)
            _save(task, body, path, octo, storage, activity_root)
            reverted.append(slug)
        return PromoteResult(
            promoted=[],
            repointed=[],
            reverted=reverted,
            target=None,
            scaffolded=False,
            request_path=None,
        )

    # ── forward path ──────────────────────────────────────────────────
    if not to:
        raise ActionError("--to is required (or use --revert)")

    try:
        target = parse_target(to, task_slugs=slugs, cfg=cfg)
    except PromotionError as exc:
        # Re-raise as ActionError so the CLI layer maps consistently.
        # Embed exit code in the message for the command layer to parse.
        raise ActionError(str(exc)) from exc

    # Resolve identifier when --to was ":new"
    if target.create_new:
        if not explicit_slug:
            raise ActionError(
                f"--to {to!r} requires --slug <new-slug> to create a new request"
            )
        target = type(target)(
            provider=target.provider,
            identifier=explicit_slug,
            create_new=True,
            explicit_slug=True,
        )

    # Pre-flight: load all tasks, validate, check idempotency rule.
    loaded = []
    for slug in slugs:
        loaded.append(_load(activity_root, slug))

    if not force:
        already = [s for s, l in zip(slugs, loaded) if l[1].promoted_to is not None]
        if already:
            msg = "; ".join(f"{s} → {l[1].promoted_to}" for s, l in zip(slugs, loaded) if l[1].promoted_to is not None)
            raise ActionError(
                f"task(s) already promoted: {msg}. Use --force to repoint or --revert to unlink."
            )

    # Smart-resolve identifier (spectacular: only). For other providers,
    # accept any identifier — adapter-specific validation is deferred.
    canonical_identifier = target.identifier
    scaffolded = False
    request_plan_path: Path | None = None

    if target.provider == "spectacular":
        existing = find_spectacular_request(activity_root, target.identifier)
        if existing is None:
            # Scaffold. Apply auto-numbering when slug has no NN- prefix.
            final_slug = apply_auto_number(target.identifier, activity_root, cfg)
            canonical_identifier = final_slug
            first_task_title = loaded[0][1].title
            try:
                request_plan_path = scaffold_request(
                    activity_root,
                    slug=final_slug,
                    title=first_task_title,
                    promoted_from=slugs[0],
                )
                scaffolded = True
            except PromotionError as exc:
                raise ActionError(str(exc)) from exc
        else:
            request_plan_path = existing / "PLAN.md"

    canonical = f"{target.provider}:{canonical_identifier}"
    today = date.today()
    promoted: list[str] = []
    repointed: list[str] = []

    for slug, (path, task, body, octo, storage) in zip(slugs, loaded):
        was_promoted = task.promoted_to is not None
        task.promoted_to = canonical
        if task.start_date is None:
            task.start_date = today
        task.end_date = today
        task.bucket = "done"
        task.pinned = None
        task.issue = None
        task.blocked_by = None
        task.waiting_for = None
        task.run_state = None
        # Body replacement happens only on FIRST promote, not on --force.
        if not was_promoted:
            body = render_stub(
                title=task.title,
                canonical=canonical,
                identifier=canonical_identifier,
            )
        _validate(task)
        _save(task, body, path, octo, storage, activity_root)
        if was_promoted:
            repointed.append(slug)
        else:
            promoted.append(slug)

    return PromoteResult(
        promoted=promoted,
        repointed=repointed,
        reverted=[],
        target=canonical,
        scaffolded=scaffolded,
        request_path=request_plan_path,
    )


# ── forget activity (D83) ──────────────────────────────────────────────


@dataclass(frozen=True)
class ForgetResult:
    activity_id: str
    activity_path: Path
    archived: bool
    archive_destination: Path | None
    rows_removed: dict[str, int]   # {table: count} for activities/tasks/sessions/refs


def forget_activity(
    activity: dict,
    *,
    archive_files: bool,
) -> ForgetResult:
    """Remove an activity from the index. Optionally archive its files.

    `activity` is the row dict returned by `resolve_activity`. Caller is
    responsible for resolving the token (path-or-id) before calling.

    Behavior:
    - Always: delete the row from `activities`. SQLite CASCADE clears
      related rows in `tasks`, `task_external_refs`, and `sessions`.
    - If `archive_files=True`: move the activity folder to
      `<parent>/_archive/<name>/`.
    """
    import shutil

    from octopus.db.connection import get_db

    activity_id = activity["id"]
    activity_path = Path(activity["path"])

    # Count what we'll remove (for reporting), then delete.
    conn = get_db()
    try:
        task_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE activity_id = ?", (activity_id,)
        ).fetchone()[0]
        session_count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE activity_id = ?", (activity_id,)
        ).fetchone()[0]
        # task_external_refs counts: refs whose task belongs to this activity.
        ref_count = conn.execute(
            "SELECT COUNT(*) FROM task_external_refs r "
            "JOIN tasks t ON t.id = r.task_id WHERE t.activity_id = ?",
            (activity_id,),
        ).fetchone()[0]

        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    finally:
        conn.close()

    archive_destination: Path | None = None
    if archive_files and activity_path.is_dir():
        parent_archive = activity_path.parent / "_archive"
        parent_archive.mkdir(parents=True, exist_ok=True)
        archive_destination = parent_archive / activity_path.name
        if archive_destination.exists():
            raise ActionError(
                f"archive destination already exists: {archive_destination}; "
                "rename or remove it first"
            )
        shutil.move(str(activity_path), str(archive_destination))

    return ForgetResult(
        activity_id=activity_id,
        activity_path=activity_path,
        archived=archive_files,
        archive_destination=archive_destination,
        rows_removed={
            "activities": 1,
            "tasks": task_count,
            "sessions": session_count,
            "task_external_refs": ref_count,
        },
    )

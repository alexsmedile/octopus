"""Octopus CLI entry point.

Exposed as both `octopus` and `octo` via pyproject.toml [project.scripts].

Reflects the v1 schema after request 02b (schema collapse): five-value bucket,
no status/kind, pinned (not open), stage, run_state, default-omission.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from octopus import __version__
from octopus.config import (
    add_root as config_add_root,
)
from octopus.config import (
    list_roots as config_list_roots,
)
from octopus.config import (
    load_config,
)
from octopus.config import (
    remove_root as config_remove_root,
)
from octopus.core.id import short_form
from octopus.core.logging import get_logger, setup_logging
from octopus.core.models import (
    ACTIVITY_STATUSES,
    ACTIVITY_TYPES,
    DEFAULT_BUCKET,
    TASK_BUCKETS,
    TASK_PRIORITIES,
    TASK_RUN_STATES,
    Task,
)
from octopus.core.slug import collision_suffix, slugify
from octopus.db.connection import get_db
from octopus.db.queries import (
    count_by_bucket,
    get_activity_by_id_or_prefix,
    tasks_all,
    tasks_for_activity,
    total_row_counts,
)
from octopus.db.queries import (
    list_activities as db_list_activities,
)
from octopus.db.queries import (
    loops as db_loops,
)
from octopus.db.reindex import reindex_all
from octopus.db.sync import (
    sync_activity_after_write,
    sync_delete_task,
    sync_task_after_write,
)
from octopus.fs.discover import find_activity_root
from octopus.fs.io import read_activity, read_task, write_task
from octopus.fs.scaffold import (
    BUCKET_FOLDERS,
    ActivityExistsError,
    init_activity,
    read_storage_mode,
)

app = typer.Typer(
    name="octopus",
    help="A folder-native task system. Local-first project & task orchestration.",
    no_args_is_help=True,
    add_completion=False,
)
task_app = typer.Typer(name="task", help="Task operations.", no_args_is_help=True)
app.add_typer(task_app, name="task")

console = Console()
err_console = Console(stderr=True)


# Exit codes
EXIT_OK = 0
EXIT_USER_ERROR = 1
EXIT_NOT_IN_ACTIVITY = 2
EXIT_CONFIG_ERROR = 3
# Promotion-specific (D49). promote uses 2 (task not found), 3 (target invalid),
# 4 (already promoted; use --force or --revert).
EXIT_PROMOTE_ALREADY = 4


def _require_activity() -> Path:
    root = find_activity_root(Path.cwd())
    if root is None:
        err_console.print("[red]✗[/] not inside an octopus activity (no .octopus/ found by walking up)")
        raise typer.Exit(EXIT_NOT_IN_ACTIVITY)
    return root


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"octopus {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Root command."""
    setup_logging()


# ── init ─────────────────────────────────────────────────────────────


@app.command()
def init(
    title: str | None = typer.Option(None, "--title", help="Human title (default: folder name)."),
    activity_type: str = typer.Option("other", "--type", help=f"One of {sorted(ACTIVITY_TYPES)}"),
    status: str = typer.Option("active", "--status", help=f"One of {sorted(ACTIVITY_STATUSES)}"),
    area: str | None = typer.Option(None, "--area", help="Free-form area tag."),
    custom_id: str | None = typer.Option(None, "--id", help="Override the auto-derived activity id."),
    storage_mode: str = typer.Option("folders", "--storage", help="Storage mode: folders | fields."),
) -> None:
    """Initialize an .octopus/ directory in the current folder."""
    cwd = Path.cwd()
    existing = find_activity_root(cwd)
    if existing is not None and existing == cwd:
        err_console.print(f"[red]✗[/] already an activity: {existing}")
        raise typer.Exit(EXIT_USER_ERROR)
    if existing is not None and existing != cwd:
        err_console.print(f"[red]✗[/] nested activities not allowed. Existing activity at: {existing}")
        raise typer.Exit(EXIT_USER_ERROR)

    try:
        activity = init_activity(
            cwd, title=title, activity_type=activity_type, status=status,
            area=area, custom_id=custom_id, storage_mode=storage_mode,
        )
    except (ActivityExistsError, ValueError) as e:
        err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(EXIT_USER_ERROR) from e

    err = sync_activity_after_write(cwd)
    if err:
        err_console.print(f"[yellow]⚠[/] {err} (run `octopus reindex` to reconcile)")

    slug = short_form(activity.id)
    console.print(f"[green]✓[/] Initialized activity [bold]{slug}[/] at {cwd}")
    if storage_mode == "folders":
        console.print(f"  storage mode: folders ({', '.join(sorted(BUCKET_FOLDERS))})")
    else:
        console.print(f"  storage mode: {storage_mode}")


# ── where ────────────────────────────────────────────────────────────


@app.command()
def where(
    show_ids: bool = typer.Option(False, "--show-ids", "-i", help="Reveal full activity IDs with hash."),
) -> None:
    """Show the current activity (walks up from cwd)."""
    root = _require_activity()
    activity_md = root / ".octopus" / "activity.md"
    activity, _ = read_activity(activity_md)
    storage_mode = read_storage_mode(root / ".octopus")
    display_id = activity.id if show_ids else short_form(activity.id)

    table = Table(show_header=False, show_edge=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Activity", f"[bold]{display_id}[/]")
    table.add_row("Title", activity.title)
    table.add_row("Path", str(root))
    table.add_row("Type", activity.type)
    table.add_row("Status", activity.status)
    if activity.area:
        table.add_row("Area", activity.area)
    table.add_row("Storage", storage_mode)
    console.print(table)

    counts = _task_counts(root, storage_mode)
    if counts:
        console.print()
        bucket_table = Table(show_header=False, padding=(0, 2))
        bucket_table.add_column(style="dim")
        bucket_table.add_column(justify="right")
        for bucket in ("now", "next", "backlog", "done", "dropped"):
            n = counts.get(bucket, 0)
            if n:
                bucket_table.add_row(bucket, str(n))
        if bucket_table.row_count:
            console.print(bucket_table)

    # Surface pinned items, if any
    pinned = [t for t in _scan_tasks(root / ".octopus", storage_mode) if t.pinned is True]
    if pinned:
        console.print()
        console.print("[bold]Pinned:[/]")
        for t in pinned:
            console.print(f"  [cyan]{t.slug}[/]  {t.title}")


# ── tui ──────────────────────────────────────────────────────────────


@app.command()
def tui() -> None:
    """Launch the Textual TUI (Focus + Board modes) for the current activity."""
    root = _require_activity()
    # Defer Textual import — keeps cold-start fast for every other command.
    from octopus.tui.app import OctopusApp

    OctopusApp(root).run()


def _task_counts(activity_root: Path, storage_mode: str) -> dict[str, int]:
    """Count tasks per bucket. In folder mode, count by directory."""
    tasks_dir = activity_root / ".octopus" / "tasks"
    if not tasks_dir.is_dir():
        return {}
    counts: dict[str, int] = {}
    if storage_mode == "folders":
        for bucket_dir in tasks_dir.iterdir():
            if not bucket_dir.is_dir() or bucket_dir.name not in BUCKET_FOLDERS:
                continue
            counts[bucket_dir.name] = sum(1 for _ in bucket_dir.glob("*.md"))
    else:
        for task_file in tasks_dir.glob("*.md"):
            try:
                task, _ = read_task(task_file)
                counts[task.bucket] = counts.get(task.bucket, 0) + 1
            except Exception:
                continue
    return counts


# ── capture ──────────────────────────────────────────────────────────


@app.command()
def capture(
    title: str = typer.Argument(..., help="Task title."),
    to_next: bool = typer.Option(False, "--next", help="Create directly in `next`."),
    to_now: bool = typer.Option(False, "--now", help="Create directly in `now`, pin it."),
    priority: str | None = typer.Option(None, "--priority", help=f"One of {sorted(TASK_PRIORITIES)} (absent = normal)"),
    slug: str | None = typer.Option(None, "--slug", help="Override the auto-slugified filename."),
) -> None:
    """Create a new task. Default bucket: backlog."""
    if to_next and to_now:
        err_console.print("[red]✗[/] --next and --now are mutually exclusive")
        raise typer.Exit(EXIT_USER_ERROR)

    root = _require_activity()
    octopus_dir = root / ".octopus"
    cfg = load_config(octopus_dir)
    storage_mode = read_storage_mode(octopus_dir)

    if priority is not None and priority not in TASK_PRIORITIES:
        err_console.print(f"[red]✗[/] invalid priority {priority!r}; valid: {sorted(TASK_PRIORITIES)}")
        raise typer.Exit(EXIT_USER_ERROR)

    bucket = "now" if to_now else ("next" if to_next else DEFAULT_BUCKET)

    if slug:
        base_slug = slug.lower().strip().strip("-")
        if not base_slug or not all(c.isalnum() or c == "-" for c in base_slug):
            err_console.print(f"[red]✗[/] invalid slug {slug!r} (lowercase alnum + hyphen only)")
            raise typer.Exit(EXIT_USER_ERROR)
    else:
        try:
            base_slug = slugify(title, noise_words=cfg.noise_words, max_length=cfg.max_length)
        except ValueError as e:
            err_console.print(f"[red]✗[/] cannot slugify title: {e}")
            raise typer.Exit(EXIT_USER_ERROR) from e

    target_dir = octopus_dir / "tasks" / (bucket if storage_mode == "folders" else "")
    target_dir.mkdir(parents=True, exist_ok=True)

    final_slug = _resolve_slug_collision(target_dir, base_slug, cfg.max_length)
    task_path = target_dir / f"{final_slug}.md"

    task = Task(
        title=title,
        created=date.today(),
        bucket=bucket,
        priority=priority,
        pinned=(True if to_now else None),
    )
    task.slug = final_slug
    task.path = task_path

    errors = task.validate()
    if errors:
        err_console.print("[red]✗[/] task validation failed:")
        for e in errors:
            err_console.print(f"  - {e}")
        raise typer.Exit(EXIT_USER_ERROR)

    body = "\n## References\n"
    write_task(task_path, task, body)
    err = sync_task_after_write(root, task)
    if err:
        err_console.print(f"[yellow]⚠[/] {err} (run `octopus reindex` to reconcile)")

    console.print(f"[green]✓[/] Created task [bold]{final_slug}[/] in {bucket}")
    console.print(f"  {task_path.relative_to(root)}")


def _resolve_slug_collision(target_dir: Path, base_slug: str, max_length: int) -> str:
    candidate = base_slug
    if not (target_dir / f"{candidate}.md").exists():
        return candidate
    counter = 2
    while True:
        candidate = collision_suffix(base_slug, counter, max_length=max_length)
        if not (target_dir / f"{candidate}.md").exists():
            return candidate
        counter += 1
        if counter > 999:
            raise RuntimeError(f"too many collisions on slug {base_slug!r}")


# ── task list / task show ────────────────────────────────────────────


def _sort_key(task: Task) -> tuple:
    """Stable sort: pinned first, then by priority, then by due date, then slug.

    Pinned: True (pinned) sorts before False.
    Priority ranking: urgent (0), high (1), normal/absent (2), low (3).
    """
    pinned_rank = 0 if task.pinned is True else 1
    priority_rank = {"urgent": 0, "high": 1, None: 2, "low": 3}.get(task.priority, 2)
    due_key = task.due or date.max
    return (pinned_rank, priority_rank, due_key, task.slug)


@task_app.command("list")
def task_list(
    bucket: str | None = typer.Option(None, "--bucket", help=f"Filter by bucket: {sorted(TASK_BUCKETS)}"),
    show_all: bool = typer.Option(False, "--all", help="Include archived tasks."),
    kind: str | None = typer.Option(
        None, "--kind",
        help="Filter by kind (feat/bug/spec/polish/test/chore). Comma-separated for multi.",
    ),
    promoted: bool = typer.Option(
        False, "--promoted",
        help="Scope override: only tasks with promoted_to set.",
    ),
    spec: str | None = typer.Option(
        None, "--spec",
        help="Scope override: only tasks promoted to spectacular:<slug>.",
    ),
) -> None:
    """List tasks in the current activity, grouped by bucket."""
    root = _require_activity()
    octopus_dir = root / ".octopus"
    storage_mode = read_storage_mode(octopus_dir)
    tasks = _scan_tasks(octopus_dir, storage_mode)
    if bucket:
        if bucket not in TASK_BUCKETS:
            err_console.print(f"[red]✗[/] invalid bucket {bucket!r}; valid: {sorted(TASK_BUCKETS)}")
            raise typer.Exit(EXIT_USER_ERROR)
        tasks = [t for t in tasks if t.bucket == bucket]
    if not show_all:
        tasks = [t for t in tasks if t.archived is not True]
    if kind:
        kinds = {k.strip() for k in kind.split(",")}
        tasks = [t for t in tasks if t.kind in kinds]
    if spec:
        target = f"spectacular:{spec}"
        tasks = [t for t in tasks if t.promoted_to == target]
    elif promoted:
        tasks = [t for t in tasks if t.promoted_to is not None]

    if not tasks:
        console.print("[dim]no tasks[/]")
        return

    _print_grouped(tasks)


def _promoted_chip(promoted_to: str) -> str:
    """Format a `promoted_to` value with the configured chip alias.

    Example: `spectacular:20-task-promotion` → `spec:20-task-promotion`
    if `[providers.chips] spectacular = "spec"`. Falls back to full provider
    name when no chip is configured.
    """
    if ":" not in promoted_to:
        return promoted_to
    provider, _, identifier = promoted_to.partition(":")
    try:
        cfg = load_config()
    except Exception:
        return promoted_to
    chip = cfg.provider_chips.get(provider, provider)
    return f"{chip}:{identifier}"


def _print_grouped(tasks: list[Task]) -> None:
    """Group tasks by bucket and print with pinned-first sort within each group."""
    bucket_order = ["now", "next", "backlog", "done", "dropped"]
    by_bucket: dict[str, list[Task]] = {b: [] for b in bucket_order}
    for t in tasks:
        by_bucket.setdefault(t.bucket, []).append(t)
    for b in bucket_order:
        items = by_bucket.get(b, [])
        if not items:
            continue
        console.print(f"\n[bold]{b.upper()}[/]")
        for t in sorted(items, key=_sort_key):
            marker = " "
            if t.pinned is True:
                marker = "📌"
            elif t.priority == "urgent":
                marker = "🔥"
            elif t.priority == "high":
                marker = "!"
            tail: list[str] = []
            if t.kind:
                tail.append(f"[blue]\\[{t.kind}][/]")
            if t.start_date and not t.is_terminal():
                tail.append("[yellow]doing[/]")
            if t.issue:
                tail.append(f"[red]{t.issue}[/]")
            if t.run_state:
                tail.append(f"[magenta]{t.run_state}[/]")
            tail_str = " " + " ".join(tail) if tail else ""
            promoted_str = ""
            if t.promoted_to:
                # Render with chip alias when available; fall back to full provider name.
                chip = _promoted_chip(t.promoted_to)
                promoted_str = f"  [dim]→ {chip}[/]"
            console.print(f"  {marker} [cyan]{t.slug}[/]{tail_str}  {t.title}{promoted_str}")


def _scan_tasks(octopus_dir: Path, storage_mode: str) -> list[Task]:
    tasks_dir = octopus_dir / "tasks"
    if not tasks_dir.is_dir():
        return []
    out: list[Task] = []
    if storage_mode == "folders":
        for bucket_dir in tasks_dir.iterdir():
            if not bucket_dir.is_dir() or bucket_dir.name not in BUCKET_FOLDERS:
                continue
            for f in bucket_dir.glob("*.md"):
                try:
                    task, _ = read_task(f)
                    out.append(task)
                except Exception as e:
                    err_console.print(f"[yellow]⚠[/] skipping {f}: {e}")
    else:
        for f in tasks_dir.glob("*.md"):
            try:
                task, _ = read_task(f)
                out.append(task)
            except Exception as e:
                err_console.print(f"[yellow]⚠[/] skipping {f}: {e}")
    return out


@task_app.command("show")
def task_show(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Print a task's frontmatter and body."""
    root = _require_activity()
    octopus_dir = root / ".octopus"
    storage_mode = read_storage_mode(octopus_dir)
    task_path = _find_task_file(octopus_dir, storage_mode, slug)
    if task_path is None:
        err_console.print(f"[red]✗[/] task not found: {slug}")
        raise typer.Exit(EXIT_USER_ERROR)
    console.print(task_path.read_text(encoding="utf-8"))


def _find_task_file(octopus_dir: Path, storage_mode: str, slug: str) -> Path | None:
    tasks_dir = octopus_dir / "tasks"
    if storage_mode == "folders":
        for bucket_dir in tasks_dir.iterdir():
            if not bucket_dir.is_dir():
                continue
            candidate = bucket_dir / f"{slug}.md"
            if candidate.is_file():
                return candidate
        return None
    else:
        candidate = tasks_dir / f"{slug}.md"
        return candidate if candidate.is_file() else None


# ── pipeline verbs ────────────────────────────────────────────────────


def _move_bucket(slug: str, new_bucket: str, *, set_pinned: bool | None = None) -> None:
    root = _require_activity()
    octopus_dir = root / ".octopus"
    storage_mode = read_storage_mode(octopus_dir)
    task_path = _find_task_file(octopus_dir, storage_mode, slug)
    if task_path is None:
        err_console.print(f"[red]✗[/] task not found: {slug}")
        raise typer.Exit(EXIT_USER_ERROR)

    task, body = read_task(task_path)
    old_bucket = task.bucket
    task.bucket = new_bucket
    if set_pinned is True:
        task.pinned = True
    elif set_pinned is False:
        task.pinned = None

    errors = task.validate()
    if errors:
        err_console.print("[red]✗[/] validation failed:")
        for e in errors:
            err_console.print(f"  - {e}")
        raise typer.Exit(EXIT_USER_ERROR)

    _save_task(task, body, task_path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug}: bucket {old_bucket} → {new_bucket}")


def _save_task(
    task: Task, body: str, current_path: Path, octopus_dir: Path, storage_mode: str,
) -> Path:
    """Write task; in folder-mode and bucket changed, move file. Then upsert index."""
    if storage_mode == "folders":
        expected_dir = octopus_dir / "tasks" / task.bucket
        expected_dir.mkdir(parents=True, exist_ok=True)
        new_path = expected_dir / current_path.name
    else:
        new_path = current_path
    write_task(new_path, task, body)
    # If the file moved, remove the old DB row pointing at the old path
    if new_path != current_path:
        sync_delete_task(current_path)
        current_path.unlink()
    task.path = new_path
    # Best-effort: index update; warn but don't fail the verb on DB issues
    err = sync_task_after_write(octopus_dir.parent, task)
    if err:
        err_console.print(f"[yellow]⚠[/] {err} (run `octopus reindex` to reconcile)")
    return new_path


@app.command()
def plan(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Promote → bucket: next."""
    _move_bucket(slug, "next")


@app.command()
def focus(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Promote → bucket: now, pin."""
    _move_bucket(slug, "now", set_pinned=True)


@app.command()
def park(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Demote → bucket: backlog, unpin."""
    _move_bucket(slug, "backlog", set_pinned=False)


@app.command()
def defer(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Demote → bucket: next (keeps pinned)."""
    _move_bucket(slug, "next")


# ── lifecycle verbs ──────────────────────────────────────────────────


def _load_task(slug: str) -> tuple[Path, Task, str, Path, str]:
    root = _require_activity()
    octopus_dir = root / ".octopus"
    storage_mode = read_storage_mode(octopus_dir)
    task_path = _find_task_file(octopus_dir, storage_mode, slug)
    if task_path is None:
        err_console.print(f"[red]✗[/] task not found: {slug}")
        raise typer.Exit(EXIT_USER_ERROR)
    task, body = read_task(task_path)
    return task_path, task, body, octopus_dir, storage_mode


@app.command()
def start(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Mark work as begun. Idempotent. On done/dropped, resumes (bucket → now)."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    today = date.today()

    if task.is_terminal():
        # Resume: clear end_date, move to now, ensure start_date set
        task.end_date = None
        task.bucket = "now"
        if task.start_date is None:
            task.start_date = today
        msg = "resumed"
    elif task.start_date is not None:
        err_console.print(f"[yellow]⚠[/] {slug} already started ({task.start_date}) — no-op")
        raise typer.Exit(EXIT_OK)
    else:
        task.start_date = today
        msg = "started"

    errors = task.validate()
    if errors:
        err_console.print("[red]✗[/] validation failed:")
        for e in errors:
            err_console.print(f"  - {e}")
        raise typer.Exit(EXIT_USER_ERROR)
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} {msg}")


@app.command()
def finish(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Mark complete: bucket: done, end_date, clear pinned/issue/run_state."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    today = date.today()
    if task.start_date is None:
        task.start_date = today  # one-shot capture-and-finish
    if task.end_date is None:
        task.end_date = today
    task.bucket = "done"
    task.pinned = None
    task.issue = None
    task.blocked_by = None
    task.waiting_for = None
    task.run_state = None

    errors = task.validate()
    if errors:
        for e in errors:
            err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(EXIT_USER_ERROR)
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} finished")


@app.command(name="end", hidden=True)
def end(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Alias for `finish`."""
    finish(slug)


@app.command()
def drop(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Mark dropped: bucket: dropped, end_date, clear pinned/issue/run_state."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    today = date.today()
    if task.end_date is None:
        task.end_date = today
    task.bucket = "dropped"
    task.pinned = None
    task.issue = None
    task.blocked_by = None
    task.waiting_for = None
    task.run_state = None

    errors = task.validate()
    if errors:
        for e in errors:
            err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(EXIT_USER_ERROR)
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} dropped")


# ── impediment verbs ──────────────────────────────────────────────────


@app.command()
def block(
    slug: str = typer.Argument(..., help="Task slug."),
    reason: str = typer.Option(..., "--reason", help="Why blocked?"),
) -> None:
    """Flag an internal blocker."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    task.issue = "blocked"
    task.blocked_by = reason
    task.waiting_for = None
    errors = task.validate()
    if errors:
        for e in errors:
            err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(EXIT_USER_ERROR)
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} blocked: {reason}")


@app.command()
def wait(
    slug: str = typer.Argument(..., help="Task slug."),
    for_: str = typer.Option(..., "--for", help="What are you waiting for?"),
) -> None:
    """Flag an external dependency."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    task.issue = "waiting"
    task.waiting_for = for_
    task.blocked_by = None
    errors = task.validate()
    if errors:
        for e in errors:
            err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(EXIT_USER_ERROR)
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} waiting for: {for_}")


@app.command()
def unblock(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Clear any impediment."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    task.issue = None
    task.blocked_by = None
    task.waiting_for = None
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} unblocked")


# ── attention verbs ───────────────────────────────────────────────────


@app.command()
def pin(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Mark for prominence (sorts to top of every list)."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    if task.is_terminal():
        err_console.print(f"[red]✗[/] cannot pin terminal task ({task.bucket})")
        raise typer.Exit(EXIT_USER_ERROR)
    task.pinned = True
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} pinned")


@app.command()
def unpin(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Clear the pinned flag."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    task.pinned = None
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} unpinned")


# ── visibility verbs ──────────────────────────────────────────────────


@app.command()
def archive(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Hide from default views."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    task.archived = True
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} archived")


@app.command()
def restore(slug: str = typer.Argument(..., help="Task slug.")) -> None:
    """Bring back from archive."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    task.archived = None
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} restored")


# ── promotion verb ────────────────────────────────────────────────────


@app.command()
def promote(
    slugs: list[str] = typer.Argument(..., help="One or more task slugs to promote."),
    to: str | None = typer.Option(
        None, "--to",
        help="Target. <provider>:<id>, <chip>:<id>, <id>, <provider>, or <provider>:new.",
    ),
    slug: str | None = typer.Option(
        None, "--slug",
        help="Explicit slug when scaffolding with <provider>:new.",
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Repoint an already-promoted task to a new target.",
    ),
    revert: bool = typer.Option(
        False, "--revert",
        help="Soft-clear promoted_to + end_date. Body stays stub.",
    ),
) -> None:
    """Promote one or more tasks to a Spectacular request (or other target).

    One-way; pure rewrite. Task body becomes a stub pointer to the PLAN.md.
    See D47–D51 in DECISIONS.md and references/cli-verbs.md for the full
    semantics.
    """
    from octopus.actions import ActionError, promote_task

    activity_root = _require_activity()
    if revert and to:
        err_console.print("[red]✗[/] --revert cannot be combined with --to")
        raise typer.Exit(EXIT_USER_ERROR)
    if not revert and not to:
        err_console.print("[red]✗[/] --to is required (or use --revert)")
        raise typer.Exit(EXIT_USER_ERROR)

    try:
        result = promote_task(
            activity_root,
            list(slugs),
            to=to,
            explicit_slug=slug,
            force=force,
            revert=revert,
        )
    except ActionError as exc:
        msg = str(exc)
        # Map by message content — promote_task carries the rule, the CLI
        # just translates to the documented exit code.
        if "not found" in msg:
            err_console.print(f"[red]✗[/] {msg}")
            raise typer.Exit(EXIT_NOT_IN_ACTIVITY) from exc
        if "already promoted" in msg:
            err_console.print(f"[red]✗[/] {msg}")
            raise typer.Exit(EXIT_PROMOTE_ALREADY) from exc
        # Everything else — bad --to target, ambiguous shorthand, validation.
        err_console.print(f"[red]✗[/] {msg}")
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc

    # ── render success output ────────────────────────────────────────
    if result.reverted:
        for s in result.reverted:
            console.print(f"[green]✓[/] {s} reverted (promoted_to cleared)")
        return

    target = result.target or ""
    if result.scaffolded and result.request_path is not None:
        rel = result.request_path
        try:
            rel = result.request_path.relative_to(activity_root)
        except ValueError:
            pass
        console.print(f"[cyan]→[/] scaffolded {target} at [dim]{rel}[/]")
    elif result.request_path is not None:
        rel = result.request_path
        try:
            rel = result.request_path.relative_to(activity_root)
        except ValueError:
            pass
        console.print(f"[cyan]→[/] linked to existing {target} at [dim]{rel}[/]")

    for s in result.promoted:
        console.print(f"[green]✓[/] {s} promoted to {target}")
    for s in result.repointed:
        console.print(f"[green]✓[/] {s} repointed to {target}")


# ── views ─────────────────────────────────────────────────────────────


# NOTE: `loops` is defined later as an index-backed command (loops_cmd).


# ── set verb ──────────────────────────────────────────────────────────


VERB_OVERLAP_FIELDS = {
    "bucket": "octopus plan / focus / park / defer / finish / drop",
    "pinned": "octopus pin / unpin",
    "issue": "octopus block / wait / unblock",
    "archived": "octopus archive / restore",
}


def set_(
    slug: str = typer.Argument(..., help="Task slug."),
    # Workflow
    bucket: str | None = typer.Option(None, "--bucket"),
    stage: str | None = typer.Option(None, "--stage"),
    # Runtime
    run_state: str | None = typer.Option(None, "--run-state"),
    # Attention / impediment / visibility
    pinned: bool | None = typer.Option(None, "--pinned/--no-pinned"),
    issue: str | None = typer.Option(None, "--issue"),
    blocked_by: str | None = typer.Option(None, "--blocked-by"),
    waiting_for: str | None = typer.Option(None, "--waiting-for"),
    archived: bool | None = typer.Option(None, "--archived/--no-archived"),
    # Dates
    due: str | None = typer.Option(None, "--due", help="ISO date YYYY-MM-DD."),
    scheduled: str | None = typer.Option(None, "--scheduled"),
    start_date: str | None = typer.Option(None, "--start-date"),
    end_date: str | None = typer.Option(None, "--end-date"),
    # Prioritization
    priority: str | None = typer.Option(None, "--priority"),
    energy: str | None = typer.Option(None, "--energy"),
    # Actors
    actor: str | None = typer.Option(None, "--actor"),
    owner: str | None = typer.Option(None, "--owner"),
    # Taxonomy
    kind: str | None = typer.Option(
        None, "--kind",
        help="Work classification: feat | bug | spec | polish | test | chore. Use '' to clear.",
    ),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated."),
    title: str | None = typer.Option(None, "--title"),
) -> None:
    """Set frontmatter fields directly. Strict types; warns on verb-overlap."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug)
    overlaps_used: list[str] = []

    def _iso(value: str, name: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as e:
            err_console.print(f"[red]✗[/] --{name.replace('_', '-')}: {value!r} is not valid ISO date.")
            raise typer.Exit(EXIT_USER_ERROR) from e

    if title is not None:
        if not title.strip():
            err_console.print("[red]✗[/] --title cannot be empty.")
            raise typer.Exit(EXIT_USER_ERROR)
        task.title = title
    if bucket is not None:
        overlaps_used.append("bucket")
        if bucket not in TASK_BUCKETS:
            err_console.print(f"[red]✗[/] --bucket: {bucket!r} not in {sorted(TASK_BUCKETS)}")
            raise typer.Exit(EXIT_USER_ERROR)
        task.bucket = bucket
    if stage is not None:
        task.stage = stage or None
    if run_state is not None:
        if run_state in ("", "none", "idle"):
            task.run_state = None
        elif run_state not in TASK_RUN_STATES:
            err_console.print(f"[red]✗[/] --run-state: {run_state!r} not in {sorted(TASK_RUN_STATES)} or 'idle'")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.run_state = run_state
    if pinned is not None:
        overlaps_used.append("pinned")
        task.pinned = True if pinned else None
    if issue is not None:
        overlaps_used.append("issue")
        if issue in ("", "none"):
            task.issue = None
        elif issue not in {"blocked", "waiting"}:
            err_console.print(f"[red]✗[/] --issue: {issue!r} not in [blocked, waiting]")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.issue = issue
    if blocked_by is not None:
        task.blocked_by = blocked_by or None
    if waiting_for is not None:
        task.waiting_for = waiting_for or None
    if archived is not None:
        overlaps_used.append("archived")
        task.archived = True if archived else None
    if due is not None:
        task.due = _iso(due, "due") if due else None
    if scheduled is not None:
        task.scheduled = _iso(scheduled, "scheduled") if scheduled else None
    if start_date is not None:
        task.start_date = _iso(start_date, "start_date") if start_date else None
    if end_date is not None:
        task.end_date = _iso(end_date, "end_date") if end_date else None
    if priority is not None:
        if priority in ("", "normal", "none"):
            task.priority = None
        elif priority not in TASK_PRIORITIES:
            err_console.print(f"[red]✗[/] --priority: {priority!r} not in {sorted(TASK_PRIORITIES)} or 'normal'")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.priority = priority
    if energy is not None:
        if energy in ("", "none"):
            task.energy = None
        elif energy not in {"low", "mid", "high"}:
            err_console.print(f"[red]✗[/] --energy: {energy!r} not in [low, mid, high]")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.energy = energy
    if actor is not None:
        if actor not in {"human", "ai", "automation"}:
            err_console.print(f"[red]✗[/] --actor: {actor!r} not in [human, ai, automation]")
            raise typer.Exit(EXIT_USER_ERROR)
        task.actor = None if actor == "human" else actor
    if owner is not None:
        task.owner = owner or None
    if kind is not None:
        # Empty string clears. Soft enum — unknown values warn via smells().
        task.kind = kind or None
    if tags is not None:
        task.tags = [t.strip() for t in tags.split(",") if t.strip()]

    errors = task.validate()
    if errors:
        err_console.print("[red]✗[/] validation failed:")
        for e in errors:
            err_console.print(f"  - {e}")
        raise typer.Exit(EXIT_USER_ERROR)

    for smell in task.smells():
        err_console.print(f"[yellow]⚠[/] {smell}")

    _save_task(task, body, path, octopus_dir, storage_mode)

    for field_name in overlaps_used:
        tip = VERB_OVERLAP_FIELDS.get(field_name)
        if tip:
            err_console.print(f"[dim]tip: dedicated verb available for --{field_name}: {tip}[/]")

    console.print(f"[green]✓[/] {slug} updated")


app.command(name="set")(set_)


# ── index-backed commands ─────────────────────────────────────────────


EMPTY_INDEX_HINT = (
    "no activities indexed.\n"
    "Run `octopus reindex` to scan configured roots,\n"
    "or `octopus config root add <path>` to add one."
)


def _is_empty_index() -> bool:
    conn = get_db()
    try:
        counts = total_row_counts(conn)
    finally:
        conn.close()
    return counts["activities"] == 0


@app.command("list")
def list_cmd(
    all_: bool = typer.Option(False, "--all", help="Force cross-activity listing regardless of cwd."),
    status: str | None = typer.Option(None, "--status", help="Filter activities by status."),
    type_: str | None = typer.Option(None, "--type", help="Filter activities by type."),
    area: str | None = typer.Option(None, "--area", help="Filter activities by area."),
    bucket: str | None = typer.Option(None, "--bucket", help="Filter tasks by bucket."),
    kind: str | None = typer.Option(
        None, "--kind",
        help="Filter tasks by kind (feat/bug/spec/polish/test/chore). Comma-separated for multi.",
    ),
    promoted: bool = typer.Option(
        False, "--promoted",
        help="Scope override: only tasks with promoted_to set.",
    ),
    spec: str | None = typer.Option(
        None, "--spec",
        help="Scope override: only tasks promoted to spectacular:<slug>.",
    ),
    show_ids: bool = typer.Option(False, "--show-ids", "-i", help="Reveal full activity IDs."),
) -> None:
    """List activities or tasks. Context-aware (use --all to force cross-activity)."""
    cwd_activity = None if all_ else find_activity_root(Path.cwd())
    kinds = [k.strip() for k in kind.split(",")] if kind else None
    # --promoted / --spec force a task listing even at cross-activity scope
    # (otherwise the activity-summary branch would render and ignore the filter).
    task_view = bool(bucket or kinds or promoted or spec)
    conn = get_db()
    try:
        if cwd_activity is not None:
            # In-activity scope: list this activity's tasks
            activity_md = cwd_activity / ".octopus" / "activity.md"
            try:
                activity, _ = read_activity(activity_md)
            except Exception as e:
                err_console.print(f"[red]✗[/] cannot read activity: {e}")
                raise typer.Exit(EXIT_USER_ERROR) from e
            rows = tasks_for_activity(
                conn, activity.id,
                bucket=bucket,
                kinds=kinds, promoted=promoted, spec=spec,
            )
            _print_task_rows(rows, show_ids=show_ids)
        else:
            # Cross-activity scope
            if _is_empty_index():
                console.print(EMPTY_INDEX_HINT)
                return
            if task_view:
                rows = tasks_all(
                    conn, bucket=bucket,
                    kinds=kinds, promoted=promoted, spec=spec,
                )
                _print_task_rows(rows, show_ids=show_ids, show_activity=True)
            else:
                rows = db_list_activities(conn, status=status, type_=type_, area=area)
                _print_activity_rows(conn, rows, show_ids=show_ids)
    finally:
        conn.close()


def _print_activity_rows(
    conn, rows: list, *, show_ids: bool = False,
) -> None:
    if not rows:
        console.print("[dim]no activities match filters[/]")
        return
    table = Table(show_edge=False)
    table.add_column("Activity", style="cyan")
    table.add_column("Title")
    table.add_column("Type", style="dim")
    table.add_column("Status", style="dim")
    table.add_column("Now", justify="right")
    table.add_column("Next", justify="right")
    table.add_column("Backlog", justify="right")
    for row in rows:
        display_id = row["id"] if show_ids else short_form(row["id"])
        counts = count_by_bucket(conn, row["id"])
        table.add_row(
            display_id, row["title"] or "", row["type"] or "", row["status"] or "",
            str(counts.get("now", 0)),
            str(counts.get("next", 0)),
            str(counts.get("backlog", 0)),
        )
    console.print(table)


def _print_task_rows(rows: list, *, show_ids: bool = False, show_activity: bool = False) -> None:
    if not rows:
        console.print("[dim]no tasks[/]")
        return
    bucket_order = ["now", "next", "backlog", "done", "dropped"]
    by_bucket: dict[str, list] = {b: [] for b in bucket_order}
    for r in rows:
        by_bucket.setdefault(r["bucket"], []).append(r)
    for b in bucket_order:
        items = by_bucket.get(b, [])
        if not items:
            continue
        console.print(f"\n[bold]{b.upper()}[/]")
        for r in items:
            marker = "📌" if r["pinned"] else (
                "🔥" if r["priority"] == "urgent" else
                "!" if r["priority"] == "high" else " "
            )
            prefix = ""
            if show_activity:
                act = r["activity_id"] if show_ids else short_form(r["activity_id"])
                prefix = f"[dim]{act}/[/]"
            kind_chip = f" [blue]\\[{r['kind']}][/]" if r["kind"] else ""
            promoted_str = ""
            if r["promoted_to"]:
                promoted_str = f"  [dim]→ {_promoted_chip(r['promoted_to'])}[/]"
            console.print(
                f"  {marker} {prefix}[cyan]{r['slug']}[/]{kind_chip}  {r['title']}{promoted_str}"
            )


@app.command()
def status(
    activity_query: str | None = typer.Argument(None, help="Activity prefix or full id. Defaults to cwd's activity."),
    show_ids: bool = typer.Option(False, "--show-ids", "-i"),
) -> None:
    """Detailed activity view, index-backed."""
    conn = get_db()
    try:
        if activity_query:
            matches = get_activity_by_id_or_prefix(conn, activity_query)
            if not matches:
                err_console.print(f"[red]✗[/] no activity matches {activity_query!r}")
                raise typer.Exit(EXIT_USER_ERROR)
            if len(matches) > 1:
                err_console.print(f"[red]✗[/] ambiguous {activity_query!r}; candidates:")
                for m in matches:
                    err_console.print(f"  {m['id']}  {m['path']}")
                raise typer.Exit(EXIT_USER_ERROR)
            activity = matches[0]
        else:
            root = find_activity_root(Path.cwd())
            if root is None:
                if _is_empty_index():
                    console.print(EMPTY_INDEX_HINT)
                    return
                err_console.print(
                    "[red]✗[/] not in an activity; pass an activity slug, "
                    "or run from inside an activity folder."
                )
                raise typer.Exit(EXIT_NOT_IN_ACTIVITY)
            activity_md = root / ".octopus" / "activity.md"
            act_obj, _ = read_activity(activity_md)
            matches = get_activity_by_id_or_prefix(conn, act_obj.id)
            if not matches:
                console.print(EMPTY_INDEX_HINT)
                return
            activity = matches[0]

        display_id = activity["id"] if show_ids else short_form(activity["id"])
        tbl = Table(show_header=False, show_edge=False, padding=(0, 2))
        tbl.add_column(style="dim")
        tbl.add_column()
        tbl.add_row("Activity", f"[bold]{display_id}[/]")
        tbl.add_row("Title", activity["title"] or "")
        tbl.add_row("Path", activity["path"])
        tbl.add_row("Type", activity["type"] or "")
        tbl.add_row("Status", activity["status"] or "")
        if activity["area"]:
            tbl.add_row("Area", activity["area"])
        console.print(tbl)

        counts = count_by_bucket(conn, activity["id"])
        if counts:
            console.print()
            ctab = Table(show_header=False, padding=(0, 2))
            ctab.add_column(style="dim")
            ctab.add_column(justify="right")
            for b in ("now", "next", "backlog", "done", "dropped"):
                n = counts.get(b, 0)
                if n:
                    ctab.add_row(b, str(n))
            if ctab.row_count:
                console.print(ctab)
    finally:
        conn.close()


@app.command()
def reindex(
    root: str | None = typer.Option(None, "--root", help="Override configured roots."),
    prune: bool = typer.Option(False, "--prune", help="Delete rows whose source files are missing."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Walk configured roots and rebuild the SQLite index."""
    cfg = load_config()
    if root:
        roots = [Path(root).expanduser().resolve()]
    else:
        roots = cfg.roots
    if not roots:
        err_console.print(
            "[red]✗[/] no roots configured. Add one with:\n"
            "  octopus config root add <path>"
        )
        raise typer.Exit(EXIT_CONFIG_ERROR)

    log = get_logger("reindex")
    log.info("reindex start roots=%s prune=%s", [str(r) for r in roots], prune)
    conn = get_db()
    try:
        result = reindex_all(conn, roots, prune=prune, accept_renames=prune)
    finally:
        conn.close()

    log.info(
        "reindex done activities=%d tasks=%d sessions=%d errors=%d",
        result.activities_seen, result.tasks_seen, result.sessions_seen, len(result.errors),
    )
    console.print(
        f"[green]✓[/] reindex complete: "
        f"{result.activities_seen} activities, "
        f"{result.tasks_seen} tasks, "
        f"{result.sessions_seen} sessions"
    )
    if result.related_tasks_propagated:
        console.print(
            f"  [cyan]→[/] propagated related_tasks to "
            f"{result.related_tasks_propagated} request(s)"
        )
    if result.promoted_to_warnings:
        for task_slug, value in result.promoted_to_warnings:
            err_console.print(
                f"[yellow]⚠[/] malformed promoted_to on {task_slug}: {value!r}"
            )
    if prune:
        console.print(
            f"  pruned: {result.pruned_activities} activities, "
            f"{result.pruned_tasks} tasks, "
            f"{result.pruned_sessions} sessions"
        )
    if result.missing_roots:
        for p in result.missing_roots:
            err_console.print(f"[yellow]⚠[/] root not found on disk: {p}")
    if result.renames:
        for aid, old, new in result.renames:
            tag = "[dim](applied)[/]" if prune else "[yellow](pending — run with --prune to apply)[/]"
            err_console.print(f"[yellow]⚠[/] rename {tag}: {short_form(aid)}: {old} → {new}")
    if result.errors and verbose:
        for e in result.errors:
            err_console.print(f"[yellow]⚠[/] {e}")
    elif result.errors:
        err_console.print(f"[yellow]⚠[/] {len(result.errors)} errors (re-run with --verbose to see)")
    if result.collisions:
        for activity_id, paths in result.collisions:
            err_console.print(f"[red]✗[/] collision: {activity_id}")
            for p in paths:
                err_console.print(f"     {p}")
        raise typer.Exit(4)


# ── diagnose ──────────────────────────────────────────────────────────


@app.command()
def diagnose(
    out: str | None = typer.Option(None, "--out", help="Write zip to this path (skip prompt)."),
    no_zip: bool = typer.Option(False, "--no-zip", help="Print summary only; don't write a zip."),
) -> None:
    """Print + bundle a diagnostic report (version, config, index stats, log tail).

    All `$HOME` paths are redacted to `~/` so the bundle is safe to share.
    """
    from octopus.core.logging import default_log_path
    from octopus.diagnose import (
        _read_log_tail,  # type: ignore[attr-defined]
        collect_diagnostics,
        default_out_path,
        format_summary,
        write_zip,
    )

    payload = collect_diagnostics()
    console.print(format_summary(payload))

    if no_zip:
        return

    out_path = Path(out).expanduser().resolve() if out else default_out_path()
    if out is None:
        console.print(f"\nWrite zip to [bold]{out_path}[/]?")
        if not typer.confirm("", default=True):
            console.print("[dim]skipped[/]")
            return

    log_tail = _read_log_tail(default_log_path())
    written = write_zip(payload, out_path, log_tail)
    console.print(f"[green]✓[/] wrote diagnostic bundle: [bold]{written}[/]")


# ── config root subcommands ───────────────────────────────────────────


config_app = typer.Typer(name="config", help="Configuration commands.", no_args_is_help=True)
config_root_app = typer.Typer(name="root", help="Manage indexed roots.", no_args_is_help=True)
config_app.add_typer(config_root_app, name="root")
app.add_typer(config_app, name="config")


@config_root_app.command("list")
def root_list() -> None:
    """List configured roots."""
    paths = config_list_roots()
    if not paths:
        console.print("[dim]no roots configured[/]")
        console.print("  add one with: octopus config root add <path>")
        return
    for p in paths:
        console.print(p)


@config_root_app.command("add")
def root_add(path: str = typer.Argument(..., help="Path to add (tilde-expanded on read).")) -> None:
    """Add a path to the indexed roots."""
    ok, msg = config_add_root(path)
    if not ok:
        err_console.print(f"[yellow]⚠[/] {msg}")
        raise typer.Exit(EXIT_USER_ERROR)
    console.print(f"[green]✓[/] {msg}")


@config_root_app.command("remove")
def root_remove(path: str = typer.Argument(..., help="Path to remove.")) -> None:
    """Remove a path from the indexed roots."""
    ok, msg = config_remove_root(path)
    if not ok:
        err_console.print(f"[red]✗[/] {msg}")
        raise typer.Exit(EXIT_USER_ERROR)
    console.print(f"[green]✓[/] {msg}")


# ── upgrade loops to use the index ────────────────────────────────────


# Override the file-native loops from request 02 with an index-backed version.
# This shadows the earlier definition.
@app.command("loops")  # type: ignore[no-redef]
def loops_cmd(
    all_: bool = typer.Option(False, "--all", help="Cross-activity (default: current activity only if in one)."),
    show_ids: bool = typer.Option(False, "--show-ids", "-i"),
) -> None:
    """Show open loops (unfinished tasks)."""
    cwd_activity = None if all_ else find_activity_root(Path.cwd())
    conn = get_db()
    try:
        if cwd_activity is not None:
            activity, _ = read_activity(cwd_activity / ".octopus" / "activity.md")
            rows = db_loops(conn, activity_id=activity.id)
            _print_task_rows(rows, show_ids=show_ids)
        else:
            if _is_empty_index():
                console.print(EMPTY_INDEX_HINT)
                return
            rows = db_loops(conn)
            _print_task_rows(rows, show_ids=show_ids, show_activity=True)
    finally:
        conn.close()


# ── session subcommands (request 04) ──────────────────────────────────


from octopus.db.upsert import upsert_session  # noqa: E402
from octopus.sessions import (  # noqa: E402
    NoActiveSessionError,
    end_session,
    log_session,
    prune_sessions,
    show_session,
    start_session,
    switch_session,
)
from octopus.sessions import (
    list_sessions as fs_list_sessions,
)
from octopus.sessions.io import read_session  # noqa: E402

session_app = typer.Typer(name="session", help="Session lifecycle.", no_args_is_help=True)
app.add_typer(session_app, name="session")


def _resolve_activity_id(activity_root: Path) -> str:
    activity, _ = read_activity(activity_root / ".octopus" / "activity.md")
    return activity.id


def _sync_session(activity_id: str, session) -> None:
    """Upsert the session row in the index after a file write."""
    try:
        conn = get_db()
    except Exception:
        return
    try:
        raw = {
            "title": session.title,
            "started": session.started.isoformat(timespec="seconds"),
        }
        if session.ended is not None:
            raw["ended"] = session.ended.isoformat(timespec="seconds")
        if session.status:
            raw["status"] = session.status
        if session.summary:
            raw["summary"] = session.summary
        if session.related_tasks:
            raw["related_tasks"] = list(session.related_tasks)
        if session.related_handoff:
            raw["related_handoff"] = session.related_handoff
        upsert_session(
            conn,
            activity_id,
            filename=session.filename,
            path=session.path,
            title=session.title,
            started=session.started,
            ended=session.ended,
            raw_frontmatter=raw,
        )
        conn.commit()
    except Exception as exc:
        err_console.print(f"[yellow]⚠[/] index sync failed: {exc} (run `octopus reindex`)")
    finally:
        conn.close()


def _prompt_open_sessions(opens) -> str:
    err_console.print(
        f"[yellow]⚠[/] {len(opens)} session(s) already open in this activity:"
    )
    for s in opens:
        marker = " (active)" if s.active else ""
        err_console.print(f"  - {s.filename}{marker}  started {s.started.isoformat(timespec='seconds')}")
    err_console.print("[c]ontinue active  [n]ew session  [e]nd previous + new  [a]bort")
    return typer.prompt("choice", default="n").strip().lower()


@session_app.command("start")
def session_start(
    title: str | None = typer.Option(None, "--title", help="Session title (default auto)."),
) -> None:
    """Start a new session in the current activity."""
    root = _require_activity()
    activity_id = _resolve_activity_id(root)
    try:
        session = start_session(
            root, activity_id, title=title, on_open_sessions=_prompt_open_sessions
        )
    except RuntimeError as exc:
        if str(exc) == "aborted":
            err_console.print("[dim]aborted[/]")
            raise typer.Exit(EXIT_USER_ERROR)
        raise
    _sync_session(activity_id, session)
    get_logger("session").info("start activity=%s slug=%s", activity_id, session.filename)
    console.print(f"[green]✓[/] started session [bold]{session.filename}[/]")


@session_app.command("log")
def session_log(note: str = typer.Argument(..., help="Note to append.")) -> None:
    """Append a timestamped note to the active session."""
    root = _require_activity()
    activity_id = _resolve_activity_id(root)
    try:
        session = log_session(root, activity_id, note)
    except NoActiveSessionError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_CONFIG_ERROR)
    _sync_session(activity_id, session)
    console.print(f"[green]✓[/] logged to [bold]{session.filename}[/]")


@session_app.command("end")
def session_end(
    slug: str | None = typer.Argument(None, help="Session filename (default: active)."),
    summary: str | None = typer.Option(None, "--summary", help="One-line summary."),
    status: str = typer.Option("done", "--status", help="done | dropped."),
    handoff: bool = typer.Option(False, "--handoff", help="Also create a handoff."),
    handoff_title: str | None = typer.Option(None, "--handoff-title", help="Handoff title (required with --non-interactive)."),
    handoff_to_actor: str | None = typer.Option(None, "--handoff-to-actor", help="human | ai | both."),
    handoff_to_owner: str | None = typer.Option(None, "--handoff-to-owner", help="Named recipient."),
    handoff_summary: str | None = typer.Option(None, "--handoff-summary", help="Handoff one-line TL;DR."),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Fail rather than prompt."),
) -> None:
    """End a session. With --handoff, also create a paired handoff file."""
    root = _require_activity()
    activity_id = _resolve_activity_id(root)
    try:
        session = end_session(
            root, activity_id, slug=slug, summary=summary, status=status
        )
    except NoActiveSessionError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_CONFIG_ERROR)
    except (ValueError, FileNotFoundError) as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR)
    _sync_session(activity_id, session)
    get_logger("session").info(
        "end activity=%s slug=%s status=%s", activity_id, session.filename, session.status
    )
    console.print(f"[green]✓[/] ended session [bold]{session.filename}[/] ({session.status})")

    if handoff:
        from octopus.handoffs import new_handoff as _new_handoff  # noqa: E402

        title = handoff_title
        to_actor = handoff_to_actor
        to_owner = handoff_to_owner
        h_summary = handoff_summary or session.summary

        if non_interactive:
            if not title:
                err_console.print("[red]✗[/] --handoff-title required with --non-interactive")
                raise typer.Exit(EXIT_USER_ERROR)
        else:
            if not title:
                title = typer.prompt("Handoff title", default=session.title)
            if not to_actor:
                to_actor = typer.prompt("To actor (human|ai|both)", default="", show_default=False) or None
            if not to_owner:
                to_owner = typer.prompt("To owner (optional)", default="", show_default=False) or None
            if not h_summary:
                h_summary = typer.prompt("Summary", default="", show_default=False) or None

        try:
            h = _new_handoff(
                root,
                title,
                from_session=session.filename,
                to_actor=to_actor,
                to_owner=to_owner,
                summary=h_summary,
            )
        except ValueError as exc:
            err_console.print(f"[red]✗[/] {exc}")
            raise typer.Exit(EXIT_USER_ERROR)

        # Symmetric backlink: set session.related_handoff and rewrite.
        session.related_handoff = h.slug
        if session.path is not None:
            from octopus.sessions.io import read_session as _read_session  # noqa: E402
            from octopus.sessions.io import write_session as _write_session  # noqa: E402
            _, body = _read_session(session.path)
            _write_session(session.path, session, body)
            _sync_session(activity_id, session)
        console.print(f"[green]✓[/] created handoff [bold]{h.slug}[/]")


@session_app.command("switch")
def session_switch(slug: str = typer.Argument(..., help="Session filename to switch to.")) -> None:
    """Switch the active session pointer."""
    root = _require_activity()
    activity_id = _resolve_activity_id(root)
    try:
        session = switch_session(root, activity_id, slug)
    except (ValueError, FileNotFoundError) as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR)
    _sync_session(activity_id, session)
    console.print(f"[green]✓[/] active session: [bold]{session.filename}[/]")


@session_app.command("list")
def session_list(
    all_: bool = typer.Option(False, "--all", help="Include closed."),
    open_only: bool = typer.Option(False, "--open", help="Open sessions only."),
    closed_only: bool = typer.Option(False, "--closed", help="Closed sessions only."),
) -> None:
    """List sessions in the current activity."""
    root = _require_activity()
    sessions = fs_list_sessions(root)
    if open_only:
        sessions = [s for s in sessions if s.is_open()]
    elif closed_only:
        sessions = [s for s in sessions if not s.is_open()]
    elif not all_:
        # Default: hide closed older than 30 days for sanity.
        from datetime import timedelta as _td
        cutoff = datetime.now().replace(microsecond=0) - _td(days=30)
        sessions = [s for s in sessions if s.is_open() or (s.ended and s.ended > cutoff)]
    if not sessions:
        console.print("[dim]no sessions[/]")
        return
    from octopus.sessions.cache import get_active as _get_active
    activity_id = _resolve_activity_id(root)
    active_name = _get_active(activity_id)
    table = Table(show_header=True, header_style="bold")
    table.add_column("active")
    table.add_column("filename")
    table.add_column("started")
    table.add_column("ended")
    table.add_column("status")
    for s in sessions:
        is_active = "●" if s.filename == active_name else ""
        table.add_row(
            is_active,
            s.filename,
            s.started.isoformat(timespec="seconds"),
            s.ended.isoformat(timespec="seconds") if s.ended else "[dim]open[/]",
            s.status or "",
        )
    console.print(table)


@session_app.command("show")
def session_show(
    slug: str | None = typer.Argument(None, help="Session filename (default: active or most-recent)."),
) -> None:
    """Show a session."""
    root = _require_activity()
    activity_id = _resolve_activity_id(root)
    try:
        session = show_session(root, activity_id, slug=slug)
    except FileNotFoundError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR)
    console.print(f"[bold]{session.title}[/] ({session.filename})")
    console.print(f"started: {session.started.isoformat(timespec='seconds')}")
    if session.ended:
        console.print(f"ended:   {session.ended.isoformat(timespec='seconds')}")
    if session.status:
        console.print(f"status:  {session.status}")
    if session.summary:
        console.print(f"summary: {session.summary}")
    if session.path and session.path.is_file():
        _, body = read_session(session.path)
        if body.strip():
            console.print("---")
            console.print(body)


@session_app.command("prune")
def session_prune(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be pruned."),
    days: int | None = typer.Option(
        None, "--days", help="Stale threshold in days (default: config session.prune_days)."
    ),
) -> None:
    """Auto-close stale open sessions in the current activity."""
    root = _require_activity()
    activity_id = _resolve_activity_id(root)
    cfg = load_config(root / ".octopus")
    effective_days = days if days is not None else cfg.session_prune_days
    pruned = prune_sessions(
        root, activity_id, days=effective_days, dry_run=dry_run
    )
    if not pruned:
        console.print(f"[dim]no stale sessions (threshold: {effective_days} days)[/]")
        return
    verb = "would prune" if dry_run else "pruned"
    console.print(f"[green]✓[/] {verb} {len(pruned)} session(s):")
    for s in pruned:
        console.print(f"  - {s.filename}")
    if not dry_run:
        for s in pruned:
            if s.path:
                s2, _ = read_session(s.path)
                _sync_session(activity_id, s2)


# ── memory subcommands (request 04) ───────────────────────────────────


import os as _os  # noqa: E402
import subprocess as _subprocess  # noqa: E402
import tempfile as _tempfile  # noqa: E402

from octopus.memory import (  # noqa: E402
    CANONICAL_SECTIONS,
    DEFAULT_SECTION,
    AmbiguousSectionError,
    UnknownSectionError,
    memory_path,
    read_memory,
)
from octopus.memory import (
    append_entry as memory_append_entry,
)
from octopus.memory import (
    resolve_section as memory_resolve_section,
)
from octopus.memory import (
    section_entries as memory_section_entries,
)
from octopus.memory import (
    set_summary as memory_set_summary,
)
from octopus.memory import (
    show_default as memory_show_default,
)
from octopus.memory.io import _split_on_marker  # noqa: E402

memory_app = typer.Typer(name="memory", help="Activity memory.", no_args_is_help=True)
app.add_typer(memory_app, name="memory")


def _activity_id_and_title(activity_root: Path) -> tuple[str, str]:
    activity, _ = read_activity(activity_root / ".octopus" / "activity.md")
    return activity.id, activity.title


def _editor_capture(initial_text: str = "") -> str | None:
    """Open $EDITOR with `initial_text` and return the saved content (None if empty/cancel)."""
    editor = _os.environ.get("EDITOR") or _os.environ.get("VISUAL") or "vi"
    with _tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tf:
        tf.write(initial_text)
        tmp_path = Path(tf.name)
    try:
        rc = _subprocess.call([editor, str(tmp_path)])
        if rc != 0:
            return None
        text = tmp_path.read_text(encoding="utf-8").strip()
        return text or None
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


@memory_app.command("append")
def memory_append(
    note: str = typer.Argument(..., help="Note text."),
    section: str = typer.Option(
        DEFAULT_SECTION.lower(), "--section", "-s",
        help=f"Section: {', '.join(s.lower() for s in CANONICAL_SECTIONS)}.",
    ),
) -> None:
    """Append a timestamped entry to a memory section."""
    root = _require_activity()
    activity_id, title = _activity_id_and_title(root)
    try:
        _, canon = memory_append_entry(
            root, activity_id, note, section=section, activity_title=title
        )
    except (UnknownSectionError, AmbiguousSectionError, ValueError) as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR)
    console.print(f"[green]✓[/] appended to [bold]## {canon}[/]")


@memory_app.command("show")
def memory_show(
    section: str | None = typer.Option(
        None, "--section", "-s",
        help="Show one section in full (omit for default preview).",
    ),
    all_: bool = typer.Option(False, "--all", help="Render the entire memory.md."),
) -> None:
    """Show memory: default preview, one section, or the whole file."""
    root = _require_activity()
    path = memory_path(root)
    if not path.is_file():
        console.print("[dim]no memory.md yet[/]")
        console.print("  start one with: octopus memory append \"<note>\"")
        return

    if all_:
        console.print(path.read_text(encoding="utf-8"))
        return

    if section is not None:
        try:
            canon = memory_resolve_section(section)
        except (UnknownSectionError, AmbiguousSectionError) as exc:
            err_console.print(f"[red]✗[/] {exc}")
            raise typer.Exit(EXIT_USER_ERROR)
        _, body = read_memory(path)
        _, below, _ = _split_on_marker(body)
        entries = memory_section_entries(below, canon)
        if not entries:
            console.print(f"[dim]## {canon} is empty[/]")
            return
        console.print(f"## {canon} ({len(entries)} entries)")
        for hdr, txt in entries:
            console.print("")
            console.print(f"### {hdr}")
            if txt.strip():
                console.print(txt)
        return

    console.print(memory_show_default(root), end="")


summary_app = typer.Typer(name="summary", help="Memory summary.", invoke_without_command=True)


@summary_app.callback(invoke_without_command=True)
def memory_summary_root(ctx: typer.Context) -> None:
    """Print the frontmatter `summary:` field (default) or dispatch to subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    root = _require_activity()
    path = memory_path(root)
    if not path.is_file():
        console.print("[dim]no memory.md yet[/]")
        return
    memory, _ = read_memory(path)
    if memory.summary:
        console.print(memory.summary)
    else:
        console.print("[dim](no summary set)[/]")


@summary_app.command("set")
def memory_summary_set(
    text: str | None = typer.Argument(None, help="Summary text (omit to open $EDITOR)."),
) -> None:
    """Set the frontmatter `summary:` field."""
    root = _require_activity()
    activity_id, title = _activity_id_and_title(root)
    if text is None:
        path = memory_path(root)
        initial = ""
        if path.is_file():
            memory, _ = read_memory(path)
            initial = memory.summary or ""
        text = _editor_capture(initial)
        if text is None:
            err_console.print("[dim]aborted (empty)[/]")
            raise typer.Exit(EXIT_USER_ERROR)
    memory_set_summary(root, activity_id, text, activity_title=title)
    console.print("[green]✓[/] summary updated")


memory_app.add_typer(summary_app, name="summary")


state_app = typer.Typer(name="state", help="Memory state.", invoke_without_command=True)


@state_app.callback(invoke_without_command=True)
def memory_state_root(ctx: typer.Context) -> None:
    """Show the State section (default) or dispatch to subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    root = _require_activity()
    path = memory_path(root)
    if not path.is_file():
        console.print("[dim]no memory.md yet[/]")
        return
    _, body = read_memory(path)
    _, below, _ = _split_on_marker(body)
    entries = memory_section_entries(below, "State")
    if not entries:
        console.print("[dim]no State entries yet[/]")
        console.print("  set one with: octopus memory state set \"<text>\"")
        return
    hdr, txt = entries[-1]
    console.print(f"### {hdr}")
    if txt.strip():
        console.print(txt)
    if len(entries) > 1:
        console.print(
            f"\n[dim]({len(entries) - 1} earlier state entries — "
            f"run `octopus memory show --section state` for all)[/]"
        )


@state_app.command("set")
def memory_state_set(
    text: str | None = typer.Argument(None, help="State text (omit to open $EDITOR)."),
) -> None:
    """Append a new entry to the State section."""
    root = _require_activity()
    activity_id, title = _activity_id_and_title(root)
    if text is None:
        text = _editor_capture("")
        if text is None:
            err_console.print("[dim]aborted (empty)[/]")
            raise typer.Exit(EXIT_USER_ERROR)
    try:
        _, canon = memory_append_entry(
            root, activity_id, text, section="state", activity_title=title
        )
    except ValueError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR)
    console.print(f"[green]✓[/] appended to [bold]## {canon}[/]")


memory_app.add_typer(state_app, name="state")


# ── handoff verbs (request 04) ───────────────────────────────────────

from octopus.handoffs import (  # noqa: E402
    HandoffNotFoundError,
)
from octopus.handoffs import (
    list_handoffs as fs_list_handoffs,
)
from octopus.handoffs import (
    new_handoff as fs_new_handoff,
)
from octopus.handoffs import (
    show_handoff as fs_show_handoff,
)
from octopus.handoffs.io import read_handoff  # noqa: E402

handoff_app = typer.Typer(name="handoff", help="Handoff: deliberate context transfer.", no_args_is_help=True)
app.add_typer(handoff_app, name="handoff")


@handoff_app.command("new")
def handoff_new(
    title: str = typer.Argument(..., help="Handoff title."),
    from_session: str | None = typer.Option(None, "--from-session", help="Session filename (without .md)."),
    from_actor: str = typer.Option("human", "--from-actor", help="human | ai | both."),
    to_actor: str | None = typer.Option(None, "--to-actor", help="human | ai | both."),
    to_owner: str | None = typer.Option(None, "--to-owner", help="Named recipient."),
    priority: str = typer.Option("medium", "--priority", help="high | medium | low."),
    summary: str | None = typer.Option(None, "--summary", help="One-line TL;DR."),
    related_task: list[str] | None = typer.Option(None, "--related-task", help="Task slug (repeatable)."),
) -> None:
    """Create a new handoff file."""
    root = _require_activity()
    try:
        h = fs_new_handoff(
            root,
            title,
            from_session=from_session,
            from_actor=from_actor,
            to_actor=to_actor,
            to_owner=to_owner,
            priority=priority,
            summary=summary,
            related_tasks=list(related_task) if related_task else None,
        )
    except ValueError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR)
    get_logger("handoff").info("new slug=%s from_session=%s", h.slug, from_session)
    console.print(f"[green]✓[/] created handoff [bold]{h.slug}[/]")
    if h.path is not None:
        console.print(f"[dim]{h.path}[/]")


@handoff_app.command("list")
def handoff_list(
    status: str | None = typer.Option(None, "--status", help="open | received | resolved | stale."),
) -> None:
    """List handoffs in the current activity."""
    root = _require_activity()
    handoffs = fs_list_handoffs(root, status=status)
    if not handoffs:
        console.print("[dim]no handoffs[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("slug")
    table.add_column("title")
    table.add_column("created")
    table.add_column("status")
    table.add_column("from → to")
    table.add_column("priority")
    for h in handoffs:
        direction = h.from_actor
        if h.to_actor:
            direction += f" → {h.to_actor}"
        elif h.to_owner:
            direction += f" → {h.to_owner}"
        table.add_row(
            h.slug,
            h.title,
            h.created.isoformat(),
            h.status,
            direction,
            h.priority,
        )
    console.print(table)


@handoff_app.command("show")
def handoff_show(slug: str = typer.Argument(..., help="Handoff slug (filename without .md).")) -> None:
    """Show a handoff."""
    root = _require_activity()
    try:
        h = fs_show_handoff(root, slug)
    except HandoffNotFoundError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR)
    console.print(f"[bold]{h.title}[/] ({h.slug})")
    console.print(f"created:    {h.created.isoformat()}")
    console.print(f"status:     {h.status}")
    console.print(f"from:       {h.from_actor}")
    if h.to_actor:
        console.print(f"to_actor:   {h.to_actor}")
    if h.to_owner:
        console.print(f"to_owner:   {h.to_owner}")
    if h.from_session:
        console.print(f"from_session: {h.from_session}")
    if h.summary:
        console.print(f"summary:    {h.summary}")
    if h.priority and h.priority != "medium":
        console.print(f"priority:   {h.priority}")
    if h.related_tasks:
        console.print(f"related_tasks: {', '.join(h.related_tasks)}")
    if h.path and h.path.is_file():
        _, body = read_handoff(h.path)
        if body.strip():
            console.print()
            console.print(body)


if __name__ == "__main__":
    app()

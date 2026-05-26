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


# ── lint ─────────────────────────────────────────────────────────────


@app.command()
def lint(
    activity: str | None = typer.Argument(None, help="Activity token (path or id). Default: cwd."),
    all_activities: bool = typer.Option(False, "--all", help="Lint every indexed activity."),
    rule: list[str] | None = typer.Option(None, "--rule", help="Run only this rule (repeatable)."),
    severity: str | None = typer.Option(None, "--severity", help="Filter: info | warn | error."),
    fix_findings: bool = typer.Option(False, "--fix", help="Apply auto-fixable findings (prompts)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip prompts when --fix is used."),
    json_output: bool = typer.Option(False, "--json", help="Emit findings as JSON."),
) -> None:
    """Audit task corpus hygiene. Read-only by default."""
    from octopus.lint import lint_activity
    from octopus.lint.cli_output import print_human, print_json
    from octopus.lint.findings import Severity
    from octopus.lint.registry import get as _get_rule
    from octopus.lint.runner import apply_fix

    # Validate --rule entries early.
    if rule:
        for code in rule:
            if _get_rule(code) is None:
                err_console.print(f"[red]✗[/] unknown rule: {code}")
                raise typer.Exit(EXIT_USER_ERROR)

    # Validate --severity.
    min_sev: Severity | None = None
    if severity is not None:
        try:
            min_sev = Severity(severity)
        except ValueError as exc:
            err_console.print("[red]✗[/] --severity must be one of: info, warn, error")
            raise typer.Exit(EXIT_USER_ERROR) from exc

    # Resolve scope.
    roots: list[Path] = []
    if all_activities:
        if activity is not None:
            err_console.print("[red]✗[/] --all and <activity> are mutually exclusive")
            raise typer.Exit(EXIT_USER_ERROR)
        from octopus.config import load_config
        cfg = load_config()
        from octopus.fs.discover import find_all_activities
        roots = find_all_activities(cfg.roots)
        if not roots:
            err_console.print("[yellow]⚠[/] no activities found in configured roots")
            raise typer.Exit(EXIT_OK)
    elif activity is not None:
        from octopus.core.identify import (
            ActivityAmbiguous,
            ActivityNotFound,
            resolve_activity,
        )
        try:
            row = resolve_activity(activity)
        except (ActivityNotFound, ActivityAmbiguous) as exc:
            err_console.print(f"[red]✗[/] {exc}")
            raise typer.Exit(EXIT_USER_ERROR) from exc
        roots = [Path(row["path"])]
    else:
        roots = [_require_activity()]

    # Run.
    from octopus.lint.runner import LintReport
    combined = LintReport()
    for r in roots:
        rep = lint_activity(r, rule_codes=rule)
        combined.findings.extend(rep.findings)
        combined.scanned += rep.scanned

    # --fix path.
    if fix_findings:
        if json_output:
            err_console.print("[red]✗[/] --fix and --json are mutually exclusive")
            raise typer.Exit(EXIT_USER_ERROR)
        fixable = [f for f in combined.findings if f.auto_fixable]
        if not fixable:
            console.print("[green]✓[/] nothing to fix")
            print_human(combined, console=console, base=Path.cwd(), min_severity=min_sev)
            raise typer.Exit(combined.exit_code())
        applied = 0
        skipped = 0
        for f in fixable:
            preview = ", ".join(f"{k}={v!r}" for k, v in f.fix_preview.items()) or "(no preview)"
            console.print(f"[cyan]{f.code}[/]  {f.path}")
            console.print(f"  → would change: {preview}")
            if not yes and not typer.confirm("apply?", default=False):
                skipped += 1
                continue
            if apply_fix(f):
                applied += 1
                console.print("  [green]✓ applied[/]")
            else:
                skipped += 1
                console.print("  [yellow]⚠ skipped (no-op)[/]")
        console.print()
        console.print(f"[green]✓[/] {applied} fix(es) applied, {skipped} skipped")
        # Re-lint to report final state.
        combined = LintReport()
        for r in roots:
            rep = lint_activity(r, rule_codes=rule)
            combined.findings.extend(rep.findings)
            combined.scanned += rep.scanned

    # Output.
    if json_output:
        print_json(combined, console=console, min_severity=min_sev)
    else:
        print_human(combined, console=console, base=Path.cwd(), min_severity=min_sev)

    raise typer.Exit(combined.exit_code())


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


_EXPLICIT_DEFAULT_VALUES_BY_FIELD: dict[str, set[str]] = {
    # D80: these values, passed explicitly, clear the field instead of rejecting.
    "priority": {"", "normal", "none"},
    "actor": {"", "human"},
    "energy": {"", "normal", "none"},
    "run_state": {"", "idle", "none"},
    "issue": {"", "none"},
    "kind": {"", "none"},
    "stage": {""},
    "owner": {""},
    "blocked_by": {""},
    "waiting_for": {""},
    "due": {""},
    "scheduled": {""},
    "start_date": {""},
    "end_date": {""},
}


def _is_explicit_default(field: str, value: str | None) -> bool:
    """D80: did the user pass an explicit-default value that should clear the field?"""
    if value is None:
        return False
    defaults = _EXPLICIT_DEFAULT_VALUES_BY_FIELD.get(field, set())
    return value in defaults


def _parse_iso_date(value: str, flag_name: str) -> date | None:
    """Parse YYYY-MM-DD; return None on explicit-default; exit on bad input."""
    if _is_explicit_default(flag_name.replace("-", "_"), value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        err_console.print(f"[red]✗[/] --{flag_name}: {value!r} is not valid ISO date.")
        raise typer.Exit(EXIT_USER_ERROR) from exc


@app.command()
def capture(
    title: str = typer.Argument(..., help="Task title."),
    to_next: bool = typer.Option(False, "--next", help="Create directly in `next`."),
    to_now: bool = typer.Option(False, "--now", help="Create directly in `now` (does NOT auto-pin, per D81)."),
    priority: str | None = typer.Option(
        None, "--priority",
        help=f"One of {sorted(TASK_PRIORITIES)} (or 'normal'/'none'/'' to clear)",
    ),
    slug: str | None = typer.Option(None, "--slug", help="Override the auto-slugified filename."),
    # Dates (D80: explicit-default clears)
    due: str | None = typer.Option(None, "--due", help="ISO date YYYY-MM-DD."),
    scheduled: str | None = typer.Option(None, "--scheduled", help="ISO date YYYY-MM-DD."),
    start_date: str | None = typer.Option(None, "--start-date", help="ISO date YYYY-MM-DD."),
    end_date: str | None = typer.Option(None, "--end-date", help="ISO date YYYY-MM-DD."),
    # Actors / energy / owner / stage
    actor: str | None = typer.Option(None, "--actor", help="human (default) | ai | automation"),
    energy: str | None = typer.Option(None, "--energy", help="low | mid | high"),
    owner: str | None = typer.Option(None, "--owner", help="Free-form name/username."),
    stage: str | None = typer.Option(None, "--stage", help="Free-form per-activity workflow stage."),
    # Tag flag matrix (D76) — all six accept comma/space/repeated input
    tag: list[str] | None = typer.Option(None, "--tag", help="Replace the tag list (alias of --tags)."),
    tags: list[str] | None = typer.Option(None, "--tags", help="Replace the tag list."),
    add_tag: list[str] | None = typer.Option(None, "--add-tag", help="Append to the tag list."),
    add_tags: list[str] | None = typer.Option(None, "--add-tags", help="Append to the tag list."),
    remove_tag: list[str] | None = typer.Option(None, "--remove-tag", help="Remove from the tag list."),
    remove_tags: list[str] | None = typer.Option(None, "--remove-tags", help="Remove from the tag list."),
    clear_tags: bool = typer.Option(False, "--clear-tags", help="Empty the tag list."),
    activity: str | None = typer.Option(
        None, "--activity",
        help="Activity id/prefix/path. Default: cwd-walk-up. (D86)",
    ),
) -> None:
    """Create a new task. Default bucket: backlog. Empty body by default (D82)."""
    _create_task_impl(
        title=title, to_next=to_next, to_now=to_now,
        priority=priority, slug=slug,
        due=due, scheduled=scheduled, start_date=start_date, end_date=end_date,
        actor=actor, energy=energy, owner=owner, stage=stage,
        tag=tag, tags=tags, add_tag=add_tag, add_tags=add_tags,
        remove_tag=remove_tag, remove_tags=remove_tags, clear_tags=clear_tags,
        activity_token=activity,
    )


def _resolve_activity_root(activity_token: str | None) -> Path:
    """Return an activity root either from cwd-walk or from --activity token.

    D86: when activity_token is given, resolve via core/identify.py and return
    that activity's path; otherwise walk up from cwd. Errors are printed and
    raise typer.Exit on failure.
    """
    if activity_token is None:
        return _require_activity()
    from octopus.core.identify import (
        ActivityAmbiguous,
        ActivityNotFound,
        resolve_activity,
    )
    try:
        row = resolve_activity(activity_token)
    except ActivityAmbiguous as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc
    except ActivityNotFound as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc
    return Path(row["path"])


def _create_task_impl(
    *,
    title: str,
    to_next: bool,
    to_now: bool,
    priority: str | None,
    slug: str | None,
    due: str | None,
    scheduled: str | None,
    start_date: str | None,
    end_date: str | None,
    actor: str | None,
    energy: str | None,
    owner: str | None,
    stage: str | None,
    tag: list[str] | None,
    tags: list[str] | None,
    add_tag: list[str] | None,
    add_tags: list[str] | None,
    remove_tag: list[str] | None,
    remove_tags: list[str] | None,
    clear_tags: bool,
    activity_token: str | None,
) -> None:
    """Shared implementation for `capture` and `add task` (D85)."""
    from octopus.core.tag_parser import TagFlagConflict, TagFlagInputs, apply_tag_mutations

    if to_next and to_now:
        err_console.print("[red]✗[/] --next and --now are mutually exclusive")
        raise typer.Exit(EXIT_USER_ERROR)

    root = _resolve_activity_root(activity_token)
    octopus_dir = root / ".octopus"
    cfg = load_config(octopus_dir)
    storage_mode = read_storage_mode(octopus_dir)

    # D80: priority handling — explicit-default clears.
    if priority is not None:
        if _is_explicit_default("priority", priority):
            priority = None
        elif priority not in TASK_PRIORITIES:
            err_console.print(
                f"[red]✗[/] invalid priority {priority!r}; "
                f"valid: {sorted(TASK_PRIORITIES)} (or 'normal' to clear)"
            )
            raise typer.Exit(EXIT_USER_ERROR)

    # D80: actor handling — `human` clears.
    if actor is not None:
        if _is_explicit_default("actor", actor):
            actor = None
        elif actor not in {"ai", "automation"}:
            err_console.print(
                f"[red]✗[/] invalid actor {actor!r}; "
                "valid: human (default) | ai | automation"
            )
            raise typer.Exit(EXIT_USER_ERROR)

    # D80: energy handling.
    if energy is not None:
        if _is_explicit_default("energy", energy):
            energy = None
        elif energy not in {"low", "mid", "high"}:
            err_console.print(f"[red]✗[/] invalid energy {energy!r}; valid: low | mid | high")
            raise typer.Exit(EXIT_USER_ERROR)

    # Dates — explicit-default clears via _parse_iso_date.
    due_date = _parse_iso_date(due, "due") if due is not None else None
    scheduled_date = _parse_iso_date(scheduled, "scheduled") if scheduled is not None else None
    start_date_val = _parse_iso_date(start_date, "start-date") if start_date is not None else None
    end_date_val = _parse_iso_date(end_date, "end-date") if end_date is not None else None

    # Stage / owner — empty string clears.
    stage_val = None if (stage is None or _is_explicit_default("stage", stage)) else stage
    owner_val = None if (owner is None or _is_explicit_default("owner", owner)) else owner

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

    # D76: build the tag list from the flag matrix.
    tag_inputs = TagFlagInputs(
        replace=(tag or []) + (tags or []) if (tag or tags) else None,
        add=(add_tag or []) + (add_tags or []) if (add_tag or add_tags) else None,
        remove=(remove_tag or []) + (remove_tags or []) if (remove_tag or remove_tags) else None,
        clear=clear_tags,
    )
    try:
        final_tags = apply_tag_mutations([], tag_inputs)
    except TagFlagConflict as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc

    task = Task(
        title=title,
        created=date.today(),
        bucket=bucket,
        priority=priority,
        # D81: no auto-pin on --now. pinned stays orthogonal to bucket.
        pinned=None,
        due=due_date,
        scheduled=scheduled_date,
        start_date=start_date_val,
        end_date=end_date_val,
        actor=actor,
        energy=energy,
        owner=owner_val,
        stage=stage_val,
        tags=final_tags,
    )
    task.slug = final_slug
    task.path = task_path

    errors = task.validate()
    if errors:
        err_console.print("[red]✗[/] task validation failed:")
        for e in errors:
            err_console.print(f"  - {e}")
        raise typer.Exit(EXIT_USER_ERROR)

    # D82: empty body by default. No more hardcoded `## References`.
    body = ""
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


def _move_bucket(
    slug: str, new_bucket: str, *,
    set_pinned: bool | None = None,
    activity_token: str | None = None,
) -> None:
    root = _resolve_activity_root(activity_token)
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
    """Write task; in folder-mode and bucket changed, move file. Then upsert index.

    Used by lifecycle verbs (start/finish/drop) that DO want the file to move
    to match the new bucket. For frontmatter-only edits (D77), use
    `_save_task_in_place` instead.
    """
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


def _save_task_in_place(
    task: Task, body: str, current_path: Path, activity_root: Path,
) -> Path:
    """D77: write task in place — never move the file, even if bucket changed.

    The caller is responsible for emitting any soft warning about a
    bucket/folder mismatch.
    """
    write_task(current_path, task, body)
    task.path = current_path
    err = sync_task_after_write(activity_root, task)
    if err:
        err_console.print(f"[yellow]⚠[/] {err} (run `octopus reindex` to reconcile)")
    return current_path


_ACTIVITY_OPT_HELP = "Activity id/prefix/path. Default: cwd-walk-up. (D86)"


@app.command()
def plan(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Promote → bucket: next."""
    _move_bucket(slug, "next", activity_token=activity)


@app.command()
def focus(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Promote → bucket: now, pin."""
    _move_bucket(slug, "now", set_pinned=True, activity_token=activity)


@app.command()
def park(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Demote → bucket: backlog, unpin."""
    _move_bucket(slug, "backlog", set_pinned=False, activity_token=activity)


@app.command()
def defer(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Demote → bucket: next (keeps pinned)."""
    _move_bucket(slug, "next", activity_token=activity)


# ── lifecycle verbs ──────────────────────────────────────────────────


def _load_task(slug: str, activity_token: str | None = None) -> tuple[Path, Task, str, Path, str]:
    root = _resolve_activity_root(activity_token)
    octopus_dir = root / ".octopus"
    storage_mode = read_storage_mode(octopus_dir)
    task_path = _find_task_file(octopus_dir, storage_mode, slug)
    if task_path is None:
        err_console.print(f"[red]✗[/] task not found: {slug}")
        raise typer.Exit(EXIT_USER_ERROR)
    task, body = read_task(task_path)
    return task_path, task, body, octopus_dir, storage_mode


@app.command()
def start(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Mark work as begun. Idempotent. On done/dropped, resumes (bucket → now)."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
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
def finish(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Mark complete: bucket: done, end_date, clear pinned/issue/run_state."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
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
def end(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Alias for `finish`."""
    finish(slug, activity)


@app.command()
def drop(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Mark dropped: bucket: dropped, end_date, clear pinned/issue/run_state."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
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
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Flag an internal blocker."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
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
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Flag an external dependency."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
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
def unblock(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Clear any impediment."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
    task.issue = None
    task.blocked_by = None
    task.waiting_for = None
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} unblocked")


# ── attention verbs ───────────────────────────────────────────────────


@app.command()
def pin(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Mark for prominence (sorts to top of every list)."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
    if task.is_terminal():
        err_console.print(f"[red]✗[/] cannot pin terminal task ({task.bucket})")
        raise typer.Exit(EXIT_USER_ERROR)
    task.pinned = True
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} pinned")


@app.command()
def unpin(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Clear the pinned flag."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
    task.pinned = None
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} unpinned")


# ── visibility verbs ──────────────────────────────────────────────────


@app.command()
def archive(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Hide from default views."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
    task.archived = True
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} archived")


@app.command()
def restore(
    slug: str = typer.Argument(..., help="Task slug."),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Bring back from archive."""
    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity)
    task.archived = None
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} restored")


# ── move / mv (D77) ───────────────────────────────────────────────────


def _move_impl(slug: str, bucket: str, activity_token: str | None = None) -> None:
    """Shared body for `move` and `mv`. Pure file-move + frontmatter update.

    No date stamps, no lifecycle side effects (D77).
    """
    if bucket not in TASK_BUCKETS:
        err_console.print(f"[red]✗[/] invalid bucket {bucket!r}; valid: {sorted(TASK_BUCKETS)}")
        raise typer.Exit(EXIT_USER_ERROR)

    path, task, body, octopus_dir, storage_mode = _load_task(slug, activity_token)
    old_bucket = task.bucket
    task.bucket = bucket

    # Run validate() — if the user tries to mv to `done` without end_date,
    # the rule "bucket=done requires end_date" fires. Direct user there to
    # `finish` or `set --end-date` first.
    errors = task.validate()
    if errors:
        err_console.print(
            f"[red]✗[/] cannot mv {slug} to {bucket!r}:"
        )
        for e in errors:
            err_console.print(f"  - {e}")
        if bucket in {"done", "dropped"}:
            err_console.print(
                f"  [dim]tip: use `octopus finish {slug}` or `octopus drop {slug}` "
                "for the lifecycle path that sets dates automatically.[/]"
            )
        raise typer.Exit(EXIT_USER_ERROR)

    # _save_task already moves the file in folder mode (that's its old behavior).
    # Now that set uses _save_task_in_place, _save_task is dedicated to verbs
    # that DO want the file move — exactly what mv needs.
    _save_task(task, body, path, octopus_dir, storage_mode)
    console.print(f"[green]✓[/] {slug} moved {old_bucket} → {bucket}")


@app.command()
def move(
    slug: str = typer.Argument(..., help="Task slug."),
    bucket: str = typer.Argument(..., help=f"Target bucket: {sorted(TASK_BUCKETS)}"),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Move a task to a different bucket: updates frontmatter AND moves the file (folder mode).

    No date stamps, no lifecycle side effects. Use `start`/`finish`/`drop` for those.
    For frontmatter-only edits without moving the file, use `octopus set --bucket`.
    """
    _move_impl(slug, bucket, activity_token=activity)


@app.command()
def mv(
    slug: str = typer.Argument(..., help="Task slug."),
    bucket: str = typer.Argument(..., help=f"Target bucket: {sorted(TASK_BUCKETS)}"),
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Alias of `octopus move`."""
    _move_impl(slug, bucket, activity_token=activity)


# ── add task / add activity (D85) ────────────────────────────────────


add_app = typer.Typer(help="Add tasks or activities from anywhere.", no_args_is_help=True)
app.add_typer(add_app, name="add")


@add_app.command("task")
def add_task_cmd(
    title: str = typer.Argument(..., help="Task title."),
    to_next: bool = typer.Option(False, "--next", help="Create directly in `next`."),
    to_now: bool = typer.Option(False, "--now", help="Create directly in `now` (does NOT auto-pin, per D81)."),
    priority: str | None = typer.Option(
        None, "--priority",
        help=f"One of {sorted(TASK_PRIORITIES)} (or 'normal'/'none'/'' to clear)",
    ),
    slug: str | None = typer.Option(None, "--slug", help="Override the auto-slugified filename."),
    due: str | None = typer.Option(None, "--due", help="ISO date YYYY-MM-DD."),
    scheduled: str | None = typer.Option(None, "--scheduled", help="ISO date YYYY-MM-DD."),
    start_date: str | None = typer.Option(None, "--start-date", help="ISO date YYYY-MM-DD."),
    end_date: str | None = typer.Option(None, "--end-date", help="ISO date YYYY-MM-DD."),
    actor: str | None = typer.Option(None, "--actor", help="human (default) | ai | automation"),
    energy: str | None = typer.Option(None, "--energy", help="low | mid | high"),
    owner: str | None = typer.Option(None, "--owner", help="Free-form name/username."),
    stage: str | None = typer.Option(None, "--stage", help="Free-form per-activity workflow stage."),
    tag: list[str] | None = typer.Option(None, "--tag", help="Replace the tag list (alias of --tags)."),
    tags: list[str] | None = typer.Option(None, "--tags", help="Replace the tag list."),
    add_tag: list[str] | None = typer.Option(None, "--add-tag", help="Append to the tag list."),
    add_tags: list[str] | None = typer.Option(None, "--add-tags", help="Append to the tag list."),
    remove_tag: list[str] | None = typer.Option(None, "--remove-tag", help="Remove from the tag list."),
    remove_tags: list[str] | None = typer.Option(None, "--remove-tags", help="Remove from the tag list."),
    clear_tags: bool = typer.Option(False, "--clear-tags", help="Empty the tag list."),
    activity: str | None = typer.Option(
        None, "--activity",
        help="Activity id/prefix/path. Default: cwd-walk-up. (D85/D86)",
    ),
) -> None:
    """Create a new task. The "from anywhere" sibling of `capture` (D85).

    Identical behavior to `capture` when called from inside an activity with
    no --activity flag. Pass --activity <id> to target a specific activity
    by id, unambiguous prefix, or path — no `cd` required.
    """
    _create_task_impl(
        title=title, to_next=to_next, to_now=to_now,
        priority=priority, slug=slug,
        due=due, scheduled=scheduled, start_date=start_date, end_date=end_date,
        actor=actor, energy=energy, owner=owner, stage=stage,
        tag=tag, tags=tags, add_tag=add_tag, add_tags=add_tags,
        remove_tag=remove_tag, remove_tags=remove_tags, clear_tags=clear_tags,
        activity_token=activity,
    )


@add_app.command("activity")
def add_activity_cmd(
    name: str = typer.Argument(..., help="Activity name (used as the folder name when --path omitted)."),
    activity_type: str = typer.Option("other", "--type", help=f"One of {sorted(ACTIVITY_TYPES)}"),
    status: str = typer.Option("active", "--status", help=f"One of {sorted(ACTIVITY_STATUSES)}"),
    area: str | None = typer.Option(None, "--area", help="Free-form area tag."),
    custom_id: str | None = typer.Option(None, "--id", help="Override the auto-derived activity id."),
    storage_mode: str = typer.Option("folders", "--storage", help="Storage mode: folders | fields."),
    path: str | None = typer.Option(
        None, "--path",
        help="Directory to initialize. Created if missing. Default: cwd/<slug-of-name>.",
    ),
    priority: str | None = typer.Option(
        None, "--priority",
        help="Activity priority: low|high|urgent (D87). Omit for normal.",
    ),
) -> None:
    """Create a new activity. The "from anywhere" sibling of `init` (D85).

    Without --path: creates a slug-of-<name> folder under cwd. With --path:
    initializes that directory (creating it if missing).
    """
    if priority is not None:
        if _is_explicit_default("priority", priority):
            priority = None
        elif priority not in {"low", "high", "urgent"}:
            err_console.print(
                f"[red]✗[/] --priority: {priority!r} not in low|high|urgent "
                "(D87; omit or pass 'normal' for the default)"
            )
            raise typer.Exit(EXIT_USER_ERROR)

    # Resolve the target directory.
    if path is not None:
        target = Path(path).expanduser().resolve()
    else:
        try:
            folder_slug = slugify(name)
        except ValueError as exc:
            err_console.print(f"[red]✗[/] cannot slugify name {name!r}: {exc}")
            raise typer.Exit(EXIT_USER_ERROR) from exc
        target = (Path.cwd() / folder_slug).resolve()

    # Guard against nested or duplicate activities.
    existing = find_activity_root(target if target.exists() else target.parent)
    if existing is not None and existing == target:
        err_console.print(f"[red]✗[/] already an activity: {existing}")
        raise typer.Exit(EXIT_USER_ERROR)
    if existing is not None and existing != target:
        err_console.print(
            f"[red]✗[/] nested activities not allowed. Existing activity at: {existing}"
        )
        raise typer.Exit(EXIT_USER_ERROR)

    target.mkdir(parents=True, exist_ok=True)

    try:
        activity = init_activity(
            target, title=name, activity_type=activity_type, status=status,
            area=area, priority=priority, custom_id=custom_id, storage_mode=storage_mode,
        )
    except (ActivityExistsError, ValueError) as e:
        err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(EXIT_USER_ERROR) from e

    err = sync_activity_after_write(target)
    if err:
        err_console.print(f"[yellow]⚠[/] {err} (run `octopus reindex` to reconcile)")

    short = short_form(activity.id)
    console.print(f"[green]✓[/] Initialized activity [bold]{short}[/] at {target}")
    if storage_mode == "folders":
        console.print(f"  storage mode: folders ({', '.join(sorted(BUCKET_FOLDERS))})")
    else:
        console.print(f"  storage mode: {storage_mode}")


# ── forget activity (D83) ────────────────────────────────────────────


forget_app = typer.Typer(help="Forget (untrack) an activity from the index.")
app.add_typer(forget_app, name="forget")


@forget_app.command("activity")
def forget_activity_cmd(
    target: str = typer.Argument(..., help="Activity path, ID, or unambiguous ID prefix."),
    archive: bool = typer.Option(
        False, "--archive", "--also-archive",
        help="Also move the activity folder to <parent>/_archive/<name>/.",
    ),
    yes: bool = typer.Option(False, "-y", help="Skip the interactive prompt."),
) -> None:
    """Remove an activity from the SQLite index.

    Files on disk are NOT touched by default. Pass --archive to also move
    the folder to <parent>/_archive/<name>/.

    Resolution (D83):
      - Token starting with `/`, `~`, or containing `/` → filesystem path.
      - Otherwise → activity ID (exact match or unambiguous prefix).
    """
    from octopus.actions import ActionError, forget_activity
    from octopus.core.identify import (
        ActivityAmbiguous,
        ActivityNotFound,
        resolve_activity,
    )

    try:
        activity = resolve_activity(target)
    except ActivityNotFound as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc
    except ActivityAmbiguous as exc:
        err_console.print(f"[red]✗[/] {exc}")
        err_console.print("    Pass a more specific prefix or the full id.")
        raise typer.Exit(EXIT_USER_ERROR) from exc

    activity_path = Path(activity["path"])

    # Decide archive intent.
    # - --archive (with or without -y) → archive
    # - -y alone → skip prompt, do NOT archive (the conservative default)
    # - neither flag → prompt interactively
    will_archive: bool
    if archive:
        will_archive = True
    elif yes:
        # `-y` skips the prompt; the prompt's default was "no archive"
        # so `-y` alone also means "no archive". For explicit archive,
        # combine: `--archive -y`.
        will_archive = False
    else:
        console.print(
            f"\nForget activity [bold cyan]{activity['id']}[/]?"
            f"\n  Path:  {activity_path}"
            f"\n  Files on disk will not be touched."
        )
        console.print(
            "\n  [dim]To skip this prompt next time:"
            f"\n    octopus forget activity {target} -y           # forget without archiving"
            f"\n    octopus forget activity {target} --archive -y # also archive[/]"
        )
        if typer.confirm("\nAlso archive files to _archive/?", default=False):
            will_archive = True
        else:
            will_archive = False

    try:
        result = forget_activity(activity, archive_files=will_archive)
    except ActionError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc

    console.print(
        f"[green]✓[/] forgot activity [bold]{result.activity_id}[/]"
    )
    counts = result.rows_removed
    console.print(
        f"  removed {counts['activities']} activity row · "
        f"{counts['tasks']} tasks · "
        f"{counts['sessions']} sessions · "
        f"{counts['task_external_refs']} external refs"
    )
    if result.archived and result.archive_destination is not None:
        console.print(f"  files archived → [dim]{result.archive_destination}[/]")
    else:
        console.print(f"  files left at [dim]{activity_path}[/] (untouched)")


# ── refs find (D79) ───────────────────────────────────────────────────


refs_app = typer.Typer(help="Find or rewrite cross-references to a slug.")
app.add_typer(refs_app, name="refs")


@refs_app.command("find")
def refs_find(
    slug: str = typer.Argument(..., help="The slug to search for."),
    cross_activity: bool = typer.Option(
        False, "--all", help="Search across every indexed activity, not just cwd's.",
    ),
) -> None:
    """Find references to a slug across Octopus-managed files (read-only).

    Prints `category | file:line | line` rows. Managed files (tasks,
    spectacular PLAN.md, TODO.md) come first; user-prose files (sessions,
    memory, handoffs) come after a separator.
    """
    from octopus.core.refs import categorize_hits, find_refs

    activities: list[Path]
    if cross_activity:
        # Walk every indexed activity.
        conn = get_db()
        try:
            rows = conn.execute("SELECT path FROM activities").fetchall()
        finally:
            conn.close()
        activities = [Path(r["path"]) for r in rows]
        if not activities:
            console.print(EMPTY_INDEX_HINT)
            return
    else:
        root = _require_activity()
        activities = [root]

    total_hits: list = []
    for act in activities:
        hits = find_refs(act, slug)
        total_hits.extend(hits)

    if not total_hits:
        console.print(f"[dim]no references to {slug!r} found.[/]")
        return

    managed, warn = categorize_hits(total_hits)

    if managed:
        console.print(f"\n[bold]Octopus-managed references[/] ({len(managed)}):")
        for h in managed:
            rel = _try_relative(h.file, activities)
            console.print(
                f"  [cyan]{h.category:12}[/] {rel}:{h.line_number}    [dim]{h.line.strip()[:100]}[/]"
            )
    if warn:
        console.print(f"\n[bold yellow]User-prose mentions[/] ({len(warn)}):")
        for h in warn:
            rel = _try_relative(h.file, activities)
            console.print(
                f"  [yellow]{h.category:12}[/] {rel}:{h.line_number}    [dim]{h.line.strip()[:100]}[/]"
            )
    console.print()


def _try_relative(p: Path, roots: list[Path]) -> str:
    """Return p relative to the first root it lives under; else the absolute path."""
    for r in roots:
        try:
            return str(p.relative_to(r))
        except ValueError:
            continue
    return str(p)


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
    activity: str | None = typer.Option(None, "--activity", help=_ACTIVITY_OPT_HELP),
) -> None:
    """Promote one or more tasks to a Spectacular request (or other target).

    One-way; pure rewrite. Task body becomes a stub pointer to the PLAN.md.
    See D47–D51 in DECISIONS.md and references/cli-verbs.md for the full
    semantics.
    """
    from octopus.actions import ActionError, promote_task

    activity_root = _resolve_activity_root(activity)
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


# ── bridge verbs (D56-D66) ────────────────────────────────────────────


bridge_app = typer.Typer(
    help="Manage adapters (Obsidian, Apple Reminders, TODO.md, future bridges)."
)
app.add_typer(bridge_app, name="bridge")
# Hidden alias per D57 — same Typer app under a second name.
app.add_typer(bridge_app, name="adapter", hidden=True)


@bridge_app.command("list")
def bridge_list(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Show all registered adapters with enabled status + health."""
    from octopus.adapters.registry import load_registry
    from octopus.config import is_adapter_enabled

    registry = load_registry()
    if not registry:
        console.print("[dim]no adapters registered[/]")
        return

    if not verbose:
        table = Table(show_edge=False)
        table.add_column("NAME", style="cyan")
        table.add_column("ENABLED", justify="center")
        table.add_column("CAPABILITIES", style="dim")
        table.add_column("STATUS")
        for name, cls in sorted(registry.items()):
            adapter = cls()
            status = adapter.status()
            enabled = "●" if is_adapter_enabled(name) else "○"
            caps = ", ".join(sorted(c.value for c in adapter.capabilities))
            status_str = "[green]healthy[/]" if status.healthy else f"[red]{status.error or 'unhealthy'}[/]"
            table.add_row(name, enabled, caps, status_str)
        console.print(table)
        return

    # Verbose: per-adapter block
    for name, cls in sorted(registry.items()):
        adapter = cls()
        status = adapter.status()
        enabled = is_adapter_enabled(name)
        console.print(f"\n[bold cyan]{name}[/]  ({'enabled' if enabled else 'disabled'})")
        console.print(f"  capabilities: {', '.join(sorted(c.value for c in adapter.capabilities))}")
        health_str = (
            "[green]✓[/] healthy" if status.healthy
            else f"[red]✗[/] {status.error or 'unhealthy'}"
        )
        console.print(f"  health: {health_str}")
        if status.last_pull:
            console.print(f"  last pull: {status.last_pull.isoformat(timespec='seconds')}")
        if status.last_push:
            console.print(f"  last push: {status.last_push.isoformat(timespec='seconds')}")


@bridge_app.command("enable")
def bridge_enable(
    name: str = typer.Argument(..., help="Adapter name (obsidian / reminders / todo-md)."),
    set_: list[str] | None = typer.Option(
        None, "--set",
        help="Set a config key. Format: key=value. Repeatable. v1 generic; per-adapter sub-apps will replace this in #07/#09/#21.",
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Skip the adapter's validate_config() check. Use for stubs or "
             "to enable an adapter that's temporarily unhealthy.",
    ),
) -> None:
    """Enable an adapter — flips main config + writes bridges/<name>.toml.

    Adapter's validate_config() runs first; rejection aborts unless --force.
    """
    from octopus.adapters.registry import get_adapter_class
    from octopus.config import (
        load_adapter_config,
        set_adapter_enabled,
        write_adapter_config,
    )

    cls = get_adapter_class(name)
    if cls is None:
        err_console.print(f"[red]✗[/] unknown adapter {name!r}")
        raise typer.Exit(EXIT_USER_ERROR)

    # Merge --set flags into existing bridge config.
    data = load_adapter_config(name)
    if set_:
        for entry in set_:
            if "=" not in entry:
                err_console.print(f"[red]✗[/] --set value must be key=value: {entry!r}")
                raise typer.Exit(EXIT_USER_ERROR)
            k, v = entry.split("=", 1)
            k = k.strip()
            data[k] = _parse_set_value(v.strip(), key=k)

    adapter = cls()
    errors = adapter.validate_config(data)
    if errors and not force:
        err_console.print(f"[red]✗[/] {name} validation failed:")
        for e in errors:
            err_console.print(f"    - {e}")
        err_console.print("    (use --force to enable anyway)")
        raise typer.Exit(EXIT_CONFIG_ERROR)
    if errors and force:
        for e in errors:
            err_console.print(f"[yellow]⚠[/] {e}")

    write_adapter_config(name, data)
    set_adapter_enabled(name, True)
    console.print(f"[green]✓[/] {name} enabled")


@bridge_app.command("disable")
def bridge_disable(
    name: str = typer.Argument(..., help="Adapter name."),
) -> None:
    """Disable an adapter — flips main config. bridges/<name>.toml is KEPT."""
    from octopus.adapters.registry import get_adapter_class
    from octopus.config import set_adapter_enabled

    if get_adapter_class(name) is None:
        # Per D66, unknown name → idempotent ignore on disable.
        console.print(f"[dim]{name!r} not registered; nothing to disable[/]")
        return
    set_adapter_enabled(name, False)
    console.print(f"[green]✓[/] {name} disabled (settings preserved)")


@bridge_app.command("status")
def bridge_status(
    name: str | None = typer.Argument(None, help="Adapter name (omit for all)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Health check. No name = table of all. With name = per-adapter block."""
    from octopus.adapters.registry import get_adapter_class, registered_names
    from octopus.config import is_adapter_enabled

    if name is None:
        # Reuse the verbose `list` path
        bridge_list(verbose=verbose)
        return

    cls = get_adapter_class(name)
    if cls is None:
        err_console.print(f"[red]✗[/] unknown adapter {name!r}; registered: {registered_names()}")
        raise typer.Exit(EXIT_USER_ERROR)

    adapter = cls()
    status = adapter.status()
    enabled = is_adapter_enabled(name)
    console.print(f"\n[bold cyan]{name}[/]  ({'enabled' if enabled else 'disabled'})")
    console.print(f"  capabilities: {', '.join(sorted(c.value for c in adapter.capabilities))}")
    health_str = (
        "[green]✓[/] healthy" if status.healthy
        else f"[red]✗[/] {status.error or 'unhealthy'}"
    )
    console.print(f"  health: {health_str}")
    if status.last_pull:
        console.print(f"  last pull: {status.last_pull.isoformat(timespec='seconds')}")
    if status.last_push:
        console.print(f"  last push: {status.last_push.isoformat(timespec='seconds')}")


@bridge_app.command("peek")
def bridge_peek(
    name: str = typer.Argument(..., help="Adapter name."),
    list_: str | None = typer.Option(None, "--list", help="Group name(s), comma-separated."),
    capture_all: bool = typer.Option(False, "--capture-all", help="Pull from every available group."),
) -> None:
    """READ-ONLY display of what the adapter sees. No files created."""
    _bridge_read_verb(name, list_, capture_all, verb="peek")


@bridge_app.command("pull")
def bridge_pull(
    name: str = typer.Argument(..., help="Adapter name."),
    list_: str | None = typer.Option(None, "--list", help="Group name(s), comma-separated."),
    capture_all: bool = typer.Option(False, "--capture-all", help="Pull from every available group."),
) -> None:
    """Import external items as Octopus tasks. Deduped via task_external_refs."""
    _bridge_read_verb(name, list_, capture_all, verb="pull")


@bridge_app.command("search")
def bridge_search(
    name: str = typer.Argument(..., help="Adapter name."),
    query: str = typer.Argument(..., help="Search query (adapter-interpreted)."),
    list_: str | None = typer.Option(None, "--list"),
    capture_all: bool = typer.Option(False, "--capture-all"),
) -> None:
    """Adapter-side search. No imports."""
    _bridge_read_verb(name, list_, capture_all, verb="search", query=query)


# ── D75: limited mutation verbs ───────────────────────────────────────


@bridge_app.command("add")
def bridge_add(
    name: str = typer.Argument(..., help="Adapter name."),
    title: str = typer.Argument(..., help="The task title."),
    priority: str | None = typer.Option(
        None, "--priority", help="urgent | low (encoded as Obsidian Tasks emoji)."
    ),
    due: str | None = typer.Option(
        None, "--due", help="ISO date YYYY-MM-DD (encoded as 📅)."
    ),
    tag: list[str] | None = typer.Option(
        None, "--tag", help="Repeatable. Tags appended as #tag.", show_default=False,
    ),
    section: str | None = typer.Option(
        None, "--section", help="Heading slug to append under. Defaults to first section_filter entry.",
    ),
    state: str = typer.Option(
        "open", "--state", help="open | in-progress (marker: [ ] or [/])."
    ),
) -> None:
    """Append a new item to the adapter's source. No import to the task tree.

    Adapter must declare MARK_PULLED capability.
    """
    from octopus.adapters.base import Capability
    from octopus.adapters.registry import get_adapter_class

    cls = get_adapter_class(name)
    if cls is None:
        err_console.print(f"[red]✗[/] unknown adapter {name!r}")
        raise typer.Exit(EXIT_USER_ERROR)
    adapter = cls()
    if Capability.MARK_PULLED not in adapter.capabilities:
        err_console.print(
            f"[red]✗[/] {name} does not support mutation verbs "
            f"(missing MARK_PULLED capability)"
        )
        raise typer.Exit(EXIT_USER_ERROR)
    if state not in ("open", "in-progress"):
        err_console.print("[red]✗[/] --state must be 'open' or 'in-progress'")
        raise typer.Exit(EXIT_USER_ERROR)
    if priority is not None and priority not in ("urgent", "low"):
        err_console.print("[red]✗[/] --priority must be 'urgent' or 'low'")
        raise typer.Exit(EXIT_USER_ERROR)

    try:
        msg = adapter.add_item(
            title,
            section=section,
            priority=priority,
            due=due,
            tags=list(tag or []),
            state=state,
        )
    except (ValueError, FileNotFoundError) as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc
    console.print(f"[green]✓[/] {msg}")


@bridge_app.command("complete")
def bridge_complete(
    name: str = typer.Argument(..., help="Adapter name."),
    match: str = typer.Argument(..., help="Substring match against open items."),
    first: bool = typer.Option(False, "--first", help="Pick the top hit if multiple match."),
) -> None:
    """Toggle a matching open item to checked, in place. No import."""
    _bridge_toggle(name, match, target="complete", first=first)


@bridge_app.command("uncomplete")
def bridge_uncomplete(
    name: str = typer.Argument(..., help="Adapter name."),
    match: str = typer.Argument(..., help="Substring match against checked items."),
    first: bool = typer.Option(False, "--first"),
) -> None:
    """Toggle a matching checked item back to open. Strips any `→` arrow."""
    _bridge_toggle(name, match, target="open", first=first)


def _bridge_toggle(name: str, match: str, *, target: str, first: bool) -> None:
    from octopus.adapters.base import Capability
    from octopus.adapters.registry import get_adapter_class

    cls = get_adapter_class(name)
    if cls is None:
        err_console.print(f"[red]✗[/] unknown adapter {name!r}")
        raise typer.Exit(EXIT_USER_ERROR)
    adapter = cls()
    if Capability.MARK_PULLED not in adapter.capabilities:
        err_console.print(f"[red]✗[/] {name} does not support mutation verbs")
        raise typer.Exit(EXIT_USER_ERROR)

    try:
        if target == "complete":
            msg = adapter.mark_complete(match, first=first)
        else:
            msg = adapter.mark_open(match, first=first)
    except (ValueError, FileNotFoundError) as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc
    console.print(f"[green]✓[/] {msg}")


def _bridge_read_verb(
    name: str,
    flag_list: str | None,
    flag_capture_all: bool,
    *,
    verb: str,
    query: str | None = None,
) -> None:
    """Shared body for peek/pull/search. Handles capability + flag + dispatch."""
    from octopus.adapters.base import Capability
    from octopus.adapters.pipeline import (
        PipelineError,
        materialize_pull_result,
        resolve_groups,
        resolve_target_activity,
    )
    from octopus.adapters.registry import get_adapter_class
    from octopus.config import is_adapter_enabled, load_adapter_config

    cls = get_adapter_class(name)
    if cls is None:
        err_console.print(f"[red]✗[/] unknown adapter {name!r}")
        raise typer.Exit(EXIT_USER_ERROR)

    if not is_adapter_enabled(name):
        err_console.print(
            f"[red]✗[/] {name} is disabled — `octopus bridge enable {name}` first"
        )
        raise typer.Exit(EXIT_CONFIG_ERROR)

    adapter = cls()

    # All three verbs require PULL capability.
    if Capability.PULL not in adapter.capabilities:
        err_console.print(f"[red]✗[/] {name} does not declare PULL capability")
        raise typer.Exit(EXIT_USER_ERROR)

    # Resolve groups per D59 flag matrix.
    bridge_cfg = load_adapter_config(name)
    configured = bridge_cfg.get("lists") if isinstance(bridge_cfg.get("lists"), list) else None
    # Probe once so resolve_groups knows whether the adapter has groups at all.
    available_groups = adapter.list_groups()
    has_groups = bool(available_groups)
    try:
        groups = resolve_groups(
            configured_lists=configured,
            flag_list=flag_list,
            flag_capture_all=flag_capture_all,
            adapter_list_groups=available_groups if flag_capture_all else None,
            adapter_has_groups=has_groups,
            verb=verb,
        )
    except PipelineError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(exc.exit_code) from exc

    # groups=None means either (a) multi-group adapter, peek-discovery, or
    # (b) single-source adapter — fall through. D60.
    if groups is None and has_groups and verb == "peek":
        console.print(
            f"\nno default list configured. Available groups for [cyan]{name}[/]:"
        )
        for g in available_groups:
            console.print(f"  - {g}")
        console.print(
            "\nSpecify --list <name> to peek into one, or --capture-all for every group."
        )
        return

    # Run the adapter call.
    try:
        if verb == "peek":
            result = adapter.peek(groups=groups)
        elif verb == "pull":
            result = adapter.pull(groups=groups)
        elif verb == "search":
            result = adapter.search(query or "", groups=groups)
        else:
            err_console.print(f"[red]✗[/] unknown verb {verb!r}")
            raise typer.Exit(EXIT_USER_ERROR)
    except Exception as exc:
        err_console.print(f"[red]✗[/] {name} {verb} raised: {exc}")
        raise typer.Exit(4) from exc

    # Surface adapter errors (e.g. stubs return errors without raising).
    if result.errors and not result.tasks:
        for e in result.errors:
            err_console.print(f"[red]✗[/] {e}")
        raise typer.Exit(4)

    # peek/search: display only.
    if verb in ("peek", "search"):
        if not result.tasks:
            console.print("[dim]no items[/]")
            for e in result.errors:
                err_console.print(f"[yellow]⚠[/] {e}")
            return
        console.print(
            f"\n[cyan]{name}[/] {verb} — {len(result.tasks)} item(s) from {groups or 'configured'}"
        )
        for et in result.tasks:
            console.print(f"  ▢ {et.title}   [dim]({et.external_id})[/]")
        for e in result.errors:
            err_console.print(f"[yellow]⚠[/] {e}")
        return

    # pull: materialize.
    try:
        activity_root = resolve_target_activity(
            config_default=bridge_cfg.get("default_activity") or None,
            cwd_activity=find_activity_root(Path.cwd()),
        )
    except PipelineError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(exc.exit_code) from exc

    mr = materialize_pull_result(activity_root, name, result)
    msg = f"pulled {mr.new_count} new · {mr.skipped_count} already-known · {mr.error_count} errors"
    if mr.source_groups:
        msg += f"  (from {', '.join(mr.source_groups)})"
    if mr.new_count > 0:
        console.print(f"[green]✓[/] {msg}")
    elif mr.error_count > 0 and mr.skipped_count == 0:
        err_console.print(f"[red]✗[/] {msg}")
        for e in mr.errors:
            err_console.print(f"    - {e}")
        raise typer.Exit(4)
    else:
        console.print(msg)
    for s in mr.new_slugs:
        console.print(f"  + {s}")


def _parse_set_value(v: str, key: str | None = None):
    """Coerce a `--set key=value` value to bool/int/list/str.

    Heuristic: keys named `lists` or ending in `_list` are ALWAYS lists,
    even for a single value (so `--set lists=Inbox` becomes `["Inbox"]`).
    Other keys: comma-separated → list; "true"/"false" → bool; digits → int.
    """
    low = v.lower()
    if key and (key == "lists" or key.endswith("_lists") or key.endswith("_list")):
        return [s.strip() for s in v.split(",") if s.strip()]
    if low == "true":
        return True
    if low == "false":
        return False
    if "," in v:
        return [s.strip() for s in v.split(",") if s.strip()]
    try:
        return int(v)
    except ValueError:
        return v


# ── views ─────────────────────────────────────────────────────────────


# NOTE: `loops` is defined later as an index-backed command (loops_cmd).


# ── set verb ──────────────────────────────────────────────────────────


VERB_OVERLAP_FIELDS = {
    "bucket": "octopus plan / focus / park / defer / finish / drop",
    "pinned": "octopus pin / unpin",
    "issue": "octopus block / wait / unblock",
    "archived": "octopus archive / restore",
}


def _handle_slug_rename(
    *,
    activity_root: Path,
    source_file: Path,
    old_slug: str,
    new_slug: str,
    yes: bool,
) -> None:
    """D78: full cascading slug rename. Builds preview, prompts, applies."""
    from octopus.core.slug_rename import (
        SlugRenameError,
        apply_rewrite_plan,
        scan_rewrite_plan,
    )

    try:
        plan = scan_rewrite_plan(activity_root, source_file, old_slug, new_slug)
    except SlugRenameError as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc

    # Build the preview output.
    console.print("\n[bold]Rename slug:[/]")
    console.print(f"  {old_slug}  →  {new_slug}")
    console.print("\n[bold]Octopus-managed refs to update automatically:[/]")
    # Group actions by category for the preview.
    by_cat: dict[str, list] = {}
    for a in plan.actions:
        by_cat.setdefault(a.category, []).append(a)
    if not by_cat:
        console.print("  [dim](none)[/]")
    else:
        for cat, items in by_cat.items():
            console.print(f"  [cyan]{cat}[/] ({len(items)}):")
            for a in items[:6]:
                console.print(f"    {a.description}")
            if len(items) > 6:
                console.print(f"    [dim]…and {len(items) - 6} more[/]")

    if plan.soft_warnings:
        console.print("\n[bold yellow]Soft warnings (user-managed, not touched):[/]")
        for w in plan.soft_warnings:
            console.print(f"  [yellow]{w.category}[/] {w.description}")
        console.print(
            "  [dim]External tools (Obsidian backlinks, IDE bookmarks, git history) "
            "not touched.[/]"
        )
        console.print(
            f"  [dim]Run `octopus refs find {new_slug}` after the rename to locate "
            "residual references.[/]"
        )

    if not yes and not typer.confirm("\nProceed?", default=False):
        console.print("[dim]aborted[/]")
        raise typer.Exit(EXIT_OK)

    # Apply rewrites.
    try:
        apply_rewrite_plan(plan)
    except Exception as exc:
        err_console.print(f"[red]✗[/] slug rename failed mid-cascade: {exc}")
        err_console.print(
            "[yellow]⚠[/] some changes may have been applied. "
            "Run `octopus reindex` to reconcile."
        )
        raise typer.Exit(4) from exc

    # Update the SQLite index — the renamed task file needs a new row, the
    # old row needs to go. sync_task_after_write handles upsert of the new
    # path; sync_delete_task drops the old.
    sync_delete_task(plan.source_file)
    # Read the new task to upsert it under its new path.
    try:
        new_task, _new_body = read_task(plan.target_file)
        new_task.slug = new_slug
        new_task.path = plan.target_file
        err = sync_task_after_write(activity_root, new_task)
        if err:
            err_console.print(f"[yellow]⚠[/] {err} (run `octopus reindex` to reconcile)")
    except Exception as exc:
        err_console.print(
            f"[yellow]⚠[/] file renamed but index sync failed: {exc}. "
            "Run `octopus reindex` to reconcile."
        )

    console.print(f"[green]✓[/] {old_slug} → {new_slug} (cascade applied)")


def _set_task_one(
    slug: str,
    activity_root: Path,
    *,
    bucket: str | None,
    stage: str | None,
    run_state: str | None,
    pinned: bool | None,
    issue: str | None,
    blocked_by: str | None,
    waiting_for: str | None,
    archived: bool | None,
    due: str | None,
    scheduled: str | None,
    start_date: str | None,
    end_date: str | None,
    priority: str | None,
    energy: str | None,
    actor: str | None,
    owner: str | None,
    kind: str | None,
    title: str | None,
    new_slug: str | None,
    yes: bool,
    tag: list[str] | None,
    tags: list[str] | None,
    add_tag: list[str] | None,
    add_tags: list[str] | None,
    remove_tag: list[str] | None,
    remove_tags: list[str] | None,
    clear_tags: bool,
) -> bool:
    """Apply a frontmatter-only edit to one task in one activity. Returns True on success.

    Errors print to stderr and return False (caller decides whether to continue).
    """

    octopus_dir = activity_root / ".octopus"
    storage_mode = read_storage_mode(octopus_dir)
    path = _find_task_file(octopus_dir, storage_mode, slug)
    if path is None:
        err_console.print(f"[red]✗[/] task not found: {slug}")
        return False
    task, body = read_task(path)

    # D78: handle --slug rename BEFORE other edits.
    if new_slug is not None:
        _handle_slug_rename(
            activity_root=activity_root,
            source_file=path,
            old_slug=slug,
            new_slug=new_slug,
            yes=yes,
        )
        slug = new_slug
        path = _find_task_file(octopus_dir, storage_mode, slug)
        if path is None:
            err_console.print(f"[red]✗[/] task not found after rename: {slug}")
            return False
        task, body = read_task(path)

    overlaps_used: list[str] = []
    bucket_changed_to: str | None = None
    return _apply_set_task_fields(
        task, body, path, activity_root, octopus_dir, storage_mode,
        slug=slug,
        bucket=bucket, stage=stage, run_state=run_state, pinned=pinned,
        issue=issue, blocked_by=blocked_by, waiting_for=waiting_for, archived=archived,
        due=due, scheduled=scheduled, start_date=start_date, end_date=end_date,
        priority=priority, energy=energy, actor=actor, owner=owner, kind=kind,
        title=title,
        tag=tag, tags=tags, add_tag=add_tag, add_tags=add_tags,
        remove_tag=remove_tag, remove_tags=remove_tags, clear_tags=clear_tags,
        overlaps_used=overlaps_used, bucket_changed_to=bucket_changed_to,
    )


def _apply_set_task_fields(
    task, body, path, activity_root, octopus_dir, storage_mode,
    *, slug, bucket, stage, run_state, pinned, issue, blocked_by, waiting_for,
    archived, due, scheduled, start_date, end_date, priority, energy, actor,
    owner, kind, title, tag, tags, add_tag, add_tags, remove_tag, remove_tags,
    clear_tags, overlaps_used, bucket_changed_to,
) -> bool:
    from octopus.core.tag_parser import TagFlagConflict, TagFlagInputs, apply_tag_mutations

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
        # D77: track that bucket changed for the post-save warning.
        if task.bucket != bucket:
            bucket_changed_to = bucket
        task.bucket = bucket
    if stage is not None:
        task.stage = None if _is_explicit_default("stage", stage) else stage
    if run_state is not None:
        if _is_explicit_default("run_state", run_state):
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
        if _is_explicit_default("issue", issue):
            task.issue = None
        elif issue not in {"blocked", "waiting"}:
            err_console.print(f"[red]✗[/] --issue: {issue!r} not in [blocked, waiting]")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.issue = issue
    if blocked_by is not None:
        task.blocked_by = None if _is_explicit_default("blocked_by", blocked_by) else blocked_by
    if waiting_for is not None:
        task.waiting_for = None if _is_explicit_default("waiting_for", waiting_for) else waiting_for
    if archived is not None:
        overlaps_used.append("archived")
        task.archived = True if archived else None
    if due is not None:
        task.due = _parse_iso_date(due, "due")
    if scheduled is not None:
        task.scheduled = _parse_iso_date(scheduled, "scheduled")
    if start_date is not None:
        task.start_date = _parse_iso_date(start_date, "start-date")
    if end_date is not None:
        task.end_date = _parse_iso_date(end_date, "end-date")
    if priority is not None:
        if _is_explicit_default("priority", priority):
            task.priority = None
        elif priority not in TASK_PRIORITIES:
            err_console.print(f"[red]✗[/] --priority: {priority!r} not in {sorted(TASK_PRIORITIES)} (or 'normal' to clear)")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.priority = priority
    if energy is not None:
        if _is_explicit_default("energy", energy):
            task.energy = None
        elif energy not in {"low", "mid", "high"}:
            err_console.print(f"[red]✗[/] --energy: {energy!r} not in [low, mid, high] (or 'normal' to clear)")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.energy = energy
    if actor is not None:
        if _is_explicit_default("actor", actor):
            task.actor = None
        elif actor not in {"ai", "automation"}:
            err_console.print(f"[red]✗[/] --actor: {actor!r} not in [human (default), ai, automation]")
            raise typer.Exit(EXIT_USER_ERROR)
        else:
            task.actor = actor
    if owner is not None:
        task.owner = None if _is_explicit_default("owner", owner) else owner
    if kind is not None:
        task.kind = None if _is_explicit_default("kind", kind) else kind

    # D76: tag flag matrix
    tag_inputs = TagFlagInputs(
        replace=(tag or []) + (tags or []) if (tag or tags) else None,
        add=(add_tag or []) + (add_tags or []) if (add_tag or add_tags) else None,
        remove=(remove_tag or []) + (remove_tags or []) if (remove_tag or remove_tags) else None,
        clear=clear_tags,
    )
    if any([tag_inputs.replace, tag_inputs.add, tag_inputs.remove, tag_inputs.clear]):
        try:
            task.tags = apply_tag_mutations(task.tags, tag_inputs)
        except TagFlagConflict as exc:
            err_console.print(f"[red]✗[/] {exc}")
            raise typer.Exit(EXIT_USER_ERROR) from exc

    errors = task.validate()
    if errors:
        err_console.print("[red]✗[/] validation failed:")
        for e in errors:
            err_console.print(f"  - {e}")
        raise typer.Exit(EXIT_USER_ERROR)

    for smell in task.smells():
        err_console.print(f"[yellow]⚠[/] {smell}")

    # D77: set is frontmatter-only — write in place, do NOT move the file.
    _save_task_in_place(task, body, path, octopus_dir.parent)

    # D77 soft warning: if --bucket changed in folder mode and the file's
    # parent directory no longer matches, point at `octopus mv`.
    if (
        bucket_changed_to is not None
        and storage_mode == "folders"
        and path.parent.name != bucket_changed_to
    ):
        err_console.print(
            f"[yellow]⚠[/] task at {path.relative_to(octopus_dir.parent)} now has "
            f"bucket: {bucket_changed_to}.\n"
            f"  Run `octopus mv {slug} {bucket_changed_to}` to move the file to match."
        )

    for field_name in overlaps_used:
        tip = VERB_OVERLAP_FIELDS.get(field_name)
        if tip:
            err_console.print(f"[dim]tip: dedicated verb available for --{field_name}: {tip}[/]")

    console.print(f"[green]✓[/] {slug} updated")
    return True


# ── activity-level set (D84) ─────────────────────────────────────────


# Flags that are valid on `set --activity`. Anything else gets rejected.
_ACTIVITY_SET_FLAGS = {
    "title", "status", "type", "area", "tag", "tags",
    "add_tag", "add_tags", "remove_tag", "remove_tags", "clear_tags",
    "last_reviewed",
}

# Task-only flags rejected on `set --activity`, for clear error messaging.
_TASK_ONLY_SET_FLAGS = {
    "bucket": "--bucket",
    "stage": "--stage",
    "run_state": "--run-state",
    "pinned": "--pinned",
    "issue": "--issue",
    "blocked_by": "--blocked-by",
    "waiting_for": "--waiting-for",
    "archived": "--archived",
    "due": "--due",
    "scheduled": "--scheduled",
    "start_date": "--start-date",
    "end_date": "--end-date",
    "energy": "--energy",
    "actor": "--actor",
    "owner": "--owner",
    "kind": "--kind",
    "new_slug": "--slug",
}


def _set_activity_one(
    activity_token: str,
    *,
    title: str | None,
    status: str | None,
    activity_type: str | None,
    area: str | None,
    priority: str | None,
    last_reviewed: str | None,
    tag: list[str] | None,
    tags: list[str] | None,
    add_tag: list[str] | None,
    add_tags: list[str] | None,
    remove_tag: list[str] | None,
    remove_tags: list[str] | None,
    clear_tags: bool,
) -> bool:
    """Apply a frontmatter-only edit to one activity. Returns True on success."""
    from octopus.core.identify import (
        ActivityAmbiguous,
        ActivityNotFound,
        resolve_activity,
    )
    from octopus.core.tag_parser import TagFlagConflict, TagFlagInputs, apply_tag_mutations
    from octopus.fs.io import write_activity

    try:
        row = resolve_activity(activity_token)
    except ActivityNotFound as exc:
        err_console.print(f"[red]✗[/] {exc}")
        return False
    except ActivityAmbiguous as exc:
        err_console.print(f"[red]✗[/] {exc}")
        return False

    root = Path(row["path"])
    activity_md = root / ".octopus" / "activity.md"
    if not activity_md.is_file():
        err_console.print(f"[red]✗[/] {activity_md} not found")
        return False
    activity, body = read_activity(activity_md)

    if priority is not None:
        if _is_explicit_default("priority", priority):
            activity.priority = None
        elif priority not in {"low", "high", "urgent"}:
            err_console.print(
                f"[red]✗[/] --priority: {priority!r} not in low|high|urgent "
                "(or 'normal'/'none'/'' to clear)"
            )
            return False
        else:
            activity.priority = priority

    if title is not None:
        if not title.strip():
            err_console.print("[red]✗[/] --title cannot be empty.")
            return False
        activity.title = title
    if status is not None:
        if status not in ACTIVITY_STATUSES:
            err_console.print(
                f"[red]✗[/] --status: {status!r} not in {sorted(ACTIVITY_STATUSES)}"
            )
            return False
        activity.status = status
    if activity_type is not None:
        if activity_type not in ACTIVITY_TYPES:
            err_console.print(
                f"[red]✗[/] --type: {activity_type!r} not in {sorted(ACTIVITY_TYPES)}"
            )
            return False
        activity.type = activity_type
    if area is not None:
        activity.area = None if area == "" else area
    if last_reviewed is not None:
        activity.last_reviewed = _parse_iso_date(last_reviewed, "last-reviewed")

    tag_inputs = TagFlagInputs(
        replace=(tag or []) + (tags or []) if (tag or tags) else None,
        add=(add_tag or []) + (add_tags or []) if (add_tag or add_tags) else None,
        remove=(remove_tag or []) + (remove_tags or []) if (remove_tag or remove_tags) else None,
        clear=clear_tags,
    )
    if any([tag_inputs.replace, tag_inputs.add, tag_inputs.remove, tag_inputs.clear]):
        try:
            activity.tags = apply_tag_mutations(activity.tags, tag_inputs)
        except TagFlagConflict as exc:
            err_console.print(f"[red]✗[/] {exc}")
            return False

    errors = activity.validate()
    if errors:
        err_console.print("[red]✗[/] validation failed:")
        for e in errors:
            err_console.print(f"  - {e}")
        return False

    write_activity(activity_md, activity, body)
    err = sync_activity_after_write(root)
    if err:
        err_console.print(f"[yellow]⚠[/] {err} (run `octopus reindex` to reconcile)")
    console.print(f"[green]✓[/] {short_form(activity.id)} updated")
    return True


# ── set Typer entrypoint (D84) ───────────────────────────────────────


def set_(
    slugs: list[str] | None = typer.Argument(
        None,
        help="Task slug(s). Resolved against cwd activity. For multi-target, prefer --task.",
    ),
    # D84: target axes
    task_targets: list[str] = typer.Option(
        [], "--task",
        help="Task slug(s) to mutate within the current activity (multi-target). (D84)",
    ),
    activity_targets: list[str] = typer.Option(
        [], "--activity",
        help="Activity id(s)/prefix(es)/path(s) to mutate (multi-target, anywhere). (D84)",
    ),
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
    title: str | None = typer.Option(None, "--title"),
    # Activity-only fields (D84)
    status: str | None = typer.Option(
        None, "--status",
        help="Activity status (only valid with --activity).",
    ),
    activity_type: str | None = typer.Option(
        None, "--type",
        help="Activity type (only valid with --activity).",
    ),
    area: str | None = typer.Option(
        None, "--area",
        help="Activity area (only valid with --activity).",
    ),
    last_reviewed: str | None = typer.Option(
        None, "--last-reviewed",
        help="Activity last-reviewed date (only valid with --activity).",
    ),
    # D78: slug rename
    new_slug: str | None = typer.Option(
        None, "--slug",
        help="Rename the task slug (filename). Cascades to Octopus-managed refs.",
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompts."),
    # Tag flag matrix (D76)
    tag: list[str] | None = typer.Option(None, "--tag", help="Replace the tag list (alias of --tags)."),
    tags: list[str] | None = typer.Option(None, "--tags", help="Replace the tag list."),
    add_tag: list[str] | None = typer.Option(None, "--add-tag", help="Append to the tag list."),
    add_tags: list[str] | None = typer.Option(None, "--add-tags", help="Append to the tag list."),
    remove_tag: list[str] | None = typer.Option(None, "--remove-tag", help="Remove from the tag list."),
    remove_tags: list[str] | None = typer.Option(None, "--remove-tags", help="Remove from the tag list."),
    clear_tags: bool = typer.Option(False, "--clear-tags", help="Empty the tag list."),
) -> None:
    """Set frontmatter fields directly. Strict types; warns on verb-overlap.

    D84: three target shapes — positional <slug> (cwd, one), --task t1 t2... (cwd,
    multi), --activity a1 a2... (anywhere, multi). Mixing axes is rejected.
    D77: this is the frontmatter-only escape hatch. `--bucket` changes the
    frontmatter field but does NOT move the file. Use `octopus mv` for that.
    D78: --slug renames the task slug with full cascading auto-fix.
    D80: explicit-default values (normal/none/human/idle/"") clear fields.
    D76: tag flag matrix — see --tag/--tags/--add-tag/--remove-tag/--clear-tags.
    """
    def _expand_csv(values: list[str] | None) -> list[str]:
        """Allow `--task t1,t2` as a shorthand for `--task t1 --task t2`."""
        out: list[str] = []
        for v in (values or []):
            for piece in v.split(","):
                piece = piece.strip()
                if piece:
                    out.append(piece)
        return out

    slugs = slugs or []
    task_targets = _expand_csv(task_targets)
    activity_targets = _expand_csv(activity_targets)

    # D84: target-axis mutex.
    if slugs and task_targets:
        err_console.print(
            "[red]✗[/] positional slug and --task are mutually exclusive (D84)"
        )
        raise typer.Exit(EXIT_USER_ERROR)
    if slugs and activity_targets:
        err_console.print(
            "[red]✗[/] positional slug and --activity are mutually exclusive (D84)"
        )
        raise typer.Exit(EXIT_USER_ERROR)
    if task_targets and activity_targets:
        err_console.print(
            "[red]✗[/] --task and --activity are mutually exclusive (D84)"
        )
        raise typer.Exit(EXIT_USER_ERROR)
    if not slugs and not task_targets and not activity_targets:
        err_console.print(
            "[red]✗[/] no target specified. Pass a task slug, --task <slugs>, "
            "or --activity <ids> (D84)"
        )
        raise typer.Exit(EXIT_USER_ERROR)
    if len(slugs) > 1 and not task_targets:
        err_console.print(
            "[red]✗[/] multiple positional slugs not allowed; use --task for "
            "multi-target (D84)"
        )
        raise typer.Exit(EXIT_USER_ERROR)

    # Activity-level fields are only valid with --activity.
    activity_field_names = {
        "--status": status, "--type": activity_type, "--area": area,
        "--last-reviewed": last_reviewed,
    }
    activity_fields_used = [name for name, val in activity_field_names.items() if val is not None]

    if activity_targets:
        # D84: reject task-only flags on --activity.
        task_only_used: list[str] = []
        for field_name, flag_name in _TASK_ONLY_SET_FLAGS.items():
            val = locals().get(field_name)
            if val is not None and val is not False:
                task_only_used.append(flag_name)
        if task_only_used:
            err_console.print(
                f"[red]✗[/] task-only flag(s) {', '.join(task_only_used)} "
                "not valid with --activity (D84)"
            )
            raise typer.Exit(EXIT_USER_ERROR)

        failures = 0
        for token in activity_targets:
            ok = _set_activity_one(
                token,
                title=title, status=status, activity_type=activity_type,
                area=area, priority=priority, last_reviewed=last_reviewed,
                tag=tag, tags=tags, add_tag=add_tag, add_tags=add_tags,
                remove_tag=remove_tag, remove_tags=remove_tags, clear_tags=clear_tags,
            )
            if not ok:
                failures += 1
        if failures:
            raise typer.Exit(EXIT_USER_ERROR)
        return

    # Task-level (positional or --task). Both require cwd in an activity.
    if activity_fields_used:
        err_console.print(
            f"[red]✗[/] activity-only flag(s) {', '.join(activity_fields_used)} "
            "require --activity (D84)"
        )
        raise typer.Exit(EXIT_USER_ERROR)

    root = _require_activity()
    target_slugs = slugs if slugs else task_targets
    failures = 0
    for slug in target_slugs:
        try:
            ok = _set_task_one(
                slug, root,
                bucket=bucket, stage=stage, run_state=run_state, pinned=pinned,
                issue=issue, blocked_by=blocked_by, waiting_for=waiting_for,
                archived=archived, due=due, scheduled=scheduled,
                start_date=start_date, end_date=end_date,
                priority=priority, energy=energy, actor=actor, owner=owner,
                kind=kind, title=title, new_slug=new_slug, yes=yes,
                tag=tag, tags=tags, add_tag=add_tag, add_tags=add_tags,
                remove_tag=remove_tag, remove_tags=remove_tags, clear_tags=clear_tags,
            )
            if not ok:
                failures += 1
        except typer.Exit:
            # _apply_set_task_fields raises on validation/flag errors.
            failures += 1
    if failures:
        raise typer.Exit(EXIT_USER_ERROR)


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


def _csv_list(values: list[str] | None) -> list[str] | None:
    """Comma-shorthand for filter flags (e.g. --status active,on_hold)."""
    if not values:
        return None
    out: list[str] = []
    for v in values:
        for piece in v.split(","):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out or None


@app.command("list")
def list_cmd(
    noun: str | None = typer.Argument(
        None, help="Optional 'tasks' or 'activities' explicit form (D90).",
    ),
    target: str | None = typer.Argument(
        None, help="When noun=tasks, optional <path-or-id> for cross-activity targeting.",
    ),
    all_: bool = typer.Option(False, "--all", help="Force cross-activity listing regardless of cwd."),
    statuses: list[str] | None = typer.Option(
        None, "--status",
        help="Filter by activity status (multi: --status a,b or repeat).",
    ),
    priorities: list[str] | None = typer.Option(
        None, "--priority",
        help="Filter by activity priority (D87): low|high|urgent.",
    ),
    types: list[str] | None = typer.Option(
        None, "--type",
        help="Filter by activity type.",
    ),
    areas: list[str] | None = typer.Option(
        None, "--area",
        help="Filter by activity area.",
    ),
    has_pinned: bool = typer.Option(False, "--has-pinned", help="Only activities with ≥1 pinned task."),
    has_overdue: bool = typer.Option(False, "--has-overdue", help="Only activities with overdue tasks."),
    has_now: bool = typer.Option(False, "--has-now", help="Only activities with ≥1 task in `now`."),
    touched_within: int | None = typer.Option(
        None, "--touched-within",
        help="Only activities touched in the last N days.",
    ),
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
    include_archived: bool = typer.Option(
        False, "--include-archived",
        help="Include activities with status: archived (hidden by default — D83).",
    ),
    show_ids: bool = typer.Option(False, "--show-ids", "-i", help="Reveal full activity IDs."),
) -> None:
    """List activities or tasks. Context-aware (use --all to force cross-activity).

    Noun-explicit forms (D90):
      octopus list tasks [<path-or-id>]    — list tasks (optionally in a named activity)
      octopus list activities              — list activities with filters

    Bare `octopus list` is context-aware:
      cwd inside .octopus/  → list tasks in current activity
      cwd outside           → list activities

    D83: Activities with `status: archived` are hidden by default.
    D87: --priority is the activity priority filter (low|high|urgent).
    """
    # D90 — noun-explicit forms
    if noun == "tasks":
        _list_tasks(
            target=target, all_=all_, bucket=bucket, kind=kind,
            promoted=promoted, spec=spec, include_archived=include_archived,
            show_ids=show_ids,
        )
        return
    if noun == "activities":
        _list_activities_view(
            statuses=_csv_list(statuses), priorities=_csv_list(priorities),
            types=_csv_list(types), areas=_csv_list(areas),
            has_pinned=has_pinned, has_overdue=has_overdue, has_now=has_now,
            touched_within=touched_within, include_archived=include_archived,
            show_ids=show_ids,
        )
        return
    if noun is not None:
        # Looks like a slug? assume the user meant `list <slug>` (legacy positional)
        err_console.print(
            f"[red]✗[/] unknown noun {noun!r}. Use 'tasks' or 'activities', or omit."
        )
        raise typer.Exit(EXIT_USER_ERROR)

    # Bare `list` — context-aware default (D90)
    cwd_activity = None if all_ else find_activity_root(Path.cwd())
    kinds = [k.strip() for k in kind.split(",")] if kind else None
    task_view = bool(bucket or kinds or promoted or spec)
    if cwd_activity is not None and not task_view:
        # In-activity → default to tasks
        _list_tasks(
            target=None, all_=False, bucket=bucket, kind=kind,
            promoted=promoted, spec=spec, include_archived=include_archived,
            show_ids=show_ids,
        )
        return
    if task_view:
        # Filters force a task view, even cross-activity
        conn = get_db()
        try:
            if _is_empty_index():
                console.print(EMPTY_INDEX_HINT)
                return
            rows = tasks_all(
                conn, bucket=bucket,
                kinds=kinds, promoted=promoted, spec=spec,
            )
            _print_task_rows(rows, show_ids=show_ids, show_activity=True)
        finally:
            conn.close()
        return
    # Cross-activity default → activities
    _list_activities_view(
        statuses=_csv_list(statuses), priorities=_csv_list(priorities),
        types=_csv_list(types), areas=_csv_list(areas),
        has_pinned=has_pinned, has_overdue=has_overdue, has_now=has_now,
        touched_within=touched_within, include_archived=include_archived,
        show_ids=show_ids,
    )


def _list_tasks(
    *, target: str | None, all_: bool, bucket: str | None, kind: str | None,
    promoted: bool, spec: str | None, include_archived: bool, show_ids: bool,
) -> None:
    """Implementation for `octopus list tasks [<path-or-id>]`."""
    kinds = [k.strip() for k in kind.split(",")] if kind else None
    conn = get_db()
    try:
        if target is not None:
            # Resolve the activity by path-or-id, then list its tasks
            root = _resolve_activity_root(target)
            activity_md = root / ".octopus" / "activity.md"
            try:
                activity, _ = read_activity(activity_md)
            except Exception as e:
                err_console.print(f"[red]✗[/] cannot read activity: {e}")
                raise typer.Exit(EXIT_USER_ERROR) from e
            rows = tasks_for_activity(
                conn, activity.id, bucket=bucket,
                kinds=kinds, promoted=promoted, spec=spec,
                include_archived=include_archived,
            )
            _print_task_rows(rows, show_ids=show_ids)
            return
        # No target: cwd-walk-up if available, else cross-activity
        cwd_activity = None if all_ else find_activity_root(Path.cwd())
        if cwd_activity is not None:
            activity, _ = read_activity(cwd_activity / ".octopus" / "activity.md")
            rows = tasks_for_activity(
                conn, activity.id, bucket=bucket,
                kinds=kinds, promoted=promoted, spec=spec,
                include_archived=include_archived,
            )
            _print_task_rows(rows, show_ids=show_ids)
        else:
            if _is_empty_index():
                console.print(EMPTY_INDEX_HINT)
                return
            rows = tasks_all(
                conn, bucket=bucket,
                kinds=kinds, promoted=promoted, spec=spec,
                include_archived=include_archived,
            )
            _print_task_rows(rows, show_ids=show_ids, show_activity=True)
    finally:
        conn.close()


def _list_activities_view(
    *, statuses, priorities, types, areas, has_pinned, has_overdue, has_now,
    touched_within, include_archived, show_ids,
) -> None:
    """Implementation for `octopus list activities` with all filter flags."""
    conn = get_db()
    try:
        if _is_empty_index():
            console.print(EMPTY_INDEX_HINT)
            return
        rows = db_list_activities(
            conn,
            statuses=statuses, priorities=priorities, types=types, areas=areas,
            has_pinned=has_pinned, has_overdue=has_overdue, has_now=has_now,
            touched_within_days=touched_within,
            include_archived=include_archived,
        )
        _print_activity_rows(conn, rows, show_ids=show_ids)
    finally:
        conn.close()


def _priority_chip(priority: str | None) -> str:
    """Render an activity priority as a colored chip. Empty for normal."""
    if priority == "urgent":
        return "[red]urgent[/]"
    if priority == "high":
        return "[yellow]high[/]"
    if priority == "low":
        return "[dim]low[/]"
    return ""


def _print_activity_rows(
    conn, rows: list, *, show_ids: bool = False,
) -> None:
    if not rows:
        console.print("[dim]no activities match filters[/]")
        return
    table = Table(show_edge=False)
    table.add_column("Activity", style="cyan")
    table.add_column("Title")
    table.add_column("Pri", style="dim")
    table.add_column("Type", style="dim")
    table.add_column("Status", style="dim")
    table.add_column("Now", justify="right")
    table.add_column("Next", justify="right")
    table.add_column("Backlog", justify="right")
    for row in rows:
        display_id = row["id"] if show_ids else short_form(row["id"])
        counts = count_by_bucket(conn, row["id"])
        # Tolerate older schema (priority column added in v4)
        try:
            priority = row["priority"]
        except (KeyError, IndexError):
            priority = None
        table.add_row(
            display_id, row["title"] or "",
            _priority_chip(priority),
            row["type"] or "", row["status"] or "",
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
    target: str | None = typer.Argument(
        None,
        help="Activity path, id, or unambiguous prefix. Defaults to cwd's activity.",
    ),
    show_ids: bool = typer.Option(False, "--show-ids", "-i"),
    limit: int = typer.Option(5, "--limit", help="Max tasks per section (now/pinned/overdue)."),
) -> None:
    """Rich activity view (D90): metadata + bucket counts + now/pinned/overdue.

    Path-or-id resolution (D83): token starts with `/`, `~`, or contains `/`
    → filesystem path; otherwise activity id (exact or unambiguous prefix).
    """
    from octopus.core.identify import (
        ActivityAmbiguous,
        ActivityNotFound,
        resolve_activity,
    )

    conn = get_db()
    try:
        if target:
            try:
                activity = resolve_activity(target)
            except ActivityNotFound as exc:
                err_console.print(f"[red]✗[/] {exc}")
                raise typer.Exit(EXIT_USER_ERROR) from exc
            except ActivityAmbiguous as exc:
                err_console.print(f"[red]✗[/] {exc}")
                raise typer.Exit(EXIT_USER_ERROR) from exc
        else:
            root = find_activity_root(Path.cwd())
            if root is None:
                if _is_empty_index():
                    console.print(EMPTY_INDEX_HINT)
                    return
                err_console.print(
                    "[red]✗[/] not in an activity; pass an activity path/id "
                    "or run from inside an activity folder."
                )
                raise typer.Exit(EXIT_NOT_IN_ACTIVITY)
            try:
                activity = resolve_activity(str(root))
            except ActivityNotFound:
                console.print(EMPTY_INDEX_HINT)
                return

        display_id = activity["id"] if show_ids else short_form(activity["id"])

        # Metadata table
        tbl = Table(show_header=False, show_edge=False, padding=(0, 2))
        tbl.add_column(style="dim")
        tbl.add_column()
        tbl.add_row("Activity", f"[bold]{display_id}[/]")
        tbl.add_row("Title", activity["title"] or "")
        tbl.add_row("Path", activity["path"])
        tbl.add_row("Type", activity["type"] or "")
        tbl.add_row("Status", activity["status"] or "")
        try:
            pri = activity["priority"]
        except (KeyError, IndexError):
            pri = None
        if pri:
            tbl.add_row("Priority", _priority_chip(pri))
        if activity["area"]:
            tbl.add_row("Area", activity["area"])
        if activity["last_reviewed"]:
            tbl.add_row("Last reviewed", str(activity["last_reviewed"]))
        try:
            lt = activity["last_touched_at"]
        except (KeyError, IndexError):
            lt = None
        if lt:
            tbl.add_row("Last touched", str(lt))
        console.print(tbl)

        # Bucket counts
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

        # Now / pinned / overdue task previews
        rows = tasks_for_activity(conn, activity["id"])
        now_rows = [r for r in rows if r["bucket"] == "now"]
        pinned_rows = [r for r in rows if r["pinned"]]
        overdue_rows = [
            r for r in rows
            if r["due"] is not None
            and str(r["due"]) < date.today().isoformat()
            and r["bucket"] not in {"done", "dropped"}
        ]
        for label, items in (
            ("Now", now_rows),
            ("Pinned", pinned_rows),
            ("Overdue", overdue_rows),
        ):
            if not items:
                continue
            console.print(f"\n[bold]{label}[/] ({len(items)})")
            for r in items[:limit]:
                marker = ""
                if r["priority"] == "urgent":
                    marker = "🔥 "
                elif r["priority"] == "high":
                    marker = "! "
                console.print(f"  {marker}[cyan]{r['slug']}[/]  {r['title']}")
            if len(items) > limit:
                console.print(f"  [dim]…and {len(items) - limit} more[/]")
    finally:
        conn.close()


# ── get / dashboard / next / impact (D90) ─────────────────────────────


get_app = typer.Typer(help="JSON-shaped programmatic reads.", no_args_is_help=True)
app.add_typer(get_app, name="get")


@get_app.command("activity")
def get_activity_cmd(
    target: str = typer.Argument(..., help="Activity path, id, or unambiguous prefix."),
    format_: str | None = typer.Option(
        None, "--format",
        help="Output format: pretty | compact. Default: pretty on TTY, compact in pipes.",
    ),
) -> None:
    """JSON dump of activity metadata + bucket counts + now/pinned/overdue (D90)."""
    import json
    import sys

    from octopus.core.identify import (
        ActivityAmbiguous,
        ActivityNotFound,
        resolve_activity,
    )

    try:
        activity = resolve_activity(target)
    except (ActivityNotFound, ActivityAmbiguous) as exc:
        err_console.print(f"[red]✗[/] {exc}")
        raise typer.Exit(EXIT_USER_ERROR) from exc

    conn = get_db()
    try:
        counts = count_by_bucket(conn, activity["id"])
        rows = tasks_for_activity(conn, activity["id"])
        today_str = date.today().isoformat()
        now_tasks = [
            {"slug": r["slug"], "title": r["title"], "priority": r["priority"]}
            for r in rows if r["bucket"] == "now"
        ]
        pinned_tasks = [
            {"slug": r["slug"], "title": r["title"], "bucket": r["bucket"]}
            for r in rows if r["pinned"]
        ]
        overdue_tasks = [
            {"slug": r["slug"], "title": r["title"], "due": str(r["due"])}
            for r in rows
            if r["due"] is not None and str(r["due"]) < today_str
            and r["bucket"] not in {"done", "dropped"}
        ]
    finally:
        conn.close()

    def _safe(row, key):
        try:
            return row[key]
        except (KeyError, IndexError):
            return None

    doc = {
        "activity": {
            "id": activity["id"],
            "title": activity["title"],
            "path": activity["path"],
            "type": activity["type"],
            "status": activity["status"],
            "area": activity["area"],
            "priority": _safe(activity, "priority"),
            "created": str(activity["created"]) if activity["created"] else None,
            "last_reviewed": (
                str(activity["last_reviewed"]) if activity["last_reviewed"] else None
            ),
            "last_touched_at": (
                str(_safe(activity, "last_touched_at")) if _safe(activity, "last_touched_at") else None
            ),
        },
        "buckets": {b: counts.get(b, 0) for b in ("backlog", "next", "now", "done", "dropped")},
        "now_tasks": now_tasks,
        "pinned_tasks": pinned_tasks,
        "overdue_tasks": overdue_tasks,
    }

    if format_ is None:
        format_ = "pretty" if sys.stdout.isatty() else "compact"
    if format_ == "compact":
        out = json.dumps(doc, ensure_ascii=False, default=str)
    else:
        out = json.dumps(doc, ensure_ascii=False, default=str, indent=2)
    # Use plain print to avoid Rich markup interpretation of JSON
    print(out)


def _gather_ranked_tasks(conn) -> list[dict]:
    """Compute the R1 score for every active task across the index.

    Returns a list of dicts with task fields + activity context + score
    breakdown, sorted by score descending (with tiebreak on last_touched_at).
    """
    from octopus.core.ranking import score_task

    # Pull all activities (incl. priority + last_touched_at)
    act_rows = conn.execute(
        "SELECT id, title, priority, last_touched_at FROM activities"
    ).fetchall()
    by_id = {r["id"]: r for r in act_rows}

    # All tasks that aren't archived/done/dropped — let the ranker do the rest
    rows = tasks_all(conn)
    ranked: list[dict] = []
    for r in rows:
        act = by_id.get(r["activity_id"])
        act_priority = None if act is None else act["priority"]
        # Build a lightweight object that score_task can read attrs from
        task_obj = type("T", (), {
            "archived": r["archived"],
            "bucket": r["bucket"],
            "pinned": r["pinned"],
            "due": r["due"] if isinstance(r["due"], date) else (
                date.fromisoformat(r["due"]) if r["due"] else None
            ),
            "priority": r["priority"],
            "issue": r["issue"],
        })()
        score = score_task(task_obj, activity_priority=act_priority)
        if score is None:
            continue
        ranked.append({
            "activity_id": r["activity_id"],
            "activity_title": act["title"] if act else "",
            "activity_priority": act_priority,
            "slug": r["slug"],
            "title": r["title"],
            "bucket": r["bucket"],
            "pinned": r["pinned"],
            "due": r["due"],
            "priority": r["priority"],
            "issue": r["issue"],
            "last_touched_at": act["last_touched_at"] if act else None,
            "score": score.total,
            "score_breakdown": score,
        })
    # Sort: score desc, then activity last_touched asc (older = stale = up)
    ranked.sort(key=lambda x: (
        -x["score"],
        x["last_touched_at"] or "9999",
    ))
    return ranked


@app.command()
def next_(
    limit: int = typer.Option(3, "--limit", help="How many tasks to show (default 3)."),
    json_flag: bool = typer.Option(False, "--json", help="Output JSON to stdout."),
    json_path: str | None = typer.Option(
        None, "--json-out", help="Write JSON to this file path.",
    ),
) -> None:
    """Top N tasks ranked by impact (R1 heuristic, D89). Default N=3."""
    conn = get_db()
    try:
        ranked = _gather_ranked_tasks(conn)
    finally:
        conn.close()
    ranked = ranked[:max(0, limit)]
    _emit_ranked(
        ranked,
        title=f"NEXT {limit} TASK{'S' if limit != 1 else ''}",
        json_flag=json_flag, json_path=json_path,
    )


# Typer doesn't allow `next` as a function name (it's a builtin in some contexts);
# register the command under `next` explicitly.
app.command(name="next")(next_)


@app.command()
def impact(
    limit: int = typer.Option(20, "--limit", help="Max tasks to show. 0 = unlimited."),
    show_score: bool = typer.Option(False, "--show-score", help="Reveal numeric R1 scores."),
    json_flag: bool = typer.Option(False, "--json", help="Output JSON to stdout."),
    json_path: str | None = typer.Option(
        None, "--json-out", help="Write JSON to this file path.",
    ),
) -> None:
    """Full ranked task list (R1 heuristic, D89). Default top 20."""
    conn = get_db()
    try:
        ranked = _gather_ranked_tasks(conn)
    finally:
        conn.close()
    if limit > 0:
        ranked = ranked[:limit]
    _emit_ranked(
        ranked, title="IMPACT (ranked)",
        json_flag=json_flag, json_path=json_path, show_score=show_score,
    )


def _emit_ranked(
    ranked: list[dict], *, title: str,
    json_flag: bool = False, json_path: str | None = None,
    show_score: bool = False,
) -> None:
    """Shared output path for next/impact. --json flag → stdout; --json-out path → file."""
    import json as _json

    if json_flag or json_path:
        payload = [
            {
                "rank": i + 1,
                "activity_id": r["activity_id"],
                "slug": r["slug"],
                "title": r["title"],
                "bucket": r["bucket"],
                "pinned": bool(r["pinned"]),
                "due": str(r["due"]) if r["due"] else None,
                "priority": r["priority"],
                "score": r["score"],
            }
            for i, r in enumerate(ranked)
        ]
        text = _json.dumps(payload, ensure_ascii=False, default=str)
        if json_path:
            path = Path(json_path).expanduser()
            path.write_text(text + "\n", encoding="utf-8")
            console.print(f"[green]✓[/] wrote {len(payload)} ranked task(s) to {path}")
        else:
            print(text)
        return

    if not ranked:
        console.print("[dim]no rankable tasks (try `octopus reindex` if you expected some).[/]")
        return
    console.print(f"\n[bold]{title}[/]\n")
    for i, r in enumerate(ranked, 1):
        marks = []
        if r["pinned"]:
            marks.append("📌")
        if r["priority"] == "urgent":
            marks.append("🔥")
        elif r["priority"] == "high":
            marks.append("!")
        if r["issue"]:
            marks.append(f"[red]{r['issue']}[/]")
        marker = " ".join(marks)
        score_str = f"  [dim]({r['score']})[/]" if show_score else ""
        act_chip = f"[dim]{short_form(r['activity_id'])}/[/]"
        console.print(
            f"{i:>2}. {act_chip}[cyan]{r['slug']}[/]  {r['title']}  {marker}{score_str}"
        )


@app.command()
def dashboard(
    json_flag: bool = typer.Option(False, "--json", help="Output JSON to stdout."),
    json_path: str | None = typer.Option(
        None, "--json-out", help="Write JSON to this file path.",
    ),
) -> None:
    """Composite cross-activity view (D90): pinned, overdue, now, blocked, sessions."""
    import json as _json

    conn = get_db()
    try:
        # Pinned across all activities, active only
        pinned = conn.execute(
            "SELECT t.*, a.title AS activity_title FROM tasks t "
            "JOIN activities a ON a.id = t.activity_id "
            "WHERE t.pinned = 1 AND (t.archived IS NULL OR t.archived = 0) "
            "AND t.bucket NOT IN ('done', 'dropped') "
            "AND (a.status IS NULL OR a.status != 'archived') "
            "ORDER BY t.due IS NULL, t.due"
        ).fetchall()

        today_str = date.today().isoformat()
        overdue = conn.execute(
            "SELECT t.*, a.title AS activity_title FROM tasks t "
            "JOIN activities a ON a.id = t.activity_id "
            "WHERE t.due IS NOT NULL AND t.due < ? "
            "AND (t.archived IS NULL OR t.archived = 0) "
            "AND t.bucket NOT IN ('done', 'dropped') "
            "AND (a.status IS NULL OR a.status != 'archived') "
            "ORDER BY t.due",
            (today_str,),
        ).fetchall()

        now_rows = conn.execute(
            "SELECT t.*, a.title AS activity_title FROM tasks t "
            "JOIN activities a ON a.id = t.activity_id "
            "WHERE t.bucket = 'now' AND (t.archived IS NULL OR t.archived = 0) "
            "AND (a.status IS NULL OR a.status != 'archived') "
            "ORDER BY t.activity_id, t.pinned DESC, t.slug"
        ).fetchall()

        blocked = conn.execute(
            "SELECT t.*, a.title AS activity_title FROM tasks t "
            "JOIN activities a ON a.id = t.activity_id "
            "WHERE t.issue IN ('blocked', 'waiting') "
            "AND (t.archived IS NULL OR t.archived = 0) "
            "AND t.bucket NOT IN ('done', 'dropped') "
            "AND (a.status IS NULL OR a.status != 'archived')"
        ).fetchall()

        # Activity priority breakdown
        prio_rows = db_list_activities(conn)
    finally:
        conn.close()

    if json_flag or json_path:
        def _row(r):
            return {
                "activity_id": r["activity_id"],
                "activity_title": r["activity_title"],
                "slug": r["slug"],
                "title": r["title"],
                "bucket": r["bucket"],
                "due": str(r["due"]) if r["due"] else None,
                "priority": r["priority"],
                "pinned": bool(r["pinned"]),
                "issue": r["issue"],
            }
        def _safe(r, key):
            try:
                return r[key]
            except (KeyError, IndexError):
                return None
        payload = {
            "date": today_str,
            "pinned": [_row(r) for r in pinned],
            "overdue": [_row(r) for r in overdue],
            "now": [_row(r) for r in now_rows],
            "blocked": [_row(r) for r in blocked],
            "activities": [
                {
                    "id": r["id"], "title": r["title"], "type": r["type"],
                    "status": r["status"], "priority": _safe(r, "priority"),
                    "last_touched_at": str(_safe(r, "last_touched_at"))
                                       if _safe(r, "last_touched_at") else None,
                }
                for r in prio_rows
            ],
        }
        text = _json.dumps(payload, ensure_ascii=False, default=str)
        if json_path:
            path = Path(json_path).expanduser()
            path.write_text(text + "\n", encoding="utf-8")
            console.print(f"[green]✓[/] dashboard JSON written to {path}")
        else:
            print(text)
        return

    # Rich text render
    console.print(f"\n[bold]DASHBOARD[/] — {today_str}\n")

    def _section(label: str, items: list, render):
        if not items:
            return
        console.print(f"[bold]{label}[/] ({len(items)})")
        for r in items:
            render(r)
        console.print()

    def _line(r, *, prefix: str = ""):
        marks = []
        if r["pinned"]:
            marks.append("📌")
        if r["priority"] == "urgent":
            marks.append("🔥")
        elif r["priority"] == "high":
            marks.append("!")
        if r["issue"]:
            marks.append(f"[red]{r['issue']}[/]")
        chip = " ".join(marks)
        act = short_form(r["activity_id"])
        due_str = ""
        if r["due"]:
            due_str = f"  [yellow]{r['due']}[/]"
        console.print(f"  {prefix}[dim]{act}/[/][cyan]{r['slug']}[/]  {r['title']}  {chip}{due_str}")

    _section("⚐ PINNED", pinned, _line)
    _section("📅 OVERDUE", overdue, _line)
    _section("● NOW", now_rows, _line)
    _section("⏸ BLOCKED", blocked, _line)

    # Activities by priority
    if prio_rows:
        urgent = [a for a in prio_rows if _row_safe(a, "priority") == "urgent"]
        high = [a for a in prio_rows if _row_safe(a, "priority") == "high"]
        if urgent or high:
            console.print("[bold]ACTIVITY PRIORITIES[/]")
            for a in urgent:
                console.print(f"  [red]urgent[/]   {a['title']}")
            for a in high:
                console.print(f"  [yellow]high[/]     {a['title']}")
            console.print()

    console.print("[dim]next 3 tasks → octopus next         full ranked list → octopus impact[/]")


def _row_safe(row, key):
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


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

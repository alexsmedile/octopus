"""Pull pipeline — materializes adapter `ExternalTask` items as Octopus tasks.

Adapters return `PullResult.tasks: list[ExternalTask]`. This module turns
those into real `.octopus/tasks/<bucket>/<slug>.md` files with provenance
fields, deduped via the `task_external_refs` join table.

See SCHEMA-ADAPTER §7 and DECISIONS D63 for the full contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from octopus import actions
from octopus.adapters.base import PullResult
from octopus.adapters.journal import update_journal
from octopus.config import load_config
from octopus.core.slug import slugify
from octopus.db.connection import get_db
from octopus.db.queries import find_by_external_ref
from octopus.fs.io import read_task, write_task


# ── result shape ──────────────────────────────────────────────────────


@dataclass
class MaterializeResult:
    """Outcome of a pull pipeline run."""

    new_slugs: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_groups: list[str] = field(default_factory=list)

    @property
    def new_count(self) -> int:
        return len(self.new_slugs)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class PipelineError(Exception):
    """Pipeline failure with an exit-code hint."""

    def __init__(self, message: str, exit_code: int = 4) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# ── target activity resolution ────────────────────────────────────────


def resolve_target_activity(
    *,
    config_default: str | None,
    cwd_activity: Path | None,
) -> Path:
    """Per CLI-VERBS.md: `default_activity` from bridge config > cwd activity > exit 2."""
    if config_default:
        # `default_activity` is an activity ID; we need the path.
        # Look it up in the index.
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT path FROM activities WHERE id = ?", (config_default,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            return Path(row["path"])
        raise PipelineError(
            f"default_activity {config_default!r} not found in index — "
            "run `octopus reindex` or fix the bridge config",
            exit_code=2,
        )
    if cwd_activity:
        return cwd_activity
    raise PipelineError(
        "no target activity — set `default_activity` in the bridge config "
        "or run from inside an activity",
        exit_code=2,
    )


# ── materialization ───────────────────────────────────────────────────


def materialize_pull_result(
    activity_root: Path,
    adapter_name: str,
    result: PullResult,
    *,
    update_cursor: bool = True,
) -> MaterializeResult:
    """Turn a PullResult into Octopus task files.

    - Dedups via `task_external_refs` — known external_ids are skipped.
    - Sets provenance: actor=human, imported_from, import_date, external_refs.
    - Updates the sync journal (last_pull, pull_count, cursor).
    - Continues on per-item errors; only raises PipelineError on activity
      resolution failure (handled by caller).
    """
    out = MaterializeResult()
    out.errors.extend(result.errors)
    out.skipped.extend(result.skipped)
    today = date.today()
    cfg = load_config(activity_root / ".octopus")

    # Collect source_groups for the summary line.
    groups_seen: set[str] = set()

    conn = get_db()
    try:
        for et in result.tasks:
            if et.source_group:
                groups_seen.add(et.source_group)

            existing = find_by_external_ref(conn, adapter_name, et.external_id)
            if existing:
                out.skipped.append((et.external_id, "already imported"))
                continue

            # Create the task. The actions layer handles bucket placement,
            # slug collision, frontmatter validation, and index sync.
            try:
                created = actions.capture_task(
                    activity_root,
                    title=et.title,
                    bucket=et.suggested_bucket or "backlog",
                    body=_render_imported_body(adapter_name, et),
                )
            except actions.ActionError as exc:
                out.errors.append(f"{et.external_id}: capture failed — {exc}")
                continue

            # Re-open the task to add the provenance + classification fields
            # that capture_task doesn't accept directly.
            task_path = created.path
            task, body = read_task(task_path)
            task.actor = "human"  # explicit even though it's the default
            task.imported_from = adapter_name
            task.import_date = today
            task.external_refs[adapter_name] = et.external_id
            if et.suggested_kind:
                task.kind = et.suggested_kind
            if et.suggested_tags:
                # Merge — don't overwrite anything the body template added.
                existing_tags = set(task.tags)
                for t in et.suggested_tags:
                    if t not in existing_tags:
                        task.tags.append(t)
            write_task(task_path, task, body)

            # Sync the index so task_external_refs gets populated.
            from octopus.db.sync import sync_task_after_write
            sync_task_after_write(activity_root, task)

            out.new_slugs.append(created.slug)
    finally:
        conn.close()

    out.source_groups = sorted(groups_seen)

    # Journal update — even on failure we record that a pull was attempted.
    update_journal(
        adapter_name,
        pulled=True,
        cursor=result.cursor if update_cursor else ...,  # type: ignore[arg-type]
    )

    return out


# ── helpers ───────────────────────────────────────────────────────────


def _render_imported_body(adapter_name: str, et) -> str:
    """3-line body for newly-imported tasks. Adapter-specific bodies are
    rendered in the adapter; this is the framework default.
    """
    lines = [
        "",
        f"## Imported from {adapter_name}",
        "",
    ]
    if et.body:
        lines.append(et.body)
        lines.append("")
    if et.source_group:
        lines.append(f"_Source group: {et.source_group}_")
        lines.append("")
    lines.append(f"_External id: `{et.external_id}`_")
    lines.append("")
    return "\n".join(lines)


# ── group resolution (D59) ────────────────────────────────────────────


def resolve_groups(
    *,
    configured_lists: list[str] | None,
    flag_list: str | None,
    flag_capture_all: bool,
    adapter_list_groups: list[str] | None = None,
    adapter_has_groups: bool = True,
    verb: str = "pull",
) -> list[str] | None:
    """Apply the D60 flag matrix for peek/pull/search.

    Args:
        adapter_has_groups: If False, the adapter is a single-source one
            (TODO.md, future single-file readers). The "lists/--list/
            --capture-all" matrix doesn't apply — return None to signal
            "use adapter default." Multi-group adapters (Reminders, GitHub)
            pass True; single-source ones pass False.

    Returns:
        list[str] — explicit groups to use
        None       — single-source adapter OR peek-discovery for multi-group

    Raises PipelineError on invalid combinations (exit 1 mutual exclusion;
    exit 3 unbounded pull/search on a multi-group adapter).
    """
    if flag_list and flag_capture_all:
        raise PipelineError(
            "--list and --capture-all are mutually exclusive",
            exit_code=1,
        )
    if flag_capture_all:
        return list(adapter_list_groups or [])
    if flag_list:
        return [s.strip() for s in flag_list.split(",") if s.strip()]
    # No flags — use configured default if any.
    if configured_lists:
        return list(configured_lists)
    # No flags and no configured default.
    if not adapter_has_groups:
        # Single-source adapter — None means "use adapter default behavior."
        return None
    if verb == "peek":
        return None  # discovery mode
    raise PipelineError(
        "no default list configured — specify --list <name> or --capture-all",
        exit_code=3,
    )

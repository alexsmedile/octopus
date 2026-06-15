"""Read/write frontmatter files preserving body and unknown fields.

Uses python-frontmatter. Critical: unknown frontmatter keys MUST round-trip
(SPEC.md §11.2 forward-compat).

Default-omission: any field equal to its default is NOT written. The cleanest
captures have 3-line frontmatter.
"""

from __future__ import annotations

import tomllib
from datetime import date, datetime
from pathlib import Path
from typing import Any

import frontmatter

from octopus.core.models import (
    DEFAULT_ACTOR,
    DEFAULT_BUCKET,
    Activity,
    Task,
)

# ── config.local.toml helpers (D110) ─────────────────────────────────

_LOCAL_STATE_FILE = "config.local.toml"


def _read_local_state(octopus_dir: Path) -> dict:
    """Read .octopus/config.local.toml. Returns empty dict if absent or invalid."""
    path = octopus_dir / _LOCAL_STATE_FILE
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}


def write_local_state(octopus_dir: Path, *, last_known_path: str) -> None:
    """Write (or overwrite) .octopus/config.local.toml with machine-local state."""
    path = octopus_dir / _LOCAL_STATE_FILE
    path.write_text(f'last_known_path = "{last_known_path}"\n', encoding="utf-8")


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to date")


# ── Activity ─────────────────────────────────────────────────────────

ACTIVITY_FIELDS = {
    "id", "title", "created", "kind", "spec_version",
    "type", "status", "area", "priority", "last_reviewed",
    "last_known_path", "source_of_truth", "locations",
    "linked_activities", "tags",
}


def read_activity(path: Path) -> tuple[Activity, str]:
    """Read activity.md. Returns (Activity, body).

    D110: last_known_path is read from .octopus/config.local.toml first;
    falls back to activity.md frontmatter for backwards compat.
    """
    post = frontmatter.load(path)
    data = post.metadata
    extra = {k: v for k, v in data.items() if k not in ACTIVITY_FIELDS}

    # D110: prefer config.local.toml; fall back to activity.md value.
    octopus_dir = path.parent
    local_state = _read_local_state(octopus_dir)
    last_known_path = str(
        local_state.get("last_known_path")
        or data.get("last_known_path")
        or ""
    )

    activity = Activity(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        created=_coerce_date(data.get("created")) or date.today(),
        kind=str(data.get("kind", "activity")),
        spec_version=int(data.get("spec_version", 1)),
        type=str(data.get("type", "other")),
        status=str(data.get("status", "active")),
        area=data.get("area"),
        priority=data.get("priority"),
        last_reviewed=_coerce_date(data.get("last_reviewed")),
        last_known_path=last_known_path,
        source_of_truth=str(data.get("source_of_truth", ".")),
        locations=list(data.get("locations") or []),
        linked_activities=list(data.get("linked_activities") or []),
        tags=list(data.get("tags") or []),
        folder_path=path.parent.parent,
        extra=extra,
    )
    return activity, post.content


def write_activity(path: Path, activity: Activity, body: str) -> None:
    """Write activity.md, preserving unknown keys and field order."""
    data: dict[str, Any] = {
        "id": activity.id,
        "title": activity.title,
        "created": activity.created.isoformat(),
        "kind": activity.kind,
        "spec_version": activity.spec_version,
        "type": activity.type,
        "status": activity.status,
    }
    if activity.area is not None:
        data["area"] = activity.area
    if activity.priority is not None:
        data["priority"] = activity.priority
    if activity.last_reviewed is not None:
        data["last_reviewed"] = activity.last_reviewed.isoformat()
    # D110: last_known_path is NOT written to activity.md — it lives in config.local.toml.
    data["source_of_truth"] = activity.source_of_truth
    if activity.locations:
        data["locations"] = activity.locations
    if activity.linked_activities:
        data["linked_activities"] = activity.linked_activities
    if activity.tags:
        data["tags"] = activity.tags
    for k, v in activity.extra.items():
        if k not in data:
            data[k] = v

    post = frontmatter.Post(body, **data)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


# ── Task ─────────────────────────────────────────────────────────────

TASK_FIELDS = {
    "title", "created",
    "bucket", "stage",
    "run_state",
    "pinned", "issue", "blocked_by", "waiting_for", "archived",
    "due", "scheduled", "start_date", "end_date",
    "priority", "energy",
    "actor", "owner",
    "kind", "tags",
    "parent", "subtasks",
    "external_refs", "import_date", "imported_from", "promoted_to",
}

# Legacy field names. `kind` was previously here but is now a v1 work-classification
# field (D46) and is parsed into Task.kind. The remaining two are still rejected.
LEGACY_FIELDS = {"status", "open"}


def read_task(path: Path) -> tuple[Task, str]:
    """Read tasks/<slug>.md. Returns (Task, body).

    Legacy fields (status, kind, open) are loaded into `extra` and surface
    as validation errors so old files are flagged loudly.
    """
    post = frontmatter.load(path)
    data = post.metadata
    extra = {k: v for k, v in data.items() if k not in TASK_FIELDS}

    task = Task(
        title=str(data.get("title", "")),
        created=_coerce_date(data.get("created")) or date.today(),
        bucket=str(data.get("bucket", DEFAULT_BUCKET)),
        stage=data.get("stage"),
        run_state=data.get("run_state"),
        pinned=data.get("pinned"),
        issue=data.get("issue"),
        blocked_by=data.get("blocked_by"),
        waiting_for=data.get("waiting_for"),
        archived=data.get("archived"),
        due=_coerce_date(data.get("due")),
        scheduled=_coerce_date(data.get("scheduled")),
        start_date=_coerce_date(data.get("start_date")),
        end_date=_coerce_date(data.get("end_date")),
        priority=data.get("priority"),
        energy=data.get("energy"),
        actor=data.get("actor"),
        owner=data.get("owner"),
        kind=data.get("kind"),
        tags=list(data.get("tags") or []),
        parent=data.get("parent") or None,
        subtasks=list(data.get("subtasks") or []),
        external_refs=dict(data.get("external_refs") or {}),
        import_date=_coerce_date(data.get("import_date")),
        imported_from=data.get("imported_from"),
        promoted_to=data.get("promoted_to"),
        slug=path.stem,
        path=path,
        extra=extra,
    )
    return task, post.content


def write_task(path: Path, task: Task, body: str) -> None:
    """Write tasks/<slug>.md.

    Default-omission: skip fields equal to defaults so frontmatter stays minimal.
    Canonical field order matches SCHEMA-TASK.md.
    """
    data: dict[str, Any] = {
        "title": task.title,
        "created": task.created.isoformat(),
        "bucket": task.bucket,
    }
    # stage
    if task.stage is not None:
        data["stage"] = task.stage
    # run_state
    if task.run_state is not None:
        data["run_state"] = task.run_state
    # pinned (only when true)
    if task.pinned is True:
        data["pinned"] = True
    # issue + context
    if task.issue is not None:
        data["issue"] = task.issue
    if task.blocked_by:
        data["blocked_by"] = task.blocked_by
    if task.waiting_for:
        data["waiting_for"] = task.waiting_for
    # archived (only when true)
    if task.archived is True:
        data["archived"] = True
    # dates
    if task.due is not None:
        data["due"] = task.due.isoformat()
    if task.scheduled is not None:
        data["scheduled"] = task.scheduled.isoformat()
    if task.start_date is not None:
        data["start_date"] = task.start_date.isoformat()
    if task.end_date is not None:
        data["end_date"] = task.end_date.isoformat()
    # prioritization — both omitted when default
    if task.priority is not None:
        data["priority"] = task.priority
    if task.energy is not None:
        data["energy"] = task.energy
    # actor — omitted when human
    if task.actor is not None and task.actor != DEFAULT_ACTOR:
        data["actor"] = task.actor
    if task.owner is not None:
        data["owner"] = task.owner
    # taxonomy — kind first, then tags
    if task.kind is not None:
        data["kind"] = task.kind
    if task.tags:
        data["tags"] = task.tags
    # subtask graph (D104) — omit when absent / empty
    if task.parent:
        data["parent"] = task.parent
    if task.subtasks:
        data["subtasks"] = task.subtasks
    # integrations & provenance
    if task.external_refs:
        data["external_refs"] = task.external_refs
    if task.import_date is not None:
        data["import_date"] = task.import_date.isoformat()
    if task.imported_from is not None:
        data["imported_from"] = task.imported_from
    if task.promoted_to is not None:
        data["promoted_to"] = task.promoted_to

    # Preserve unknown fields at the end (excluding legacy fields)
    for k, v in task.extra.items():
        if k in LEGACY_FIELDS:
            continue
        if k not in data:
            data[k] = v

    post = frontmatter.Post(body, **data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

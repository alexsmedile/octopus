"""Native Open Task Format (OTF) 0.1.0 codec for Octopus Task models.

Maps losslessly between Octopus `Task` dataclasses and OTF 0.1.0 Record Markdown:
- Preserves immutable UUID (`id`) in `Task.otf_id`
- Maps Octopus `bucket` <-> OTF `status` + `extensions["octopus.core"]["bucket"]`
- Maps Octopus `issue`/`blocked_by`/`waiting_for` <-> flat OTF `impediment` + `impediment_reason`
- Maps Octopus `tags` <-> OTF `labels`, `owner` <-> `assignees` + `extensions["octopus.core"]["owner"]`
- Preserves unknown top-level keys and third-party/standard DLC `extensions` (`otf.agile`, `otf.schedule`, ...)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from octopus.core.models import DEFAULT_ACTOR, DEFAULT_BUCKET, Task

OTF_VERSION = "0.1.0"

_BUCKET_TO_STATUS = {
    "backlog": "open",
    "next": "open",
    "now": "in_progress",
    "done": "done",
    "dropped": "cancelled",
}

_STATUS_TO_BUCKET = {
    "open": "backlog",
    "in_progress": "now",
    "done": "done",
    "cancelled": "dropped",
}

_OTF_KNOWN_KEYS = {
    "type", "otf_version", "id", "title", "status",
    "description", "stage", "kind", "priority", "project",
    "assignees", "labels", "scheduled", "due",
    "impediment", "impediment_reason", "parent", "depends_on",
    "duplicate_of", "archived", "created_at", "updated_at", "completed_at",
    "external_refs", "extensions",
}


def is_otf_frontmatter(data: dict[str, Any]) -> bool:
    """Return True when frontmatter represents an OTF 0.1.0 task record."""
    return data.get("type") == "task" and isinstance(data.get("otf_version"), str)


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # Accept both YYYY-MM-DD and RFC 3339 timestamps
        return date.fromisoformat(value[:10])
    return None


def task_to_otf_dict(task: Task, *, project_id: str | None = None) -> dict[str, Any]:
    """Serialize an Octopus Task into a conformant OTF 0.1.0 frontmatter mapping."""
    otf_id = task.otf_id or str(uuid.uuid4())
    status = _BUCKET_TO_STATUS.get(task.bucket, "open")

    data: dict[str, Any] = {
        "type": "task",
        "otf_version": OTF_VERSION,
        "id": otf_id,
        "title": task.title,
        "status": status,
    }

    if task.description:
        data["description"] = task.description
    if task.stage:
        data["stage"] = task.stage
    if task.kind:
        data["kind"] = task.kind
    if task.priority is not None:
        data["priority"] = task.priority
    if project_id:
        data["project"] = project_id
    if task.owner:
        data["assignees"] = [task.owner]
    if task.tags:
        data["labels"] = list(dict.fromkeys(task.tags))
    if task.scheduled is not None:
        data["scheduled"] = task.scheduled.isoformat()
    if task.due is not None:
        data["due"] = task.due.isoformat()
    if task.issue is not None:
        reason = task.blocked_by if task.issue == "blocked" else task.waiting_for
        if reason:
            data["impediment"] = task.issue
            data["impediment_reason"] = reason
    if task.duplicate_of and status == "cancelled":
        data["duplicate_of"] = task.duplicate_of
    if task.archived is True:
        data["archived"] = True
    if task.created is not None:
        data["created_at"] = task.created.isoformat()
    if status == "done" and task.end_date is not None:
        data["completed_at"] = task.end_date.isoformat()

    if task.external_refs:
        refs = []
        for system, ext_id in task.external_refs.items():
            refs.append({
                "system": str(system),
                "scope": project_id or "octopus",
                "id": str(ext_id),
                "role": "source",
            })
        data["external_refs"] = refs

    # Preserve existing extensions and populate octopus.core for Octopus-specific axes
    extensions: dict[str, Any] = {k: v for k, v in task.extensions.items()}
    octo_ext: dict[str, Any] = dict(extensions.get("octopus.core") or {})
    if task.bucket in {"backlog", "next", "now"}:
        octo_ext["bucket"] = task.bucket
    if task.owner:
        octo_ext["owner"] = task.owner
    if task.actor and task.actor != DEFAULT_ACTOR:
        octo_ext["actor"] = task.actor
    if task.run_state:
        octo_ext["run_state"] = task.run_state
    if task.pinned is True:
        octo_ext["pinned"] = True
    if task.energy:
        octo_ext["energy"] = task.energy
    if task.start_date is not None:
        octo_ext["start_date"] = task.start_date.isoformat()
    if task.subtasks:
        octo_ext["subtasks"] = list(task.subtasks)
    if task.promoted_to:
        octo_ext["promoted_to"] = task.promoted_to
    if octo_ext:
        extensions["octopus.core"] = octo_ext
    if extensions:
        data["extensions"] = extensions

    # Preserve unknown top-level keys
    for k, v in task.extra.items():
        if k not in data:
            data[k] = v

    return data


def otf_dict_to_task(
    data: dict[str, Any],
    *,
    slug: str = "",
    path: Path | None = None,
) -> Task:
    """Parse an OTF 0.1.0 frontmatter mapping into an Octopus Task."""
    extensions = dict(data.get("extensions") or {})
    octo_ext = dict(extensions.get("octopus.core") or {})

    status = str(data.get("status", "open"))
    if status in {"done", "cancelled"}:
        bucket = _STATUS_TO_BUCKET[status]
    else:
        ext_bucket = octo_ext.get("bucket")
        bucket = str(ext_bucket) if ext_bucket in {"backlog", "next", "now"} else _STATUS_TO_BUCKET.get(status, DEFAULT_BUCKET)

    impediment = data.get("impediment")
    impediment_reason = data.get("impediment_reason")
    blocked_by = str(impediment_reason) if impediment == "blocked" and impediment_reason else None
    waiting_for = str(impediment_reason) if impediment == "waiting" and impediment_reason else None

    # Map scoped OTF external_refs array back to Octopus dict[system, id]
    ext_refs: dict[str, str] = {}
    raw_refs = data.get("external_refs")
    if isinstance(raw_refs, list):
        for entry in raw_refs:
            if isinstance(entry, dict) and entry.get("system") and entry.get("id"):
                ext_refs[str(entry["system"])] = str(entry["id"])
    elif isinstance(raw_refs, dict):
        ext_refs = {str(k): str(v) for k, v in raw_refs.items()}

    assignees = data.get("assignees") or []
    owner = octo_ext.get("owner") or (assignees[0] if isinstance(assignees, list) and assignees else None)

    priority = data.get("priority")
    # Octopus v1 omits medium/none; keep low/high/urgent directly and map medium/none -> None for v1 compat
    octo_priority = priority if priority in {"low", "high", "urgent"} else None

    extra = {k: v for k, v in data.items() if k not in _OTF_KNOWN_KEYS}

    return Task(
        title=str(data.get("title", "")),
        created=_coerce_date(data.get("created_at")) or date.today(),
        bucket=bucket,
        stage=data.get("stage"),
        run_state=octo_ext.get("run_state"),
        pinned=octo_ext.get("pinned"),
        issue=impediment if impediment in {"blocked", "waiting"} else None,
        blocked_by=blocked_by,
        waiting_for=waiting_for,
        archived=data.get("archived"),
        due=_coerce_date(data.get("due")),
        scheduled=_coerce_date(data.get("scheduled")),
        start_date=_coerce_date(octo_ext.get("start_date")),
        end_date=_coerce_date(data.get("completed_at")),
        priority=octo_priority,
        energy=octo_ext.get("energy"),
        actor=octo_ext.get("actor"),
        owner=str(owner) if owner else None,
        kind=data.get("kind"),
        tags=list(data.get("labels") or []),
        parent=data.get("parent") or None,
        subtasks=list(octo_ext.get("subtasks") or []),
        external_refs=ext_refs,
        promoted_to=octo_ext.get("promoted_to"),
        otf_id=str(data["id"]) if data.get("id") else None,
        description=data.get("description"),
        duplicate_of=data.get("duplicate_of"),
        extensions=extensions,
        slug=slug,
        path=path,
        extra=extra,
    )

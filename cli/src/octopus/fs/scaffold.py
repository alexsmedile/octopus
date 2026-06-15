"""Create a new `.octopus/` directory tree per SPEC.md §2."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from octopus.core.id import derive_activity_id
from octopus.core.models import (
    ACTIVITY_STATUSES,
    ACTIVITY_TYPES,
    TASK_BUCKETS,
    Activity,
)
from octopus.fs.io import write_activity, write_local_state

# Subfolder names in folder-storage mode. Equals TASK_BUCKETS since v1.
BUCKET_FOLDERS = TASK_BUCKETS

DEFAULT_STORAGE_MODE = "folders"


class ActivityExistsError(Exception):
    """Raised when init is called inside an existing activity."""


def init_activity(
    folder: Path,
    *,
    title: str | None = None,
    activity_type: str = "other",
    status: str = "active",
    area: str | None = None,
    priority: str | None = None,
    custom_id: str | None = None,
    storage_mode: str = DEFAULT_STORAGE_MODE,
) -> Activity:
    """Create `.octopus/` inside `folder` and return the new Activity.

    Raises:
        ActivityExistsError: if `folder/.octopus/activity.md` already exists.
        ValueError: on invalid type/status/storage_mode.
    """
    folder = folder.resolve()
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(f"unknown type {activity_type!r}; valid: {sorted(ACTIVITY_TYPES)}")
    if status not in ACTIVITY_STATUSES:
        raise ValueError(f"unknown status {status!r}; valid: {sorted(ACTIVITY_STATUSES)}")
    if storage_mode not in {"folders", "fields"}:
        raise ValueError(f"unknown storage_mode {storage_mode!r}; valid: folders, fields")
    if not folder.is_dir():
        raise FileNotFoundError(f"folder does not exist: {folder}")

    octopus_dir = folder / ".octopus"
    activity_md = octopus_dir / "activity.md"
    if activity_md.exists():
        raise ActivityExistsError(f"activity already initialized: {activity_md}")

    octopus_dir.mkdir(exist_ok=True)
    tasks_dir = octopus_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    if storage_mode == "folders":
        for bucket in BUCKET_FOLDERS:
            (tasks_dir / bucket).mkdir(exist_ok=True)
    # sessions/, handoffs/, memory.md, .trash/ are lazy — not created at init

    resolved_title = title if title is not None else folder.name
    activity_id = custom_id or derive_activity_id(folder)

    if priority is not None and priority not in {"low", "high", "urgent"}:
        raise ValueError(
            f"unknown priority {priority!r}; valid: low, high, urgent (or omit for normal)"
        )

    activity = Activity(
        id=activity_id,
        title=resolved_title,
        created=date.today(),
        type=activity_type,
        status=status,
        area=area,
        priority=priority,
        last_reviewed=None,
        last_known_path=str(folder),
    )

    body = f"\n# {resolved_title}\n"
    write_activity(activity_md, activity, body)
    # D110: machine-local path lives in config.local.toml, not activity.md.
    write_local_state(octopus_dir, last_known_path=str(folder))

    # Per-activity config (only emit if non-default)
    if storage_mode != DEFAULT_STORAGE_MODE:
        config_path = octopus_dir / "config.toml"
        config_path.write_text(f'[storage]\nmode = "{storage_mode}"\n', encoding="utf-8")

    return activity


def read_storage_mode(octopus_dir: Path) -> str:
    """Read [storage] mode from .octopus/config.toml. Returns default if absent."""
    config = octopus_dir / "config.toml"
    if not config.is_file():
        return DEFAULT_STORAGE_MODE
    # Minimal TOML parsing — only [storage] mode for now.
    import tomllib
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return DEFAULT_STORAGE_MODE
    return data.get("storage", {}).get("mode", DEFAULT_STORAGE_MODE)

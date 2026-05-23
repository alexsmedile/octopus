"""Activity ID derivation per SPEC.md §9.

Format: <slug>-<4-hex-hash>
where hash = sha256(absolute_path + iso8601_creation_timestamp)[:4]
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from octopus.core.slug import slugify


def derive_activity_id(
    folder_path: Path,
    *,
    created_at: datetime | None = None,
) -> str:
    """Derive a stable activity ID for a folder.

    Per SPEC.md §9.1, the slug portion comes from the folder name (not the
    user-provided title). This means renaming the folder doesn't change the
    activity's identity slug — `last_known_path` absorbs that.

    Args:
        folder_path: absolute path to the activity folder.
        created_at: optional creation timestamp; defaults to now.
    """
    if not folder_path.is_absolute():
        raise ValueError(f"folder_path must be absolute: {folder_path}")

    if not folder_path.name:
        raise ValueError(f"cannot derive ID: folder has empty name: {folder_path}")

    slug = slugify(folder_path.name, max_length=100, extension="")  # generous; we add hash next

    if created_at is None:
        created_at = datetime.now()

    seed = f"{folder_path.resolve()}{created_at.isoformat()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    hash4 = digest[:4]

    return f"{slug}-{hash4}"


def parse_activity_id(activity_id: str) -> tuple[str, str]:
    """Split an activity ID into (slug, hash). Raises if malformed."""
    if not activity_id or "-" not in activity_id:
        raise ValueError(f"malformed activity id: {activity_id!r}")
    slug, _, hash_part = activity_id.rpartition("-")
    if len(hash_part) != 4 or not all(c in "0123456789abcdef" for c in hash_part):
        raise ValueError(f"activity id hash must be 4 hex chars: {activity_id!r}")
    if not slug:
        raise ValueError(f"activity id has empty slug: {activity_id!r}")
    return slug, hash_part


def short_form(activity_id: str) -> str:
    """Return the slug portion (without hash) for display."""
    slug, _ = parse_activity_id(activity_id)
    return slug

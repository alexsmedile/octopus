"""Active-session pointer per activity, cached in ~/.cache/octopus/active-sessions.json.

The cache is the source of truth for "which session am I in right now?"
in each activity. Frontmatter `active:` is a courtesy mirror; cache wins
on disagreement (SCHEMA-SESSION.md line 89).

Format:
    {"<activity_id>": "<session_filename_without_ext>", ...}

Corruption recovery: malformed JSON is treated as empty + a stderr warning.
We never crash on a bad cache file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def cache_path() -> Path:
    """Resolve the cache file path (XDG-respectful, overridable via env)."""
    env = os.environ.get("OCTOPUS_CACHE_HOME")
    base = Path(env) if env else Path.home() / ".cache" / "octopus"
    return base / "active-sessions.json"


def load_active_map() -> dict[str, str]:
    """Read the active-sessions map. Returns empty dict if missing or corrupt."""
    path = cache_path()
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"warning: active-sessions cache unreadable ({exc}); treating as empty",
            file=sys.stderr,
        )
        return {}
    if not isinstance(data, dict):
        print(
            "warning: active-sessions cache is not a JSON object; treating as empty",
            file=sys.stderr,
        )
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def _save_map(data: dict[str, str]) -> None:
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    _atomic_write(cache_path(), payload)


def get_active(activity_id: str) -> str | None:
    """Return the active session filename (without `.md`) for an activity."""
    return load_active_map().get(activity_id)


def set_active(activity_id: str, session_filename: str) -> None:
    """Set the active session pointer for an activity. Atomic."""
    data = load_active_map()
    data[activity_id] = session_filename
    _save_map(data)


def clear_active(activity_id: str) -> None:
    """Clear the active pointer for an activity. No-op if not set."""
    data = load_active_map()
    if activity_id in data:
        del data[activity_id]
        _save_map(data)

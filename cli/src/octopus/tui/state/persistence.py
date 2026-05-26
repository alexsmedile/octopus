"""Cache I/O for ViewState (L3 — opt-in disk persistence).

Cache location: `~/.cache/octopus/ui-state.json` (overridable via the
`OCTOPUS_CACHE_DIR` env var, primarily for tests).

Errors are swallowed silently — losing UI state is annoying for one
session, never harmful. The user's recovery button is `octopus tui --reset-view`.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from octopus.tui.state.model import SCHEMA_VERSION, ViewState

_CACHE_FILENAME = "ui-state.json"


def cache_path() -> Path:
    """Resolve the cache file path. Honors $OCTOPUS_CACHE_DIR for tests."""
    override = os.environ.get("OCTOPUS_CACHE_DIR")
    if override:
        base = Path(override).expanduser()
    else:
        base = Path.home() / ".cache" / "octopus"
    return base / _CACHE_FILENAME


def load() -> ViewState:
    """Read ViewState from cache. Returns an empty ViewState on any error."""
    path = cache_path()
    if not path.is_file():
        return ViewState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ViewState()
    if not isinstance(data, dict):
        return ViewState()
    # Gate on schema version. Unknown future versions → cold-start.
    if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
        return ViewState()
    try:
        return ViewState.from_dict(data)
    except (TypeError, ValueError, KeyError):
        return ViewState()


def save(state: ViewState) -> bool:
    """Atomically write ViewState to cache. Returns True on success.

    Failures swallow silently — UI state is disposable.
    """
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    payload = state.to_dict()
    payload["saved_at"] = datetime.now(UTC).isoformat()
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def reset() -> bool:
    """Delete the cache file. Returns True on success or if the file
    didn't exist to begin with.
    """
    path = cache_path()
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False

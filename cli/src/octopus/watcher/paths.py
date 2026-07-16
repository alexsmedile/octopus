"""Path resolution for the watcher daemon's PID and log files.

Mirrors the XDG-respectful, env-overridable pattern used by
octopus.sessions.cache (OCTOPUS_CACHE_HOME) and octopus.core.logging
(XDG_DATA_HOME).
"""

from __future__ import annotations

import os
from pathlib import Path


def pid_path() -> Path:
    """Resolve `~/.cache/octopus/watcher.pid` (SCHEMA-CONFIG.md §5.2)."""
    env = os.environ.get("OCTOPUS_CACHE_HOME")
    base = Path(env) if env else Path.home() / ".cache" / "octopus"
    return base / "watcher.pid"


def log_path() -> Path:
    """Resolve `~/.local/share/octopus/logs/watcher.log` (SCHEMA-CONFIG.md §5.3)."""
    env = os.environ.get("XDG_DATA_HOME")
    base = Path(env) if env else Path.home() / ".local" / "share"
    return base / "octopus" / "logs" / "watcher.log"

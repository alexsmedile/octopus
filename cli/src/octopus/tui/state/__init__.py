"""TUI view-state persistence (request #44).

Three layers:
- L1 (always-on): per-tab cursor memory while octopus is running
- L2 (always-on): last-active tab/panel memory
- L3 (opt-in via `[ui] restore_last_view = true`): write to `~/.cache/octopus/ui-state.json`
  so state survives quitting and relaunching.
"""

from octopus.tui.state.model import (
    SCHEMA_VERSION,
    ActivityCursor,
    TabState,
    ViewState,
)
from octopus.tui.state.persistence import cache_path, load, save
from octopus.tui.state.resolve import resolve_cursor

__all__ = [
    "SCHEMA_VERSION",
    "ActivityCursor",
    "TabState",
    "ViewState",
    "cache_path",
    "load",
    "save",
    "resolve_cursor",
]

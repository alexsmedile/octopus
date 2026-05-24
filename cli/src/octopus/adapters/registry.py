"""Adapter registry — built-in + entry-point discovery (D64).

Built-in adapters are hardcoded for v1 ergonomics (no import scan on
every CLI call, no surprise overrides). Entry-point discovery is
forward-stable for #15 (adapter SDK, v2); v1 finds none and the merge
is a no-op.

Conflict resolution: built-in wins. Third-party adapter declaring an
existing name is logged + skipped.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from octopus.adapters.base import Adapter


log = logging.getLogger(__name__)


# Built-in registry. Stub adapters ship in #06; #07/#09/#21 replace bodies.
# Deferred import to avoid forcing every CLI call to load all adapter modules.
def _load_builtins() -> dict[str, type[Adapter]]:
    from octopus.adapters.obsidian import ObsidianAdapter
    from octopus.adapters.reminders import RemindersAdapter
    from octopus.adapters.todo_md import TodoMdAdapter

    return {
        "obsidian": ObsidianAdapter,
        "reminders": RemindersAdapter,
        "todo-md": TodoMdAdapter,
    }


def load_registry() -> dict[str, type[Adapter]]:
    """Return the merged registry: built-in + any entry-point contributions.

    Built-in wins on name conflict (D64). Broken entry-point adapters are
    logged + skipped so one bad third-party package can't kill the CLI.
    """
    result = _load_builtins()
    for ep in entry_points(group="octopus.adapters"):
        if ep.name in result:
            log.warning(
                "third-party adapter %r conflicts with built-in; skipping",
                ep.name,
            )
            continue
        try:
            result[ep.name] = ep.load()
        except Exception as exc:
            log.warning(
                "failed to load third-party adapter %r: %s",
                ep.name, exc,
            )
            continue
    return result


def get_adapter_class(name: str) -> type[Adapter] | None:
    """Look up one adapter by name. Returns None if not registered."""
    return load_registry().get(name)


def registered_names() -> list[str]:
    """Sorted list of all registered adapter names."""
    return sorted(load_registry().keys())

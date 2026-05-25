"""OctopusApp — Textual app shell.

Boots into FocusScreen. `1`/`2` switch between Focus and Board modes.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

from octopus.fs.io import read_activity
from octopus.tui.board import BoardScreen
from octopus.tui.focus import FocusScreen


class OctopusApp(App):
    """Top-level Textual app for `octopus tui`."""

    TITLE = "octopus"
    SUB_TITLE = "tui"

    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, activity_root: Path) -> None:
        super().__init__()
        self._activity_root = activity_root
        activity_md = activity_root / ".octopus" / "activity.md"
        activity, _ = read_activity(activity_md)
        self._activity_title = activity.title or activity_root.name

    def on_mount(self) -> None:
        self.push_screen(FocusScreen(self._activity_title, self._activity_root))

    # ── mode switching (called by screens) ──────────────────────────────

    def switch_to_focus(self) -> None:
        # Swap the top screen for a fresh FocusScreen. Pop any modals first.
        self._swap_top(FocusScreen(self._activity_title, self._activity_root))

    def switch_to_board(self) -> None:
        self._swap_top(BoardScreen(self._activity_title, self._activity_root))

    def _swap_top(self, new_screen) -> None:
        """Pop any modals + the current root screen, then push a fresh one.

        Textual 8.x's `switch_screen` requires a result callback on the
        outgoing screen — our root screens are pushed without one (via
        `push_screen` in `on_mount`), so `switch_screen` blows up with
        `IndexError: pop from empty list`. Avoid by popping then pushing.
        """
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(new_screen)

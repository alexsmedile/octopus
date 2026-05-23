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
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.switch_screen(FocusScreen(self._activity_title, self._activity_root))

    def switch_to_board(self) -> None:
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.switch_screen(BoardScreen(self._activity_title, self._activity_root))

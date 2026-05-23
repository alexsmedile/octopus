"""HelpOverlay — modal showing the full keymap.

Triggered by `?` from Focus or Board. Esc closes.
"""

from __future__ import annotations

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

# Two-column groups: (key, description)
_GROUPS = [
    ("Navigation", [
        ("←  →",  "move between quadrants / columns"),
        ("↑  ↓",  "move within a list (jumps quadrants at edges)"),
        ("Tab",   "next pane"),
        ("S-Tab", "previous pane"),
        ("Enter", "open task detail"),
        ("Esc",   "close overlay"),
    ]),
    ("Modes", [
        ("1", "Focus mode (BACKLOG / NOW / NEXT)"),
        ("2", "Board mode (backlog → next → now → done)"),
    ]),
    ("Mutations", [
        ("n", "capture new task into focused pane"),
        ("m", "advance task one step along the pipeline"),
        ("M", "move to a chosen bucket"),
        ("f", "finish task"),
        ("d", "drop task (with confirm)"),
        ("p", "toggle pin"),
        ("e", "open task in $EDITOR"),
        ("s", "start a session"),
        ("S", "start session with title"),
    ]),
    ("View", [
        ("/", "filter visible tasks by title substring"),
        ("r", "refresh from index"),
        ("?", "this help"),
        ("q", "quit"),
    ]),
]


class HelpOverlay(ModalScreen[None]):
    """Help overlay — Esc / ? close."""

    BINDINGS = [
        Binding("escape", "dismiss_overlay", "close", show=False),
        Binding("?", "dismiss_overlay", "close", show=False),
        Binding("q", "dismiss_overlay", "close", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield VerticalScroll(
            Static(self._render(), id="help-body"),
            id="help-modal",
            classes="overlay",
        )

    def _render(self) -> Group:
        lines: list[Text] = []
        title = Text("Octopus — keymap", style="bold #CBA6F7")
        lines.append(title)
        lines.append(Text(""))

        for group_name, entries in _GROUPS:
            header = Text(group_name, style="bold #F5F5F7")
            lines.append(header)
            for key, desc in entries:
                row = Text()
                row.append(f"  {key:<8}", style="bold #89DCEB")
                row.append(desc, style="#F5F5F7")
                lines.append(row)
            lines.append(Text(""))

        hint = Text("Press Esc or ? to close", style="dim")
        lines.append(hint)
        return Group(*lines)

    def action_dismiss_overlay(self) -> None:
        self.dismiss(None)

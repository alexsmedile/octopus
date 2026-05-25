"""Small modal prompts used by FocusScreen and BoardScreen mutations.

Design language matches `edit_modal.py` and the main view:
- Heavy borders (lavender outer frame, `#CBA6F7`).
- Title in `border-title`, no Static title row.
- Hints rendered as chip strip in a docked footer (same vocabulary as
  `keymap_bar.py`).
- Flexible sizing — width/height as percentages with `min-*` floors so
  the modal stays readable on small terminals.
- Text input uses `_OctopusInput` for macOS-native alt+arrow word jump.

Modals:
- ConfirmModal     — y/n for destructive `d` drop and similar.
- InputModal       — single-line text prompt (used by `n` capture, `g` go-to,
                     `b` block-reason, `S` titled-session).
- BucketPickerModal — pick a bucket from TASK_BUCKETS for `M`.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from octopus.core.models import TASK_BUCKETS


def _chip(out: Text, key: str, desc: str, color: str) -> None:
    """Append a key/description chip pair to `out` — same vocab as keymap_bar."""
    out.append(f" {key} ", style=f"bold {color} on #16171E")
    out.append(" ", style="on #0F1014")
    out.append(desc, style="#8A8D9A on #0F1014")
    out.append("   ", style="on #0F1014")


class _OctopusInput(Input):
    """Input with macOS-native alt+arrow word navigation.

    Stock Textual binds word-jump to ctrl+arrow; this adds alt+arrow so
    text entry matches the OS-level shortcut convention.
    """

    BINDINGS = [
        Binding("alt+left", "cursor_left_word", "word left", show=False),
        Binding("alt+right", "cursor_right_word", "word right", show=False),
        Binding("alt+backspace", "delete_left_word", "delete word", show=False),
    ]


class ConfirmModal(ModalScreen[bool]):
    """Yes/No confirmation. Returns True on 'y', False on 'n'/Esc."""

    BINDINGS = [
        Binding("y", "yes", "yes", show=False),
        Binding("Y", "yes", "yes", show=False),
        Binding("n", "no", "no", show=False),
        Binding("N", "no", "no", show=False),
        Binding("escape", "no", "cancel", show=False),
    ]

    def __init__(self, message: str, *, title: str = "confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Container(id="confirm-modal", classes="prompt-modal"):
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-footer", classes="prompt-footer"):
                yield Static(self._hint_text(), classes="prompt-hint")

    def _hint_text(self) -> Text:
        out = Text()
        _chip(out, "y", "confirm", "#F38BA8")
        _chip(out, "n", "cancel", "#3A3D48")
        _chip(out, "ESC", "cancel", "#3A3D48")
        return out

    def on_mount(self) -> None:
        modal = self.query_one("#confirm-modal")
        modal.border_title = f"◇ {self._title}"

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class InputModal(ModalScreen[str | None]):
    """Single-line input prompt. Returns the entered string, or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel", show=False, priority=True),
    ]

    def __init__(self, label: str, *, placeholder: str = "") -> None:
        super().__init__()
        self._label = label
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        self._input = _OctopusInput(placeholder=self._placeholder, id="input-field")
        with Container(id="input-modal", classes="prompt-modal"):
            yield self._input
            with Horizontal(id="input-footer", classes="prompt-footer"):
                yield Static(self._hint_text(), classes="prompt-hint")

    def _hint_text(self) -> Text:
        out = Text()
        _chip(out, "CR", "commit", "#86EFAC")
        _chip(out, "ESC", "cancel", "#3A3D48")
        _chip(out, "⌥←→", "word", "#3A3D48")
        return out

    def on_mount(self) -> None:
        modal = self.query_one("#input-modal")
        modal.border_title = f"◇ {self._label}"
        self.set_focus(self._input)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = (event.value or "").strip()
        self.dismiss(value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class BucketPickerModal(ModalScreen[str | None]):
    """Pick a bucket from TASK_BUCKETS. Returns the chosen bucket or None."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel", show=False),
        Binding("enter", "select", "select", show=False),
    ]

    # Bucket → color, mirrors main-view panel colors.
    _BUCKET_COLORS = {
        "backlog": "#8A8D9A",
        "next": "#89DCEB",
        "now": "#F38BA8",
        "done": "#A6E3A1",
        "dropped": "#F38BA8",
    }

    def __init__(self, current: str | None = None) -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        # Stable, pipeline-order list (not alphabetical).
        order = ["backlog", "next", "now", "done", "dropped"]
        ordered = [b for b in order if b in TASK_BUCKETS]
        self._buckets = ordered

        items: list[ListItem] = []
        for b in ordered:
            color = self._BUCKET_COLORS.get(b, "#F5F5F7")
            row = Text()
            row.append("  ◇ ", style=color)
            row.append(b, style=f"bold {color}")
            if b == self._current:
                row.append("   ← current", style="#8A8D9A")
            items.append(ListItem(Static(row)))
        self._list = ListView(*items, id="picker-list")

        with Container(id="picker-modal", classes="prompt-modal"):
            yield self._list
            with Horizontal(id="picker-footer", classes="prompt-footer"):
                yield Static(self._hint_text(), classes="prompt-hint")

    def _hint_text(self) -> Text:
        out = Text()
        _chip(out, "↑↓", "navigate", "#3A3D48")
        _chip(out, "CR", "select", "#86EFAC")
        _chip(out, "ESC", "cancel", "#3A3D48")
        return out

    def on_mount(self) -> None:
        modal = self.query_one("#picker-modal")
        modal.border_title = "◇ move to bucket"
        # Land cursor on the current bucket if present.
        if self._current and self._current in self._buckets:
            self._list.index = self._buckets.index(self._current)
        self.set_focus(self._list)

    def action_select(self) -> None:
        idx = self._list.index
        if idx is None or idx < 0 or idx >= len(self._buckets):
            self.dismiss(None)
            return
        self.dismiss(self._buckets[idx])

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.action_select()

"""Small modal prompts used by FocusScreen mutations.

- ConfirmModal: y/n for destructive `d` drop.
- InputModal: single-line text prompt (used by inline capture `n`).
- BucketPickerModal: pick one of TASK_BUCKETS for `M`.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static

from octopus.core.models import TASK_BUCKETS


class ConfirmModal(ModalScreen[bool]):
    """Yes/No confirmation. Returns True on 'y', False on 'n'/Esc."""

    BINDINGS = [
        Binding("y", "yes", "yes", show=True),
        Binding("n", "no", "no", show=True),
        Binding("escape", "no", "cancel", show=True),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self._message, classes="overlay-title"),
            Static("  [#F38BA8 bold]y[/] confirm    [#8A8D9A]n / Esc[/] cancel",
                   classes="overlay-hint"),
            classes="overlay",
        )

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class InputModal(ModalScreen[str | None]):
    """Single-line input prompt. Returns the entered string, or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel", show=True),
    ]

    def __init__(self, label: str, *, placeholder: str = "") -> None:
        super().__init__()
        self._label = label
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        self._input = Input(placeholder=self._placeholder)
        yield Container(
            Static(self._label, classes="overlay-title"),
            self._input,
            Static("  [#F38BA8 bold]Enter[/] commit    [#8A8D9A]Esc[/] cancel",
                   classes="overlay-hint"),
            classes="overlay",
        )

    def on_mount(self) -> None:
        self.set_focus(self._input)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = (event.value or "").strip()
        self.dismiss(value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class BucketPickerModal(ModalScreen[str | None]):
    """Pick a bucket from TASK_BUCKETS. Returns the chosen bucket or None."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel", show=True),
        Binding("enter", "select", "select", show=False),
    ]

    def __init__(self, current: str | None = None) -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        # Stable, pipeline-order list (not alphabetical).
        order = ["backlog", "next", "now", "done", "dropped"]
        ordered = [b for b in order if b in TASK_BUCKETS]
        self._list = ListView(
            *(
                ListItem(Label(f"  {b}" + ("   ← current" if b == self._current else "")))
                for b in ordered
            )
        )
        self._buckets = ordered
        yield Container(
            Static("Move to bucket", classes="overlay-title"),
            self._list,
            Static("  [#F38BA8 bold]Enter[/] select    [#8A8D9A]Esc[/] cancel",
                   classes="overlay-hint"),
            classes="overlay",
        )

    def on_mount(self) -> None:
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

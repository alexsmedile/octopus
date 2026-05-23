"""FilterBar — bottom slide-up input for live title-substring filtering.

Triggered by `/`. Esc cancels and restores; Enter commits and closes the bar
but keeps the filter applied until cleared (Esc again, or by typing in the
empty filter).

Reports text changes via a callback so the screen can re-fill its lists in
real time.
"""

from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class FilterBar(ModalScreen[str | None]):
    """Modal filter bar. Returns the committed string or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "cancel", show=False),
    ]

    def __init__(
        self,
        *,
        initial: str = "",
        on_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._initial = initial
        self._on_change = on_change

    def compose(self) -> ComposeResult:
        self._input = Input(
            value=self._initial,
            placeholder="filter by title…",
            id="filter-input",
        )
        yield Horizontal(
            Static("/", id="filter-prefix"),
            self._input,
            id="filter-bar",
        )

    def on_mount(self) -> None:
        self._input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._on_change is not None:
            try:
                self._on_change(event.value)
            except Exception:
                pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        # Tell caller filter was cleared.
        if self._on_change is not None:
            try:
                self._on_change("")
            except Exception:
                pass
        self.dismiss(None)

"""Tall header bar with the pixel-accurate octo mascot + rich status block.

7 rows tall. Left: 16-px-wide mascot rendered via rich-pixels half-blocks.
Right: title, activity, path, session, counts, mode tabs — stacked.

    ▄▄▄▄▄▄▄▄▄▄    OCTOPUS                                      1 focus  2 board
    ██████████    demo activity
    ████████████  ⌂ ~/vault/data/skills_db/octopus
    ██●●██●●████  ◆ session 12m  ·  3 now  ·  7 next  ·  2 blocked
    ████████████  ⟳ ready
    ██ ██ ██ ██
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from octopus.tui.icons import HOME, SESSION, SPINNER
from octopus.tui.mascot import (
    TICK_INTERVAL_MS,
    TICK_INTERVAL_S,
    MascotController,
    render_grid,
)


@dataclass(frozen=True)
class HeaderCounts:
    now: int = 0
    next_: int = 0
    blocked: int = 0


class _Mascot(Static):
    """Animated mascot — runs Calm-A by default, plays one-shot animations
    when `trigger()` is called.

    See #31 PLAN.md for the spec. The controller logic is in
    `mascot.MascotController`; this widget just owns the Textual interval
    and re-renders on each tick.
    """

    def __init__(self) -> None:
        super().__init__(id="header-mascot")
        self._controller = MascotController()
        # First render — set initial frame so the widget isn't empty before
        # the first tick.
        self.update(render_grid(self._controller.current_grid()))

    def on_mount(self) -> None:
        # Drive the controller at 50ms granularity. Each tick advances the
        # body / blink / animation state and re-renders if the grid changed.
        self._last_grid = self._controller.current_grid()
        self.set_interval(TICK_INTERVAL_S, self._tick)

    def _tick(self) -> None:
        self._controller.tick(TICK_INTERVAL_MS)
        grid = self._controller.current_grid()
        # Only re-render when the grid actually changes — cheap diff to
        # avoid burning cycles repainting identical frames.
        if grid != self._last_grid:
            self._last_grid = grid
            self.update(render_grid(grid))

    def trigger(self, animation_name: str) -> bool:
        """Public API for verbs to trigger an animation. Returns True if the
        trigger was accepted (state was idle), False otherwise.
        """
        return self._controller.trigger(animation_name)


class _HeaderText(Static):
    """Right side of the header — title, path, status, mode tabs."""

    DEFAULT_CSS = ""

    title_text: reactive[str] = reactive("OCTOPUS")
    activity_name: reactive[str] = reactive("")
    cwd_path: reactive[str] = reactive("")
    session_label: reactive[str] = reactive("")
    state_label: reactive[str] = reactive("ready")
    state_busy: reactive[bool] = reactive(False)
    counts: reactive[HeaderCounts] = reactive(HeaderCounts())
    active_mode: reactive[str] = reactive("focus")

    def __init__(self) -> None:
        super().__init__(id="header-text")

    def render(self) -> Group:
        # Row 0: title (left) + mode tabs (right) on the same line.
        line0 = Text(no_wrap=True, overflow="ellipsis")
        line0.append(self.title_text, style="bold #CBA6F7")
        # Pad to push tabs right.
        try:
            width = self.size.width or 80
        except Exception:
            width = 80
        tabs = Text()
        for i, (key, label) in enumerate((("focus", "1 focus"), ("board", "2 board"))):
            if i:
                tabs.append("   ")
            if key == self.active_mode:
                tabs.append(f" {label} ", style="bold #0F1014 on #CBA6F7")
            else:
                tabs.append(f" {label} ", style="#8A8D9A")
        slack = max(2, width - line0.cell_len - tabs.cell_len)
        line0.append(" " * slack)
        line0.append_text(tabs)

        # Row 1: activity name.
        line1 = Text(no_wrap=True, overflow="ellipsis")
        line1.append(self.activity_name or "—", style="#F5F5F7")

        # Row 2: CWD path.
        line2 = Text(no_wrap=True, overflow="ellipsis")
        line2.append(f"{HOME} ", style="dim")
        line2.append(self.cwd_path or "—", style="#8A8D9A")

        # Row 3: session + counts.
        line3 = Text(no_wrap=True, overflow="ellipsis")
        if self.session_label:
            line3.append(f"{SESSION} session {self.session_label}", style="#6DD3A7")
            line3.append("  ·  ", style="dim")
        c = self.counts
        parts = []
        if c.now:
            parts.append(f"{c.now} now")
        if c.next_:
            parts.append(f"{c.next_} next")
        if c.blocked:
            parts.append(f"{c.blocked} blocked")
        if parts:
            line3.append(" · ".join(parts), style="dim")
        elif not self.session_label:
            line3.append("no session", style="dim")

        # Row 4: state.
        state_style = "#F5C76E" if self.state_busy else "dim"
        line4 = Text(no_wrap=True)
        line4.append(f"{SPINNER} {self.state_label}", style=state_style)

        return Group(line0, line1, line2, line3, line4)


class HeaderBar(Widget):
    """Tall header bar — mascot left, rich status right."""

    DEFAULT_CSS = ""

    def __init__(self) -> None:
        super().__init__(id="header-bar")
        self._text = _HeaderText()
        self._mascot = _Mascot()

    def compose(self) -> ComposeResult:
        yield Horizontal(self._mascot, self._text)

    # ── public API ───────────────────────────────────────────────────

    @property
    def title_text(self) -> str:
        return self._text.title_text

    @title_text.setter
    def title_text(self, value: str) -> None:
        self._text.title_text = value

    def set_activity(self, value: str) -> None:
        self._text.activity_name = value

    def set_cwd(self, value: str) -> None:
        self._text.cwd_path = value

    def set_subtitle(self, value: str) -> None:
        # Backwards-compat: treat subtitle as activity name.
        self._text.activity_name = value

    def set_session(self, value: str) -> None:
        self._text.session_label = value

    def set_state(self, label: str, *, busy: bool = False) -> None:
        self._text.state_label = label
        self._text.state_busy = busy

    def set_counts(self, now: int, next_: int, blocked: int) -> None:
        self._text.counts = HeaderCounts(now=now, next_=next_, blocked=blocked)

    def set_mode(self, mode: str) -> None:
        self._text.active_mode = mode

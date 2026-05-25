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
    backlog: int = 0
    now: int = 0
    next_: int = 0
    done: int = 0
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
    display_mode: reactive[str] = reactive("full")  # full | compact | slim

    def __init__(self) -> None:
        super().__init__(id="header-text")

    def _render_tabs(self) -> Text:
        tabs = Text()
        for i, (key, label) in enumerate((("focus", "1 focus"), ("board", "2 board"))):
            if i:
                tabs.append("   ")
            if key == self.active_mode:
                tabs.append(f" {label} ", style="bold #0F1014 on #CBA6F7")
            else:
                tabs.append(f" {label} ", style="#8A8D9A")
        return tabs

    def _render_counts(self) -> Text:
        c = self.counts
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append(f"· {c.backlog}", style="#8A8D9A")
        line.append("   ", style="dim")
        line.append(f"◐ {c.now}", style="#F38BA8")
        line.append("   ", style="dim")
        line.append(f"○ {c.next_}", style="#89DCEB")
        line.append("   ", style="dim")
        line.append(f"● {c.done}", style="#A6E3A1")
        if c.blocked:
            line.append("   ", style="dim")
            line.append(f"! {c.blocked}", style="#FAB387")
        return line

    def render(self) -> Group:
        mode = self.display_mode
        if mode == "slim":
            return Group(self._render_slim())
        if mode == "compact":
            return self._render_compact()
        return self._render_full()

    def _render_slim(self) -> Text:
        # One row: TITLE · activity · counts · …pad… · tabs
        try:
            width = self.size.width or 80
        except Exception:
            width = 80
        left = Text(no_wrap=True, overflow="ellipsis")
        left.append(self.title_text, style="bold #CBA6F7")
        if self.activity_name:
            left.append("  ·  ", style="dim")
            left.append(self.activity_name, style="#F5F5F7")
        left.append("  ·  ", style="dim")
        left.append_text(self._render_counts())
        tabs = self._render_tabs()
        slack = max(2, width - left.cell_len - tabs.cell_len)
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append_text(left)
        line.append(" " * slack)
        line.append_text(tabs)
        return line

    def _render_compact(self) -> Group:
        try:
            width = self.size.width or 80
        except Exception:
            width = 80
        # Row 0: title + tabs
        line0 = Text(no_wrap=True, overflow="ellipsis")
        line0.append(self.title_text, style="bold #CBA6F7")
        if self.activity_name:
            line0.append("  ·  ", style="dim")
            line0.append(self.activity_name, style="#F5F5F7")
        tabs = self._render_tabs()
        slack = max(2, width - line0.cell_len - tabs.cell_len)
        line0.append(" " * slack)
        line0.append_text(tabs)
        # Row 1: path
        line1 = Text(no_wrap=True, overflow="ellipsis")
        line1.append(f"{HOME} ", style="dim")
        line1.append(self.cwd_path or "—", style="#8A8D9A")
        # Row 2: counts
        return Group(line0, line1, self._render_counts())

    def _render_full(self) -> Group:
        try:
            width = self.size.width or 80
        except Exception:
            width = 80
        # Row 0: title + tabs
        line0 = Text(no_wrap=True, overflow="ellipsis")
        line0.append(self.title_text, style="bold #CBA6F7")
        tabs = self._render_tabs()
        slack = max(2, width - line0.cell_len - tabs.cell_len)
        line0.append(" " * slack)
        line0.append_text(tabs)
        # Row 1: activity name
        line1 = Text(no_wrap=True, overflow="ellipsis")
        line1.append(self.activity_name or "—", style="#F5F5F7")
        # Row 2: cwd
        line2 = Text(no_wrap=True, overflow="ellipsis")
        line2.append(f"{HOME} ", style="dim")
        line2.append(self.cwd_path or "—", style="#8A8D9A")
        # Row 3: counts
        line3 = self._render_counts()
        # Row 4: session + state
        line4 = Text(no_wrap=True)
        if self.session_label:
            line4.append(f"{SESSION} session {self.session_label}", style="#89DCEB")
            line4.append("  ·  ", style="dim")
        state_style = "#F5C76E" if self.state_busy else "dim"
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

    def set_counts(
        self,
        now: int,
        next_: int,
        blocked: int,
        backlog: int = 0,
        done: int = 0,
    ) -> None:
        self._text.counts = HeaderCounts(
            backlog=backlog, now=now, next_=next_, done=done, blocked=blocked
        )

    def set_mode(self, mode: str) -> None:
        self._text.active_mode = mode

    # ── Header display mode (full / compact / slim) ─────────────────────

    _MODE_HEIGHTS = {"full": 7, "compact": 3, "slim": 1}
    _MODE_CYCLE = ("full", "compact", "slim")

    @property
    def display_mode(self) -> str:
        return self._text.display_mode

    def set_display_mode(self, mode: str) -> None:
        if mode not in self._MODE_HEIGHTS:
            return
        self._text.display_mode = mode
        height = self._MODE_HEIGHTS[mode]
        self.styles.height = height
        # Mascot only appears in full mode; hide otherwise to reclaim width.
        self._mascot.styles.display = "block" if mode == "full" else "none"
        self._text.refresh()

    def cycle_display_mode(self) -> str:
        cur = self._text.display_mode
        try:
            i = self._MODE_CYCLE.index(cur)
        except ValueError:
            i = 0
        nxt = self._MODE_CYCLE[(i + 1) % len(self._MODE_CYCLE)]
        self.set_display_mode(nxt)
        return nxt

    @staticmethod
    def auto_mode_for_width(width: int) -> str:
        if width < 80:
            return "slim"
        if width < 120:
            return "compact"
        return "full"

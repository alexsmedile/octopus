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

from octopus.tui.icons import ACTIVITY, HOME, REPO, SESSION_RUN, SPINNER
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


class _MascotSmall(Static):
    """Smaller, non-animated mascot for Mid header mode."""

    def __init__(self) -> None:
        super().__init__(id="header-mascot-small")
        from octopus.tui.mascot import render_mascot_small
        self.update(render_mascot_small())
        self.styles.display = "none"


def _tabs_text(active_mode: str) -> Text:
    tabs = Text()
    for i, (key, label) in enumerate((("focus", "1 focus"), ("board", "2 board"))):
        if i:
            tabs.append("   ")
        if key == active_mode:
            tabs.append(f" {label} ", style="bold #0F1014 on #CBA6F7")
        else:
            tabs.append(f" {label} ", style="#8A8D9A")
    return tabs


def _counts_cells(counts: HeaderCounts) -> list[tuple[str, str, str]]:
    """Return [(glyph_chunk, label, color), …] in display order.
    `glyph_chunk` already includes the number (e.g. "· 12")."""
    cells = [
        (f"· {counts.backlog}", "backlog", "#8A8D9A"),
        (f"◐ {counts.now}", "now",     "#F38BA8"),
        (f"○ {counts.next_}", "next",    "#89DCEB"),
        (f"● {counts.done}", "done",    "#A6E3A1"),
    ]
    if counts.blocked:
        cells.append((f"! {counts.blocked}", "blocked", "#FAB387"))
    return cells


def _counts_text(counts: HeaderCounts) -> Text:
    """Single-row glyphs + numbers (no labels). Used by Compact and Slim."""
    line = Text(no_wrap=True, overflow="ellipsis")
    for i, (chunk, _label, color) in enumerate(_counts_cells(counts)):
        if i:
            line.append("   ", style="dim")
        line.append(chunk, style=color)
    return line


def _counts_two_rows(counts: HeaderCounts, *, with_labels: bool) -> tuple[Text, Text]:
    """Two-row layout for Full mode. Glyphs+numbers on row 1, optional labels
    on row 2 (aligned under each glyph cell, same color, dim)."""
    cells = _counts_cells(counts)
    # Each cell pads to max(glyph_width, label_width) so labels sit under glyphs.
    widths = [max(len(c), len(l)) for c, l, _ in cells]
    gap = "   "

    row_glyphs = Text(no_wrap=True, overflow="ellipsis")
    row_labels = Text(no_wrap=True, overflow="ellipsis")
    for i, ((chunk, label, color), w) in enumerate(zip(cells, widths, strict=False)):
        if i:
            row_glyphs.append(gap, style="dim")
            row_labels.append(gap, style="dim")
        row_glyphs.append(chunk.ljust(w), style=color)
        if with_labels:
            row_labels.append(label.ljust(w), style=f"{color} dim")
        else:
            row_labels.append(" " * w)
    return row_glyphs, row_labels


# ASCII wordmark used in Full mode (3 rows). Compact/Slim use plain "OCTOPUS".
_WORDMARK_FULL = (
    "█▀█ █▀▀ ▀█▀ █▀█ █▀█ █ █ █▀",
    "█ █ █    █  █ █ █▀▀ █ █ ▀▀▄",
    "▀▀▀ ▀▀▀  ▀  ▀▀▀ ▀    ▀  ▀▀▀",
)


class _HeaderLeft(Static):
    """Left text column — title, activity, path, session, state."""

    title_text: reactive[str] = reactive("OCTOPUS")
    activity_name: reactive[str] = reactive("")
    cwd_path: reactive[str] = reactive("")
    session_label: reactive[str] = reactive("")
    state_label: reactive[str] = reactive("ready")
    state_busy: reactive[bool] = reactive(False)
    repo_name: reactive[str] = reactive("")
    display_mode: reactive[str] = reactive("full")  # full | mid | compact | slim
    # Mirrored from the right column so Slim mode can render inline.
    counts: reactive[HeaderCounts] = reactive(HeaderCounts())
    active_mode: reactive[str] = reactive("focus")

    def __init__(self) -> None:
        super().__init__(id="header-left")

    def render(self) -> Group:
        if self.display_mode == "slim":
            return Group(self._render_slim_combined())

        # Activity row (white) — `◇ activity-name   ⬡ repo-name`.
        # Repo glyph + name only appear when the activity root is a git repo;
        # filled variants are reserved (see D91).
        activity = Text(no_wrap=True, overflow="ellipsis")
        if self.activity_name:
            activity.append(f"{ACTIVITY} ", style="#CBA6F7")
            activity.append(self.activity_name, style="#F5F5F7")
            if self.repo_name:
                activity.append("   ", style="dim")
                activity.append(f"{REPO} ", style="#CBA6F7")
                activity.append(self.repo_name, style="#8A8D9A")

        # Path (dim).
        path = Text(no_wrap=True, overflow="ellipsis")
        path.append(f"{HOME} ", style="dim")
        path.append(self.cwd_path or "—", style="#8A8D9A")

        if self.display_mode == "compact":
            # 3 rows:
            #   row 0: OCTOPUS  ·  ◇ activity  ·  ⬡ repo
            #   row 1: ⌂ path
            #   row 2: ⟳ ready / ◆ session …
            combined = Text(no_wrap=True, overflow="ellipsis")
            combined.append(self.title_text, style="bold #CBA6F7")
            if self.activity_name:
                combined.append("  ·  ", style="dim")
                combined.append(f"{ACTIVITY} ", style="#CBA6F7")
                combined.append(self.activity_name, style="#F5F5F7")
            if self.repo_name:
                combined.append("  ·  ", style="dim")
                combined.append(f"{REPO} ", style="#CBA6F7")
                combined.append(self.repo_name, style="#8A8D9A")

            state_compact = Text(no_wrap=True)
            if self.session_label:
                state_compact.append(
                    f"{SESSION_RUN} session {self.session_label}", style="#89DCEB"
                )
                state_compact.append("  ·  ", style="dim")
            state_compact_style = "#F5C76E" if self.state_busy else "dim"
            state_compact.append(
                f"{SPINNER} {self.state_label}", style=state_compact_style
            )
            return Group(combined, path, state_compact)

        # State row (used by mid + full).
        state = Text(no_wrap=True)
        if self.session_label:
            state.append(f"{SESSION_RUN} session {self.session_label}", style="#89DCEB")
            state.append("  ·  ", style="dim")
        state_style = "#F5C76E" if self.state_busy else "dim"
        state.append(f"{SPINNER} {self.state_label}", style=state_style)

        if self.display_mode == "mid":
            # 5 rows: blank + plain title + activity + path + state.
            title = Text(no_wrap=True, overflow="ellipsis")
            title.append(self.title_text, style="bold #CBA6F7")
            return Group(Text(""), title, activity, path, state)

        # Full mode: blank + ASCII wordmark (3 rows) + activity + path + state.
        wm = [Text(line, style="bold #CBA6F7", no_wrap=True) for line in _WORDMARK_FULL]
        return Group(Text(""), *wm, activity, path, state)

    def _render_slim_combined(self) -> Text:
        """Slim mode renders everything in this single column — the right
        column hides itself."""
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append(self.title_text, style="bold #CBA6F7")
        line.append("  ·  ", style="dim")
        line.append_text(_counts_text(self.counts))
        line.append("  ·  ", style="dim")
        line.append_text(_tabs_text(self.active_mode))
        return line


class _HeaderRight(Static):
    """Right text column — tabs (top), counts (bottom)."""

    counts: reactive[HeaderCounts] = reactive(HeaderCounts())
    active_mode: reactive[str] = reactive("focus")
    display_mode: reactive[str] = reactive("full")

    def __init__(self) -> None:
        super().__init__(id="header-right")

    def render(self) -> Group:
        if self.display_mode == "slim":
            # Slim collapses into the left column.
            return Group(Text(""))

        tabs = _tabs_text(self.active_mode)

        if self.display_mode == "compact":
            # 3 rows: tabs, glyphs, numbers — no labels (no vertical room).
            counts_row, _ = _counts_two_rows(self.counts, with_labels=False)
            return Group(tabs, Text(""), counts_row)

        # Full / Mid: tabs, blank, glyphs row, labels row (4 rows).
        glyphs, labels = _counts_two_rows(self.counts, with_labels=True)
        return Group(tabs, Text(""), glyphs, labels)


class HeaderBar(Widget):
    """Tall header bar — mascot left, rich status right."""

    DEFAULT_CSS = ""

    def __init__(self) -> None:
        super().__init__(id="header-bar")
        self._left = _HeaderLeft()
        self._right = _HeaderRight()
        self._mascot = _Mascot()
        self._mascot_small = _MascotSmall()

    def compose(self) -> ComposeResult:
        yield Horizontal(self._mascot, self._mascot_small, self._left, self._right)

    # ── public API ───────────────────────────────────────────────────

    @property
    def title_text(self) -> str:
        return self._left.title_text

    @title_text.setter
    def title_text(self, value: str) -> None:
        self._left.title_text = value

    def set_activity(self, value: str) -> None:
        self._left.activity_name = value

    def set_cwd(self, value: str) -> None:
        self._left.cwd_path = value

    def set_subtitle(self, value: str) -> None:
        # Backwards-compat: treat subtitle as activity name.
        self._left.activity_name = value

    def set_session(self, value: str) -> None:
        self._left.session_label = value

    def set_state(self, label: str, *, busy: bool = False) -> None:
        self._left.state_label = label
        self._left.state_busy = busy

    def set_counts(
        self,
        now: int,
        next_: int,
        blocked: int,
        backlog: int = 0,
        done: int = 0,
    ) -> None:
        counts = HeaderCounts(
            backlog=backlog, now=now, next_=next_, done=done, blocked=blocked
        )
        self._right.counts = counts
        self._left.counts = counts  # for slim-mode inline render

    def set_mode(self, mode: str) -> None:
        self._right.active_mode = mode
        self._left.active_mode = mode

    def set_repo_name(self, name: str) -> None:
        """Show `⬡ <name>` next to the activity name. Empty string hides it."""
        self._left.repo_name = (name or "").strip()

    def set_git_detected(self, detected: bool) -> None:
        # Back-compat shim: callers that only know "is this git or not" can
        # still call this; it clears the repo name when False. Prefer
        # set_repo_name(<basename>) for new code.
        if not detected:
            self._left.repo_name = ""

    # ── Header display mode (full / compact / slim) ─────────────────────

    _MODE_HEIGHTS = {"full": 7, "mid": 5, "compact": 3, "slim": 1}
    _MODE_CYCLE = ("full", "mid", "compact", "slim")

    @property
    def display_mode(self) -> str:
        return self._left.display_mode

    def set_display_mode(self, mode: str) -> None:
        if mode not in self._MODE_HEIGHTS:
            return
        self._left.display_mode = mode
        self._right.display_mode = mode
        height = self._MODE_HEIGHTS[mode]
        self.styles.height = height
        # Mascot variants: animated in Full, small static in Mid, hidden elsewhere.
        self._mascot.styles.display = "block" if mode == "full" else "none"
        self._mascot_small.styles.display = "block" if mode == "mid" else "none"
        # Right column hides in slim — slim renders everything in the left col.
        self._right.styles.display = "none" if mode == "slim" else "block"
        self._left.refresh()
        self._right.refresh()

    def cycle_display_mode(self) -> str:
        cur = self._left.display_mode
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
        if width < 110:
            return "compact"
        if width < 140:
            return "mid"
        return "full"

"""Status bar widget — three-zone layout docked at screen bottom.

Layout:

    ⌂ activity   ◆ session 12m   │   ⟳ ready · 3 now · 7 next · 2 blocked   │   ? help  q quit

Left:   activity name (with HOME glyph)
Center: session state + index state + bucket counts
Right:  static key hints (always visible)
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from octopus.tui.icons import HOME, SESSION, SPINNER


@dataclass(frozen=True)
class BucketCounts:
    now: int = 0
    next_: int = 0
    blocked: int = 0


class StatusBar(Static):
    """Bottom status bar. Reactive — update via the public setter methods."""

    DEFAULT_CSS = ""  # styled by theme.tcss via #status-bar

    activity_name: reactive[str] = reactive("")
    session_label: reactive[str] = reactive("")   # e.g. "12m" or "" when no session
    state_label: reactive[str] = reactive("ready")  # "ready" | "reindexing…" | etc.
    state_busy: reactive[bool] = reactive(False)
    counts: reactive[BucketCounts] = reactive(BucketCounts())

    def __init__(self) -> None:
        super().__init__(id="status-bar")

    def render(self) -> Text:
        left = Text()
        left.append(f"{HOME} ", style="dim")
        left.append(self.activity_name or "—", style="bold")

        center = Text()
        if self.session_label:
            center.append(f"{SESSION} session {self.session_label}", style="#6DD3A7")
            center.append("   │   ", style="dim")

        state_style = "#F5C76E" if self.state_busy else "dim"
        center.append(f"{SPINNER} {self.state_label}", style=state_style)

        c = self.counts
        if c.now or c.next_ or c.blocked:
            center.append("  ·  ", style="dim")
            parts = []
            if c.now:
                parts.append(f"{c.now} now")
            if c.next_:
                parts.append(f"{c.next_} next")
            if c.blocked:
                parts.append(f"{c.blocked} blocked")
            center.append(" · ".join(parts), style="dim")

        right = Text("? help  q quit", style="dim")

        # Compose with flexible spacing — Textual Static doesn't auto-stretch,
        # so pad the center to fill. Width is queried at render time.
        try:
            total_width = self.size.width or 100
        except Exception:
            total_width = 100

        left_str = left.plain
        center_str = center.plain
        right_str = right.plain

        # Layout: [left]   [center centered]   [right]
        # Compute pad so right hugs the right edge.
        used = len(left_str) + len(center_str) + len(right_str)
        slack = max(2, total_width - used)
        left_pad = slack // 2
        right_pad = slack - left_pad

        out = Text()
        out.append_text(left)
        out.append(" " * left_pad, style="dim")
        out.append_text(center)
        out.append(" " * right_pad, style="dim")
        out.append_text(right)
        return out

    # ── public setters (called from App / Screen) ──────────────────────

    def set_activity(self, name: str) -> None:
        self.activity_name = name

    def set_session(self, label: str) -> None:
        self.session_label = label

    def set_state(self, label: str, *, busy: bool = False) -> None:
        self.state_label = label
        self.state_busy = busy

    def set_counts(self, now: int, next_: int, blocked: int) -> None:
        self.counts = BucketCounts(now=now, next_=next_, blocked=blocked)

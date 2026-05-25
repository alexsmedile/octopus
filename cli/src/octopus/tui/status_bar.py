"""Status bar widget — docked at screen bottom.

Layout (v3 design):

    id: my-project-4f2a                                  ● synced · v0.9.6

Left:   activity-id (canonical, no path duplication — header has the path)
Right:  sync indicator + app version

Counters moved to the header. State/session label optional (shown center
when present, e.g. while reindexing).
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from octopus import __version__


@dataclass(frozen=True)
class BucketCounts:
    now: int = 0
    next_: int = 0
    blocked: int = 0


class StatusBar(Static):
    """Bottom status bar. Reactive — update via the public setter methods."""

    DEFAULT_CSS = ""  # styled by theme.tcss via #status-bar

    activity_id: reactive[str] = reactive("")
    session_label: reactive[str] = reactive("")
    state_label: reactive[str] = reactive("ready")
    state_busy: reactive[bool] = reactive(False)
    counts: reactive[BucketCounts] = reactive(BucketCounts())  # kept for back-compat

    def __init__(self) -> None:
        super().__init__(id="status-bar")

    def render(self) -> Text:
        # Left: activity id.
        left = Text()
        left.append("id: ", style="dim")
        left.append(self.activity_id or "—", style="#8A8D9A")

        # Center (optional): non-ready state ("reindexing…") or active session.
        center = Text()
        if self.state_busy and self.state_label and self.state_label != "ready":
            center.append(f"⟳ {self.state_label}", style="#F5C76E")
        elif self.session_label:
            center.append(f"◆ session {self.session_label}", style="#89DCEB")

        # Right: sync indicator + version.
        right = Text()
        if self.state_busy:
            right.append("◐ syncing", style="#F5C76E")
        else:
            right.append("● synced", style="#A6E3A1")
        right.append(" · ", style="dim")
        right.append(f"v{__version__}", style="#8A8D9A")

        # Three-zone layout.
        try:
            total_width = self.size.width or 100
        except Exception:
            total_width = 100

        left_len = left.cell_len
        center_len = center.cell_len
        right_len = right.cell_len

        used = left_len + center_len + right_len
        slack = max(2, total_width - used)
        if center_len:
            left_pad = slack // 2
            right_pad = slack - left_pad
        else:
            left_pad = slack
            right_pad = 0

        out = Text()
        out.append_text(left)
        out.append(" " * left_pad, style="dim")
        out.append_text(center)
        out.append(" " * right_pad, style="dim")
        out.append_text(right)
        return out

    # ── public setters ─────────────────────────────────────────────────

    def set_activity(self, name: str) -> None:
        # Back-compat shim — older callers passed a display name; treat as id.
        self.activity_id = name

    def set_activity_id(self, value: str) -> None:
        self.activity_id = value

    def set_session(self, label: str) -> None:
        self.session_label = label

    def set_state(self, label: str, *, busy: bool = False) -> None:
        self.state_label = label
        self.state_busy = busy

    def set_counts(self, now: int, next_: int, blocked: int) -> None:
        # Kept for back-compat — counts now live in the header. We accept the
        # call so existing callers don't break, but render ignores them.
        self.counts = BucketCounts(now=now, next_=next_, blocked=blocked)

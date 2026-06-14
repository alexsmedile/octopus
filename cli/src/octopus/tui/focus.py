"""FocusScreen — the daily-driver view.

Three-quadrant layout:

    ┌──── BACKLOG ────────┬──── NOW ──────────────┐
    │  ▸ task A           │  ▸ task X   <chips>   │
    │    task B           │    task Y             │
    │    task C           ├──── NEXT ─────────────┤
    │    task D           │  ▸ task M             │
    │    …                │    task N             │
    └─────────────────────┴───────────────────────┘
    [status bar]

Arrow keys move within a list AND jump across quadrants when hitting an edge:
  - In BACKLOG (left): `→` jumps to NOW. Up/down stays in BACKLOG (full height).
  - In NOW (top-right): `↑` stays at top, `↓` jumps to NEXT when past last row;
                        `←` jumps to BACKLOG.
  - In NEXT (bottom-right): `↑` jumps up to NOW when at first row;
                            `←` jumps to BACKLOG.

`n` captures into the *currently focused* quadrant.
`m` advances the highlighted task one step along the pipeline.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.containers import VerticalScroll
from textual.widgets import ListItem, ListView, Static

from octopus.tui.keymap_bar import KeymapBar

from octopus import actions
from octopus.actions import ActionError
from octopus.db.connection import get_db
from octopus.db.queries import tasks_for_activity
from octopus.fs.io import read_activity
from octopus.tui.filter_bar import FilterBar
from octopus.tui.header_bar import HeaderBar
from octopus.tui.help import HelpOverlay
from octopus.tui.icons import (
    BLOCKED, CURSOR, PINNED,
    SUBTASK_BRANCH, SUBTASK_CHILD, SUBTASK_CHILD_LAST,
    status_glyph, status_glyph_color,
)
from octopus.tui.overlay import TaskDetailOverlay
from octopus.tui.prompts import BucketPickerModal, ConfirmModal, InputModal
from octopus.tui.status_bar import StatusBar
from octopus.tui.toast import Toast


def _row_has(row, key: str) -> bool:
    """sqlite3.Row's __contains__ checks values, not column names. Use keys()."""
    try:
        return key in row.keys()
    except AttributeError:
        return key in row


def _drop_zombies(activity_root: Path, rows):
    """Drop rows whose backing task file is missing on disk.

    Index drift (e.g. a task file was moved or archived without reindex) used
    to surface as ghost rows in the TUI that errored on every mutation with
    'task not found'. Trust the filesystem.
    """
    from octopus.actions import find_task_file
    from octopus.fs.scaffold import read_storage_mode

    try:
        mode = read_storage_mode(activity_root / ".octopus")
    except Exception:
        return list(rows)

    out = []
    octopus_dir = activity_root / ".octopus"
    for r in rows:
        slug = r["slug"] if _row_has(r, "slug") else None
        if not slug:
            continue
        if find_task_file(octopus_dir, mode, slug) is not None:
            out.append(r)
    return out


def _filter_rows(rows, needle: str):
    """Case-insensitive title-substring filter. Empty needle = passthrough."""
    n = (needle or "").strip().lower()
    if not n:
        return list(rows)
    out = []
    for r in rows:
        title = (r["title"] if _row_has(r, "title") else "") or ""
        if n in title.lower():
            out.append(r)
    return out


def _git_repo_name(start: Path) -> str:
    """Walk up from `start` looking for a directory containing `.git/`.
    Returns the basename of the git toplevel, or "" if none found.
    Stops at filesystem root or $HOME — whichever comes first.
    """
    try:
        cur = start.resolve()
    except Exception:
        return ""
    home = Path.home().resolve()
    while True:
        if (cur / ".git").exists():
            return cur.name
        if cur == cur.parent or cur == home:
            return ""
        cur = cur.parent


def _short_path(p: Path) -> str:
    """Render a path with $HOME collapsed to ~ for header display."""
    try:
        home = Path.home()
        rel = p.resolve().relative_to(home)
        return f"~/{rel}"
    except Exception:
        return str(p)


def _provider_chip(promoted_to: str, chips: dict[str, str]) -> str:
    """Format promoted_to with [providers.chips] alias. Defensive against malformed."""
    if not promoted_to or ":" not in promoted_to:
        return promoted_to or ""
    provider, _, identifier = promoted_to.partition(":")
    return f"{chips.get(provider, provider)}:{identifier}"


def _row_chips(row: sqlite3.Row, *, provider_chips: dict[str, str] | None = None) -> Text:
    """Right-side chips (kind, pinned, blocked, promoted) — separate Text suffix."""
    t = Text(no_wrap=True, overflow="ellipsis")
    parts: list[tuple[str, str]] = []

    # kind chip (D46) — shown left-most among chips when present
    kind = row["kind"] if _row_has(row, "kind") else None
    if kind:
        parts.append((f"[{kind}]", "#89DCEB"))

    if _row_has(row, "pinned") and row["pinned"]:
        parts.append((PINNED, "#CBA6F7"))
    run_state = row["run_state"] if _row_has(row, "run_state") else None
    if run_state == "blocked":
        parts.append((BLOCKED, "#FAB387"))

    # promotion arrow (D48) — right-most chip, dim
    promoted_to = row["promoted_to"] if _row_has(row, "promoted_to") else None
    if promoted_to:
        chip_label = _provider_chip(promoted_to, provider_chips or {})
        parts.append((f"→ {chip_label}", "#8A8D9A"))

    for i, (glyph, color) in enumerate(parts):
        if i:
            t.append(" ")
        t.append(glyph, style=color)
    return t


def _row_text(
    row: sqlite3.Row,
    *,
    selected: bool,
    title_offset: int = 0,
) -> Text:
    """Render one task row. Single line, no wrap, ellipsis on overflow.

    `title_offset` shifts the title text left by N cells — used for the
    marquee animation on the selected row when the title clips.
    """
    t = Text(no_wrap=True, overflow="ellipsis")
    if selected:
        t.append(f"{CURSOR} ", style="#F38BA8 bold")
    else:
        t.append("  ")

    # Leading status glyph — encodes progress; bucket carried by color.
    bucket = (row["bucket"] if _row_has(row, "bucket") else "") or ""
    glyph = status_glyph(row)
    t.append(f"{glyph} ", style=status_glyph_color(glyph, bucket))

    title = row["title"] or "(untitled)"
    if title_offset > 0:
        # Marquee loop: build a continuous "title · title · title …" strip and
        # slice from the rolling offset. The strip must be long enough that any
        # offset within `period` still yields >= period characters of content,
        # otherwise the slice gets shorter than the visible budget and the row
        # looks like it's gaining/losing chars (the "duplicating" artifact).
        gap = "   ·   "
        period = len(title) + len(gap)
        strip = (title + gap) * 3
        title = strip[title_offset % period :][:period]

    if bucket in ("done", "dropped"):
        t.append(title, style="#8A8D9A strike")
    else:
        t.append(title)

    # ⎇N subtask-count decoration (D106) — always visible on parent rows.
    subtask_count = _row_subtask_count(row)
    if subtask_count > 0:
        t.append(f" {SUBTASK_BRANCH}{subtask_count}", style="#8A8D9A")

    return t


def _row_subtask_count(row) -> int:
    """Return the number of subtasks for this row, or 0 if not a parent."""
    import json
    raw = row["subtasks"] if _row_has(row, "subtasks") else None
    if not raw:
        return 0
    try:
        v = json.loads(raw)
        return len(v) if isinstance(v, list) else 0
    except Exception:
        return 0


def _row_parent_slug(row) -> str | None:
    """Return the parent slug for a child row, or None."""
    if _row_has(row, "parent"):
        return row["parent"] or None
    return None


def _child_row_text(row, *, selected: bool, is_last: bool) -> Text:
    """Render a child (subtask) row, indented with tree prefix."""
    t = Text(no_wrap=True, overflow="ellipsis")
    if selected:
        t.append(f"{CURSOR} ", style="#F38BA8 bold")
    else:
        t.append("  ")
    prefix = SUBTASK_CHILD_LAST if is_last else SUBTASK_CHILD
    t.append(f"{prefix} ", style="#8A8D9A")

    bucket = (row["bucket"] if _row_has(row, "bucket") else "") or ""
    glyph = status_glyph(row)
    t.append(f"{glyph} ", style=status_glyph_color(glyph, bucket))

    title = row["title"] or "(untitled)"
    if bucket in ("done", "dropped"):
        t.append(title, style="#8A8D9A strike")
    else:
        t.append(title, style="#CDD6F4")  # slightly dimmer than parent rows
    return t


# Per-bucket preview property pairs. Format: (label, column-name).
_BUCKET_PREVIEW: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "backlog":  (("created",   "created"),     ("priority",  "priority")),
    "next":     (("scheduled", "scheduled"),   ("priority",  "priority")),
    "now":      (("started",   "start_date"),  ("due",       "due")),
    "done":     (("ended",     "end_date"),    ("kind",      "kind")),
    "dropped":  (("ended",     "end_date"),    ("kind",      "kind")),
}


def _block_reason(row: sqlite3.Row) -> tuple[str, str, str] | None:
    """Return (label, value, color) for a blocked/waiting task, or None.

    `issue` lives in its own column; `blocked_by` and `waiting_for` are
    inside `raw_frontmatter` JSON. We extract them defensively so a
    missing/malformed payload never breaks rendering.

    Color matches the slot-1 exception glyph color:
      blocked → #FAB387 amber  (same as `!` glyph)
      waiting → #F5C76E mustard (same as `?` glyph)
    """
    issue = (row["issue"] if _row_has(row, "issue") else None) or ""
    if issue not in ("blocked", "waiting"):
        return None
    key = "blocked_by" if issue == "blocked" else "waiting_for"
    color = "#FAB387" if issue == "blocked" else "#F5C76E"
    col = key  # promoted column — no JSON parsing needed
    value = (row[col] if _row_has(row, col) else None) or ""
    return (key, str(value).strip() or issue, color)


def _row_preview(row: sqlite3.Row) -> Text:
    """Render the per-bucket two-property preview line.

    A blocked/waiting task ALWAYS shows its `blocked_by` / `waiting_for`
    reason in slot 2, regardless of bucket — that's load-bearing
    information no matter which view the user is in.
    """
    bucket = (row["bucket"] if _row_has(row, "bucket") else "") or ""
    pair = _BUCKET_PREVIEW.get(bucket, _BUCKET_PREVIEW["backlog"])

    out = Text(no_wrap=True, overflow="ellipsis")
    out.append("    ", style="#0F1014")

    if _row_has(row, "pinned") and row["pinned"]:
        out.append("* pinned", style="#CBA6F7")
        out.append("   ·   ", style="#3A3D48")

    def _chip(label: str, value, *, color: str | None = None) -> None:
        label_style = f"{color} bold" if color else "#8A8D9A"
        out.append(f"{label} ", style=label_style)
        if value is None or value == "":
            out.append("—", style="#3A3D48")
        else:
            value_style = color if color else "#F5F5F7"
            out.append(str(value), style=value_style)

    (l1, c1), (l2, c2) = pair
    v1 = row[c1] if _row_has(row, c1) else None
    _chip(l1, v1)
    out.append("   ·   ", style="#3A3D48")

    reason = _block_reason(row)
    if reason is not None:
        _chip(reason[0], reason[1], color=reason[2])
    else:
        v2 = row[c2] if _row_has(row, c2) else None
        _chip(l2, v2)

    actor = (row["actor"] if _row_has(row, "actor") else "") or ""
    if actor and actor != "human":
        out.append(f"   ·   {actor}", style="#CBA6F7")
    return out


class _TaskListItem(ListItem):
    def __init__(
        self,
        row: sqlite3.Row,
        *,
        provider_chips: dict[str, str] | None = None,
    ) -> None:
        self._provider_chips = provider_chips or {}
        self._title_static = Static(
            _row_text(row, selected=False), classes="row-title"
        )
        self._chips_static = Static(
            _row_chips(row, provider_chips=self._provider_chips), classes="row-chips"
        )
        self._preview_static = Static("", classes="row-preview")
        self._preview_static.styles.display = "none"
        super().__init__(
            Vertical(
                Horizontal(self._title_static, self._chips_static, classes="row-line"),
                self._preview_static,
                classes="row-stack",
            )
        )
        self.task_row = row
        self.task_slug = row["slug"]
        self._expanded = False

    def render_title(self, *, selected: bool, title_offset: int = 0) -> None:
        self._title_static.update(
            _row_text(self.task_row, selected=selected, title_offset=title_offset)
        )

    def set_expanded(self, expanded: bool) -> None:
        """Show/hide the one-row property preview beneath the title."""
        if expanded == self._expanded:
            return
        self._expanded = expanded
        if expanded:
            self._preview_static.update(_row_preview(self.task_row))
            self._preview_static.styles.display = "block"
        else:
            self._preview_static.styles.display = "none"


class _ChildListItem(ListItem):
    """Non-selectable inline child row rendered under a parent task."""

    def __init__(self, row: sqlite3.Row, *, is_last: bool) -> None:
        self._row = row
        self._title_static = Static(
            _child_row_text(row, selected=False, is_last=is_last),
            classes="row-title",
        )
        super().__init__(self._title_static)
        self.disabled = True

    def render_title(self, *, selected: bool, is_last: bool) -> None:
        self._title_static.update(
            _child_row_text(self._row, selected=selected, is_last=is_last)
        )


# Quadrant ids — used in focus tracking & captures.
Q_BACKLOG = "backlog"
Q_NOW = "now"
Q_NEXT = "next"


def _render_detail(activity_root: Path, slug: str | None) -> Text:
    """Build the detail-pane body for a slug. Defensive: never raises."""
    if not slug:
        return Text("(no task selected)", style="#8A8D9A")

    from octopus.actions import find_task_file
    from octopus.fs.io import read_task
    from octopus.fs.scaffold import read_storage_mode

    octopus_dir = activity_root / ".octopus"
    try:
        mode = read_storage_mode(octopus_dir)
    except Exception:
        mode = "flat"

    path = find_task_file(octopus_dir, mode, slug)
    if path is None:
        return Text(f"(task file not found: {slug})", style="#FAB387")

    try:
        task, body = read_task(path)
    except Exception as exc:
        return Text(f"(read failed: {exc})", style="#FAB387")

    title = (getattr(task, "title", None) or slug).strip()
    bucket = (getattr(task, "bucket", "") or "").lower()

    out = Text(no_wrap=False)
    out.append(title + "\n", style="#F5F5F7 bold")
    meta_parts: list[str] = []
    if bucket:
        meta_parts.append(bucket)
    pinned = getattr(task, "pinned", False)
    if pinned:
        meta_parts.append("pinned")
    run_state = (getattr(task, "run_state", "") or "").lower()
    if run_state:
        meta_parts.append(run_state)
    if meta_parts:
        out.append("  ·  ".join(meta_parts) + "\n", style="#8A8D9A")
    out.append("\n")
    body_text = (body or "").strip() or "(no body)"
    out.append(body_text, style="#F5F5F7")
    return out


class FocusScreen(Screen):
    """Three-quadrant Focus mode."""

    BINDINGS = [
        # Navigation
        Binding("q", "quit", "quit", show=True),
        Binding("?", "help", "help", show=True),
        Binding("slash", "filter", "filter", show=True),
        Binding("r", "reindex", "refresh", show=True),
        Binding("enter", "open_detail", "preview", show=False, priority=True),
        Binding("right", "nav_right", "→", show=False),
        Binding("left", "nav_left", "←", show=False),
        Binding("up", "nav_up", "↑", show=False),
        Binding("down", "nav_down", "↓", show=False),
        Binding("tab", "nav_tab", "next pane", show=False),
        Binding("shift+tab", "nav_shift_tab", "prev pane", show=False),
        Binding("escape", "noop", "close", show=False),
        # Mode switch. priority=True so ListView focus doesn't swallow the digit.
        Binding("0", "activities_mode", "activities", show=True, priority=True),
        Binding("1", "focus_mode", "focus", show=True, priority=True),
        Binding("2", "board_mode", "board", show=True, priority=True),
        # Mutations
        Binding("s", "session_start", "session", show=True),
        Binding("S", "session_start_titled", "session+title", show=False),
        Binding("f", "finish", "finish", show=True),
        Binding("F", "finish", "finish", show=False),
        Binding("n", "capture_inline", "capture", show=True),
        Binding("N", "capture_inline", "capture", show=False),
        Binding("m", "move_next", "advance", show=True),
        Binding("M", "move_picker", "move…", show=False),
        Binding("e", "edit_inline", "edit", show=True),
        Binding("E", "edit_external", "edit ($EDITOR)", show=False),
        Binding("d", "drop", "drop", show=True),
        Binding("p", "toggle_pin", "pin", show=True),
        # Detail pane
        Binding("comma", "toggle_detail", "detail pane", show=True),
        # Header display mode (Full / Compact / Slim)
        Binding("H", "cycle_header_mode", "header size", show=False),
        # Block / unblock
        Binding("b", "block", "block", show=True),
        Binding("B", "unblock", "unblock", show=False),
        # Undo / yank / go-to
        Binding("u", "undo", "undo", show=False),
        Binding("y", "yank_slug", "yank slug", show=False),
        Binding("g", "goto_slug", "go to…", show=False),
        # Subtasks expand/collapse
        Binding("space", "toggle_subtasks", "expand/collapse subtasks", show=False),
    ]

    def __init__(self, activity_title: str, activity_root: Path) -> None:
        super().__init__()
        self._activity_title = activity_title
        self._activity_root = activity_root
        activity, _ = read_activity(activity_root / ".octopus" / "activity.md")
        self._activity_id = activity.id
        # Snapshot provider chip aliases so kind/promotion rendering doesn't
        # re-hit disk on every row build. Safe default: empty dict.
        try:
            from octopus.config import load_config
            self._provider_chips = dict(
                load_config(activity_root / ".octopus").provider_chips
            )
        except Exception:
            self._provider_chips = {}

        # Three lists, one per quadrant.
        self._lists: dict[str, ListView] = {
            Q_BACKLOG: ListView(id="backlog-list"),
            Q_NOW: ListView(id="now-list"),
            Q_NEXT: ListView(id="next-list"),
        }
        # Track which quadrant is "active" (driving captures + focused border).
        self._active: str = Q_NOW  # land on NOW by default; gets re-evaluated on mount

        self._status_bar = StatusBar()
        self._toast = Toast()
        self._header = HeaderBar()
        self._filter_text: str = ""

        # Refs to the Vertical wrappers so we can flip border classes.
        self._panels: dict[str, Vertical] = {}

        # Detail pane state. Hidden by default; toggled with `,`.
        self._detail_visible: bool = False
        self._detail_body = Static("", id="detail-body", expand=True)

        # Subtask expansion state: slug → bool (default True = expanded).
        self._subtask_expanded: dict[str, bool] = {}
        self._detail_scroll = VerticalScroll(self._detail_body, id="detail-scroll")
        self._detail_panel: Vertical | None = None

        # Marquee state — increments while the selected row's title clips.
        self._marquee_offset: int = 0
        self._marquee_timer = None
        # The single item currently being marquee'd. When this changes we must
        # reset the previous item back to offset=0 so its title isn't left
        # mid-scroll (which would look like a leading "▸" and a chopped title).
        self._marquee_item: _TaskListItem | None = None

    def compose(self) -> ComposeResult:
        yield self._header

        backlog_panel = Vertical(
            self._lists[Q_BACKLOG],
            classes="panel",
            id="backlog-panel",
        )
        backlog_panel.border_title = "BACKLOG"
        now_panel = Vertical(
            self._lists[Q_NOW],
            classes="panel",
            id="now-panel",
        )
        now_panel.border_title = "▣ NOW"
        next_panel = Vertical(
            self._lists[Q_NEXT],
            classes="panel",
            id="next-panel",
        )
        next_panel.border_title = "□ NEXT"
        self._panels[Q_BACKLOG] = backlog_panel
        self._panels[Q_NOW] = now_panel
        self._panels[Q_NEXT] = next_panel

        # NEXT on top, NOW on bottom — pipeline funnels downward into "what
        # you're working on now". Header chip row keeps backlog → next → now
        # → done order separately (D-entry preserved).
        right_column = Vertical(next_panel, now_panel, id="right-column")

        detail_panel = Vertical(
            self._detail_scroll,
            classes="panel",
            id="detail-panel",
        )
        detail_panel.border_title = "DETAIL"
        detail_panel.styles.display = "none"
        self._detail_panel = detail_panel

        # `detail-hidden` class controls backlog width — wider when the
        # detail pane is collapsed. Toggled by action_toggle_detail.
        yield Horizontal(
            backlog_panel, right_column, detail_panel,
            id="quadrants", classes="detail-hidden",
        )
        yield self._toast
        yield self._status_bar
        yield KeymapBar()

    def on_mount(self) -> None:
        self._header.title_text = "OCTOPUS"
        self._header.set_activity(self._activity_title)
        self._header.set_cwd(_short_path(self._activity_root))
        self._header.set_repo_name(_git_repo_name(self._activity_root))
        self._header.set_mode("focus")
        self._header.set_state("ready")
        self._status_bar.set_activity_id(self._activity_id)
        self._status_bar.set_state("ready")
        # Auto-pick header mode for current terminal width.
        try:
            term_width = self.app.size.width
        except Exception:
            term_width = 120
        self._header.set_display_mode(self._header.auto_mode_for_width(term_width))
        self._refresh_data()
        # Restore cursor from ViewState if any (req #44). Returns silently
        # if no state for this activity exists yet — falls through to the
        # default landing logic below.
        self._restore_from_view_state()
        # Land on whichever quadrant has tasks, preferring NOW → NEXT → BACKLOG.
        # Skipped if _restore_from_view_state already set an active quadrant
        # (we detect by checking whether _active was reassigned from its
        # initial Q_NOW default — but that's racy; safest is to only run the
        # default landing when no per-bucket cursors were restored).
        vs = getattr(self.app, "view_state", None)
        has_restored = bool(
            vs and vs.get_tab(self._view_state_key())
            and vs.get_tab(self._view_state_key()).cursors
        )
        if not has_restored:
            for q in (Q_NOW, Q_NEXT, Q_BACKLOG):
                if self._lists[q].index is not None and len(self._lists[q].children) > 0:
                    self._set_active(q)
                    break
            else:
                self._set_active(Q_NOW)
        # Start the marquee tick.
        self._marquee_timer = self.set_interval(0.4, self._tick_marquee)

    def _tick_marquee(self) -> None:
        """Advance the marquee offset on the currently selected row, if its
        title clips. Resets the previously-marquee'd row when selection moves."""
        item = self._current_item()

        # Selection moved (different quadrant or different row): reset the
        # previous item's title to offset=0 so it doesn't stay mid-scroll.
        if self._marquee_item is not item:
            if self._marquee_item is not None:
                try:
                    self._marquee_item.render_title(selected=False, title_offset=0)
                except Exception:
                    pass
            self._marquee_item = item
            self._marquee_offset = 0

        if item is None:
            return

        title = (item.task_row["title"] or "").strip()
        if not title:
            return

        # Title cell width budget: panel inner width minus cursor (2) minus
        # chips padding (~6). Read from the list's render size if available.
        try:
            visible_width = max(10, item._title_static.size.width)
        except Exception:
            visible_width = 40
        # Account for the leading cursor "▸ " (2 cells).
        title_budget = max(4, visible_width - 2)

        if len(title) <= title_budget:
            # No clipping → make sure offset is zero & re-render once.
            if self._marquee_offset != 0:
                self._marquee_offset = 0
                item.render_title(selected=True, title_offset=0)
            return

        self._marquee_offset += 1
        item.render_title(selected=True, title_offset=self._marquee_offset)

    # ── data ──────────────────────────────────────────────────────────

    def _refresh_data(self) -> None:
        try:
            conn = get_db()
        except Exception as exc:
            for q in (Q_BACKLOG, Q_NOW, Q_NEXT):
                self._render_empty(q, f"(index unavailable: {exc})")
            self._status_bar.set_counts(0, 0, 0)
            self._header.set_counts(0, 0, 0)
            return

        try:
            backlog_rows = list(tasks_for_activity(conn, self._activity_id, bucket="backlog"))
            now_rows = list(tasks_for_activity(conn, self._activity_id, bucket="now"))
            next_rows = list(tasks_for_activity(conn, self._activity_id, bucket="next"))
            done_count = len(list(tasks_for_activity(conn, self._activity_id, bucket="done")))
            dropped_count = len(list(tasks_for_activity(conn, self._activity_id, bucket="dropped")))
            blocked = sum(
                1 for r in backlog_rows + now_rows + next_rows
                if _row_has(r, "run_state") and r["run_state"] == "blocked"
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Drop zombie rows — index entries whose backing file has vanished.
        # Without this, the TUI shows ghost tasks that the mutation layer
        # can't act on (every action errors with "task not found").
        backlog_rows = _drop_zombies(self._activity_root, backlog_rows)
        now_rows = _drop_zombies(self._activity_root, now_rows)
        next_rows = _drop_zombies(self._activity_root, next_rows)

        # Apply filter (case-insensitive title substring match).
        if self._filter_text:
            backlog_rows = _filter_rows(backlog_rows, self._filter_text)
            now_rows = _filter_rows(now_rows, self._filter_text)
            next_rows = _filter_rows(next_rows, self._filter_text)

        self._fill(Q_BACKLOG, backlog_rows, empty_msg=(
            "  No backlog.   Press [#F38BA8 bold]n[/] to capture."
        ))
        self._fill(Q_NOW, now_rows, empty_msg=(
            "  Nothing active.   Use [#F38BA8 bold]m[/] from NEXT to promote."
        ))
        self._fill(Q_NEXT, next_rows, empty_msg=(
            "  Nothing planned.   Use [#F38BA8 bold]m[/] from BACKLOG to promote."
        ))

        self._status_bar.set_counts(len(now_rows), len(next_rows), blocked)
        self._header.set_counts(
            now=len(now_rows),
            next_=len(next_rows),
            blocked=blocked,
            backlog=len(backlog_rows),
            done=done_count,
            dropped=dropped_count,
        )

    def _fill(self, quadrant: str, rows: list[sqlite3.Row], *, empty_msg: str) -> None:
        lst = self._lists[quadrant]
        lst.clear()
        if not rows:
            self._render_empty(quadrant, empty_msg)
            return

        # Separate parent rows from child rows.
        by_slug: dict[str, sqlite3.Row] = {r["slug"]: r for r in rows if r["slug"]}
        child_by_parent: dict[str, list[sqlite3.Row]] = {}
        top_level: list[sqlite3.Row] = []
        orphan_children: list[sqlite3.Row] = []
        for r in rows:
            p = _row_parent_slug(r)
            if p is not None:
                child_by_parent.setdefault(p, []).append(r)
            else:
                top_level.append(r)

        for r in top_level:
            lst.append(_TaskListItem(r, provider_chips=self._provider_chips))
            slug = r["slug"]
            children = child_by_parent.get(slug, [])
            if children:
                expanded = self._subtask_expanded.get(slug, True)
                if expanded:
                    for i, cr in enumerate(children):
                        is_last = i == len(children) - 1
                        lst.append(_ChildListItem(cr, is_last=is_last))

        # Children whose parent isn't in this quadrant: append as regular items.
        for p_slug, children in child_by_parent.items():
            if p_slug not in by_slug:
                for cr in children:
                    lst.append(_TaskListItem(cr, provider_chips=self._provider_chips))

        try:
            lst.index = 0
        except Exception:
            pass

    def _render_empty(self, quadrant: str, message: str) -> None:
        lst = self._lists[quadrant]
        lst.clear()
        item = ListItem(Static(message, classes="empty-hint"))
        item.disabled = True
        lst.append(item)

    # ── focus / quadrant nav ──────────────────────────────────────────

    def _set_active(self, quadrant: str) -> None:
        # Strip the cursor from every row in every quadrant — only the active
        # quadrant's selected row should show "▸".
        for _q, lst in self._lists.items():
            for child in lst.children:
                if isinstance(child, _TaskListItem):
                    try:
                        child.render_title(selected=False, title_offset=0)
                    except Exception:
                        pass
        self._marquee_item = None

        self._active = quadrant
        self._marquee_offset = 0

        for q, panel in self._panels.items():
            if q == quadrant:
                panel.add_class("panel--focused")
            else:
                panel.remove_class("panel--focused")
        try:
            self.set_focus(self._lists[quadrant])
        except Exception:
            pass

        # Paint the new selection with cursor glyph.
        new_item = self._current_item()
        if new_item is not None:
            try:
                new_item.render_title(selected=True, title_offset=0)
            except Exception:
                pass
        self._refresh_detail()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Repaint when arrow-nav moves within a list — keeps the cursor glyph
        in sync with the highlight without waiting for the marquee tick."""
        # Only the *active* quadrant's selected row should show "▸".
        # Strip the cursor from every row in every quadrant, then repaint the
        # one currently selected in the active list.
        new_item = self._current_item()
        for lst in self._lists.values():
            for child in lst.children:
                if isinstance(child, _TaskListItem):
                    try:
                        child.render_title(selected=False, title_offset=0)
                    except Exception:
                        pass
                    if child._expanded and child is not new_item:
                        try:
                            child.set_expanded(False)
                        except Exception:
                            pass
        self._marquee_item = None
        self._marquee_offset = 0
        if new_item is not None:
            try:
                new_item.render_title(selected=True, title_offset=0)
            except Exception:
                pass
        self._refresh_detail()

    def _current_list(self) -> ListView:
        return self._lists[self._active]

    def _current_item(self) -> _TaskListItem | None:
        item = self._current_list().highlighted_child
        if isinstance(item, _TaskListItem):
            return item
        return None

    def _current_slug(self) -> str | None:
        item = self._current_item()
        return item.task_slug if item else None

    def _current_bucket(self) -> str | None:
        item = self._current_item()
        if item is None:
            return None
        try:
            return item.task_row["bucket"]
        except (KeyError, IndexError):
            return None

    # ── view-state integration (req #44) ─────────────────────────────

    def _view_state_key(self) -> str:
        return f"focus:{self._activity_id}"

    def _restore_from_view_state(self) -> None:
        """Restore cursor + active bucket.

        Two-stage:
        1. Per-view state (`focus:<id>`) — per-bucket cursors + active quadrant.
        2. Per-activity shared cursor — overrides (bucket, slug) if present
           and the slug exists, so switching from Board to Focus lands you
           on the same task.

        Silent on any failure.
        """
        try:
            vs = getattr(self.app, "view_state", None)
            if vs is None:
                return

            # Stage 1: per-view state.
            ts = vs.get_tab(self._view_state_key())
            if ts is not None:
                for bucket, lst in self._lists.items():
                    target = ts.cursors.get(bucket)
                    if not target:
                        continue
                    for idx, child in enumerate(lst.children):
                        if isinstance(child, _TaskListItem) and child.task_slug == target:
                            lst.index = idx
                            break
                if ts.active_panel in self._lists:
                    self._set_active(ts.active_panel)

            # Stage 2: shared activity cursor overrides if the slug exists.
            shared = vs.get_activity_cursor(self._activity_id)
            if shared is None or not shared.slug:
                return
            for bucket, lst in self._lists.items():
                for idx, child in enumerate(lst.children):
                    if isinstance(child, _TaskListItem) and child.task_slug == shared.slug:
                        lst.index = idx
                        self._set_active(bucket)
                        return
        except Exception:
            return

    def capture_view_state(self, vs) -> None:
        """Write current screen state into the app-wide ViewState.

        Writes both the per-view TabState (per-bucket cursors, active quadrant)
        AND the per-activity shared cursor (bucket + slug) so the next view
        for this activity can land on the same task.
        """
        from octopus.tui.state import TabState

        cursors: dict[str, str] = {}
        scroll_offsets: dict[str, int] = {}
        for bucket, lst in self._lists.items():
            item = lst.highlighted_child
            if isinstance(item, _TaskListItem) and item.task_slug:
                cursors[bucket] = item.task_slug
            try:
                scroll_offsets[bucket] = int(lst.scroll_offset.y)
            except Exception:
                pass
        ts = TabState(
            tab_id="focus",
            activity_id=self._activity_id,
            cursors=cursors,
            active_panel=self._active,
            scroll_offsets=scroll_offsets,
        )
        vs.set_tab(self._view_state_key(), ts)
        vs.active_tab = self._view_state_key()

        # Per-activity shared cursor — what the user is currently looking at.
        current_item = self._current_item()
        if isinstance(current_item, _TaskListItem) and current_item.task_slug:
            vs.set_activity_cursor(
                self._activity_id, self._active, current_item.task_slug
            )

    def _has_real_tasks(self, q: str) -> bool:
        """True if this quadrant has at least one selectable task (not just empty-state)."""
        return any(isinstance(child, _TaskListItem) for child in self._lists[q].children)

    def _is_at_first(self, q: str) -> bool:
        # An empty/empty-hint list is treated as "already past the top".
        if not self._has_real_tasks(q):
            return True
        return (self._lists[q].index or 0) <= 0

    def _is_at_last(self, q: str) -> bool:
        # An empty/empty-hint list is treated as "already past the bottom".
        if not self._has_real_tasks(q):
            return True
        lst = self._lists[q]
        idx = lst.index
        n = len(lst.children)
        return idx is None or n == 0 or idx >= n - 1

    def action_nav_right(self) -> None:
        # Circular pipeline walk: BACKLOG → NEXT (planned) → NOW (current) → BACKLOG.
        order = [Q_BACKLOG, Q_NEXT, Q_NOW]
        i = order.index(self._active) if self._active in order else 0
        self._set_active(order[(i + 1) % len(order)])

    def action_nav_left(self) -> None:
        # Reverse circular: NOW → NEXT → BACKLOG → NOW.
        order = [Q_BACKLOG, Q_NEXT, Q_NOW]
        i = order.index(self._active) if self._active in order else 0
        self._set_active(order[(i - 1) % len(order)])

    def action_nav_up(self) -> None:
        # Right column is now NEXT (top) / NOW (bottom). At top of NOW
        # (bottom panel) → jump up to NEXT (top panel, last row).
        if self._active == Q_NOW and self._is_at_first(Q_NOW) and self._has_real_tasks(Q_NEXT):
            self._set_active(Q_NEXT)
            try:
                self._lists[Q_NEXT].index = len(self._lists[Q_NEXT].children) - 1
            except Exception:
                pass
            return
        # Otherwise move within the current list.
        try:
            self._current_list().action_cursor_up()
        except Exception:
            pass

    def action_nav_down(self) -> None:
        # At bottom of NEXT (top panel) → fall through to NOW (bottom panel).
        if self._active == Q_NEXT and self._is_at_last(Q_NEXT) and self._has_real_tasks(Q_NOW):
            self._set_active(Q_NOW)
            try:
                self._lists[Q_NOW].index = 0
            except Exception:
                pass
            return
        try:
            self._current_list().action_cursor_down()
        except Exception:
            pass

    def action_nav_tab(self) -> None:
        # Pipeline order: BACKLOG → NEXT → NOW → BACKLOG (circular).
        order = [Q_BACKLOG, Q_NEXT, Q_NOW]
        i = order.index(self._active) if self._active in order else 0
        self._set_active(order[(i + 1) % len(order)])

    def action_nav_shift_tab(self) -> None:
        order = [Q_BACKLOG, Q_NEXT, Q_NOW]
        i = order.index(self._active) if self._active in order else 0
        self._set_active(order[(i - 1) % len(order)])

    # ── nav actions ───────────────────────────────────────────────────

    def action_noop(self) -> None:
        # Esc with no modal/preview to close → prompt "back to Activities?".
        if hasattr(self.app, "switch_to_activities"):
            from octopus.tui.prompts import ConfirmModal

            def _on_confirm(confirmed: bool | None) -> None:
                if confirmed:
                    self.app.switch_to_activities()

            self.app.push_screen(
                ConfirmModal("Back to Activities?", title="back"),
                _on_confirm,
            )

    def action_quit(self) -> None:
        # Quit-confirm if the activity has an active session — avoids stranding
        # an open session pointer when the user just hits q out of habit.
        try:
            from octopus.sessions.cache import get_active
            active = get_active(self._activity_id)
        except Exception:
            active = None
        if not active:
            self.app.exit()
            return

        def _on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self.app.exit()
            else:
                self._toast.flash("cancelled — session still open")

        self.app.push_screen(
            ConfirmModal(f"Quit while session [bold]{active}[/] is open?"),
            _on_confirm,
        )

    def action_focus_mode(self) -> None:
        # Already in Focus — no-op.
        pass

    def action_activities_mode(self) -> None:
        if hasattr(self.app, "switch_to_activities"):
            self.app.switch_to_activities()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay())

    def action_filter(self) -> None:
        def _on_change(value: str) -> None:
            self._filter_text = value
            self._refresh_data()

        def _on_done(_committed: str | None) -> None:
            # Filter persists after commit; Esc inside the bar clears it.
            if self._filter_text:
                self._toast.flash(f"filter: {self._filter_text!r}  (r to clear)")

        self.app.push_screen(
            FilterBar(initial=self._filter_text, on_change=_on_change),
            _on_done,
        )

    def action_board_mode(self) -> None:
        if hasattr(self.app, "switch_to_board"):
            self.app.switch_to_board()

    def action_reindex(self) -> None:
        had_filter = bool(self._filter_text)
        self._filter_text = ""
        self._status_bar.set_state("refreshing…", busy=True)
        self._header.set_state("refreshing…", busy=True)
        self._refresh_data()
        self._status_bar.set_state("ready", busy=False)
        self._header.set_state("ready", busy=False)
        self._toast.flash("⟳ refreshed · filter cleared" if had_filter else "⟳ refreshed")

    def _refresh_detail(self) -> None:
        """Repaint the detail pane for the currently highlighted task.
        Cheap no-op when the pane is hidden — skip disk I/O entirely."""
        if not self._detail_visible:
            return
        slug = self._current_slug()
        try:
            self._detail_body.update(_render_detail(self._activity_root, slug))
        except Exception:
            pass

    def action_cycle_header_mode(self) -> None:
        try:
            new_mode = self._header.cycle_display_mode()
        except Exception:
            return
        self._toast.flash(f"header: {new_mode}")

    def action_toggle_detail(self) -> None:
        self._detail_visible = not self._detail_visible
        if self._detail_panel is not None:
            self._detail_panel.styles.display = "block" if self._detail_visible else "none"
        # Flip the wrapper class so backlog reclaims the freed width.
        try:
            quadrants = self.query_one("#quadrants")
            if self._detail_visible:
                quadrants.remove_class("detail-hidden")
            else:
                quadrants.add_class("detail-hidden")
        except Exception:
            pass
        if self._detail_visible:
            self._refresh_detail()

    def action_open_detail(self) -> None:
        """Enter toggles a one-row property preview beneath the highlighted
        task. Edit lives on `e` — Enter is preview-only."""
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        item = self._current_item()
        if item is None:
            return
        if item._expanded:
            item.set_expanded(False)
            return
        self._collapse_all_previews()
        item.set_expanded(True)

    def _collapse_all_previews(self) -> None:
        for lst in self._lists.values():
            for child in lst.children:
                if isinstance(child, _TaskListItem) and child._expanded:
                    child.set_expanded(False)

    # ── mutation actions ──────────────────────────────────────────────

    def _run(
        self,
        fn,
        *,
        success_msg: str,
        refresh: bool = True,
        mascot_anim: str | None = None,
    ) -> None:
        try:
            result = fn()
        except ActionError as exc:
            self._toast.flash(f"✗ {exc}")
            return
        except Exception as exc:
            self._toast.flash(f"✗ {type(exc).__name__}: {exc}")
            return
        msg = getattr(result, "message", None) or success_msg
        self._toast.flash(f"✓ {msg}")
        if mascot_anim is not None:
            self._trigger_mascot(mascot_anim)
        if refresh:
            self._refresh_data()

    def _trigger_mascot(self, animation_name: str) -> None:
        """Send a trigger to the header mascot. No-op if it can't be found
        (e.g. the header isn't mounted yet during early-init refreshes).
        """
        try:
            from octopus.tui.header_bar import _Mascot
            mascot = self.app.query_one("#header-mascot", _Mascot)
            mascot.trigger(animation_name)
        except Exception:
            # Don't let the mascot fail a verb. Silent on lookup misses.
            pass

    def action_finish(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        self._run(
            lambda: actions.finish_task(self._activity_root, slug),
            success_msg=f"{slug} finished",
            mascot_anim="capovolta",
        )

    def action_drop(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return

        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                self._toast.flash("cancelled")
                return
            self._run(
                lambda: actions.drop_task(self._activity_root, slug),
                success_msg=f"{slug} dropped",
            )

        self.app.push_screen(
            ConfirmModal(f"Drop [bold]{slug}[/]?"),
            _on_confirm,
        )

    def action_toggle_pin(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        self._run(
            lambda: actions.toggle_pin(self._activity_root, slug),
            success_msg="pin toggled",
            mascot_anim="moonwalk-d6",
        )

    def action_move_next(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        self._run(
            lambda: actions.move_next(self._activity_root, slug),
            success_msg="advanced",
        )

    def action_move_picker(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return

        item = self._current_item()
        current = None
        if item and "bucket" in item.task_row:
            current = item.task_row["bucket"]

        def _on_choice(bucket: str | None) -> None:
            if bucket is None:
                self._toast.flash("cancelled")
                return
            self._run(
                lambda: actions.move_task(self._activity_root, slug, bucket),
                success_msg=f"{slug} → {bucket}",
            )

        self.app.push_screen(BucketPickerModal(current=current), _on_choice)

    def action_capture_inline(self) -> None:
        # Captures into the *currently focused* quadrant.
        target_bucket = self._active  # Q_BACKLOG | Q_NOW | Q_NEXT all match bucket names

        def _on_title(title: str | None) -> None:
            if not title:
                self._toast.flash("cancelled")
                return
            self._run(
                lambda: actions.capture_task(
                    self._activity_root, title, bucket=target_bucket,
                ),
                success_msg=f"captured into {target_bucket}: {title}",
            )

        self.app.push_screen(
            InputModal(f"Capture into {target_bucket.upper()}", placeholder="task title…"),
            _on_title,
        )

    def _resolve_task_path(self, slug: str):
        from octopus.actions import find_task_file
        from octopus.fs.scaffold import read_storage_mode

        try:
            storage_mode = read_storage_mode(self._activity_root / ".octopus")
            path = find_task_file(self._activity_root / ".octopus", storage_mode, slug)
        except Exception as exc:
            self._toast.flash(f"✗ {exc}")
            return None
        if path is None:
            self._toast.flash(f"✗ task file not found: {slug}")
            return None
        return path

    def action_edit_inline(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        path = self._resolve_task_path(slug)
        if path is None:
            return
        bucket = self._current_bucket() or "backlog"

        from octopus.tui.edit_modal import EditModal

        def _on_close(saved: bool | None) -> None:
            if saved:
                self._refresh_data()
                self._toast.flash(f"✓ saved {slug}")

        self.app.push_screen(EditModal(path, slug, bucket), _on_close)

    def action_edit_external(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        path = self._resolve_task_path(slug)
        if path is None:
            return

        editor = os.environ.get("EDITOR", "vi")
        with self.app.suspend():
            try:
                subprocess.run([editor, str(path)], check=False)
            except Exception as exc:
                print(f"editor failed: {exc}", flush=True)
        self._refresh_data()
        self._toast.flash(f"✓ edited {slug}")

    def action_block(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return

        def _on_reason(reason: str | None) -> None:
            # Empty reason still blocks — the user pressed Enter on purpose.
            self._run(
                lambda: actions.block_task(self._activity_root, slug, reason or None),
                success_msg=f"{slug} blocked",
            )

        self.app.push_screen(
            InputModal(f"Block {slug} — reason (optional)", placeholder="reason…"),
            _on_reason,
        )

    def action_unblock(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        self._run(
            lambda: actions.unblock_task(self._activity_root, slug),
            success_msg=f"{slug} unblocked",
        )

    def action_toggle_subtasks(self) -> None:
        """Space: toggle expand/collapse subtasks under the highlighted parent."""
        item = self._current_item()
        if item is None:
            return
        slug = item.task_slug
        if not slug:
            return
        count = _row_subtask_count(item.task_row)
        if count == 0:
            return
        current = self._subtask_expanded.get(slug, True)
        self._subtask_expanded[slug] = not current
        self._refresh_data()

    def action_undo(self) -> None:
        # Real undo requires snapshot/journaling — not yet implemented.
        self._toast.flash("undo: not yet implemented")

    def action_yank_slug(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        # Best-effort macOS clipboard. Falls back to a toast showing the slug.
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(input=slug.encode("utf-8"), timeout=2)
            if proc.returncode == 0:
                self._toast.flash(f"✓ yanked {slug}")
                return
        except Exception:
            pass
        self._toast.flash(f"slug: {slug}")

    def action_goto_slug(self) -> None:
        def _on_value(value: str | None) -> None:
            if not value:
                return
            target = value.strip()
            if not target:
                return
            # Find the slug in any quadrant and select it.
            for q, lst in self._lists.items():
                for i, child in enumerate(lst.children):
                    if isinstance(child, _TaskListItem) and child.task_slug == target:
                        self._set_active(q)
                        try:
                            lst.index = i
                        except Exception:
                            pass
                        self._refresh_detail()
                        self._toast.flash(f"→ {target}")
                        return
            self._toast.flash(f"not in view: {target}")

        self.app.push_screen(
            InputModal("Go to slug", placeholder="task slug…"),
            _on_value,
        )

    def action_session_start(self) -> None:
        self._run(
            lambda: actions.start_session_for(self._activity_root),
            success_msg="session started",
            refresh=False,
        )

    def action_session_start_titled(self) -> None:
        def _on_title(title: str | None) -> None:
            self._run(
                lambda: actions.start_session_for(self._activity_root, title=title or None),
                success_msg="session started",
                refresh=False,
            )

        self.app.push_screen(
            InputModal("Start session (optional title)", placeholder="title (Enter to skip)…"),
            _on_title,
        )

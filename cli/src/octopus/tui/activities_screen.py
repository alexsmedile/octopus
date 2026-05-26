"""ActivitiesScreen — Tab 0 of the TUI (request #43).

Adds a third top-level view to the existing Focus (1) and Board (2) modes.
Cross-activity navigation surface with three vertically stacked, collapsible
panels:

- ◇ INDEX  : all activities from the global index (cross-vault)
- ◆ CURRENT: the activity walked-up from cwd, if any
- ◈ NESTED : sub-activities found under cwd

Tab cycles panel focus. ↑↓ moves cursor within a panel. Enter drills into
the highlighted activity — replaces the screen with Focus mode for that
activity (`0` returns).

Panel-header glyphs activate the D95-reserved diamond family:
- ◇ outline    = label (Index)
- ◆ filled     = active state (Current — "the one I'm in")
- ◈ contains   = nested containment (Nested)

Chrome (header bar, status bar, keymap bar) matches Focus/Board so the
app feels like one coherent thing with three views, not three different
apps.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import ListItem, ListView, Static

from octopus.db.connection import get_db
from octopus.db.queries import count_by_bucket, list_activities
from octopus.fs.discover import find_activity_root, find_all_activities
from octopus.fs.io import read_activity
from octopus.tui.header_bar import HeaderBar
from octopus.tui.status_bar import StatusBar
from octopus.tui.toast import Toast

# ── glyphs ─────────────────────────────────────────────────────────────


GLYPH_INDEX = "◇"
GLYPH_CURRENT = "◆"
GLYPH_NESTED = "◈"
GLYPH_CURSOR = "▸"
GLYPH_OPEN = "▼"
GLYPH_CLOSED = "▶"


# ── activities-mode keymap bar ─────────────────────────────────────────


_GREY_FG = "#3A3D48"
_GREY_BG = "#16171E"
_TEXT_BG = "#0F1014"
_DESC_FG = "#8A8D9A"


# (key_label, description, fg_color) — chips for Activities mode.
# Mirrors KeymapBar styling exactly so the bar reads identically across views.
_ACT_CHIPS_WIDE: tuple[tuple[str, str, str], ...] = (
    ("CR", "drill",    "#CBA6F7"),
    ("TAB", "panel",   "#FACC15"),
    ("⏎",  "open",    _GREY_FG),
    ("␣",  "collapse", _GREY_FG),
    ("/",  "filter",  _GREY_FG),
    ("r",  "refresh", _GREY_FG),
    ("1",  "focus",   "#86EFAC"),
    ("2",  "board",   "#5EEAD4"),
    ("?",  "help",    _GREY_FG),
    ("q",  "quit",    _GREY_FG),
)

_ACT_CHIPS_MEDIUM: tuple[tuple[str, str, str], ...] = (
    ("CR",  "drill",  "#CBA6F7"),
    ("TAB", "panel",  "#FACC15"),
    ("␣",   "fold",   _GREY_FG),
    ("/",   "filter", _GREY_FG),
    ("r",   "refresh", _GREY_FG),
    ("1",   "focus",  "#86EFAC"),
    ("q",   "quit",   _GREY_FG),
)

_ACT_CHIPS_NARROW: tuple[tuple[str, str, str], ...] = (
    ("CR",  "drill",  "#CBA6F7"),
    ("TAB", "panel",  "#FACC15"),
    ("1",   "focus",  "#86EFAC"),
    ("q",   "quit",   _GREY_FG),
)


def _select_activities_chips(width: int) -> tuple[tuple[str, str, str], ...]:
    if width >= 120:
        return _ACT_CHIPS_WIDE
    if width >= 100:
        return _ACT_CHIPS_MEDIUM
    return _ACT_CHIPS_NARROW


class ActivitiesKeymapBar(Static):
    """Docked-bottom keymap chips for Activities mode."""

    DEFAULT_CSS = ""

    def __init__(self) -> None:
        super().__init__(id="keymap-bar")

    def on_resize(self, _event) -> None:
        self.refresh()

    def render(self) -> Text:
        try:
            width = self.size.width or 100
        except Exception:
            width = 100
        chips = _select_activities_chips(width)
        out = Text()
        for i, (key, desc, color) in enumerate(chips):
            if i:
                out.append("  ", style=f"on {_TEXT_BG}")
            out.append(f" {key} ", style=f"bold {color} on {_GREY_BG}")
            out.append(" ", style=f"on {_TEXT_BG}")
            out.append(desc, style=f"{_DESC_FG} on {_TEXT_BG}")
        return out


# ── helpers ────────────────────────────────────────────────────────────


def _short_path(path: Path, max_len: int = 60) -> str:
    """Render a path with $HOME → ~ and middle-truncation if long."""
    home = str(Path.home())
    s = str(path)
    if s.startswith(home):
        s = "~" + s[len(home):]
    if len(s) <= max_len:
        return s
    keep = max_len - 3
    left = keep // 2
    right = keep - left
    return s[:left] + "..." + s[-right:]


def _short_id(activity_id: str) -> str:
    """Strip the 4-char hash suffix off an activity id (per D1)."""
    parts = activity_id.rsplit("-", 1)
    if len(parts) == 2 and len(parts[1]) == 4:
        return parts[0]
    return activity_id


# ── ActivityBlock — 3-row renderer ─────────────────────────────────────


class ActivityBlock(ListItem):
    """A single activity rendered as 3 logical rows in one Static.

    Single-Static implementation (instead of Vertical of 3 Statics) avoids
    a Textual visual-cache edge case where nested empty Statics inside a
    ListItem can produce visual=None on first render.
    """

    def __init__(
        self,
        activity_row: dict,
        bucket_counts: dict[str, int] | None = None,
    ) -> None:
        self._row = dict(activity_row)
        self._counts = bucket_counts or {}
        self.activity_id = self._row.get("id", "")
        self.activity_path = self._row.get("path", "")
        self._selected = False
        self._body = Static(self._build_content(), classes="act-block")
        super().__init__(self._body)

    def set_selected(self, selected: bool) -> None:
        if selected == self._selected:
            return
        self._selected = selected
        self._body.update(self._build_content())

    def _build_content(self) -> str:
        short = _short_id(self.activity_id)
        title = self._row.get("title") or short
        cursor = GLYPH_CURSOR if self._selected else " "
        if self._selected:
            row1 = f"[bold]{cursor}[/] [bold cyan]{short}[/]  [bold]{title}[/]"
        else:
            row1 = f"{cursor} [cyan]{short}[/]  {title}"

        t = self._row.get("type") or "—"
        st = self._row.get("status") or "—"
        n_now = self._counts.get("now", 0)
        n_next = self._counts.get("next", 0)
        n_bk = self._counts.get("backlog", 0)

        def _chip(label: str, n: int) -> str:
            return f"{label} {n}" if n else f"[dim]{label} {n}[/]"

        row2 = (
            f"    [dim]{t} · {st}[/]   "
            f"{_chip('NOW', n_now)}  "
            f"{_chip('NEXT', n_next)}  "
            f"{_chip('BACKLOG', n_bk)}"
        )

        path = _short_path(Path(self.activity_path)) if self.activity_path else ""
        row3 = f"[dim]    {path}[/]"

        return f"{row1}\n{row2}\n{row3}"


class _EmptyHint(ListItem):
    def __init__(self, message: str) -> None:
        super().__init__(Static(f"    {message}", classes="act-empty"))


# ── Panel containers ───────────────────────────────────────────────────


class _Panel(Vertical):
    """Wraps a ListView with a collapsible header + counter."""

    def __init__(self, panel_id: str, glyph: str, label: str) -> None:
        self.panel_id = panel_id
        self.glyph = glyph
        self.label = label
        self.collapsed = False
        self._list = ListView(id=f"{panel_id}-list", classes="act-list")
        super().__init__(self._list, id=f"{panel_id}-panel", classes="panel act-panel")

    @property
    def list_view(self) -> ListView:
        return self._list

    def set_count(self, n: int) -> None:
        indicator = GLYPH_CLOSED if self.collapsed else GLYPH_OPEN
        self.border_title = f"{indicator} {self.glyph} {self.label} ({n})"

    def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        self._list.styles.display = "none" if self.collapsed else "block"
        try:
            old = str(self.border_title)
            n = int(old.rsplit("(", 1)[-1].rstrip(")"))
        except Exception:
            n = len(self._list.children)
        self.set_count(n)


# ── ActivitiesScreen ────────────────────────────────────────────────────


class ActivitiesScreen(Screen):
    """View 0 — cross-activity navigation (sits beside Focus + Board)."""

    BINDINGS = [
        Binding("q", "quit", "quit", show=True),
        Binding("0", "noop", "activities", show=True, priority=True),
        Binding("1", "go_focus", "focus", show=True, priority=True),
        Binding("2", "go_board", "board", show=True, priority=True),
        Binding("up", "cursor_up", "↑", show=False, priority=True),
        Binding("down", "cursor_down", "↓", show=False, priority=True),
        Binding("tab", "next_panel", "next panel", show=True, priority=True),
        Binding("shift+tab", "prev_panel", "prev panel", show=False, priority=True),
        Binding("enter", "drill", "drill", show=True, priority=True),
        Binding("space", "toggle_panel", "collapse", show=True),
        Binding("r", "refresh", "refresh", show=True),
        Binding("A", "toggle_archived", "archived", show=False),
    ]

    def __init__(self, cwd: Path | None = None) -> None:
        super().__init__()
        self._cwd = cwd or Path.cwd()
        self._index = _Panel("index", GLYPH_INDEX, "INDEX")
        self._current = _Panel("current", GLYPH_CURRENT, "CURRENT")
        self._nested = _Panel("nested", GLYPH_NESTED, "NESTED")
        self._panels = [self._index, self._current, self._nested]
        self._active_panel_idx = 0
        self._include_archived = False
        self._header = HeaderBar()
        self._status_bar = StatusBar()
        self._toast = Toast()

    # ── compose / mount ──────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield self._header
        yield Vertical(
            self._index,
            self._current,
            self._nested,
            id="activities-root",
        )
        yield self._toast
        yield self._status_bar
        yield ActivitiesKeymapBar()

    def on_mount(self) -> None:
        # Header — same layout as Focus/Board, just without an activity name.
        self._header.title_text = "OCTOPUS"
        self._header.set_activity("(all activities)")
        self._header.set_cwd(_short_path(self._cwd))
        self._header.set_mode("activities")
        self._header.set_subtitle("activities · tab 0")
        # Status bar
        self._status_bar.set_activity("all")
        self._status_bar.set_state("ready")
        # Populate panels
        for p in self._panels:
            p.set_count(0)
        self._refresh_all()
        # Restore from ViewState if available (req #44).
        self._restore_from_view_state()
        self._focus_panel(self._active_panel_idx)

    # ── view-state integration (req #44) ─────────────────────────────

    def _restore_from_view_state(self) -> None:
        """Read this screen's TabState (if any) and restore active panel +
        cursor per panel. Silent on any failure."""
        try:
            vs = getattr(self.app, "view_state", None)
            if vs is None:
                return
            ts = vs.get_tab("activities")
            if ts is None:
                return
            # Active panel
            panel_ids = ["index", "current", "nested"]
            if ts.active_panel in panel_ids:
                self._active_panel_idx = panel_ids.index(ts.active_panel)
            # Per-panel cursors
            for panel, pid in zip(self._panels, panel_ids, strict=False):
                target = ts.cursors.get(pid)
                if not target:
                    continue
                # Find the matching ActivityBlock by activity_id.
                for idx, child in enumerate(panel.list_view.children):
                    if isinstance(child, ActivityBlock) and child.activity_id == target:
                        panel.list_view.index = idx
                        break
            # Collapsed state
            for panel, pid in zip(self._panels, panel_ids, strict=False):
                want_collapsed = pid in (ts.collapsed_panels or [])
                if want_collapsed != panel.collapsed:
                    panel.toggle_collapsed()
        except Exception:
            return

    def capture_view_state(self, vs) -> None:
        """Write current screen state into the app-wide ViewState."""
        from octopus.tui.state import TabState

        panel_ids = ["index", "current", "nested"]
        cursors: dict[str, str] = {}
        scroll_offsets: dict[str, int] = {}
        for panel, pid in zip(self._panels, panel_ids, strict=False):
            item = panel.list_view.highlighted_child
            if isinstance(item, ActivityBlock) and item.activity_id:
                cursors[pid] = item.activity_id
            try:
                scroll_offsets[pid] = int(panel.list_view.scroll_offset.y)
            except Exception:
                pass
        ts = TabState(
            tab_id="activities",
            cursors=cursors,
            active_panel=panel_ids[self._active_panel_idx],
            scroll_offsets=scroll_offsets,
            collapsed_panels=[pid for p, pid in zip(self._panels, panel_ids, strict=False) if p.collapsed],
        )
        vs.set_tab("activities", ts)
        vs.active_tab = "activities"

    # ── data loading ─────────────────────────────────────────────────

    def _load_index(self) -> list[ActivityBlock]:
        conn = get_db()
        try:
            rows = list_activities(conn, include_archived=self._include_archived)
            blocks: list[ActivityBlock] = []
            for row in rows:
                counts = count_by_bucket(conn, row["id"])
                blocks.append(ActivityBlock(row, counts))
            return blocks
        except sqlite3.Error:
            return []

    def _load_current(self) -> list[ActivityBlock]:
        root = find_activity_root(self._cwd)
        if root is None:
            return []
        try:
            activity, _ = read_activity(root / ".octopus" / "activity.md")
        except Exception:
            return []
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM activities WHERE path = ?", (str(root),)
            ).fetchone()
        except sqlite3.Error:
            row = None
        if row is None:
            row = {
                "id": activity.id,
                "title": activity.title,
                "type": activity.type,
                "status": activity.status,
                "path": str(root),
            }
        counts = count_by_bucket(conn, row["id"]) if row else {}
        return [ActivityBlock(row, counts)]

    def _load_nested(self) -> list[ActivityBlock]:
        # Bail on $HOME / fs-root cwd to avoid walking huge trees (including
        # network-mounted cloud storage which can hang for minutes).
        if self._cwd == Path.home() or self._cwd == Path(self._cwd.anchor):
            return []
        try:
            current_root = find_activity_root(self._cwd)
        except Exception:
            current_root = None
        all_below = find_all_activities([self._cwd])
        nested_roots = [p for p in all_below if p != current_root]
        if not nested_roots:
            return []
        conn = get_db()
        blocks: list[ActivityBlock] = []
        for root in nested_roots:
            try:
                activity, _ = read_activity(root / ".octopus" / "activity.md")
            except Exception:
                continue
            try:
                row = conn.execute(
                    "SELECT * FROM activities WHERE path = ?", (str(root),)
                ).fetchone()
            except sqlite3.Error:
                row = None
            if row is None:
                row = {
                    "id": activity.id,
                    "title": activity.title,
                    "type": activity.type,
                    "status": activity.status,
                    "path": str(root),
                }
            counts = count_by_bucket(conn, row["id"]) if row else {}
            blocks.append(ActivityBlock(row, counts))
        return blocks

    def _populate(self, panel: _Panel, blocks: list[ActivityBlock], empty_hint: str) -> None:
        panel.list_view.clear()
        if not blocks:
            panel.list_view.append(_EmptyHint(empty_hint))
            panel.set_count(0)
            return
        for b in blocks:
            panel.list_view.append(b)
        panel.set_count(len(blocks))
        if panel.list_view.children:
            panel.list_view.index = 0

    def _refresh_all(self) -> None:
        self._populate(self._index, self._load_index(), "(no activities indexed)")
        self._populate(self._current, self._load_current(), "(no current activity)")
        self._populate(self._nested, self._load_nested(), "(no sub-activities)")
        self._update_selection_highlights()

    # ── selection / cursor ───────────────────────────────────────────

    def _update_selection_highlights(self) -> None:
        for i, panel in enumerate(self._panels):
            is_active = i == self._active_panel_idx
            for child in panel.list_view.children:
                if isinstance(child, ActivityBlock):
                    selected = is_active and child is panel.list_view.highlighted_child
                    child.set_selected(selected)
        # Toggle panel-focused class for the border highlight (uses existing .panel--focused).
        for i, panel in enumerate(self._panels):
            if i == self._active_panel_idx:
                panel.add_class("panel--focused")
            else:
                panel.remove_class("panel--focused")

    def _focus_panel(self, idx: int) -> None:
        idx = idx % len(self._panels)
        self._active_panel_idx = idx
        target = self._panels[idx]
        if target.collapsed:
            target.toggle_collapsed()
        target.list_view.focus()
        self._update_selection_highlights()

    @property
    def _active_panel(self) -> _Panel:
        return self._panels[self._active_panel_idx]

    @property
    def _selected_block(self) -> ActivityBlock | None:
        item = self._active_panel.list_view.highlighted_child
        return item if isinstance(item, ActivityBlock) else None

    # ── actions ──────────────────────────────────────────────────────

    def action_noop(self) -> None:
        return

    def action_quit(self) -> None:
        self.app.exit()

    def action_cursor_up(self) -> None:
        lv = self._active_panel.list_view
        n = len(lv.children)
        if n == 0:
            return
        current = lv.index if lv.index is not None else 0
        # Wrap-around: top of list → bottom.
        lv.index = (current - 1) % n
        self._update_selection_highlights()

    def action_cursor_down(self) -> None:
        lv = self._active_panel.list_view
        n = len(lv.children)
        if n == 0:
            return
        current = lv.index if lv.index is not None else -1
        # Wrap-around: bottom of list → top.
        lv.index = (current + 1) % n
        self._update_selection_highlights()

    def action_next_panel(self) -> None:
        self._focus_panel(self._active_panel_idx + 1)

    def action_prev_panel(self) -> None:
        self._focus_panel(self._active_panel_idx - 1)

    def action_toggle_panel(self) -> None:
        self._active_panel.toggle_collapsed()

    def action_refresh(self) -> None:
        self._refresh_all()

    def action_toggle_archived(self) -> None:
        self._include_archived = not self._include_archived
        self._populate(self._index, self._load_index(), "(no activities indexed)")
        self._update_selection_highlights()

    def action_drill(self) -> None:
        block = self._selected_block
        if block is None or not block.activity_path:
            return
        path = Path(block.activity_path)
        if not (path / ".octopus" / "activity.md").is_file():
            return
        if hasattr(self.app, "drill_into_activity"):
            self.app.drill_into_activity(path)

    def action_go_focus(self) -> None:
        block = self._selected_block
        if block is None:
            return
        path = Path(block.activity_path)
        if hasattr(self.app, "drill_into_activity"):
            self.app.drill_into_activity(path)

    def action_go_board(self) -> None:
        block = self._selected_block
        if block is None:
            return
        path = Path(block.activity_path)
        if hasattr(self.app, "drill_into_activity"):
            self.app.drill_into_activity(path, mode="board")

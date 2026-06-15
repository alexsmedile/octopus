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
import subprocess
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
    """A single activity rendered as one compact line.

    Used by INDEX + NESTED. CURRENT uses the richer ActivityOverview.
    Layout: `▸ id  title   · type · status · NOW n NEXT n BACKLOG n`.
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
        # Single-line row: cursor + id + full title, then inline bucket
        # chips. Locked bucket glyphs per D6: now ▣ · next □ · backlog · · done ●.
        short = _short_id(self.activity_id)
        title = self._row.get("title") or short
        cursor = GLYPH_CURSOR if self._selected else " "

        n_bk = self._counts.get("backlog", 0)
        n_next = self._counts.get("next", 0)
        n_now = self._counts.get("now", 0)
        n_done = self._counts.get("done", 0)
        n_drop = self._counts.get("dropped", 0)

        def _chip(glyph: str, n: int, color: str) -> str:
            if n:
                return f"[{color}]{glyph} {n}[/]"
            return f"[dim]{glyph} {n}[/]"

        # Pipeline order: backlog → next → now → done → dropped.
        chips = (
            f"{_chip('·', n_bk,   '#8A8D9A')}  "
            f"{_chip('□', n_next, '#89DCEB')}  "
            f"{_chip('▣', n_now,  '#F38BA8')}  "
            f"{_chip('●', n_done, '#A6E3A1')}  "
            f"{_chip('✕', n_drop, '#F38BA8')}"
        )

        if self._selected:
            head = f"[bold]{cursor}[/] [bold cyan]{short}[/]  [bold]{title}[/]"
        else:
            head = f"{cursor} [cyan]{short}[/]  {title}"
        return f"{head}   {chips}"


class _EmptyHint(ListItem):
    def __init__(self, message: str) -> None:
        super().__init__(Static(f"    {message}", classes="act-empty"))


# Anything carrying an activity_id + activity_path + set_selected.
# Used by isinstance() checks across the screen so ActivityOverview is
# treated identically to ActivityBlock by cursor-restore + drill actions.
ACTIVITY_ITEM_TYPES: tuple[type, ...]  # filled in below


class ActivityOverview(ListItem):
    """Property-rich render of a single activity.

    Used only by the CURRENT panel — it always holds exactly one item and
    has more vertical room than INDEX/NESTED rows, so surface more than
    the 3-row ActivityBlock: identity, classification, four bucket counts,
    attention signals (pinned / active session / blocked / due-soon),
    "what's playing now," metadata (tags, dates), and path.
    """

    def __init__(
        self,
        activity_row: dict,
        bucket_counts: dict[str, int] | None = None,
        extras: dict | None = None,
    ) -> None:
        self._row = dict(activity_row)
        self._counts = bucket_counts or {}
        # extras keys (all optional):
        #   pinned_task: str | None        — title of the single pinned task
        #   top_now_task: str | None       — title of first NOW task (slot-0)
        #   active_session: dict | None    — {"title": str, "started": str}
        #   blocked_count: int             — tasks with issue=blocked|waiting
        #   due_soon_count: int            — tasks with due ≤ today + 7d
        #   linked_count: int              — len(activity.linked_activities)
        self._extras = extras or {}
        self.activity_id = self._row.get("id", "")
        self.activity_path = self._row.get("path", "")
        self._selected = False
        self._body = Static(self._build_content(), classes="act-overview")
        super().__init__(self._body)

    def set_selected(self, selected: bool) -> None:
        if selected == self._selected:
            return
        self._selected = selected
        self._body.update(self._build_content())

    # ── builders ────────────────────────────────────────────────────────

    def _build_content(self) -> str:
        rows: list[str] = []
        rows.append(self._row_title())
        meta = self._row_meta()
        if meta:
            rows.append(meta)
        rows.append(self._row_counts())
        attn = self._row_attention()
        if attn:
            rows.append(attn)
        now_line = self._row_now_playing()
        if now_line:
            rows.append(now_line)
        session_line = self._row_session()
        if session_line:
            rows.append(session_line)
        tags = self._row_tags()
        if tags:
            rows.append(tags)
        dates = self._row_dates()
        if dates:
            rows.append(dates)
        path = self._row_path()
        if path:
            rows.append(path)
        return "\n".join(rows)

    def _row_title(self) -> str:
        short = _short_id(self.activity_id)
        title = self._row.get("title") or short
        cursor = GLYPH_CURSOR if self._selected else " "
        if self._selected:
            return f"[bold]{cursor}[/] [bold cyan]{short}[/]  [bold]{title}[/]"
        return f"{cursor} [cyan]{short}[/]  {title}"

    def _row_meta(self) -> str | None:
        # type · status · priority · area
        parts: list[str] = []
        for key, style in (
            ("type", None),
            ("status", None),
            ("priority", "yellow"),
            ("area", None),
        ):
            v = self._row.get(key)
            if not v:
                continue
            v = str(v)
            if style:
                parts.append(f"[{style}]{v}[/]")
            else:
                parts.append(v)
        return f"    [dim]{' · '.join(parts)}[/]" if parts else None

    def _row_counts(self) -> str:
        n_bk = self._counts.get("backlog", 0)
        n_next = self._counts.get("next", 0)
        n_now = self._counts.get("now", 0)
        n_done = self._counts.get("done", 0)
        n_drop = self._counts.get("dropped", 0)

        def _chip(label: str, n: int, color: str | None = None) -> str:
            if not n:
                return f"[dim]{label} {n}[/]"
            if color:
                return f"[{color}]{label} {n}[/]"
            return f"{label} {n}"

        # Pipeline order: backlog → next → now → done → dropped.
        return (
            f"    {_chip('BACKLOG', n_bk)}  "
            f"{_chip('NEXT', n_next, '#5EEAD4')}  "
            f"{_chip('NOW', n_now, '#FACC15')}  "
            f"{_chip('DONE', n_done, '#86EFAC')}  "
            f"{_chip('DROPPED', n_drop)}"
        )

    def _row_attention(self) -> str | None:
        """Chips for signals that need attention: pinned, blocked, due-soon."""
        blocked = int(self._extras.get("blocked_count") or 0)
        due_soon = int(self._extras.get("due_soon_count") or 0)
        pinned = self._extras.get("pinned_task")
        linked = int(self._extras.get("linked_count") or 0)
        chips: list[str] = []
        if pinned:
            chips.append("[#CBA6F7]◆ pinned[/]")
        if blocked:
            chips.append(f"[#F38BA8]⊘ blocked {blocked}[/]")
        if due_soon:
            chips.append(f"[#FACC15]◷ due≤7d {due_soon}[/]")
        if linked:
            chips.append(f"[dim]↔ links {linked}[/]")
        return f"    {'  '.join(chips)}" if chips else None

    def _row_now_playing(self) -> str | None:
        """Show pinned task title if present, else the top NOW task."""
        pinned = self._extras.get("pinned_task")
        if pinned:
            return f"    [#CBA6F7]◆[/] [bold]{pinned}[/]"
        top = self._extras.get("top_now_task")
        if top:
            return f"    [#FACC15]▶[/] [bold]{top}[/]"
        return None

    def _row_session(self) -> str | None:
        sess = self._extras.get("active_session")
        if not sess:
            return None
        title = sess.get("title") or "session"
        started = sess.get("started") or ""
        if started:
            return f"    [#86EFAC]● session:[/] {title} [dim]({started})[/]"
        return f"    [#86EFAC]● session:[/] {title}"

    def _row_tags(self) -> str | None:
        tags = self._row.get("tags")
        if not tags:
            return None
        if isinstance(tags, (list, tuple)):
            tag_str = ", ".join(str(x) for x in tags if x)
        else:
            tag_str = str(tags)
        return f"    [dim]tags:[/] {tag_str}" if tag_str else None

    def _row_dates(self) -> str | None:
        created = self._row.get("created")
        last_reviewed = self._row.get("last_reviewed")
        last_touched = self._row.get("last_touched_at")
        parts: list[str] = []
        if created:
            parts.append(f"[dim]created:[/] {created}")
        if last_touched:
            # Trim time component if present.
            s = str(last_touched).split("T")[0].split(" ")[0]
            parts.append(f"[dim]touched:[/] {s}")
        if last_reviewed:
            parts.append(f"[dim]reviewed:[/] {last_reviewed}")
        return f"    {'   '.join(parts)}" if parts else None

    def _row_path(self) -> str | None:
        if not self.activity_path:
            return None
        # Labelled + un-dimmed so the path reads as a first-class property
        # of the activity, not a footer.
        return f"    [dim]path:[/] {_short_path(Path(self.activity_path))}"


ACTIVITY_ITEM_TYPES = (ActivityBlock, ActivityOverview)


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
        Binding("y", "yank_slug", "yank slug", show=False),
        Binding("A", "toggle_archived", "archived", show=False),
    ]

    def __init__(
        self,
        cwd: Path | None = None,
        *,
        prefer_current: bool = False,
    ) -> None:
        super().__init__()
        self._cwd = cwd or Path.cwd()
        # When returning from a drilled activity (Esc → "Back to Activities?"),
        # the caller sets prefer_current=True so the focus rule prioritizes
        # the CURRENT panel over any saved active_panel — matches the user
        # mental model: "I just left an activity, take me back to it."
        self._prefer_current = bool(prefer_current)
        self._index = _Panel("index", GLYPH_INDEX, "INDEX")
        self._current = _Panel("current", GLYPH_CURRENT, "CURRENT")
        self._nested = _Panel("nested", GLYPH_NESTED, "NESTED")
        # Visual + cycle order: CURRENT (top) → INDEX → NESTED (req #45).
        self._panels = [self._current, self._index, self._nested]
        self._active_panel_idx = 0
        self._include_archived = False
        self._header = HeaderBar()
        self._status_bar = StatusBar()
        self._toast = Toast()

    # ── compose / mount ──────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield self._header
        yield Vertical(
            self._current,
            self._index,
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
        restored = self._restore_from_view_state()
        # prefer_current overrides saved state — used when returning from a
        # drilled activity (req #45 follow-up): land back on CURRENT, not
        # wherever the user happened to be before drilling.
        if self._prefer_current:
            idx = self._current_panel_idx_if_populated()
            if idx is not None:
                self._active_panel_idx = idx
            else:
                self._active_panel_idx = self._default_focus_idx()
        elif not restored:
            # Fallback focus: CURRENT when populated, else INDEX.
            self._active_panel_idx = self._default_focus_idx()
        self._focus_panel(self._active_panel_idx)

    def _current_panel_idx_if_populated(self) -> int | None:
        for idx, panel in enumerate(self._panels):
            if panel.panel_id != "current":
                continue
            has_activity = any(
                isinstance(c, ACTIVITY_ITEM_TYPES)
                for c in panel.list_view.children
            )
            return idx if has_activity else None
        return None

    def _default_focus_idx(self) -> int:
        """Pick the initial active panel when there's no saved state.

        CURRENT if it has an ActivityOverview child; else INDEX.
        """
        for idx, panel in enumerate(self._panels):
            if panel.panel_id == "current":
                has_activity = any(
                    isinstance(c, ACTIVITY_ITEM_TYPES)
                    for c in panel.list_view.children
                )
                if has_activity:
                    return idx
                break
        for idx, panel in enumerate(self._panels):
            if panel.panel_id == "index":
                return idx
        return 0

    # ── view-state integration (req #44) ─────────────────────────────

    def _restore_from_view_state(self) -> bool:
        """Read this screen's TabState (if any) and restore active panel +
        cursor per panel. Silent on any failure.

        Returns True if active_panel was restored from saved state, False
        otherwise — callers use this to decide whether to apply the
        fallback-focus rule (req #45).
        """
        restored_active_panel = False
        try:
            vs = getattr(self.app, "view_state", None)
            if vs is None:
                return False
            ts = vs.get_tab("activities")
            if ts is None:
                return False
            # Active panel — match by panel.panel_id, not list position
            # (req #45 changed visual order; per-panel keys are the SoT).
            panel_ids = [p.panel_id for p in self._panels]
            if ts.active_panel in panel_ids:
                self._active_panel_idx = panel_ids.index(ts.active_panel)
                restored_active_panel = True
            # Per-panel cursors
            for panel in self._panels:
                target = ts.cursors.get(panel.panel_id)
                if not target:
                    continue
                # Find the matching activity item by activity_id.
                for idx, child in enumerate(panel.list_view.children):
                    if isinstance(child, ACTIVITY_ITEM_TYPES) and child.activity_id == target:
                        panel.list_view.index = idx
                        break
            # Collapsed state
            for panel in self._panels:
                want_collapsed = panel.panel_id in (ts.collapsed_panels or [])
                if want_collapsed != panel.collapsed:
                    panel.toggle_collapsed()
        except Exception:
            return restored_active_panel
        return restored_active_panel

    def capture_view_state(self, vs) -> None:
        """Write current screen state into the app-wide ViewState."""
        from octopus.tui.state import TabState

        cursors: dict[str, str] = {}
        scroll_offsets: dict[str, int] = {}
        for panel in self._panels:
            pid = panel.panel_id
            item = panel.list_view.highlighted_child
            if isinstance(item, ACTIVITY_ITEM_TYPES) and item.activity_id:
                cursors[pid] = item.activity_id
            try:
                scroll_offsets[pid] = int(panel.list_view.scroll_offset.y)
            except Exception:
                pass
        ts = TabState(
            tab_id="activities",
            cursors=cursors,
            active_panel=self._panels[self._active_panel_idx].panel_id,
            scroll_offsets=scroll_offsets,
            collapsed_panels=[p.panel_id for p in self._panels if p.collapsed],
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

    def _load_current(self) -> list[ListItem]:
        root = find_activity_root(self._cwd)
        if root is None:
            return []
        try:
            activity, _ = read_activity(root / ".octopus" / "activity.md")
        except Exception:
            return []
        conn = get_db()
        try:
            db_row = conn.execute(
                "SELECT * FROM activities WHERE path = ?", (str(root),)
            ).fetchone()
        except sqlite3.Error:
            db_row = None
        # Start with DB row (if any), then overlay properties from the
        # parsed activity.md so we get tags / priority / area / last_reviewed
        # which the index table doesn't surface.
        row: dict = dict(db_row) if db_row else {}
        row.setdefault("id", activity.id)
        row.setdefault("title", activity.title)
        row.setdefault("type", activity.type)
        row.setdefault("status", activity.status)
        row["path"] = str(root)
        if getattr(activity, "priority", None):
            row["priority"] = activity.priority
        if getattr(activity, "area", None):
            row["area"] = activity.area
        if getattr(activity, "tags", None):
            row["tags"] = activity.tags
        if getattr(activity, "last_reviewed", None):
            row["last_reviewed"] = activity.last_reviewed
        if getattr(activity, "created", None) and not row.get("created"):
            row["created"] = activity.created
        linked = getattr(activity, "linked_activities", None) or []
        counts = count_by_bucket(conn, row["id"]) if row.get("id") else {}
        extras = self._gather_current_extras(conn, row.get("id"))
        extras["linked_count"] = len(linked)
        return [ActivityOverview(row, counts, extras)]

    def _gather_current_extras(self, conn: sqlite3.Connection, activity_id: str | None) -> dict:
        """Collect attention-surface signals for the CURRENT panel overview."""
        if not activity_id:
            return {}
        from datetime import date, timedelta
        extras: dict = {}
        # Pinned task (slot-0 attention).
        try:
            pinned = conn.execute(
                "SELECT title FROM tasks "
                "WHERE activity_id = ? AND pinned = 1 "
                "AND (archived IS NULL OR archived = 0) "
                "ORDER BY bucket, slug LIMIT 1",
                (activity_id,),
            ).fetchone()
            if pinned and pinned["title"]:
                extras["pinned_task"] = pinned["title"]
        except sqlite3.Error:
            pass
        # Top of NOW.
        try:
            top_now = conn.execute(
                "SELECT title FROM tasks "
                "WHERE activity_id = ? AND bucket = 'now' "
                "AND (archived IS NULL OR archived = 0) "
                "ORDER BY CASE WHEN pinned = 1 THEN 0 ELSE 1 END, slug LIMIT 1",
                (activity_id,),
            ).fetchone()
            if top_now and top_now["title"]:
                extras["top_now_task"] = top_now["title"]
        except sqlite3.Error:
            pass
        # Active session = started but not ended.
        try:
            sess = conn.execute(
                "SELECT title, started FROM sessions "
                "WHERE activity_id = ? AND ended IS NULL "
                "ORDER BY started DESC LIMIT 1",
                (activity_id,),
            ).fetchone()
            if sess:
                started_val = sess["started"]
                started_str = ""
                if started_val:
                    s = str(started_val)
                    # Compact: keep date + HH:MM
                    started_str = s.replace("T", " ")[:16]
                extras["active_session"] = {
                    "title": sess["title"] or "session",
                    "started": started_str,
                }
        except sqlite3.Error:
            pass
        # Blocked/waiting count (visible in NOW + NEXT).
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM tasks "
                "WHERE activity_id = ? "
                "AND issue IN ('blocked', 'waiting') "
                "AND (archived IS NULL OR archived = 0)",
                (activity_id,),
            ).fetchone()
            if row:
                extras["blocked_count"] = int(row["n"] or 0)
        except sqlite3.Error:
            pass
        # Due within 7 days.
        try:
            soon = (date.today() + timedelta(days=7)).isoformat()
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM tasks "
                "WHERE activity_id = ? AND due IS NOT NULL AND due <= ? "
                "AND bucket != 'done' "
                "AND (archived IS NULL OR archived = 0)",
                (activity_id, soon),
            ).fetchone()
            if row:
                extras["due_soon_count"] = int(row["n"] or 0)
        except sqlite3.Error:
            pass
        return extras

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
                if isinstance(child, ACTIVITY_ITEM_TYPES):
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
        return item if isinstance(item, ACTIVITY_ITEM_TYPES) else None

    # ── actions ──────────────────────────────────────────────────────

    def action_noop(self) -> None:
        return

    def action_quit(self) -> None:
        self.app.exit()

    def action_cursor_up(self) -> None:
        lv = self._active_panel.list_view
        n = len(lv.children)
        if n == 0:
            # Empty panel — spill to previous panel that has items.
            self._spill_to_neighbor(direction=-1)
            return
        current = lv.index if lv.index is not None else 0
        if current <= 0:  # noqa: SIM102
            # Top of list — spill into previous populated panel (lands on
            # its last item). Falls through to wrap if no neighbor has items.
            if self._spill_to_neighbor(direction=-1):
                return
        lv.index = (current - 1) % n
        self._update_selection_highlights()

    def action_cursor_down(self) -> None:
        lv = self._active_panel.list_view
        n = len(lv.children)
        if n == 0:
            self._spill_to_neighbor(direction=1)
            return
        current = lv.index if lv.index is not None else -1
        if current >= n - 1:  # noqa: SIM102
            # Bottom of list — spill into next populated panel (lands on
            # its first item). Falls through to wrap if no neighbor has items.
            if self._spill_to_neighbor(direction=1):
                return
        lv.index = (current + 1) % n
        self._update_selection_highlights()

    def _spill_to_neighbor(self, *, direction: int) -> bool:
        """Move active panel to the next/previous panel that has activity
        items, landing on the first item (down) or last item (up).

        Returns True if a spill happened, False if no neighbor qualified
        (caller can then wrap within the current panel as before).
        """
        n_panels = len(self._panels)
        # Walk neighbors, skipping the current panel; stop before completing
        # a full loop so we don't spill back to ourselves.
        for step in range(1, n_panels):
            idx = (self._active_panel_idx + direction * step) % n_panels
            if idx == self._active_panel_idx:
                break
            cand = self._panels[idx]
            has_items = any(
                isinstance(c, ACTIVITY_ITEM_TYPES)
                for c in cand.list_view.children
            )
            if not has_items:
                continue
            self._focus_panel(idx)
            lv = cand.list_view
            children = list(lv.children)
            # Find first/last child that is an ACTIVITY item.
            if direction > 0:
                for j, c in enumerate(children):
                    if isinstance(c, ACTIVITY_ITEM_TYPES):
                        lv.index = j
                        break
            else:
                for j in range(len(children) - 1, -1, -1):
                    if isinstance(children[j], ACTIVITY_ITEM_TYPES):
                        lv.index = j
                        break
            self._update_selection_highlights()
            return True
        return False

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

    def action_yank_slug(self) -> None:
        block = self._selected_block
        if block is None or not block.activity_id:
            self._toast.flash("nothing selected")
            return
        slug = _short_id(block.activity_id)
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(input=slug.encode("utf-8"), timeout=2)
            if proc.returncode == 0:
                self._toast.flash(f"✓ yanked {slug}")
                return
        except Exception:
            pass
        self._toast.flash(f"slug: {slug}")

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

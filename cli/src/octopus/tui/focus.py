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
from textual.widgets import Footer, ListItem, ListView, Static

from octopus import actions
from octopus.actions import ActionError
from octopus.db.connection import get_db
from octopus.db.queries import tasks_for_activity
from octopus.fs.io import read_activity
from octopus.tui.filter_bar import FilterBar
from octopus.tui.header_bar import HeaderBar
from octopus.tui.help import HelpOverlay
from octopus.tui.icons import BLOCKED, CURSOR, PINNED
from octopus.tui.overlay import TaskDetailOverlay
from octopus.tui.prompts import BucketPickerModal, ConfirmModal, InputModal
from octopus.tui.status_bar import StatusBar
from octopus.tui.toast import Toast


def _filter_rows(rows, needle: str):
    """Case-insensitive title-substring filter. Empty needle = passthrough."""
    n = (needle or "").strip().lower()
    if not n:
        return list(rows)
    out = []
    for r in rows:
        title = (r["title"] if "title" in r.keys() else "") or ""
        if n in title.lower():
            out.append(r)
    return out


def _short_path(p: Path) -> str:
    """Render a path with $HOME collapsed to ~ for header display."""
    try:
        home = Path.home()
        rel = p.resolve().relative_to(home)
        return f"~/{rel}"
    except Exception:
        return str(p)


def _row_chips(row: sqlite3.Row) -> Text:
    """Right-side chips (pinned, blocked) — rendered as a separate Text suffix."""
    chips: list[tuple[str, str]] = []
    if "pinned" in row.keys() and row["pinned"]:
        chips.append((PINNED, "#CBA6F7"))
    run_state = row["run_state"] if "run_state" in row.keys() else None
    if run_state == "blocked":
        chips.append((BLOCKED, "#FAB387"))
    t = Text(no_wrap=True, overflow="ellipsis")
    for i, (glyph, color) in enumerate(chips):
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

    bucket = (row["bucket"] if "bucket" in row.keys() else "") or ""
    if bucket in ("done", "dropped"):
        t.append(title, style="#8A8D9A strike")
    else:
        t.append(title)
    return t


class _TaskListItem(ListItem):
    def __init__(self, row: sqlite3.Row) -> None:
        # Two static columns inside a Horizontal: title (flex) + chips (right).
        self._title_static = Static(
            _row_text(row, selected=False), classes="row-title"
        )
        self._chips_static = Static(_row_chips(row), classes="row-chips")
        super().__init__(
            Horizontal(self._title_static, self._chips_static, classes="row-line")
        )
        self.task_row = row
        self.task_slug = row["slug"]

    def render_title(self, *, selected: bool, title_offset: int = 0) -> None:
        self._title_static.update(
            _row_text(self.task_row, selected=selected, title_offset=title_offset)
        )


# Quadrant ids — used in focus tracking & captures.
Q_BACKLOG = "backlog"
Q_NOW = "now"
Q_NEXT = "next"


class FocusScreen(Screen):
    """Three-quadrant Focus mode."""

    BINDINGS = [
        # Navigation
        Binding("q", "quit", "quit", show=True),
        Binding("?", "help", "help", show=True),
        Binding("slash", "filter", "filter", show=True),
        Binding("r", "reindex", "refresh", show=True),
        Binding("enter", "open_detail", "detail", show=False),
        Binding("right", "nav_right", "→", show=False),
        Binding("left", "nav_left", "←", show=False),
        Binding("up", "nav_up", "↑", show=False),
        Binding("down", "nav_down", "↓", show=False),
        Binding("tab", "nav_tab", "next pane", show=False),
        Binding("shift+tab", "nav_shift_tab", "prev pane", show=False),
        Binding("escape", "noop", "close", show=False),
        # Mode switch
        Binding("1", "focus_mode", "focus", show=True),
        Binding("2", "board_mode", "board", show=True),
        # Mutations
        Binding("s", "session_start", "session", show=True),
        Binding("S", "session_start_titled", "session+title", show=False),
        Binding("f", "finish", "finish", show=True),
        Binding("F", "finish", "finish", show=False),
        Binding("n", "capture_inline", "capture", show=True),
        Binding("N", "capture_inline", "capture", show=False),
        Binding("m", "move_next", "advance", show=True),
        Binding("M", "move_picker", "move…", show=False),
        Binding("e", "edit_external", "edit", show=True),
        Binding("d", "drop", "drop", show=True),
        Binding("p", "toggle_pin", "pin", show=True),
    ]

    def __init__(self, activity_title: str, activity_root: Path) -> None:
        super().__init__()
        self._activity_title = activity_title
        self._activity_root = activity_root
        activity, _ = read_activity(activity_root / ".octopus" / "activity.md")
        self._activity_id = activity.id

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
            Static("  [bold]BACKLOG[/]", classes="panel-header"),
            self._lists[Q_BACKLOG],
            classes="panel",
            id="backlog-panel",
        )
        now_panel = Vertical(
            Static("  [bold]● NOW[/]", classes="panel-header"),
            self._lists[Q_NOW],
            classes="panel",
            id="now-panel",
        )
        next_panel = Vertical(
            Static("  [bold]○ NEXT[/]", classes="panel-header"),
            self._lists[Q_NEXT],
            classes="panel",
            id="next-panel",
        )
        self._panels[Q_BACKLOG] = backlog_panel
        self._panels[Q_NOW] = now_panel
        self._panels[Q_NEXT] = next_panel

        right_column = Vertical(now_panel, next_panel, id="right-column")
        yield Horizontal(backlog_panel, right_column, id="quadrants")
        yield self._toast
        yield self._status_bar
        yield Footer()

    def on_mount(self) -> None:
        self._header.title_text = "OCTOPUS"
        self._header.set_activity(self._activity_title)
        self._header.set_cwd(_short_path(self._activity_root))
        self._header.set_mode("focus")
        self._header.set_state("ready")
        self._status_bar.set_activity(self._activity_title)
        self._status_bar.set_state("ready")
        self._refresh_data()
        # Land on whichever quadrant has tasks, preferring NOW → NEXT → BACKLOG.
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
            blocked = sum(
                1 for r in backlog_rows + now_rows + next_rows
                if "run_state" in r.keys() and r["run_state"] == "blocked"
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
        self._header.set_counts(len(now_rows), len(next_rows), blocked)

    def _fill(self, quadrant: str, rows: list[sqlite3.Row], *, empty_msg: str) -> None:
        lst = self._lists[quadrant]
        lst.clear()
        if not rows:
            self._render_empty(quadrant, empty_msg)
            return
        for r in rows:
            lst.append(_TaskListItem(r))
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
        for q, lst in self._lists.items():
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

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Repaint when arrow-nav moves within a list — keeps the cursor glyph
        in sync with the highlight without waiting for the marquee tick."""
        # Only the *active* quadrant's selected row should show "▸".
        # Strip the cursor from every row in every quadrant, then repaint the
        # one currently selected in the active list.
        for lst in self._lists.values():
            for child in lst.children:
                if isinstance(child, _TaskListItem):
                    try:
                        child.render_title(selected=False, title_offset=0)
                    except Exception:
                        pass
        self._marquee_item = None
        self._marquee_offset = 0
        new_item = self._current_item()
        if new_item is not None:
            try:
                new_item.render_title(selected=True, title_offset=0)
            except Exception:
                pass

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

    def _has_real_tasks(self, q: str) -> bool:
        """True if this quadrant has at least one selectable task (not just empty-state)."""
        for child in self._lists[q].children:
            if isinstance(child, _TaskListItem):
                return True
        return False

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
        # Linear walk: BACKLOG → NOW → NEXT. Right from NEXT is a no-op.
        if self._active == Q_BACKLOG:
            self._set_active(Q_NOW)
        elif self._active == Q_NOW:
            self._set_active(Q_NEXT)
        # Already in NEXT: no-op (rightmost)

    def action_nav_left(self) -> None:
        # Linear walk back: NEXT → NOW → BACKLOG. Left from BACKLOG is a no-op.
        if self._active == Q_NEXT:
            self._set_active(Q_NOW)
        elif self._active == Q_NOW:
            self._set_active(Q_BACKLOG)

    def action_nav_up(self) -> None:
        # If at top of NEXT (or NEXT empty), jump up to NOW.
        if self._active == Q_NEXT and self._is_at_first(Q_NEXT):
            if self._has_real_tasks(Q_NOW):
                self._set_active(Q_NOW)
                try:
                    self._lists[Q_NOW].index = len(self._lists[Q_NOW].children) - 1
                except Exception:
                    pass
                return
        # Otherwise move within the current list.
        try:
            self._current_list().action_cursor_up()
        except Exception:
            pass

    def action_nav_down(self) -> None:
        # If at bottom of NOW (or NOW empty), fall through to NEXT.
        if self._active == Q_NOW and self._is_at_last(Q_NOW):
            if self._has_real_tasks(Q_NEXT):
                self._set_active(Q_NEXT)
                try:
                    self._lists[Q_NEXT].index = 0
                except Exception:
                    pass
                return
        try:
            self._current_list().action_cursor_down()
        except Exception:
            pass

    def action_nav_tab(self) -> None:
        order = [Q_BACKLOG, Q_NOW, Q_NEXT]
        i = order.index(self._active)
        self._set_active(order[(i + 1) % len(order)])

    def action_nav_shift_tab(self) -> None:
        order = [Q_BACKLOG, Q_NOW, Q_NEXT]
        i = order.index(self._active)
        self._set_active(order[(i - 1) % len(order)])

    # ── nav actions ───────────────────────────────────────────────────

    def action_noop(self) -> None:
        pass

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

    def action_open_detail(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        self.app.push_screen(TaskDetailOverlay(self._activity_root, slug))

    # ── mutation actions ──────────────────────────────────────────────

    def _run(self, fn, *, success_msg: str, refresh: bool = True) -> None:
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
        if refresh:
            self._refresh_data()

    def action_finish(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return
        self._run(
            lambda: actions.finish_task(self._activity_root, slug),
            success_msg=f"{slug} finished",
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
        if item and "bucket" in item.task_row.keys():
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

    def action_edit_external(self) -> None:
        slug = self._current_slug()
        if slug is None:
            self._toast.flash("nothing selected")
            return

        from octopus.actions import find_task_file
        from octopus.fs.scaffold import read_storage_mode

        try:
            storage_mode = read_storage_mode(self._activity_root / ".octopus")
            path = find_task_file(self._activity_root / ".octopus", storage_mode, slug)
        except Exception as exc:
            self._toast.flash(f"✗ {exc}")
            return
        if path is None:
            self._toast.flash(f"✗ task file not found: {slug}")
            return

        editor = os.environ.get("EDITOR", "vi")
        if hasattr(self.app, "suspend"):
            with self.app.suspend():
                try:
                    subprocess.run([editor, str(path)], check=False)
                except Exception as exc:
                    print(f"editor failed: {exc}", flush=True)
            self._refresh_data()
            self._toast.flash(f"✓ edited {slug}")
        else:
            self._toast.flash(f"open: {path}  (e needs newer Textual)")

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

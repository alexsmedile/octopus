"""BoardScreen — kanban-style sliding 3-column view over 5 buckets.

Layout (3 of 5 buckets visible at a time):

    ┌── BACKLOG ──┬── NEXT ──┬── NOW ──┐
    │  ▸ task A   │  task X  │  task M │
    │    task B   │  task Y  │  task N │
    └─────────────┴──────────┴─────────┘

Pages (5 buckets, window of 3 → 3 pages):

    page 0: backlog | next    | now
    page 1: next    | now     | done
    page 2: now     | done    | dropped

Same row widget, overlay, and mutation keymap as FocusScreen. Navigation:
  - `←`/`→` walks the cursor within the visible window; pressing past the
    rightmost panel slides to the next page (cursor stays on rightmost
    slot). Same for left-edge.
  - `]` / `[` slide the window without moving the cursor slot.
  - Tab / Shift-Tab mirror →/←.
  - `↑`/`↓` move within the focused column.
  - `n` captures into the focused column.
  - Left hard-stops at page 0; right past page 2 jumps back to page 0
    (explicit reset to start — not a circular loop).

Mode switcher: `1` = Focus, `2` = Board (handled at App level).
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import ListItem, ListView, Static

from octopus.tui.keymap_bar import KeymapBar

from octopus import actions
from octopus.actions import ActionError
from octopus.db.connection import get_db
from octopus.db.queries import tasks_for_activity
from octopus.fs.io import read_activity
from octopus.tui.filter_bar import FilterBar
from octopus.tui.focus import (
    _drop_zombies,
    _filter_rows,
    _render_detail,
    _TaskListItem,
)
from octopus.tui.header_bar import HeaderBar
from octopus.tui.help import HelpOverlay
from octopus.tui.prompts import BucketPickerModal, ConfirmModal, InputModal
from octopus.tui.status_bar import StatusBar
from octopus.tui.toast import Toast

# Column ids — match real bucket names (used directly in captures + moves).
C_BACKLOG = "backlog"
C_NEXT = "next"
C_NOW = "now"
C_DONE = "done"
C_DROPPED = "dropped"
# Pipeline order. The board renders a 3-wide window over this cycle.
COLUMNS = (C_BACKLOG, C_NEXT, C_NOW, C_DONE, C_DROPPED)

# Number of buckets visible at a time.
WINDOW_SIZE = 3


class BoardScreen(Screen):
    """Four-column kanban Board."""

    BINDINGS = [
        Binding("q", "quit", "quit", show=True),
        Binding("?", "help", "help", show=True),
        Binding("slash", "filter", "filter", show=True),
        Binding("r", "reindex", "refresh", show=True),
        Binding("comma", "toggle_detail_pane", "detail", show=True, priority=True),
        Binding("enter", "preview", "preview", show=False, priority=True),
        Binding("right", "nav_right", "→", show=False),
        Binding("left", "nav_left", "←", show=False),
        Binding("up", "nav_up", "↑", show=False),
        Binding("down", "nav_down", "↓", show=False),
        Binding("tab", "nav_tab", "next col", show=False),
        Binding("shift+tab", "nav_shift_tab", "prev col", show=False),
        Binding("right_square_bracket", "slide_right", "slide →", show=False),
        Binding("left_square_bracket", "slide_left", "slide ←", show=False),
        Binding("escape", "noop", "close", show=False, priority=True),
        # Mode switch (App-level alias). priority=True so ListView focus
        # doesn't swallow the digit on Textual 8.x.
        Binding("0", "activities_mode", "activities", show=True, priority=True),
        Binding("1", "focus_mode", "focus", show=True, priority=True),
        Binding("2", "board_mode", "board", show=True, priority=True),
        # Mutations
        Binding("s", "session_start", "session", show=True),
        Binding("f", "finish", "finish", show=True),
        Binding("n", "capture_inline", "capture", show=True),
        Binding("m", "move_next", "advance", show=True),
        Binding("M", "move_picker", "move…", show=False),
        Binding("e", "edit_inline", "edit", show=True),
        Binding("E", "edit_external", "edit ($EDITOR)", show=False),
        Binding("d", "drop", "drop", show=True),
        Binding("p", "toggle_pin", "pin", show=True),
        Binding("H", "cycle_header_mode", "header size", show=False),
    ]

    def action_cycle_header_mode(self) -> None:
        try:
            new_mode = self._header.cycle_display_mode()
        except Exception:
            return
        try:
            self._toast.flash(f"header: {new_mode}")
        except Exception:
            pass

    def __init__(self, activity_title: str, activity_root: Path) -> None:
        super().__init__()
        self._activity_title = activity_title
        self._activity_root = activity_root
        activity, _ = read_activity(activity_root / ".octopus" / "activity.md")
        self._activity_id = activity.id
        try:
            from octopus.config import load_config
            self._provider_chips = dict(
                load_config(activity_root / ".octopus").provider_chips
            )
        except Exception:
            self._provider_chips = {}

        self._lists: dict[str, ListView] = {
            c: ListView(id=f"board-{c}-list") for c in COLUMNS
        }
        self._panels: dict[str, Vertical] = {}
        # Sliding 3-column window over COLUMNS. Initial: backlog | next | now.
        self._window_start: int = 0
        self._active: str = C_NOW

        self._status_bar = StatusBar()
        self._toast = Toast()
        self._header = HeaderBar()
        self._filter_text: str = ""

        self._marquee_offset: int = 0
        self._marquee_timer = None
        self._marquee_item: _TaskListItem | None = None

        # Inline detail pane (docks bottom when visible).
        self._detail_visible: bool = False
        self._detail_body = Static("", id="board-detail-body", expand=True)
        self._detail_scroll = VerticalScroll(
            self._detail_body, id="board-detail-scroll"
        )

    # Border titles per bucket.
    _HEADERS = {
        C_BACKLOG: "BACKLOG",
        C_NEXT: "□ NEXT",
        C_NOW: "▣ NOW",
        C_DONE: "● DONE",
        C_DROPPED: "✕ DROPPED",
    }

    def compose(self) -> ComposeResult:
        yield self._header

        cols = []
        for c in COLUMNS:
            panel = Vertical(
                self._lists[c],
                classes="panel",
                id=f"board-{c}-panel",
            )
            panel.border_title = self._HEADERS[c]
            self._panels[c] = panel
            cols.append(panel)

        yield Horizontal(*cols, id="board-columns")

        # Inline detail panel — hidden until user opens it.
        detail_panel = Vertical(
            self._detail_scroll,
            classes="panel",
            id="board-detail-panel",
        )
        detail_panel.border_title = "DETAIL"
        detail_panel.styles.display = "none"
        self._detail_panel = detail_panel
        yield detail_panel

        yield self._toast
        yield self._status_bar
        yield KeymapBar()

    def on_mount(self) -> None:
        from octopus.tui.focus import _short_path
        self._header.title_text = "OCTOPUS"
        self._header.set_activity(self._activity_title)
        self._header.set_cwd(_short_path(self._activity_root))
        from octopus.tui.focus import _git_repo_name
        self._header.set_repo_name(_git_repo_name(self._activity_root))
        self._header.set_mode("board")
        self._header.set_state("ready")
        try:
            term_width = self.app.size.width
        except Exception:
            term_width = 120
        self._header.set_display_mode(self._header.auto_mode_for_width(term_width))
        self._status_bar.set_activity_id(self._activity_id)
        self._status_bar.set_state("ready")
        self._refresh_data()
        # Restore cursor from a prior view, if one was stashed.
        shared = getattr(self.app, "shared_cursor", (None, None))
        prev_bucket, prev_slug = shared if isinstance(shared, tuple) else (None, None)

        # Pick window page: align to the page that contains prev_bucket if any.
        if prev_bucket in COLUMNS:
            idx = COLUMNS.index(prev_bucket)
            # Window must contain idx and stay within bounds.
            self._window_start = max(0, min(idx, self._MAX_START))
        # else: default page 0
        self._apply_window()

        # Pick active column.
        visible = self._visible_columns()
        chosen: str | None = None
        if prev_bucket in visible:
            chosen = prev_bucket
        else:
            for c in (C_NOW, C_NEXT, C_BACKLOG):
                if c in visible and self._has_real_tasks(c):
                    chosen = c
                    break
        if chosen is None:
            chosen = C_NOW if C_NOW in visible else visible[-1]
        self._set_active(chosen)

        # Restore highlight to the previously selected slug, if still present.
        if prev_slug:
            self._highlight_slug(chosen, prev_slug)

    def _highlight_slug(self, col: str, slug: str) -> None:
        lst = self._lists.get(col)
        if lst is None:
            return
        for i, child in enumerate(lst.children):
            if isinstance(child, _TaskListItem) and child.task_slug == slug:
                try:
                    lst.index = i
                except Exception:
                    pass
                return
        self._marquee_timer = self.set_interval(0.4, self._tick_marquee)

    # ── data ──────────────────────────────────────────────────────────

    def _refresh_data(self) -> None:
        try:
            conn = get_db()
        except Exception as exc:
            for c in COLUMNS:
                self._render_empty(c, f"(index unavailable: {exc})")
            self._status_bar.set_counts(0, 0, 0)
            self._header.set_counts(0, 0, 0)
            return

        rows_by_col: dict[str, list[sqlite3.Row]] = {}
        try:
            for c in COLUMNS:
                rows_by_col[c] = list(tasks_for_activity(conn, self._activity_id, bucket=c))
            from octopus.tui.focus import _row_has
            blocked = sum(
                1 for rows in rows_by_col.values() for r in rows
                if _row_has(r, "run_state") and r["run_state"] == "blocked"
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Drop zombie rows — index entries with missing backing files.
        for c in COLUMNS:
            rows_by_col[c] = _drop_zombies(self._activity_root, rows_by_col[c])

        if self._filter_text:
            for c in COLUMNS:
                rows_by_col[c] = _filter_rows(rows_by_col[c], self._filter_text)

        empties = {
            C_BACKLOG: "  Empty.   Press [#F38BA8 bold]n[/] to capture.",
            C_NEXT: "  Empty.   Use [#F38BA8 bold]m[/] from backlog to plan.",
            C_NOW: "  Empty.   Use [#F38BA8 bold]m[/] from next to activate.",
            C_DONE: "  Nothing finished yet.",
            C_DROPPED: "  Nothing dropped.",
        }
        for c in COLUMNS:
            self._fill(c, rows_by_col[c], empty_msg=empties[c])

        self._status_bar.set_counts(
            len(rows_by_col[C_NOW]), len(rows_by_col[C_NEXT]), blocked,
        )
        self._header.set_counts(
            now=len(rows_by_col[C_NOW]),
            next_=len(rows_by_col[C_NEXT]),
            blocked=blocked,
            backlog=len(rows_by_col[C_BACKLOG]),
            done=len(rows_by_col[C_DONE]),
        )

    def _fill(self, col: str, rows: list[sqlite3.Row], *, empty_msg: str) -> None:
        lst = self._lists[col]
        lst.clear()
        if not rows:
            self._render_empty(col, empty_msg)
            return
        for r in rows:
            lst.append(_TaskListItem(r, provider_chips=self._provider_chips))
        try:
            lst.index = 0
        except Exception:
            pass

    def _render_empty(self, col: str, message: str) -> None:
        lst = self._lists[col]
        lst.clear()
        item = ListItem(Static(message, classes="empty-hint"))
        item.disabled = True
        lst.append(item)

    # ── focus / nav ───────────────────────────────────────────────────

    def _set_active(self, col: str) -> None:
        # Strip cursor from every row in every column.
        for _c, lst in self._lists.items():
            for child in lst.children:
                if isinstance(child, _TaskListItem):
                    try:
                        child.render_title(selected=False, title_offset=0)
                    except Exception:
                        pass
        self._marquee_item = None
        self._marquee_offset = 0

        self._active = col

        for c, panel in self._panels.items():
            if c == col:
                panel.add_class("panel--focused")
            else:
                panel.remove_class("panel--focused")
        try:
            self.set_focus(self._lists[col])
        except Exception:
            pass

        new_item = self._current_item()
        if new_item is not None:
            try:
                new_item.render_title(selected=True, title_offset=0)
            except Exception:
                pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
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
        if self._detail_visible:
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

    def _has_real_tasks(self, c: str) -> bool:
        return any(isinstance(child, _TaskListItem) for child in self._lists[c].children)

    # ── window ────────────────────────────────────────────────────────

    def _visible_columns(self) -> tuple[str, ...]:
        """Return the WINDOW_SIZE buckets currently visible, in display order.

        Window is clamped to 0 <= _window_start <= len(COLUMNS) - WINDOW_SIZE,
        so this is just a plain slice — no wrap.
        """
        return tuple(
            COLUMNS[self._window_start + i] for i in range(WINDOW_SIZE)
        )

    def _apply_window(self) -> None:
        """Show only the panels in the current window; hide the rest.

        Order matters — the visible panels keep COLUMNS' DOM order, so the
        leftmost on-screen column may be any bucket depending on
        _window_start. We use `display = True/False` and a per-panel
        `layout-order` style to reorder visible panels left-to-right.
        """
        visible = self._visible_columns()
        for c, panel in self._panels.items():
            if c in visible:
                panel.display = True
            else:
                panel.display = False
        # Reorder visible panels so they appear left-to-right in window order.
        # Textual lays out by DOM order; move each visible panel after the
        # previous one to enforce the desired sequence.
        try:
            container = self.query_one("#board-columns")
        except Exception:
            return
        prev_panel = None
        for c in visible:
            panel = self._panels[c]
            try:
                if prev_panel is None:
                    # Put first visible panel before everything else.
                    container.move_child(panel, before=0)
                else:
                    container.move_child(panel, after=prev_panel)
            except Exception:
                pass
            prev_panel = panel

    def _cursor_slot(self) -> int:
        """Index (0..WINDOW_SIZE-1) of `_active` within the visible window."""
        visible = self._visible_columns()
        try:
            return visible.index(self._active)
        except ValueError:
            return 0

    # Last valid window start. With 5 buckets and WINDOW_SIZE=3 → 2,
    # giving pages 0..2: backlog|next|now, next|now|done, now|done|dropped.
    _MAX_START = len(COLUMNS) - WINDOW_SIZE

    def action_slide_right(self) -> None:
        """Slide window +1. Past the last page, jump back to page 0."""
        slot = self._cursor_slot()
        if self._window_start < self._MAX_START:
            self._window_start += 1
        else:
            # Already at the rightmost page — jump back to the start.
            self._window_start = 0
        self._apply_window()
        self._set_active(self._visible_columns()[slot])

    def action_slide_left(self) -> None:
        """Slide window -1. Hard stop at page 0 (no wrap)."""
        if self._window_start <= 0:
            return
        slot = self._cursor_slot()
        self._window_start -= 1
        self._apply_window()
        self._set_active(self._visible_columns()[slot])

    # ── nav ───────────────────────────────────────────────────────────

    def action_nav_right(self) -> None:
        slot = self._cursor_slot()
        if slot < WINDOW_SIZE - 1:
            self._set_active(self._visible_columns()[slot + 1])
        elif self._window_start < self._MAX_START:
            # Past rightmost and more pages to the right: slide window.
            self._window_start += 1
            self._apply_window()
            self._set_active(self._visible_columns()[WINDOW_SIZE - 1])
        else:
            # At the rightmost slot of the last page — jump back to page 0
            # and land the cursor on its leftmost bucket (backlog).
            self._window_start = 0
            self._apply_window()
            self._set_active(self._visible_columns()[0])

    def action_nav_left(self) -> None:
        slot = self._cursor_slot()
        if slot > 0:
            self._set_active(self._visible_columns()[slot - 1])
        elif self._window_start > 0:
            # Before leftmost and more pages to the left: slide window back.
            self._window_start -= 1
            self._apply_window()
            self._set_active(self._visible_columns()[0])
        # else: at the leftmost slot of page 0 — hard stop, no wrap.

    def action_nav_up(self) -> None:
        try:
            self._current_list().action_cursor_up()
        except Exception:
            pass

    def action_nav_down(self) -> None:
        try:
            self._current_list().action_cursor_down()
        except Exception:
            pass

    def action_nav_tab(self) -> None:
        # Same shape as nav_right — slides past the rightmost.
        self.action_nav_right()

    def action_nav_shift_tab(self) -> None:
        # Same shape as nav_left.
        self.action_nav_left()

    def action_focus_mode(self) -> None:
        # Stash current (bucket, slug) so the incoming FocusScreen can
        # restore the same row.
        try:
            self.app.shared_cursor = (self._active, self._current_slug())
        except Exception:
            pass
        if hasattr(self.app, "switch_to_focus"):
            self.app.switch_to_focus()

    def action_board_mode(self) -> None:
        # Already in Board — no-op.
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
            if self._filter_text:
                self._toast.flash(f"filter: {self._filter_text!r}  (r to clear)")

        self.app.push_screen(
            FilterBar(initial=self._filter_text, on_change=_on_change),
            _on_done,
        )

    # ── marquee ───────────────────────────────────────────────────────

    def _tick_marquee(self) -> None:
        item = self._current_item()
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
        try:
            visible_width = max(10, item._title_static.size.width)
        except Exception:
            visible_width = 40
        title_budget = max(4, visible_width - 2)
        if len(title) <= title_budget:
            if self._marquee_offset != 0:
                self._marquee_offset = 0
                item.render_title(selected=True, title_offset=0)
            return
        self._marquee_offset += 1
        item.render_title(selected=True, title_offset=self._marquee_offset)

    # ── actions ───────────────────────────────────────────────────────

    def action_noop(self) -> None:
        # Esc cascades: collapse expanded preview → close detail pane →
        # prompt "back to Activities?".
        item = self._current_item()
        if item is not None and item._expanded:
            item.set_expanded(False)
            return
        if self._detail_visible:
            self.action_toggle_detail_pane()
            return
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

    def action_reindex(self) -> None:
        had_filter = bool(self._filter_text)
        self._filter_text = ""
        self._status_bar.set_state("refreshing…", busy=True)
        self._header.set_state("refreshing…", busy=True)
        self._refresh_data()
        self._status_bar.set_state("ready", busy=False)
        self._header.set_state("ready", busy=False)
        self._toast.flash("⟳ refreshed · filter cleared" if had_filter else "⟳ refreshed")

    def action_preview(self) -> None:
        """Enter toggles a one-row property preview beneath the highlighted task."""
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

    def action_toggle_detail_pane(self) -> None:
        """Toggle the inline detail pane (docks at the bottom of the board)."""
        slug = self._current_slug()
        if slug is None and not self._detail_visible:
            self._toast.flash("nothing selected")
            return
        self._detail_visible = not self._detail_visible
        if self._detail_panel is None:
            return
        if self._detail_visible:
            self._detail_panel.styles.display = "block"
            self._refresh_detail()
            # Focus the scroll so ↓/↑ scroll the body.
            try:
                self.set_focus(self._detail_scroll)
            except Exception:
                pass
        else:
            self._detail_panel.styles.display = "none"
            # Return focus to the active column.
            try:
                self.set_focus(self._lists[self._active])
            except Exception:
                pass

    def _refresh_detail(self) -> None:
        if not self._detail_visible:
            return
        slug = self._current_slug()
        try:
            self._detail_body.update(_render_detail(self._activity_root, slug))
        except Exception as exc:
            self._detail_body.update(f"(detail unavailable: {exc})")

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
        """Send a trigger to the header mascot. Silent on lookup miss."""
        try:
            from octopus.tui.header_bar import _Mascot
            mascot = self.app.query_one("#header-mascot", _Mascot)
            mascot.trigger(animation_name)
        except Exception:
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

        self.app.push_screen(ConfirmModal(f"Drop [bold]{slug}[/]?"), _on_confirm)

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
        current = item.task_row["bucket"] if item and "bucket" in item.task_row else None

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
        # Don't allow capturing into terminal buckets — pointless.
        target_bucket = self._active
        if target_bucket in (C_DONE, C_DROPPED):
            self._toast.flash(f"can't capture into {target_bucket}")
            return

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

    def action_session_start(self) -> None:
        self._run(
            lambda: actions.start_session_for(self._activity_root),
            success_msg="session started",
            refresh=False,
        )

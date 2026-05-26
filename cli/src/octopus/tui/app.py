"""OctopusApp — Textual app shell.

Boots into ActivitiesScreen when launched without an activity context;
otherwise boots into FocusScreen for that activity. `0/1/2` switch
between Activities / Focus / Board modes.

View-state persistence (request #44):
- `view_state` is a process-singleton holding per-tab cursor/scroll/panel
  state, always-on while octopus runs (L1+L2).
- If config `[ui] restore_last_view = true`, state is read from
  `~/.cache/octopus/ui-state.json` on boot and written back on quit + on
  every tab swap (L3).
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

from octopus.config import load_config
from octopus.fs.io import read_activity
from octopus.tui.activities_screen import ActivitiesScreen
from octopus.tui.board import BoardScreen
from octopus.tui.focus import FocusScreen
from octopus.tui.state import ViewState
from octopus.tui.state import load as load_view_state
from octopus.tui.state import save as save_view_state


class OctopusApp(App):
    """Top-level Textual app for `octopus tui`."""

    TITLE = "octopus"
    SUB_TITLE = "tui"

    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "quit"),
    ]

    def __init__(
        self,
        activity_root: Path | None = None,
        *,
        restore_last_view: bool | None = None,
    ) -> None:
        super().__init__()
        self._activity_root = activity_root
        if activity_root is not None:
            activity_md = activity_root / ".octopus" / "activity.md"
            activity, _ = read_activity(activity_md)
            self._activity_title = activity.title or activity_root.name
        else:
            self._activity_title = None
        # Legacy shared cursor (kept for back-compat with board.py's mode-swap path).
        self.shared_cursor: tuple[str | None, str | None] = (None, None)

        # ── View-state persistence (req #44) ─────────────────────────
        # Resolve the L3 toggle: explicit arg wins, else read config.
        if restore_last_view is None:
            try:
                restore_last_view = bool(load_config().restore_last_view)
            except Exception:
                restore_last_view = False
        self._restore_last_view: bool = bool(restore_last_view)
        # L1+L2 are always-on in memory. L3 only changes whether we read/write disk.
        self.view_state: ViewState = (
            load_view_state() if self._restore_last_view else ViewState()
        )

    def on_mount(self) -> None:
        # Determine boot screen.
        # L3 restore takes priority when enabled and a meaningful target exists.
        if self._restore_last_view and self.view_state.per_tab:
            screen = self._restore_boot_screen()
            if screen is not None:
                self.push_screen(screen)
                return
        if self._activity_root is None:
            self.push_screen(ActivitiesScreen())
        else:
            self.push_screen(
                FocusScreen(self._activity_title, self._activity_root)
            )

    def _restore_boot_screen(self):
        """Pick boot screen from `view_state.active_tab`. Returns None on
        unresolvable state — caller falls back to the default boot path."""
        active = self.view_state.active_tab
        if active == "activities":
            return ActivitiesScreen(cwd=self._activity_root or Path.cwd())
        if active.startswith("focus:") or active.startswith("board:"):
            # Namespaced state needs an activity_root to launch into.
            if self._activity_root is None:
                # Can't honor a per-activity restore without a cwd activity;
                # fall back to Activities so the user can pick.
                return ActivitiesScreen()
            if active.startswith("board:"):
                return BoardScreen(self._activity_title, self._activity_root)
            return FocusScreen(self._activity_title, self._activity_root)
        return None

    # ── mode switching (called by screens) ──────────────────────────────

    def switch_to_activities(self) -> None:
        self._swap_top(ActivitiesScreen(cwd=self._activity_root or Path.cwd()))

    def switch_to_focus(self) -> None:
        if self._activity_root is None:
            return
        self._swap_top(
            FocusScreen(self._activity_title, self._activity_root)
        )

    def switch_to_board(self) -> None:
        if self._activity_root is None:
            return
        self._swap_top(
            BoardScreen(self._activity_title, self._activity_root)
        )

    def drill_into_activity(self, activity_root: Path, *, mode: str = "focus") -> None:
        """Enter a per-activity TUI for the given activity (Activities → Focus/Board)."""
        activity_md = activity_root / ".octopus" / "activity.md"
        if not activity_md.is_file():
            return
        activity, _ = read_activity(activity_md)
        title = activity.title or activity_root.name
        self._activity_root = activity_root
        self._activity_title = title
        if mode == "board":
            self._swap_top(BoardScreen(title, activity_root))
        else:
            self._swap_top(FocusScreen(title, activity_root))

    # ── view-state hooks ───────────────────────────────────────────────

    def _capture_outgoing_state(self) -> None:
        """Ask the top screen to write its current state into ViewState."""
        if not self.screen_stack:
            return
        for screen in reversed(self.screen_stack):
            if hasattr(screen, "capture_view_state"):
                try:
                    screen.capture_view_state(self.view_state)
                except Exception:
                    pass
                return

    def _swap_top(self, new_screen) -> None:
        """Pop any modals + the current root screen, then push a fresh one.

        Textual 8.x's `switch_screen` requires a result callback on the
        outgoing screen — our root screens are pushed without one (via
        `push_screen` in `on_mount`), so `switch_screen` blows up with
        `IndexError: pop from empty list`. Avoid by popping then pushing.
        """
        # Capture state from the screen we're leaving before tearing it down.
        self._capture_outgoing_state()
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(new_screen)
        # Persist on every transition when L3 enabled.
        if self._restore_last_view:
            save_view_state(self.view_state)

    def exit(self, *args, **kwargs):
        """Override exit to capture + persist view state before tearing down."""
        try:
            self._capture_outgoing_state()
            if self._restore_last_view:
                save_view_state(self.view_state)
        except Exception:
            pass
        super().exit(*args, **kwargs)

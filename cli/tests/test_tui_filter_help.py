"""Tests for filter helper and help/filter-bar modules."""

from __future__ import annotations


def _row(title: str):
    """Tiny stand-in for sqlite3.Row with a .keys()/__getitem__ shape."""
    class R(dict):
        def keys(self):
            return super().keys()
        def __getitem__(self, k):
            return super().__getitem__(k)
    return R(title=title)


def test_filter_rows_empty_needle_passthrough() -> None:
    from octopus.tui.focus import _filter_rows
    rows = [_row("alpha"), _row("beta"), _row("gamma")]
    assert len(_filter_rows(rows, "")) == 3
    assert len(_filter_rows(rows, "   ")) == 3


def test_filter_rows_case_insensitive_substring() -> None:
    from octopus.tui.focus import _filter_rows
    rows = [_row("Ship the TUI"), _row("Build SQLite indexer"), _row("Apple Reminders")]
    out = _filter_rows(rows, "sql")
    assert len(out) == 1
    assert out[0]["title"] == "Build SQLite indexer"
    # Case folding both sides.
    assert len(_filter_rows(rows, "APPLE")) == 1
    assert len(_filter_rows(rows, "no-match-here")) == 0


def test_help_overlay_imports_and_renders_keymap() -> None:
    """Help module loads and the keymap groups include the key bindings users
    actually have."""
    from octopus.tui.help import _GROUPS, HelpOverlay

    keys = {k for _, entries in _GROUPS for k, _ in entries}
    # A few non-negotiables.
    for k in ("n", "m", "f", "d", "p", "q", "?", "/", "r"):
        assert k in keys, f"help groups missing key {k!r}"
    assert HelpOverlay is not None


def test_filter_bar_module_imports() -> None:
    from octopus.tui.filter_bar import FilterBar
    assert FilterBar is not None


def test_focus_and_board_bind_filter_and_help() -> None:
    from octopus.tui.board import BoardScreen
    from octopus.tui.focus import FocusScreen

    for scr in (FocusScreen, BoardScreen):
        keys = {b.key for b in scr.BINDINGS}
        assert "slash" in keys, f"{scr.__name__} missing `/` binding"
        assert "?" in keys, f"{scr.__name__} missing `?` binding"
        assert "r" in keys, f"{scr.__name__} missing `r` binding"

"""Tests for BoardScreen — sliding 3-column kanban over 5 buckets."""

from __future__ import annotations


def test_board_columns_are_real_buckets() -> None:
    """Column ids must match real bucket names (used for captures + moves)."""
    from octopus.core.models import TASK_BUCKETS
    from octopus.tui.board import (
        C_BACKLOG,
        C_DONE,
        C_DROPPED,
        C_NEXT,
        C_NOW,
        COLUMNS,
        WINDOW_SIZE,
    )

    assert COLUMNS == (C_BACKLOG, C_NEXT, C_NOW, C_DONE, C_DROPPED)
    assert WINDOW_SIZE == 3
    for c in COLUMNS:
        assert c in TASK_BUCKETS


def test_board_module_imports() -> None:
    """Board module loads without pulling textual at import-of-octopus.cli time."""
    import sys

    for mod in list(sys.modules):
        if mod == "textual" or mod.startswith("textual."):
            del sys.modules[mod]
    if "octopus.cli" in sys.modules:
        del sys.modules["octopus.cli"]
    import octopus.cli  # noqa: F401

    assert "textual" not in sys.modules, "textual must not load on cli import"


def test_board_screen_class_present() -> None:
    from octopus.tui.board import BoardScreen

    assert hasattr(BoardScreen, "BINDINGS")
    binding_keys = {b.key for b in BoardScreen.BINDINGS}
    # Mode switches + core nav + window slide + mutations must all be bound.
    for k in (
        "1", "2", "left", "right", "up", "down",
        "n", "m", "f", "d", "p", "e", "s",
        "left_square_bracket", "right_square_bracket",
    ):
        assert k in binding_keys, f"Board missing binding for {k!r}"


def test_app_has_mode_switchers() -> None:
    from octopus.tui.app import OctopusApp

    assert hasattr(OctopusApp, "switch_to_focus")
    assert hasattr(OctopusApp, "switch_to_board")


def test_window_math_clamps_no_wrap() -> None:
    """Sliding window walks pages 0..MAX_START in order, no wrap."""
    from octopus.tui.board import COLUMNS, WINDOW_SIZE

    max_start = len(COLUMNS) - WINDOW_SIZE
    pages = [
        tuple(COLUMNS[start + i] for i in range(WINDOW_SIZE))
        for start in range(max_start + 1)
    ]
    # 5 buckets, window 3 → 3 pages.
    assert len(pages) == 3
    assert pages[0] == ("backlog", "next", "now")
    assert pages[1] == ("next", "now", "done")
    assert pages[2] == ("now", "done", "dropped")
    # Every page is a contiguous slice (no wrap), buckets unique.
    for w in pages:
        assert len(set(w)) == WINDOW_SIZE

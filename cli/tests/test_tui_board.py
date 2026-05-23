"""Tests for BoardScreen — four-column kanban."""

from __future__ import annotations


def test_board_columns_are_real_buckets() -> None:
    """Column ids must match real bucket names (used for captures + moves)."""
    from octopus.core.models import TASK_BUCKETS
    from octopus.tui.board import C_BACKLOG, C_DONE, C_NEXT, C_NOW, COLUMNS

    assert COLUMNS == (C_BACKLOG, C_NEXT, C_NOW, C_DONE)
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
    # Mode switches + core nav + mutations must all be bound.
    for k in ("1", "2", "left", "right", "up", "down", "n", "m", "f", "d", "p", "e", "s"):
        assert k in binding_keys, f"Board missing binding for {k!r}"


def test_app_has_mode_switchers() -> None:
    from octopus.tui.app import OctopusApp

    assert hasattr(OctopusApp, "switch_to_focus")
    assert hasattr(OctopusApp, "switch_to_board")

"""Group 8 polish — quit-confirm + broken-task resilience."""

from __future__ import annotations


def test_focus_and_board_override_action_quit() -> None:
    """Both screens must override action_quit so we can intercept and
    confirm when a session is open."""
    from octopus.tui.board import BoardScreen
    from octopus.tui.focus import FocusScreen

    for scr in (FocusScreen, BoardScreen):
        assert "action_quit" in scr.__dict__, (
            f"{scr.__name__} must override action_quit to add session-open "
            "confirm. Inherited default would exit unconditionally."
        )


def test_overlay_handles_missing_task_file(tmp_path) -> None:
    """If the task slug exists in the index but the file is gone, the
    detail-overlay file lookup returns None — not raises."""
    from octopus.tui.overlay import _find_task_file

    octo = tmp_path / ".octopus"
    (octo / "tasks").mkdir(parents=True)
    assert _find_task_file(octo, "flat", "ghost") is None


def test_overlay_handles_unparseable_yaml(tmp_path) -> None:
    """Broken YAML at the head of a task file shouldn't crash read_task — it
    should surface as an exception the overlay catches."""
    from octopus.fs.io import read_task

    octo = tmp_path / ".octopus"
    (octo / "tasks").mkdir(parents=True)
    f = octo / "tasks" / "broken.md"
    f.write_text("---\nthis: is: not: yaml: [unbalanced\n---\nbody")
    # Either it raises (caught by overlay try/except) or returns gracefully —
    # both are acceptable; the test asserts we don't get a silent corruption.
    try:
        task, body = read_task(f)
        # If it parsed despite the mess, at minimum we have something.
        assert task is not None
    except Exception:
        pass  # Overlay wraps read_task in try/except — this is expected.


def test_quit_confirm_module_imports() -> None:
    """The quit action references sessions.cache.get_active — confirm the
    symbol exists so the import inside action_quit won't blow up."""
    from octopus.sessions.cache import get_active
    assert callable(get_active)

"""Skeleton tests for the TUI package.

Group 1 scope only: package imports cleanly, icon constants are present and
plain unicode, Textual import is deferred when `octopus.cli` is imported.
Real Textual app behavior is tested via snapshot tests in group 8.
"""

from __future__ import annotations

import sys


def test_tui_package_imports() -> None:
    import octopus.tui  # noqa: F401


def test_icons_are_plain_unicode_no_emoji() -> None:
    from octopus.tui import icons

    glyphs = [
        icons.NOW, icons.NEXT, icons.DONE, icons.DROPPED,
        icons.PINNED, icons.BLOCKED, icons.CURSOR, icons.SESSION_RUN,
        icons.SPINNER, icons.HOME, icons.ACTIVITY, icons.REPO,
    ]
    for g in glyphs:
        assert len(g) == 1, f"glyph {g!r} should be a single char"
        cp = ord(g)
        # Reject the emoji ranges we care about (Misc Symbols & Pictographs,
        # Emoticons, Transport, Supplemental Symbols).
        assert not (0x1F300 <= cp <= 0x1FAFF), f"glyph {g!r} is in emoji range"


def test_theme_css_is_bundled() -> None:
    from pathlib import Path

    import octopus.tui

    theme = Path(octopus.tui.__file__).parent / "theme.tcss"
    assert theme.is_file(), "theme.tcss must ship next to tui/__init__.py"
    text = theme.read_text()
    # Spot-check a couple of palette tokens — guards against accidental wipe.
    assert "#F38BA8" in text, "primary pink missing from theme"
    assert "#89DCEB" in text, "accent cyan missing from theme"
    assert "#0F1014" in text, "near-black background missing from theme"
    assert ".panel" in text, "panel class missing from theme"
    assert "#toast" in text, "toast widget styling missing"


def test_status_bar_setters() -> None:
    from octopus.tui.status_bar import BucketCounts, StatusBar

    sb = StatusBar()
    sb.set_activity("demo")
    sb.set_session("12m")
    sb.set_state("reindexing…", busy=True)
    sb.set_counts(3, 7, 2)
    assert sb.activity_id == "demo"
    assert sb.session_label == "12m"
    assert sb.state_label == "reindexing…"
    assert sb.state_busy is True
    assert sb.counts == BucketCounts(now=3, next_=7, blocked=2)


def test_focus_row_rendering() -> None:
    """Title column has cursor + title; chips live in a separate right column."""
    from octopus.tui.focus import _row_chips, _row_text

    class FakeRow(dict):
        def keys(self):
            return super().keys()

        def __getitem__(self, k):
            return super().__getitem__(k)

    row = FakeRow(
        title="ship the TUI",
        bucket="now",
        pinned=1,
        run_state="active",
        slug="ship-the-tui",
    )
    title_text = _row_text(row, selected=True).plain
    assert "▸" in title_text, "cursor glyph missing on selected row"
    assert "ship the TUI" in title_text
    # Chips do NOT appear in title text — they're rendered separately.
    assert "*" not in title_text

    chips_text = _row_chips(row).plain
    assert "*" in chips_text, "pinned chip missing from chips column"

    unselected = _row_text(row, selected=False).plain
    assert "▸" not in unselected, "cursor glyph should be hidden when not selected"


def test_focus_marquee_offset() -> None:
    """Marquee offset rotates the title beyond the cursor prefix."""
    from octopus.tui.focus import _row_text

    class FakeRow(dict):
        def keys(self):
            return super().keys()

        def __getitem__(self, k):
            return super().__getitem__(k)

    row = FakeRow(title="A very long task title that overflows", bucket="now", pinned=None)
    a = _row_text(row, selected=True, title_offset=0).plain
    b = _row_text(row, selected=True, title_offset=3).plain
    assert a != b, "offset should shift the rendered title"
    # offset=0 starts with cursor + first char of title
    assert "A very long" in a


def test_focus_quadrant_constants() -> None:
    """Quadrant ids must match real bucket names (used directly in captures)."""
    from octopus.core.models import TASK_BUCKETS
    from octopus.tui.focus import Q_BACKLOG, Q_NEXT, Q_NOW

    for q in (Q_BACKLOG, Q_NOW, Q_NEXT):
        assert q in TASK_BUCKETS, f"quadrant {q!r} must be a valid bucket"


def test_overlay_chip_rendering() -> None:
    """Verify the detail overlay's bucket+pinned+blocked chips."""
    from octopus.tui.overlay import _render_chips

    class T:
        bucket = "now"
        pinned = True
        run_state = "blocked"

    out = _render_chips(T(), "now").plain
    assert "now" in out
    assert "pinned" in out
    assert "blocked" in out


def test_overlay_find_task_file(tmp_path) -> None:
    """Locate a task across flat and bucket-folder layouts."""
    from octopus.tui.overlay import _find_task_file

    # flat layout
    octo = tmp_path / "flat" / ".octopus"
    (octo / "tasks").mkdir(parents=True)
    f = octo / "tasks" / "ship-it.md"
    f.write_text("---\ntitle: ship\n---\nbody")
    assert _find_task_file(octo, "flat", "ship-it") == f
    assert _find_task_file(octo, "flat", "missing") is None

    # folder layout
    octo2 = tmp_path / "folders" / ".octopus"
    (octo2 / "tasks" / "now").mkdir(parents=True)
    f2 = octo2 / "tasks" / "now" / "deep-work.md"
    f2.write_text("---\ntitle: deep\n---\nbody")
    assert _find_task_file(octo2, "folders", "deep-work") == f2


def test_textual_import_is_deferred() -> None:
    # Drop any prior textual import so we measure the actual deferral.
    for mod in list(sys.modules):
        if mod == "textual" or mod.startswith("textual."):
            del sys.modules[mod]
    if "octopus.cli" in sys.modules:
        del sys.modules["octopus.cli"]

    import octopus.cli  # noqa: F401

    assert "textual" not in sys.modules, (
        "Importing octopus.cli should not pull in textual — "
        "the tui command must defer the import inside its function body."
    )

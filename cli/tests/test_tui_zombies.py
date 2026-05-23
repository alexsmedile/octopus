"""Drop zombie rows (index entries whose backing file is missing)."""

from __future__ import annotations

from octopus.fs.scaffold import init_activity


def _row(slug: str, title: str = "x"):
    class R(dict):
        def keys(self):
            return super().keys()
        def __getitem__(self, k):
            return super().__getitem__(k)
    return R(slug=slug, title=title)


def test_drop_zombies_keeps_live_files(tmp_path) -> None:
    """A row whose .md file exists on disk should survive _drop_zombies."""
    from octopus import actions
    from octopus.tui.focus import _drop_zombies

    init_activity(tmp_path, title="t", activity_type="other")
    cap = actions.capture_task(tmp_path, "real one")

    rows = [_row(cap.slug, "real one")]
    out = _drop_zombies(tmp_path, rows)
    assert len(out) == 1


def test_drop_zombies_removes_missing_files(tmp_path) -> None:
    """A row whose .md file does NOT exist on disk should be dropped."""
    from octopus.tui.focus import _drop_zombies

    init_activity(tmp_path, title="t", activity_type="other")

    rows = [_row("ghost-task", "this never existed")]
    out = _drop_zombies(tmp_path, rows)
    assert out == [], "zombie rows must be filtered out before display"


def test_drop_zombies_mixed(tmp_path) -> None:
    from octopus import actions
    from octopus.tui.focus import _drop_zombies

    init_activity(tmp_path, title="t", activity_type="other")
    real = actions.capture_task(tmp_path, "stays")

    rows = [
        _row(real.slug, "stays"),
        _row("ghost-1", "gone"),
        _row("ghost-2", "also gone"),
    ]
    out = _drop_zombies(tmp_path, rows)
    assert len(out) == 1
    assert out[0]["slug"] == real.slug

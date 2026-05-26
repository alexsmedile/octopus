"""Tests for tui.state — model, persistence, resolve."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from octopus.tui.state import (
    SCHEMA_VERSION,
    TabState,
    ViewState,
    cache_path,
    load,
    resolve_cursor,
    save,
)
from octopus.tui.state.persistence import reset
from octopus.tui.state.resolve import resolve_cursor_with_index


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch):
    """Redirect cache to tmp_path for every test."""
    monkeypatch.setenv("OCTOPUS_CACHE_DIR", str(tmp_path))
    yield tmp_path


# ── model ─────────────────────────────────────────────────────────────


def test_tabstate_round_trip():
    ts = TabState(
        tab_id="focus",
        cursors={"now": "do-it", "next": "later"},
        active_panel="now",
        scroll_offsets={"now": 3},
        filter="urgent",
        collapsed_panels=["nested"],
        activity_id="octopus-aaaa",
    )
    data = ts.to_dict()
    ts2 = TabState.from_dict(data)
    assert ts2.tab_id == "focus"
    assert ts2.cursors == {"now": "do-it", "next": "later"}
    assert ts2.active_panel == "now"
    assert ts2.scroll_offsets == {"now": 3}
    assert ts2.filter == "urgent"
    assert ts2.collapsed_panels == ["nested"]
    assert ts2.activity_id == "octopus-aaaa"


def test_tabstate_preserves_unknown_fields():
    raw = {
        "tab_id": "focus",
        "cursors": {},
        "future_field": "preserved",
    }
    ts = TabState.from_dict(raw)
    assert ts.extra == {"future_field": "preserved"}
    out = ts.to_dict()
    assert out["future_field"] == "preserved"


def test_viewstate_round_trip():
    v = ViewState(active_tab="board:foo-aaaa")
    v.set_tab("activities", TabState(tab_id="activities", cursors={"index": "x"}))
    v.set_tab(
        "focus:foo-aaaa",
        TabState(tab_id="focus", activity_id="foo-aaaa", cursors={"now": "y"}),
    )
    data = v.to_dict()
    v2 = ViewState.from_dict(data)
    assert v2.active_tab == "board:foo-aaaa"
    assert v2.schema_version == SCHEMA_VERSION
    assert v2.per_tab["activities"].cursors == {"index": "x"}
    assert v2.per_tab["focus:foo-aaaa"].activity_id == "foo-aaaa"


# ── persistence ───────────────────────────────────────────────────────


def test_load_missing_cache_returns_empty():
    state = load()
    assert state.active_tab == "activities"
    assert state.per_tab == {}


def test_save_then_load():
    v = ViewState(active_tab="focus:x")
    v.set_tab("focus:x", TabState(tab_id="focus", activity_id="x", cursors={"now": "t"}))
    assert save(v) is True
    v2 = load()
    assert v2.active_tab == "focus:x"
    assert v2.per_tab["focus:x"].cursors["now"] == "t"


def test_load_corrupt_cache_returns_empty(_isolated_cache: Path):
    cache_path().parent.mkdir(parents=True, exist_ok=True)
    cache_path().write_text("not json {", encoding="utf-8")
    v = load()
    assert v.per_tab == {}


def test_load_wrong_schema_returns_empty(_isolated_cache: Path):
    cache_path().parent.mkdir(parents=True, exist_ok=True)
    cache_path().write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    v = load()
    assert v.per_tab == {}


def test_load_not_a_dict_returns_empty(_isolated_cache: Path):
    cache_path().parent.mkdir(parents=True, exist_ok=True)
    cache_path().write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    v = load()
    assert v.per_tab == {}


def test_save_writes_saved_at_field(_isolated_cache: Path):
    v = ViewState()
    save(v)
    data = json.loads(cache_path().read_text(encoding="utf-8"))
    assert "saved_at" in data


def test_save_is_atomic_no_tmp_leftover(_isolated_cache: Path):
    v = ViewState()
    save(v)
    tmp = cache_path().with_suffix(cache_path().suffix + ".tmp")
    assert not tmp.exists()


def test_reset_deletes_cache(_isolated_cache: Path):
    save(ViewState())
    assert cache_path().is_file()
    assert reset() is True
    assert not cache_path().is_file()


def test_reset_missing_file_is_ok():
    assert reset() is True


def test_cache_path_honors_env_var(_isolated_cache: Path):
    assert str(cache_path()).startswith(str(_isolated_cache))


def test_unknown_top_level_fields_preserved(_isolated_cache: Path):
    cache_path().parent.mkdir(parents=True, exist_ok=True)
    cache_path().write_text(
        json.dumps({
            "schema_version": SCHEMA_VERSION,
            "active_tab": "activities",
            "per_tab": {},
            "future_top_level": "kept",
        }),
        encoding="utf-8",
    )
    v = load()
    assert v.extra.get("future_top_level") == "kept"
    save(v)
    data = json.loads(cache_path().read_text(encoding="utf-8"))
    assert data["future_top_level"] == "kept"


# ── resolve ───────────────────────────────────────────────────────────


def test_resolve_cursor_hits_target():
    assert resolve_cursor("b", ["a", "b", "c"]) == "b"


def test_resolve_cursor_missing_target_falls_back_to_first():
    assert resolve_cursor("z", ["a", "b", "c"]) == "a"


def test_resolve_cursor_empty_candidates_returns_none():
    assert resolve_cursor("x", []) is None


def test_resolve_cursor_none_target():
    assert resolve_cursor(None, ["a"]) == "a"


def test_resolve_with_index_returns_nearest_sibling():
    # Target "b" was at index 1; after deletion candidates are [a, c, d].
    # Same index → "c".
    assert resolve_cursor_with_index("b", ["a", "c", "d"], previous_index=1) == "c"


def test_resolve_with_index_clamps_to_last_when_list_shrank():
    # Target at index 5, candidates now only have 3 items → clamp to last.
    assert resolve_cursor_with_index("gone", ["a", "b", "c"], previous_index=5) == "c"


def test_resolve_with_index_target_present_returns_target():
    assert resolve_cursor_with_index("b", ["a", "b", "c"], previous_index=99) == "b"


def test_resolve_with_index_no_previous_index():
    assert resolve_cursor_with_index("gone", ["a", "b"], previous_index=None) == "a"


# ── per-activity shared cursor (Focus ↔ Board continuity) ─────────────


def test_activity_cursor_round_trip():
    v = ViewState()
    v.set_activity_cursor("octopus-aaaa", "now", "do-thing")
    data = v.to_dict()
    v2 = ViewState.from_dict(data)
    cursor = v2.get_activity_cursor("octopus-aaaa")
    assert cursor is not None
    assert cursor.bucket == "now"
    assert cursor.slug == "do-thing"


def test_activity_cursor_missing_returns_none():
    v = ViewState()
    assert v.get_activity_cursor("nope") is None


def test_activity_cursor_overwrites():
    v = ViewState()
    v.set_activity_cursor("x", "now", "first")
    v.set_activity_cursor("x", "next", "second")
    cur = v.get_activity_cursor("x")
    assert cur.bucket == "next"
    assert cur.slug == "second"


def test_activity_cursor_persists_to_disk(_isolated_cache: Path):
    v = ViewState()
    v.set_activity_cursor("octopus-aaaa", "now", "shared-task")
    assert save(v) is True
    v2 = load()
    cur = v2.get_activity_cursor("octopus-aaaa")
    assert cur is not None
    assert cur.bucket == "now"
    assert cur.slug == "shared-task"

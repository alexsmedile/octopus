"""Tests for ActivityOverview + panel order (req #45)."""

from __future__ import annotations

from octopus.tui.activities_screen import (
    ACTIVITY_ITEM_TYPES,
    ActivitiesScreen,
    ActivityBlock,
    ActivityOverview,
)


def test_activity_overview_renders_all_rows():
    row = {
        "id": "octopus-aaaa",
        "title": "Octopus",
        "type": "project",
        "status": "active",
        "priority": "high",
        "area": "personal",
        "tags": ["tui", "cli"],
        "last_reviewed": "2026-05-20",
        "path": "/tmp/octopus",
    }
    o = ActivityOverview(row, {"now": 3, "next": 7, "backlog": 12, "done": 41})
    out = o._build_content()
    assert "octopus" in out
    assert "Octopus" in out
    # Meta row — priority is highlighted but the values appear in order.
    assert "project" in out and "active" in out and "high" in out and "personal" in out
    assert "NOW 3" in out
    assert "DONE 41" in out
    assert "tags:" in out
    assert "tui, cli" in out
    assert "reviewed:" in out
    assert "/tmp/octopus" in out


def test_activity_overview_omits_empty_rows():
    row = {
        "id": "x-bbbb",
        "title": "Bare",
        "type": "other",
        "status": "active",
        "path": "/tmp/x",
    }
    o = ActivityOverview(row, {})
    out = o._build_content()
    assert "tags:" not in out
    assert "last reviewed:" not in out
    # type · status still rendered, with no extra dots
    assert "other · active" in out


def test_overview_is_in_activity_item_types():
    assert ActivityOverview in ACTIVITY_ITEM_TYPES
    assert ActivityBlock in ACTIVITY_ITEM_TYPES


def test_panel_order_current_first():
    """Visual + cycle order: CURRENT → INDEX → NESTED."""
    screen = ActivitiesScreen.__new__(ActivitiesScreen)
    # __init__ wires _panels — instantiate enough to populate it.
    ActivitiesScreen.__init__(screen)
    assert screen._panels[0].panel_id == "current"
    assert screen._panels[1].panel_id == "index"
    assert screen._panels[2].panel_id == "nested"


def test_overview_set_selected_toggles_cursor():
    row = {"id": "x-cccc", "title": "T", "type": "other", "status": "active", "path": "/x"}
    o = ActivityOverview(row, {})
    plain = o._build_content()
    assert "▸" not in plain
    o.set_selected(True)
    selected = o._build_content()
    assert "▸" in selected


def test_overview_renders_extras():
    row = {"id": "x-dddd", "title": "T", "type": "other", "status": "active", "path": "/x"}
    extras = {
        "pinned_task": "Wire the relay",
        "active_session": {"title": "morning push", "started": "2026-05-26 09:12"},
        "blocked_count": 2,
        "due_soon_count": 3,
        "linked_count": 4,
    }
    o = ActivityOverview(row, {"now": 1}, extras)
    out = o._build_content()
    assert "Wire the relay" in out
    assert "pinned" in out
    assert "blocked 2" in out
    assert "due≤7d 3" in out
    assert "links 4" in out
    assert "session:" in out
    assert "morning push" in out


def test_overview_top_now_when_no_pinned():
    row = {"id": "x-eeee", "title": "T", "type": "other", "status": "active", "path": "/x"}
    extras = {"top_now_task": "First NOW item"}
    o = ActivityOverview(row, {}, extras)
    out = o._build_content()
    assert "First NOW item" in out


def test_overview_pinned_wins_over_top_now():
    row = {"id": "x-ffff", "title": "T", "type": "other", "status": "active", "path": "/x"}
    extras = {"pinned_task": "Pinned one", "top_now_task": "Not me"}
    o = ActivityOverview(row, {}, extras)
    out = o._build_content()
    assert "Pinned one" in out
    assert "Not me" not in out


def test_activities_screen_accepts_prefer_current_kwarg():
    """Constructor accepts prefer_current; flag is stored on the instance."""
    s = ActivitiesScreen(prefer_current=True)
    assert s._prefer_current is True
    s2 = ActivitiesScreen()
    assert s2._prefer_current is False

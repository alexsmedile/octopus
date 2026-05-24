"""Tests for the Apple Reminders adapter (#09).

The wrapper module `_reminders_io.py` is stubbed everywhere except the
unit tests for `_iso_to_date`. Real `remindctl` calls are never made in
tests — that would require a macOS host with auth granted and a real
Reminders database. The manual smoke command in CHANGELOG covers that.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from octopus.adapters._reminders_io import (
    RemindctlError,
    RemindctlNotInstalled,
    RemindersItem,
    RemindersList,
    _iso_to_date,
    _parse_item_row,
    _parse_list_row,
)
from octopus.adapters.base import ExternalTask, PullResult
from octopus.adapters.reminders import (
    _PRIORITY_MAP,
    RemindersAdapter,
    _reminder_to_external_task,
)


# ── _iso_to_date (pure helper) ────────────────────────────────────────


def test_iso_to_date_utc_z_suffix():
    """Apple's `dueDate` format: '2024-06-16T22:00:00Z' — strips time."""
    assert _iso_to_date("2024-06-16T22:00:00Z") == date(2024, 6, 16)


def test_iso_to_date_with_offset():
    assert _iso_to_date("2024-06-16T22:00:00+00:00") == date(2024, 6, 16)


def test_iso_to_date_date_only():
    assert _iso_to_date("2024-06-16") == date(2024, 6, 16)


def test_iso_to_date_none_and_empty():
    assert _iso_to_date(None) is None
    assert _iso_to_date("") is None


def test_iso_to_date_malformed_returns_none():
    assert _iso_to_date("not a date") is None
    assert _iso_to_date(12345) is None  # wrong type


# ── _parse_list_row / _parse_item_row ─────────────────────────────────


def test_parse_list_row_full():
    row = {
        "id": "E3A9D562-...",
        "title": "Default",
        "reminderCount": 3,
        "overdueCount": 1,
    }
    parsed = _parse_list_row(row)
    assert parsed.title == "Default"
    assert parsed.reminder_count == 3
    assert parsed.overdue_count == 1


def test_parse_list_row_with_missing_counts_defaults_zero():
    parsed = _parse_list_row({"id": "x", "title": "Lonely"})
    assert parsed.reminder_count == 0
    assert parsed.overdue_count == 0


def test_parse_item_row_minimal():
    """Incomplete reminder with no due, no priority, no notes — common shape."""
    row = {
        "id": "DF95D91C-...",
        "title": "Cypher 007",
        "isCompleted": False,
        "listID": "E3A9D562-...",
        "listName": "Default",
        "priority": "none",
    }
    item = _parse_item_row(row)
    assert item.id == "DF95D91C-..."
    assert item.title == "Cypher 007"
    assert item.is_completed is False
    assert item.list_name == "Default"
    assert item.priority == "none"
    assert item.due_date is None
    assert item.notes is None


def test_parse_item_row_full_with_due_and_notes():
    row = {
        "id": "B116C997-...",
        "title": "Call mom",
        "isCompleted": False,
        "listID": "...",
        "listName": "Personal",
        "priority": "high",
        "dueDate": "2024-06-16T22:00:00Z",
        "notes": "Ask about garden",
    }
    item = _parse_item_row(row)
    assert item.priority == "high"
    assert item.due_date == date(2024, 6, 16)
    assert item.notes == "Ask about garden"


def test_parse_item_row_completed():
    row = {
        "id": "x", "title": "y", "listID": "z", "listName": "L",
        "isCompleted": True, "priority": "none",
        "completionDate": "2024-07-13T11:41:26Z",
    }
    item = _parse_item_row(row)
    assert item.is_completed is True
    assert item.completion_date == date(2024, 7, 13)


# ── D70 mapping (_reminder_to_external_task) ──────────────────────────


def _item(
    *,
    id="UUID-1",
    title="task",
    list_name="Default",
    priority="none",
    due_date=None,
    notes=None,
    is_completed=False,
):
    return RemindersItem(
        id=id, title=title, list_name=list_name, list_id="L1",
        priority=priority, due_date=due_date, notes=notes,
        is_completed=is_completed,
    )


def test_mapping_priority_enum():
    """D70: none/medium → None; low → low; high → high."""
    assert _PRIORITY_MAP["none"] is None
    assert _PRIORITY_MAP["low"] == "low"
    assert _PRIORITY_MAP["medium"] is None  # Octopus has no medium
    assert _PRIORITY_MAP["high"] == "high"


def test_mapping_external_id_is_bare_uuid():
    """D69: no path prefix, no encoding — just the UUID."""
    et = _reminder_to_external_task(_item(id="DF95D91C-7F56-47E4-8AAD-07335A5DC086"))
    assert et.external_id == "DF95D91C-7F56-47E4-8AAD-07335A5DC086"


def test_mapping_default_bucket_is_backlog():
    """D70: no auto-`now` for Reminders (Apple has no in-progress state)."""
    et = _reminder_to_external_task(_item())
    assert et.suggested_bucket == "backlog"


def test_mapping_priority_flows_through():
    et = _reminder_to_external_task(_item(priority="high"))
    assert et.suggested_priority == "high"


def test_mapping_priority_none_omitted():
    et = _reminder_to_external_task(_item(priority="none"))
    assert et.suggested_priority is None


def test_mapping_priority_medium_dropped():
    """Octopus has no medium — D70 says drop it (default omission)."""
    et = _reminder_to_external_task(_item(priority="medium"))
    assert et.suggested_priority is None


def test_mapping_due_date_passed_through():
    et = _reminder_to_external_task(_item(due_date=date(2026, 7, 1)))
    assert et.suggested_due == date(2026, 7, 1)


def test_mapping_notes_become_body():
    et = _reminder_to_external_task(_item(notes="some context\nmore"))
    assert et.body == "some context\nmore"


def test_mapping_empty_notes_omitted():
    assert _reminder_to_external_task(_item(notes=None)).body is None
    assert _reminder_to_external_task(_item(notes="")).body is None


def test_mapping_source_group_is_list_name():
    et = _reminder_to_external_task(_item(list_name="Errands"))
    assert et.source_group == "Errands"


# ── adapter behavior (with subprocess mocked) ─────────────────────────


def test_adapter_validate_config_happy():
    a = RemindersAdapter()
    # When remindctl is present (it is on our dev box) + auth full, empty
    # config validates. Mock `which_remindctl` + `auth_status` to make this
    # deterministic regardless of host.
    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.auth_status", return_value="Full access"):
        assert a.validate_config({"lists": ["Inbox"]}) == []


def test_adapter_validate_config_missing_binary():
    a = RemindersAdapter()
    with patch("octopus.adapters.reminders.which_remindctl", return_value=None):
        errors = a.validate_config({})
        assert any("not installed" in e for e in errors)


def test_adapter_validate_config_denied():
    a = RemindersAdapter()
    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.auth_status", return_value="Denied"):
        errors = a.validate_config({})
        assert any("denied" in e.lower() for e in errors)


def test_adapter_validate_config_rejects_bad_types():
    a = RemindersAdapter()
    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.auth_status", return_value="Full access"):
        assert a.validate_config({"lists": "not a list"}) != []
        assert a.validate_config({"lists": [1, 2, 3]}) != []
        assert a.validate_config({"include_completed": "yes"}) != []
        assert a.validate_config({"default_activity": 42}) != []


def test_adapter_status_missing_binary():
    with patch("octopus.adapters.reminders.which_remindctl", return_value=None):
        s = RemindersAdapter().status()
        assert s.healthy is False
        assert "not installed" in s.error.lower()


def test_adapter_status_healthy_with_full_access(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    import importlib

    import octopus.adapters.journal as J

    importlib.reload(J)

    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.auth_status", return_value="Full access"):
        s = RemindersAdapter().status()
        assert s.healthy is True
        assert s.error is None


def test_adapter_status_denied(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    import importlib

    import octopus.adapters.journal as J

    importlib.reload(J)

    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.auth_status", return_value="Denied"):
        s = RemindersAdapter().status()
        assert s.healthy is False
        assert "denied" in (s.error or "").lower()


def test_adapter_list_groups_returns_titles():
    fake = [RemindersList(id="1", title="Inbox"), RemindersList(id="2", title="Work")]
    with patch("octopus.adapters.reminders.list_lists", return_value=fake):
        assert RemindersAdapter().list_groups() == ["Inbox", "Work"]


def test_adapter_list_groups_on_error_returns_empty():
    """list_groups must never throw — degrades gracefully."""
    with patch(
        "octopus.adapters.reminders.list_lists",
        side_effect=RemindctlError("auth denied"),
    ):
        assert RemindersAdapter().list_groups() == []


def test_adapter_push_is_pull_only():
    r = RemindersAdapter().push(None)
    assert r.ref is None
    assert "pull-only" in (r.error or "").lower()


def test_adapter_peek_aggregates_multi_lists(monkeypatch, tmp_path):
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    import importlib

    import octopus.config

    importlib.reload(octopus.config)

    from octopus.config import set_adapter_enabled, write_adapter_config

    set_adapter_enabled("reminders", True)
    write_adapter_config("reminders", {"lists": ["Inbox", "Work"]})

    def fake_show(name, *, include_completed=False):
        if name == "Inbox":
            return [_item(id="A", title="from inbox", list_name="Inbox")]
        return [_item(id="B", title="from work", list_name="Work")]

    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.show_list", side_effect=fake_show):
        result = RemindersAdapter().peek()
        titles = [t.title for t in result.tasks]
        assert "from inbox" in titles
        assert "from work" in titles
        # Each carries its source_group
        groups = {t.source_group for t in result.tasks}
        assert groups == {"Inbox", "Work"}

    # Restore for downstream tests
    importlib.reload(octopus.config)


def test_adapter_peek_no_lists_configured_returns_error(monkeypatch, tmp_path):
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    import importlib

    import octopus.config

    importlib.reload(octopus.config)

    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"):
        result = RemindersAdapter().peek()  # no groups arg, no config
        assert result.errors
        assert "no lists configured" in result.errors[0].lower()

    importlib.reload(octopus.config)


def test_adapter_peek_missing_binary_returns_error():
    with patch("octopus.adapters.reminders.which_remindctl", return_value=None):
        result = RemindersAdapter().peek(groups=["Inbox"])
        assert result.errors
        assert "not installed" in result.errors[0].lower()


def test_adapter_search_filters_by_substring():
    items = [
        _item(id="A", title="buy milk"),
        _item(id="B", title="schedule dentist"),
        _item(id="C", title="reply to alex"),
    ]
    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.show_list", return_value=items):
        result = RemindersAdapter().search("alex", groups=["Inbox"])
        titles = [t.title for t in result.tasks]
        assert titles == ["reply to alex"]


def test_adapter_groups_param_overrides_config(monkeypatch, tmp_path):
    """--list passed at CLI should override `lists = ...` in config."""
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    import importlib

    import octopus.config

    importlib.reload(octopus.config)

    from octopus.config import write_adapter_config

    write_adapter_config("reminders", {"lists": ["ConfiguredList"]})

    captured: list[str] = []

    def fake_show(name, *, include_completed=False):
        captured.append(name)
        return []

    with patch("octopus.adapters.reminders.which_remindctl", return_value="/usr/bin/remindctl"), \
         patch("octopus.adapters.reminders.show_list", side_effect=fake_show):
        RemindersAdapter().peek(groups=["OverrideList"])

    assert captured == ["OverrideList"]
    importlib.reload(octopus.config)

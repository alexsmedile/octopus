"""Cache layer: atomicity, corruption recovery, cache-wins-on-mismatch."""

from __future__ import annotations

import pytest

from octopus.sessions.cache import (
    cache_path,
    clear_active,
    get_active,
    load_active_map,
    set_active,
)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / ".cache" / "octopus"))


def test_missing_cache_returns_empty():
    assert load_active_map() == {}
    assert get_active("anything") is None


def test_set_then_get():
    set_active("act-1", "2026-05-23-foo")
    assert get_active("act-1") == "2026-05-23-foo"
    assert load_active_map() == {"act-1": "2026-05-23-foo"}


def test_clear_removes_entry():
    set_active("act-1", "f1")
    set_active("act-2", "f2")
    clear_active("act-1")
    assert get_active("act-1") is None
    assert get_active("act-2") == "f2"


def test_clear_missing_is_noop():
    clear_active("never-set")  # no exception
    assert load_active_map() == {}


def test_atomic_write_no_partial_file(tmp_path):
    """No leftover .tmp file after a successful write."""
    set_active("a", "f")
    base = cache_path().parent
    assert cache_path().is_file()
    leftovers = [p for p in base.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_corrupt_json_treated_as_empty(capsys):
    cp = cache_path()
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text("{not valid json", encoding="utf-8")
    assert load_active_map() == {}
    captured = capsys.readouterr()
    assert "unreadable" in captured.err


def test_non_object_json_treated_as_empty(capsys):
    cp = cache_path()
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text('["array", "not", "object"]', encoding="utf-8")
    assert load_active_map() == {}
    captured = capsys.readouterr()
    assert "not a JSON object" in captured.err

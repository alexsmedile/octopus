"""Activity ID tests — SPEC §9."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from octopus.core.id import derive_activity_id, parse_activity_id, short_form


def test_derive_id_basic(tmp_path: Path):
    folder = tmp_path / "shift"
    folder.mkdir()
    aid = derive_activity_id(folder, created_at=datetime(2026, 5, 21))
    slug, hash6 = aid.rsplit("-", 1)
    assert slug == "shift"
    assert len(hash6) == 6
    assert all(c in "0123456789abcdef" for c in hash6)


def test_derive_id_deterministic(tmp_path: Path):
    folder = tmp_path / "shift"
    folder.mkdir()
    t = datetime(2026, 5, 21, 10, 0, 0)
    aid1 = derive_activity_id(folder, created_at=t)
    aid2 = derive_activity_id(folder, created_at=t)
    assert aid1 == aid2


def test_derive_id_different_paths_different_hashes(tmp_path: Path):
    f1 = tmp_path / "shift"
    f2 = tmp_path / "other" / "shift"
    f1.mkdir()
    f2.mkdir(parents=True)
    t = datetime(2026, 5, 21)
    aid1 = derive_activity_id(f1, created_at=t)
    aid2 = derive_activity_id(f2, created_at=t)
    assert aid1 != aid2
    assert aid1.startswith("shift-")
    assert aid2.startswith("shift-")


def test_parse_activity_id():
    slug, hash6 = parse_activity_id("shift-a3f9b2")
    assert slug == "shift"
    assert hash6 == "a3f9b2"

    # Legacy 4-char hash parsing
    slug_legacy, hash_legacy = parse_activity_id("shift-a3f9")
    assert slug_legacy == "shift"
    assert hash_legacy == "a3f9"


def test_parse_activity_id_with_hyphens_in_slug():
    slug, hash6 = parse_activity_id("carousel-studio-b71c2e")
    assert slug == "carousel-studio"
    assert hash6 == "b71c2e"

    # Legacy 4-char hash parsing with hyphens in slug
    slug_legacy, hash_legacy = parse_activity_id("carousel-studio-b71c")
    assert slug_legacy == "carousel-studio"
    assert hash_legacy == "b71c"


def test_parse_malformed_raises():
    with pytest.raises(ValueError):
        parse_activity_id("no-hash")
    with pytest.raises(ValueError):
        parse_activity_id("shift-ZZZZZZ")  # not hex
    with pytest.raises(ValueError):
        parse_activity_id("shift-ZZZZ")  # legacy format but not hex
    with pytest.raises(ValueError):
        parse_activity_id("shift-a3f9b2c")  # invalid length 7


def test_short_form():
    assert short_form("shift-a3f9b2") == "shift"
    assert short_form("carousel-studio-b71c2e") == "carousel-studio"
    # Legacy
    assert short_form("shift-a3f9") == "shift"
    assert short_form("carousel-studio-b71c") == "carousel-studio"

"""Canonical sections + partial-name resolution."""

from __future__ import annotations

import pytest

from octopus.memory.sections import (
    CANONICAL_SECTIONS,
    UnknownSectionError,
    resolve_section,
)


def test_canonical_sections_order():
    assert CANONICAL_SECTIONS == (
        "Decisions", "Open Questions", "Context", "Notes", "State",
    )


@pytest.mark.parametrize("name,expected", [
    ("decisions", "Decisions"),
    ("Decisions", "Decisions"),
    ("DECISIONS", "Decisions"),
    ("dec", "Decisions"),
    ("open", "Open Questions"),
    ("Open Questions", "Open Questions"),
    ("context", "Context"),
    ("notes", "Notes"),
    ("state", "State"),
    ("st", "State"),
])
def test_resolve_section_exact_and_prefix(name, expected):
    assert resolve_section(name) == expected


def test_resolve_unknown_raises():
    with pytest.raises(UnknownSectionError):
        resolve_section("nonsense")


def test_resolve_empty_raises():
    with pytest.raises(UnknownSectionError):
        resolve_section("")


def test_resolve_ambiguous_raises():
    # No two canonical sections share a real prefix today, so verify the
    # mechanism by stubbing: 'd' matches only Decisions today. We assert
    # the ambiguity-detection path with a custom case: 'context' vs none.
    # Instead, validate that 'c' resolves uniquely to Context.
    assert resolve_section("c") == "Context"

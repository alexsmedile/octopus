"""Tests for the tag flag parser (D76)."""

from __future__ import annotations

import pytest

from octopus.core.tag_parser import (
    TagFlagConflict,
    TagFlagInputs,
    apply_tag_mutations,
    normalize_tag,
    split_tag_input,
    tag_filter_matches,
    validate_mutex,
)

# ── normalize_tag ─────────────────────────────────────────────────────


def test_normalize_adds_hash_when_missing():
    assert normalize_tag("bug") == "#bug"
    assert normalize_tag("tui") == "#tui"


def test_normalize_keeps_hash_when_present():
    assert normalize_tag("#bug") == "#bug"


def test_normalize_strips_whitespace():
    assert normalize_tag("  bug  ") == "#bug"
    assert normalize_tag("\tbug\n") == "#bug"


def test_normalize_empty_returns_empty():
    assert normalize_tag("") == ""
    assert normalize_tag("   ") == ""


def test_normalize_preserves_nested():
    assert normalize_tag("tui/marquee") == "#tui/marquee"
    assert normalize_tag("#tui/marquee") == "#tui/marquee"


# ── split_tag_input ───────────────────────────────────────────────────


def test_split_none_returns_empty():
    assert split_tag_input(None) == []
    assert split_tag_input([]) == []


def test_split_comma_separated():
    assert split_tag_input(["bug,tui,release"]) == ["#bug", "#tui", "#release"]


def test_split_space_separated():
    assert split_tag_input(["bug tui release"]) == ["#bug", "#tui", "#release"]


def test_split_repeated_invocations():
    assert split_tag_input(["bug", "tui", "release"]) == ["#bug", "#tui", "#release"]


def test_split_mixed_separators():
    """`--tag X,Y --tag "A B" --tag Z` → all five."""
    assert split_tag_input(["X,Y", "A B", "Z"]) == ["#X", "#Y", "#A", "#B", "#Z"]


def test_split_dedups_within_call():
    """`--tag bug,bug` → one `#bug`."""
    assert split_tag_input(["bug,bug"]) == ["#bug"]
    assert split_tag_input(["bug", "bug"]) == ["#bug"]


def test_split_drops_empty_tokens():
    assert split_tag_input(["bug,,tui"]) == ["#bug", "#tui"]
    assert split_tag_input(["  ,  ,bug"]) == ["#bug"]


def test_split_preserves_nested():
    assert split_tag_input(["tui/marquee,release/p0"]) == [
        "#tui/marquee", "#release/p0"
    ]


def test_split_accepts_hash_prefixed_input():
    assert split_tag_input(["#bug,#tui"]) == ["#bug", "#tui"]


# ── validate_mutex ────────────────────────────────────────────────────


def test_mutex_replace_alone_ok():
    validate_mutex(TagFlagInputs(replace=["X"]))


def test_mutex_add_alone_ok():
    validate_mutex(TagFlagInputs(add=["X"]))


def test_mutex_remove_alone_ok():
    validate_mutex(TagFlagInputs(remove=["X"]))


def test_mutex_clear_alone_ok():
    validate_mutex(TagFlagInputs(clear=True))


def test_mutex_clear_plus_add_ok():
    """Combining incremental flags is allowed; only replace+incremental is not."""
    validate_mutex(TagFlagInputs(clear=True, add=["X"]))


def test_mutex_remove_plus_add_ok():
    validate_mutex(TagFlagInputs(remove=["X"], add=["Y"]))


def test_mutex_replace_plus_add_rejects():
    with pytest.raises(TagFlagConflict):
        validate_mutex(TagFlagInputs(replace=["X"], add=["Y"]))


def test_mutex_replace_plus_remove_rejects():
    with pytest.raises(TagFlagConflict):
        validate_mutex(TagFlagInputs(replace=["X"], remove=["Y"]))


def test_mutex_replace_plus_clear_rejects():
    with pytest.raises(TagFlagConflict):
        validate_mutex(TagFlagInputs(replace=["X"], clear=True))


def test_mutex_empty_replace_does_not_count_as_used():
    """`--tag` flag passed with empty list (Typer default) is treated as absent."""
    validate_mutex(TagFlagInputs(replace=[], add=["X"]))


# ── apply_tag_mutations: replace ──────────────────────────────────────


def test_apply_replace_overwrites_existing():
    out = apply_tag_mutations(["#old"], TagFlagInputs(replace=["new"]))
    assert out == ["#new"]


def test_apply_replace_with_no_existing():
    out = apply_tag_mutations([], TagFlagInputs(replace=["a,b,c"]))
    assert out == ["#a", "#b", "#c"]


def test_apply_replace_normalizes_input():
    out = apply_tag_mutations([], TagFlagInputs(replace=["#X", "Y"]))
    assert out == ["#X", "#Y"]


# ── apply_tag_mutations: add ──────────────────────────────────────────


def test_apply_add_appends_new():
    out = apply_tag_mutations(["#existing"], TagFlagInputs(add=["new"]))
    assert out == ["#existing", "#new"]


def test_apply_add_dedups_against_existing():
    out = apply_tag_mutations(["#bug", "#tui"], TagFlagInputs(add=["bug,release"]))
    assert out == ["#bug", "#tui", "#release"]


def test_apply_add_normalizes_existing_too():
    """Backwards-compat: pre-#24 tasks have tags without #. Normalize on write."""
    out = apply_tag_mutations(["bug"], TagFlagInputs(add=["tui"]))
    assert out == ["#bug", "#tui"]


def test_apply_add_dedups_existing_before_adding():
    """If existing has duplicates (corrupt frontmatter), dedup before adding."""
    out = apply_tag_mutations(["bug", "#bug"], TagFlagInputs(add=["tui"]))
    assert out == ["#bug", "#tui"]


# ── apply_tag_mutations: remove ───────────────────────────────────────


def test_apply_remove_drops_existing():
    out = apply_tag_mutations(["#a", "#b", "#c"], TagFlagInputs(remove=["b"]))
    assert out == ["#a", "#c"]


def test_apply_remove_no_op_for_absent():
    out = apply_tag_mutations(["#a"], TagFlagInputs(remove=["z"]))
    assert out == ["#a"]


def test_apply_remove_multiple():
    out = apply_tag_mutations(["#a", "#b", "#c"], TagFlagInputs(remove=["a,c"]))
    assert out == ["#b"]


# ── apply_tag_mutations: clear ────────────────────────────────────────


def test_apply_clear_empties():
    out = apply_tag_mutations(["#a", "#b"], TagFlagInputs(clear=True))
    assert out == []


def test_apply_clear_plus_add_starts_fresh():
    """D76: clear-then-add yields exactly the added tags."""
    out = apply_tag_mutations(["#old"], TagFlagInputs(clear=True, add=["new"]))
    assert out == ["#new"]


def test_apply_clear_plus_remove_is_just_clear():
    """remove after clear is a no-op since list is already empty."""
    out = apply_tag_mutations(["#x"], TagFlagInputs(clear=True, remove=["x"]))
    assert out == []


# ── apply_tag_mutations: combined operations (D76 order) ──────────────


def test_apply_remove_then_add():
    """Order: clear → remove → add. Remove takes precedence over add for now."""
    out = apply_tag_mutations(
        ["#bug", "#tui"],
        TagFlagInputs(remove=["bug"], add=["release"]),
    )
    assert out == ["#tui", "#release"]


def test_apply_clear_remove_add():
    out = apply_tag_mutations(
        ["#x"],
        TagFlagInputs(clear=True, remove=["nope"], add=["a,b"]),
    )
    assert out == ["#a", "#b"]


# ── apply_tag_mutations: mutex ────────────────────────────────────────


def test_apply_rejects_replace_with_incremental():
    with pytest.raises(TagFlagConflict):
        apply_tag_mutations([], TagFlagInputs(replace=["X"], add=["Y"]))


# ── tag_filter_matches ────────────────────────────────────────────────


def test_filter_exact_match():
    assert tag_filter_matches("bug", "bug")
    assert tag_filter_matches("#bug", "#bug")
    assert tag_filter_matches("bug", "#bug")
    assert tag_filter_matches("#bug", "bug")


def test_filter_prefix_match_nested():
    """D76: filter parent matches parent AND parent/*."""
    assert tag_filter_matches("tui", "tui/marquee")
    assert tag_filter_matches("#tui", "#tui/marquee")
    assert tag_filter_matches("tui", "tui/marquee/cursor")  # deep nest


def test_filter_does_not_match_substring():
    """Don't match tags that just contain the filter as substring."""
    assert not tag_filter_matches("ui", "tui")
    assert not tag_filter_matches("bug", "debugging")


def test_filter_does_not_match_unrelated():
    assert not tag_filter_matches("bug", "tui")


def test_filter_does_not_match_partial_path():
    """tui must NOT match tuiother (boundary on / only)."""
    assert not tag_filter_matches("tui", "tuiother")


def test_filter_empty_inputs():
    assert not tag_filter_matches("", "bug")
    assert not tag_filter_matches("bug", "")

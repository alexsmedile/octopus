"""Slugification tests — SPEC §10."""

from __future__ import annotations

import pytest

from octopus.core.slug import collision_suffix, slugify


def test_basic_slug():
    assert slugify("Fix the webhook auth bug") == "fix-webhook-auth-bug"


def test_noise_words_dropped():
    assert slugify("Draft the landing page copy for the Shift launch") == "draft-landing-page-copy-shift-launch"


def test_italian_noise_words():
    # Full noise-trimmed result would be "aggiornare-documentazione-octopus-primo-rilascio"
    # but it exceeds the 47-char slug budget (50 - .md) so truncates at last word boundary.
    result = slugify("Aggiornare la documentazione di Octopus per il primo rilascio")
    # `la`, `di`, `per`, `il` are dropped; ends at the last word that fits in 47 chars.
    assert result == "aggiornare-documentazione-octopus-primo"
    assert len(result) <= 47


def test_unicode_folding():
    assert slugify("Café résumé") == "cafe-resume"


def test_truncation_at_word_boundary():
    # 50-char cap including .md (3 chars) = 47-char slug budget
    title = "this is a very long title that exceeds the typical filename length limit"
    slug = slugify(title)
    assert len(slug) <= 47
    # Must end at a word boundary (no mid-word cuts)
    assert not slug.endswith("-")


def test_empty_after_normalization_raises():
    with pytest.raises(ValueError):
        slugify("!!!")


def test_empty_input_raises():
    with pytest.raises(ValueError):
        slugify("")


def test_collision_suffix_basic():
    assert collision_suffix("fix-bug", 2) == "fix-bug-2"
    assert collision_suffix("fix-bug", 3) == "fix-bug-3"


def test_collision_suffix_respects_cap():
    # Force truncation
    base = "a" * 47
    result = collision_suffix(base, 2)
    assert len(result) + len(".md") <= 50


def test_all_noise_falls_back():
    # "the the" → all noise; falls back to keeping the original words
    result = slugify("the the")
    assert result == "the-the"

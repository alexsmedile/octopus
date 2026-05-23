"""Slugification per SPEC.md §10.

Algorithm:
1. Lowercase.
2. NFKD-fold non-ASCII; drop combining marks; strip emoji/CJK.
3. Replace non-alphanumeric sequences with single hyphens.
4. Trim leading/trailing hyphens.
5. Trim noise words.
6. Truncate at last word boundary so slug + ".md" <= max_length.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Default noise words shipped with the implementation.
# Configurable per project via .octopus/config.toml [slug] noise_words.
DEFAULT_NOISE_WORDS_EN = frozenset(
    {"a", "an", "the", "of", "to", "for", "in", "on", "at", "with", "and", "or", "but"}
)
DEFAULT_NOISE_WORDS_IT = frozenset(
    {
        "il", "la", "lo", "i", "gli", "le",
        "un", "una", "di", "da", "con", "su", "per",
        "e", "o", "ma",
    }
)
DEFAULT_NOISE_WORDS = DEFAULT_NOISE_WORDS_EN | DEFAULT_NOISE_WORDS_IT
DEFAULT_MAX_LENGTH = 50  # includes .md extension
EXTENSION = ".md"


def _ascii_fold(text: str) -> str:
    """NFKD decompose, drop combining marks, strip non-ASCII."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch) and ord(ch) < 128)


def slugify(
    title: str,
    *,
    noise_words: Iterable[str] | None = None,
    max_length: int = DEFAULT_MAX_LENGTH,
    extension: str = EXTENSION,
) -> str:
    """Convert a title into a slug per SPEC §10.

    Returns the slug WITHOUT the extension. Caller appends ".md" when writing.

    Raises:
        ValueError: if the result is empty after slugification.
    """
    if not title or not title.strip():
        raise ValueError("title is empty")

    noise = frozenset(w.lower() for w in (noise_words if noise_words is not None else DEFAULT_NOISE_WORDS))

    # 1-2. lowercase + ASCII fold
    text = _ascii_fold(title.lower())

    # 3. non-alphanumeric -> hyphen
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # 4. trim hyphens
    text = text.strip("-")

    if not text:
        raise ValueError(f"slug is empty after normalization: {title!r}")

    # 5. trim noise words
    words = [w for w in text.split("-") if w and w not in noise]

    if not words:
        # All words were noise — fall back to keeping them
        # (otherwise "the a" → empty, which is worse than "the-a")
        words = [w for w in text.split("-") if w]

    if not words:
        raise ValueError(f"slug is empty after noise-word trim: {title!r}")

    # 6. truncate at word boundary so slug + extension <= max_length
    budget = max_length - len(extension)
    if budget <= 0:
        raise ValueError(f"max_length {max_length} too small for extension {extension!r}")

    slug = ""
    for word in words:
        if not slug:
            # First word — accept even if it alone exceeds budget (truncate the word itself)
            slug = word[:budget]
            continue
        candidate = f"{slug}-{word}"
        if len(candidate) <= budget:
            slug = candidate
        else:
            break

    if not slug:
        raise ValueError(f"slug is empty after truncation: {title!r}")

    return slug


def collision_suffix(base_slug: str, counter: int, *, max_length: int = DEFAULT_MAX_LENGTH, extension: str = EXTENSION) -> str:
    """Append `-N` to a slug, truncating base if needed to fit max_length."""
    if counter < 2:
        raise ValueError(f"counter must be >= 2, got {counter}")
    suffix = f"-{counter}"
    budget = max_length - len(extension) - len(suffix)
    if budget < 1:
        raise ValueError(f"counter {counter} doesn't fit within max_length {max_length}")
    truncated = base_slug[:budget].rstrip("-")
    return f"{truncated}{suffix}"

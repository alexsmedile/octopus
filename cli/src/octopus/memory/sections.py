"""Canonical memory sections + partial-name resolution.

Five sections, in display order: Decisions / Open Questions / Context /
Notes / State. Names accept prefix matching when unambiguous.
"""

from __future__ import annotations

# Display order matters: this is the order sections appear in a freshly-
# scaffolded memory.md, and the order `memory show --all` renders them.
CANONICAL_SECTIONS: tuple[str, ...] = (
    "Decisions",
    "Open Questions",
    "Context",
    "Notes",
    "State",
)


class UnknownSectionError(ValueError):
    """No canonical section matches the given name."""


class AmbiguousSectionError(ValueError):
    """The given name matches more than one canonical section."""


def resolve_section(name: str) -> str:
    """Return the canonical section name for a user-supplied name.

    Matching rules (case-insensitive):
      1. Exact match wins.
      2. Prefix match against the canonical name (or its first word).
      3. Multiple matches → AmbiguousSectionError.
      4. No matches → UnknownSectionError.

    Examples:
        resolve_section("decisions") → "Decisions"
        resolve_section("open")      → "Open Questions"
        resolve_section("state")     → "State"
        resolve_section("s")         → AmbiguousSectionError (state, … vs notes/context starts)
                                       (Actually only State starts with "s", but stays explicit.)
    """
    if not name:
        raise UnknownSectionError("section name is empty")
    needle = name.strip().lower()

    # 1. Exact match (case-insensitive on full canonical name).
    for canon in CANONICAL_SECTIONS:
        if canon.lower() == needle:
            return canon

    # 2. Prefix match against the canonical name (full string) OR the first word.
    candidates: list[str] = []
    for canon in CANONICAL_SECTIONS:
        low_full = canon.lower()
        low_first = canon.split()[0].lower()
        if low_full.startswith(needle) or low_first.startswith(needle):
            candidates.append(canon)

    if not candidates:
        raise UnknownSectionError(
            f"unknown section {name!r}; "
            f"valid: {', '.join(s.lower() for s in CANONICAL_SECTIONS)}"
        )
    if len(candidates) > 1:
        raise AmbiguousSectionError(
            f"section {name!r} is ambiguous: matches {candidates}"
        )
    return candidates[0]

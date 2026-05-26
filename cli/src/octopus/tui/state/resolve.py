"""Stale-target cursor fallback.

When restoring a cursor position, the previously-hovered task or activity
may no longer exist (deleted, archived, moved). Strategy: pick the nearest
sibling in panel order — down-first, then up. Always silent.
"""

from __future__ import annotations


def resolve_cursor(target: str | None, candidates: list[str]) -> str | None:
    """Return a valid cursor target from `candidates`.

    - If `target` is in `candidates`, return it unchanged.
    - If `target` is not in `candidates` but we have history of where it
      *was* (via the original ordered candidates), pick the closest sibling.
      Without that history, just return the first candidate.
    - If `candidates` is empty, return None.

    This signature only knows the current candidates — for true nearest-sibling
    behavior, callers should pass the previous index along by calling the
    overload below.
    """
    if not candidates:
        return None
    if target is not None and target in candidates:
        return target
    return candidates[0]


def resolve_cursor_with_index(
    target: str | None,
    candidates: list[str],
    previous_index: int | None = None,
) -> str | None:
    """Nearest-sibling resolve: if target is gone, pick the candidate at the
    same index (clamped), falling back down-then-up.

    `previous_index` is where the target used to be in its previous list.
    If the candidates list shrank, we clamp to `len(candidates) - 1`.
    """
    if not candidates:
        return None
    if target is not None and target in candidates:
        return target
    if previous_index is None:
        return candidates[0]
    # Clamp the previous index to the new list length.
    idx = max(0, min(previous_index, len(candidates) - 1))
    return candidates[idx]

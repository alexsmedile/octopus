"""Tag flag input parsing + mutation (D76).

The full input matrix for `capture`/`set`:

  --tag / --tags                 REPLACE the tag list
  --add-tag / --add-tags         APPEND (dedup)
  --remove-tag / --remove-tags   REMOVE (no-op if absent)
  --clear-tags                   EMPTY the tag list

Each flag value accepts comma-separated, space-separated, or repeated
invocations:
  --tag X,Y
  --tag "X Y Z"
  --tag X --tag Y

Storage convention: tags are stored with leading `#` in frontmatter
(Obsidian-compatible). Nested tags use `/` separator: `#tui/marquee`.

Input is normalized — leading `#` is optional in flag values; the
normalizer adds it.

This module is intentionally pure: no I/O, no logging. Easy to unit-test
and re-use from both `capture` and `set`.
"""

from __future__ import annotations

from dataclasses import dataclass


class TagFlagConflict(ValueError):
    """The user mixed --tag (replace) with --add/--remove/--clear (incremental)."""


@dataclass(frozen=True)
class TagFlagInputs:
    """Raw flag values as captured from Typer. Any field can be None or [].

    `tag` and `add_tag` etc. are the Typer-side accumulated values: each
    invocation appends a string; comma/space splitting happens later.
    """

    replace: list[str] | None = None      # --tag/--tags (None == flag not used)
    add: list[str] | None = None          # --add-tag/--add-tags
    remove: list[str] | None = None       # --remove-tag/--remove-tags
    clear: bool = False                   # --clear-tags


def normalize_tag(raw: str) -> str:
    """Add leading `#` if missing. Empty input returns empty string."""
    s = raw.strip()
    if not s:
        return ""
    if not s.startswith("#"):
        s = "#" + s
    return s


def split_tag_input(values: list[str] | None) -> list[str]:
    """Flatten a list of raw flag values into individual normalized tags.

    Each value may itself be comma-separated or space-separated, or both:
        ["bug,tui", "release p0"]  →  ["#bug", "#tui", "#release", "#p0"]

    Empty/whitespace tokens are dropped. Duplicates within ONE call are
    deduped (preserving first-seen order). The caller decides what to do
    on the larger merge (e.g. add vs. replace).
    """
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if raw is None:
            continue
        # Split on comma first, then on whitespace within each piece.
        for piece in raw.split(","):
            for token in piece.split():
                tag = normalize_tag(token)
                if not tag or tag == "#":
                    continue
                if tag not in seen:
                    seen.add(tag)
                    out.append(tag)
    return out


def validate_mutex(inputs: TagFlagInputs) -> None:
    """Raise TagFlagConflict if replace is mixed with any incremental flag."""
    has_replace = inputs.replace is not None and len(inputs.replace) > 0
    has_incremental = (
        (inputs.add is not None and len(inputs.add) > 0)
        or (inputs.remove is not None and len(inputs.remove) > 0)
        or inputs.clear
    )
    if has_replace and has_incremental:
        raise TagFlagConflict(
            "--tag/--tags (replace) cannot be combined with "
            "--add-tag/--remove-tag/--clear-tags (incremental). "
            "Use one or the other."
        )


def apply_tag_mutations(existing: list[str], inputs: TagFlagInputs) -> list[str]:
    """Apply the locked D76 flag matrix to a tag list. Returns the new list.

    Raises TagFlagConflict on mutex violation.

    Apply order (when no replace is used):
        1. --clear-tags    (empty everything)
        2. --remove-tags   (subtract)
        3. --add-tags      (append, dedup)
    """
    validate_mutex(inputs)

    # Normalize existing tags too — backwards-compat shim. Pre-#24 tags
    # may lack the leading #; we normalize on every write.
    normalized_existing = [normalize_tag(t) for t in existing if normalize_tag(t)]
    # Dedup while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for t in normalized_existing:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    # Replace wins outright (mutex already checked)
    if inputs.replace is not None and len(inputs.replace) > 0:
        return split_tag_input(inputs.replace)

    result = list(deduped)

    if inputs.clear:
        result = []

    if inputs.remove:
        to_remove = set(split_tag_input(inputs.remove))
        result = [t for t in result if t not in to_remove]

    if inputs.add:
        to_add = split_tag_input(inputs.add)
        existing_set = set(result)
        for t in to_add:
            if t not in existing_set:
                existing_set.add(t)
                result.append(t)

    return result


def tag_filter_matches(filter_tag: str, task_tag: str) -> bool:
    """D76 filter behavior: prefix match on `/` boundary.

    `--tag parent` matches `#parent` AND `#parent/anything`.
    Exact-only filtering deferred to a future `--exact` modifier.
    """
    filter_norm = normalize_tag(filter_tag)
    task_norm = normalize_tag(task_tag)
    if not filter_norm or not task_norm:
        return False
    if task_norm == filter_norm:
        return True
    return task_norm.startswith(filter_norm + "/")

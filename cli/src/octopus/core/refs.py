"""Find textual references to a slug across all Octopus-managed files (D79).

Used by both:
  - `octopus refs find <slug>` (read-only)
  - The `set --slug` slug-rename cascade (D78), which auto-rewrites known
    Octopus-managed locations and warns about user-written prose.

Scope (per D78/D79):
  Always greppable (auto-fix candidates):
    - tasks/<bucket>/*.md  (waiting_for, related slug fields)
    - .spectacular/requests/*/PLAN.md  (related_tasks, promoted_from)
    - .spectacular/requests/_archive/**/PLAN.md  (same)
    - <activity root>/TODO.md  (→ octopus:<slug> arrows)

  Soft warnings (named, not auto-fixed):
    - .octopus/sessions/*.md
    - .octopus/memory.md
    - .octopus/handoffs/*.md

All operations are pure read here. The rewriter (in cli.py's set --slug
path) reuses these scan helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Category tags surface in both the find output and the rename cascade preview.
CATEGORY_TASKS = "tasks"
CATEGORY_SPEC = "spectacular"
CATEGORY_TODO_MD = "todo-md"
CATEGORY_SESSIONS = "sessions"
CATEGORY_MEMORY = "memory"
CATEGORY_HANDOFFS = "handoffs"


# Octopus-managed (safe to auto-fix on rename)
MANAGED_CATEGORIES = {CATEGORY_TASKS, CATEGORY_SPEC, CATEGORY_TODO_MD}
# Soft-warn (user prose; named only)
WARN_CATEGORIES = {CATEGORY_SESSIONS, CATEGORY_MEMORY, CATEGORY_HANDOFFS}


@dataclass(frozen=True)
class RefHit:
    """One textual hit of a slug in a file."""

    file: Path
    line_number: int
    line: str
    category: str


def find_refs(
    activity_root: Path,
    slug: str,
) -> list[RefHit]:
    """Scan every Octopus-managed text file in the activity for a slug.

    Returns hits sorted by category (managed first, then warn-only).
    Whole-word match on the slug to avoid false positives on substrings.
    """
    if not slug:
        return []

    pattern = _word_boundary_regex(slug)
    hits: list[RefHit] = []

    octopus_dir = activity_root / ".octopus"
    spec_dir = activity_root / ".spectacular" / "requests"

    # Tasks (managed) — every bucket, every flat task in field mode.
    tasks_root = octopus_dir / "tasks"
    if tasks_root.is_dir():
        for f in _walk_md(tasks_root):
            hits.extend(_scan_file(f, pattern, CATEGORY_TASKS))

    # Spectacular requests (managed) — live + archived.
    if spec_dir.is_dir():
        for plan in spec_dir.glob("**/PLAN.md"):
            hits.extend(_scan_file(plan, pattern, CATEGORY_SPEC))

    # TODO.md (managed) — single file at activity root.
    todo = activity_root / "TODO.md"
    if todo.is_file():
        hits.extend(_scan_file(todo, pattern, CATEGORY_TODO_MD))

    # Sessions (warn).
    sessions_root = octopus_dir / "sessions"
    if sessions_root.is_dir():
        for f in _walk_md(sessions_root):
            hits.extend(_scan_file(f, pattern, CATEGORY_SESSIONS))

    # Memory (warn).
    memory = octopus_dir / "memory.md"
    if memory.is_file():
        hits.extend(_scan_file(memory, pattern, CATEGORY_MEMORY))

    # Handoffs (warn).
    handoffs_root = octopus_dir / "handoffs"
    if handoffs_root.is_dir():
        for f in _walk_md(handoffs_root):
            hits.extend(_scan_file(f, pattern, CATEGORY_HANDOFFS))

    # Stable sort: managed first, then by file path.
    def _sort_key(h: RefHit) -> tuple:
        cat_rank = 0 if h.category in MANAGED_CATEGORIES else 1
        return (cat_rank, str(h.file), h.line_number)

    hits.sort(key=_sort_key)
    return hits


def categorize_hits(hits: list[RefHit]) -> tuple[list[RefHit], list[RefHit]]:
    """Split hits into (managed, warn-only) groups."""
    managed = [h for h in hits if h.category in MANAGED_CATEGORIES]
    warn = [h for h in hits if h.category in WARN_CATEGORIES]
    return managed, warn


# ── internals ─────────────────────────────────────────────────────────


def _word_boundary_regex(slug: str) -> re.Pattern[str]:
    """Match the slug only at word boundaries.

    Slugs use lowercase + hyphens, so the boundary characters are anything
    that isn't `[a-z0-9-]`. `re.escape(slug)` guards against any future
    slug formats that include regex metachars.
    """
    return re.compile(
        r"(?<![A-Za-z0-9_-])" + re.escape(slug) + r"(?![A-Za-z0-9_-])"
    )


def _walk_md(root: Path):
    """Yield all *.md files under root, skipping .trash/ and hidden dirs."""
    for path in root.rglob("*.md"):
        # Skip trash + hidden subdirs (defensive — most don't exist anyway)
        if any(p.startswith(".") or p == ".trash" for p in path.relative_to(root).parts[:-1]):
            continue
        yield path


def _scan_file(path: Path, pattern: re.Pattern[str], category: str) -> list[RefHit]:
    """Read a file line-by-line; emit RefHit for each line matching the regex."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[RefHit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            out.append(
                RefHit(
                    file=path,
                    line_number=lineno,
                    line=line.rstrip(),
                    category=category,
                )
            )
    return out

"""Slug renaming with cascading auto-fix of Octopus-managed references (D78).

Used by `octopus set <slug> --slug <new>`. Always-auto-fixed locations:
  1. Filesystem: tasks/<bucket>/<old>.md → tasks/<bucket>/<new>.md
  2. SQLite index: tasks.slug + tasks.id
  3. waiting_for: <old> in other tasks
  4. related_tasks: [..., <old>, ...] in spectacular PLAN.md
  5. promoted_from: <old> in spectacular PLAN.md
  6. → octopus:<old> arrows in TODO.md files

Soft-warned (named, not touched):
  - sessions/*.md, memory.md, handoffs/*.md

Two phases:
  scan_rewrite_plan() — read-only, returns a RewritePlan with all the
                        actions that would happen. Used for the prompt.
  apply_rewrite_plan() — performs the rewrites + filesystem move.

This split lets us preview without committing — and makes the rename
testable without writing files in test mode (apply only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from octopus.core.refs import (
    CATEGORY_HANDOFFS,
    CATEGORY_MEMORY,
    CATEGORY_SESSIONS,
    CATEGORY_SPEC,
    CATEGORY_TASKS,
    CATEGORY_TODO_MD,
    find_refs,
)


@dataclass
class RewriteAction:
    """One file edit that the cascade will perform."""

    file: Path
    category: str
    description: str    # human-readable, for the preview prompt


@dataclass
class RewritePlan:
    """Complete cascade preview. Returned by scan_rewrite_plan()."""

    old_slug: str
    new_slug: str
    activity_root: Path
    source_file: Path                       # old task file path
    target_file: Path                       # new task file path

    # Auto-fix actions (D78 top six)
    actions: list[RewriteAction] = field(default_factory=list)

    # Soft warnings (D78 sessions/memory/handoffs + external tools)
    soft_warnings: list[RewriteAction] = field(default_factory=list)


class SlugRenameError(Exception):
    """User-facing error during slug rename."""


# ── public API ────────────────────────────────────────────────────────


def scan_rewrite_plan(
    activity_root: Path,
    source_file: Path,
    old_slug: str,
    new_slug: str,
) -> RewritePlan:
    """Build a RewritePlan WITHOUT modifying anything. Used for the prompt."""
    if not new_slug or not _is_valid_slug(new_slug):
        raise SlugRenameError(
            f"invalid new slug {new_slug!r} (lowercase alphanumerics + hyphens only)"
        )
    if old_slug == new_slug:
        raise SlugRenameError(f"old and new slugs are identical: {old_slug!r}")

    target_file = source_file.parent / f"{new_slug}.md"
    if target_file.exists():
        raise SlugRenameError(
            f"a task at {target_file} already exists; choose another slug"
        )

    plan = RewritePlan(
        old_slug=old_slug,
        new_slug=new_slug,
        activity_root=activity_root,
        source_file=source_file,
        target_file=target_file,
    )

    # 1. Filesystem rename — always.
    plan.actions.append(RewriteAction(
        file=source_file,
        category=CATEGORY_TASKS,
        description=f"rename file: {source_file.name} → {new_slug}.md",
    ))

    # Now scan every Octopus-managed file for the old slug.
    hits = find_refs(activity_root, old_slug)

    # Skip the source file itself from the rewrite preview (it's renamed,
    # and its own `title:` field is unaffected — title ≠ slug).
    for h in hits:
        # The source-file's own title/path won't change semantically — its
        # content doesn't reference the slug textually except via `title`,
        # which we don't change. Skip self-hits.
        if h.file == source_file:
            continue

        if h.category == CATEGORY_TASKS:
            plan.actions.append(RewriteAction(
                file=h.file,
                category=CATEGORY_TASKS,
                description=f"update {h.file.name} line {h.line_number}: rewrite {old_slug!r} → {new_slug!r}",
            ))
        elif h.category == CATEGORY_SPEC:
            plan.actions.append(RewriteAction(
                file=h.file,
                category=CATEGORY_SPEC,
                description=f"update {h.file.name} line {h.line_number}: rewrite {old_slug!r} → {new_slug!r}",
            ))
        elif h.category == CATEGORY_TODO_MD:
            plan.actions.append(RewriteAction(
                file=h.file,
                category=CATEGORY_TODO_MD,
                description=f"update {h.file.name} line {h.line_number}: → octopus:{old_slug} → → octopus:{new_slug}",
            ))
        elif h.category in (CATEGORY_SESSIONS, CATEGORY_MEMORY, CATEGORY_HANDOFFS):
            # Soft warning only.
            plan.soft_warnings.append(RewriteAction(
                file=h.file,
                category=h.category,
                description=f"{h.file.name} line {h.line_number}: {h.line.strip()[:80]}",
            ))

    return plan


def apply_rewrite_plan(plan: RewritePlan) -> None:
    """Execute the auto-fix actions in a RewritePlan.

    Order:
      1. Rewrite every non-source file (in-place line-level text rewrite).
      2. Move the source task file.

    Frontmatter title is unchanged — `title:` is the displayed name; slug
    is the filename. Existing `external_refs.todo-md` etc. inside the task
    are also unchanged (they refer to external IDs, not the task slug).
    """
    old_pattern = _word_boundary_regex(plan.old_slug)
    new_slug = plan.new_slug

    # Group actions by file so multiple line-edits within one file land
    # in a single read-modify-write cycle.
    edits_by_file: dict[Path, list[RewriteAction]] = {}
    file_rename: Path | None = None

    for action in plan.actions:
        if action.category == CATEGORY_TASKS and action.file == plan.source_file:
            # The source-file rename (action 1) is handled separately.
            file_rename = action.file
            continue
        edits_by_file.setdefault(action.file, []).append(action)

    # 1. Apply text rewrites to every other file.
    for file, _actions in edits_by_file.items():
        text = file.read_text(encoding="utf-8")
        new_text = old_pattern.sub(new_slug, text)
        if new_text != text:
            file.write_text(new_text, encoding="utf-8")

    # 2. Move the source task file.
    if file_rename is not None:
        plan.source_file.rename(plan.target_file)


# ── helpers ───────────────────────────────────────────────────────────


_SLUG_VALID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _is_valid_slug(slug: str) -> bool:
    if not slug or len(slug) > 200:
        return False
    return bool(_SLUG_VALID_RE.match(slug))


def _word_boundary_regex(slug: str) -> re.Pattern[str]:
    """Same boundaries as core.refs._word_boundary_regex — kept here to
    avoid a circular dep between rename and refs.
    """
    return re.compile(
        r"(?<![A-Za-z0-9_-])" + re.escape(slug) + r"(?![A-Za-z0-9_-])"
    )

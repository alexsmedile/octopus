"""`subtask-orphan` — `parent:` slug points to a task that doesn't exist.

D104: parent/child links are activity-scoped. A child whose parent slug is
not present among sibling tasks has a dangling reference. Warn (not error)
because the parent may have been legitimately dropped or moved.
"""

from __future__ import annotations

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "subtask-orphan"


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    t = ctx.task
    if not t.parent:
        return []
    # Cross-activity slash syntax is a hard error (caught by model validation),
    # but lint defensively skips it here — subtask-cross-activity handles it.
    if "/" in t.parent:
        return []
    if t.parent not in ctx.sibling_slugs:
        return [
            Finding(
                code=CODE,
                severity=Severity.WARN,
                path=ctx.path,
                message=(
                    f"parent={t.parent!r} not found among activity tasks "
                    "(dropped, moved, or slug mismatch)"
                ),
                auto_fixable=False,
            )
        ]
    return []


register(Rule(
    code=CODE,
    description="parent: slug points to a non-existent sibling task (D104)",
    auto_fixable=False,
    check=check,
))

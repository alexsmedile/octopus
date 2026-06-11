"""`subtask-depth` — a task cannot be both a child (parent set) and a parent (subtasks set).

D104: max nesting depth is 1. A task with `parent:` set must not also have
`subtasks:` entries. The model validates this too, but lint catches files
that were hand-edited or written by an older version.
"""

from __future__ import annotations

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "subtask-depth"


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    t = ctx.task
    if not t.parent or not t.subtasks:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.ERROR,
            path=ctx.path,
            message=(
                f"task has parent={t.parent!r} AND subtasks={t.subtasks!r}; "
                "nesting depth may not exceed 1 (D104)"
            ),
            auto_fixable=False,
        )
    ]


register(Rule(
    code=CODE,
    description="task cannot be both a child (parent:) and a parent (subtasks:) — D104",
    auto_fixable=False,
    check=check,
))

"""`subtask-cross-activity` — `parent:` contains a `/` (cross-activity slug).

D104: subtask relationships are activity-scoped only. A `parent:` value
with a `/` is structurally invalid.
"""

from __future__ import annotations

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "subtask-cross-activity"


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    t = ctx.task
    if not t.parent:
        return []
    if "/" not in t.parent:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.ERROR,
            path=ctx.path,
            message=(
                f"parent={t.parent!r} contains '/'; cross-activity subtasks "
                "are not supported (D104)"
            ),
            auto_fixable=False,
        )
    ]


register(Rule(
    code=CODE,
    description="parent: field must not contain '/' — cross-activity subtasks unsupported (D104)",
    auto_fixable=False,
    check=check,
))

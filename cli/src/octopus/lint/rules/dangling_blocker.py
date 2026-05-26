"""`dangling-blocker` — `blocked_by:` references a slug that doesn't exist locally.

Local meaning: in the same activity. Cross-activity references (D26/27) are
out of scope for this rule — treat any token that looks like a fully-qualified
reference (contains `/`, `:`, or `@`) as "not our problem."
"""

from __future__ import annotations

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "dangling-blocker"


def _looks_like_external_ref(token: str) -> bool:
    return any(ch in token for ch in ("/", ":", "@"))


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    target = ctx.task.blocked_by
    if not target or not isinstance(target, str):
        return []
    target = target.strip()
    if not target:
        return []
    if _looks_like_external_ref(target):
        return []
    # If the value looks like free-text ("needs key schema review"), skip — there's
    # no slug to validate against. Heuristic: a slug never contains spaces.
    if " " in target:
        return []
    if target in ctx.sibling_slugs:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.WARN,
            path=ctx.path,
            message=f"blocked_by={target!r} does not match any task slug in this activity",
            auto_fixable=False,
        )
    ]


register(Rule(
    code=CODE,
    description="blocked_by references a real local slug",
    auto_fixable=False,
    check=check,
))

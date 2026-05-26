"""`bucket-blocked` — `issue: blocked|waiting` in NOW or NEXT (info-only, per D100).

D100: human-set blocked/waiting tasks are allowed in any bucket. This rule
surfaces them for visibility but never auto-fixes and never raises severity
above INFO. A future request will tighten the rule for AI-actor flows.
"""

from __future__ import annotations

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "bucket-blocked"
_ACTIVE_BUCKETS = {"now", "next"}
_FLAGGED_ISSUES = {"blocked", "waiting"}


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    t = ctx.task
    if t.bucket not in _ACTIVE_BUCKETS:
        return []
    if t.issue not in _FLAGGED_ISSUES:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.INFO,
            path=ctx.path,
            message=(
                f"issue={t.issue!r} in {t.bucket.upper()} "
                "(allowed per D100; AI-actor flows will be tightened separately)"
            ),
            auto_fixable=False,
        )
    ]


register(Rule(
    code=CODE,
    description="surface blocked/waiting tasks in NOW or NEXT (D100, info-only)",
    auto_fixable=False,
    check=check,
))

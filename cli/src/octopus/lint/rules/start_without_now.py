"""`start-without-now` — `start_date` set but bucket is not `now`."""

from __future__ import annotations

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "start-without-now"


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    t = ctx.task
    if t.start_date is None:
        return []
    if t.bucket == "now":
        return []
    # Done/dropped legitimately have start_date in the past — don't flag those.
    if t.bucket in {"done", "dropped"}:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.WARN,
            path=ctx.path,
            message=(
                f"start_date={t.start_date.isoformat()} set but bucket={t.bucket!r} "
                "— promote to `now` or clear start_date"
            ),
            auto_fixable=False,
        )
    ]


register(Rule(
    code=CODE,
    description="start_date implies bucket=now",
    auto_fixable=False,
    check=check,
))

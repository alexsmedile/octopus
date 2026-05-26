"""`corrupt-frontmatter` — YAML parses cleanly; no unknown legacy fields."""

from __future__ import annotations

from octopus.fs.io import LEGACY_FIELDS
from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "corrupt-frontmatter"


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.parse_error is not None:
        return [
            Finding(
                code=CODE,
                severity=Severity.ERROR,
                path=ctx.path,
                message=f"frontmatter parse failed: {ctx.parse_error}",
                auto_fixable=False,
            )
        ]
    if ctx.task is None:
        return []
    legacy_present = [k for k in ctx.task.extra if k in LEGACY_FIELDS]
    if not legacy_present:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.ERROR,
            path=ctx.path,
            message=f"legacy field(s) present: {sorted(legacy_present)}",
            auto_fixable=False,
        )
    ]


register(Rule(
    code=CODE,
    description="frontmatter parses and uses only canonical fields",
    auto_fixable=False,
    check=check,
))

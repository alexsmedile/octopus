"""`bucket-match` — `bucket:` field equals parent folder name (folder storage)."""

from __future__ import annotations

from octopus.fs.io import read_task, write_task
from octopus.fs.scaffold import BUCKET_FOLDERS
from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "bucket-match"


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    parent = ctx.path.parent.name
    # Only meaningful for folder storage mode — skip files at the tasks/ root.
    if parent not in BUCKET_FOLDERS:
        return []
    if ctx.task.bucket == parent:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.ERROR,
            path=ctx.path,
            message=(
                f"bucket field {ctx.task.bucket!r} does not match "
                f"parent folder {parent!r}"
            ),
            auto_fixable=True,
            fix_preview={"bucket": parent},
        )
    ]


def fix(finding: Finding, ctx: RuleContext) -> bool:
    if ctx.task is None or ctx.body is None:
        return False
    expected = ctx.path.parent.name
    task, body = read_task(ctx.path)
    task.bucket = expected
    write_task(ctx.path, task, body)
    return True


register(Rule(
    code=CODE,
    description="bucket field equals parent folder name",
    auto_fixable=True,
    check=check,
    fix=fix,
))

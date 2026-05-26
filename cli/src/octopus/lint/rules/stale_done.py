"""`stale-done` — bucket=done with end_date older than 30 days.

Auto-fix moves the file into `<activity_root>/_archive/tasks-<YYYY-MM>/` based
on the task's `end_date`. The move is FS-level only; the index is not updated
here (callers run `octopus reindex` afterwards if needed).
"""

from __future__ import annotations

from datetime import date, timedelta

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "stale-done"
THRESHOLD_DAYS = 30


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    t = ctx.task
    if t.bucket != "done":
        return []
    if t.end_date is None:
        return []
    age = (date.today() - t.end_date).days
    if age <= THRESHOLD_DAYS:
        return []
    archive_dir = f"_archive/tasks-{t.end_date.strftime('%Y-%m')}"
    return [
        Finding(
            code=CODE,
            severity=Severity.INFO,
            path=ctx.path,
            message=(
                f"done {age}d ago (end_date={t.end_date.isoformat()}); "
                f"candidate for {archive_dir}/"
            ),
            auto_fixable=True,
            fix_preview={"move_to": archive_dir},
        )
    ]


def fix(finding: Finding, ctx: RuleContext) -> bool:
    if ctx.task is None or ctx.task.end_date is None:
        return False
    archive_dir = ctx.activity_root / "_archive" / f"tasks-{ctx.task.end_date.strftime('%Y-%m')}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / ctx.path.name
    if target.exists():
        return False  # don't overwrite; caller must resolve manually
    ctx.path.rename(target)
    return True


# Suppress unused-import warning for timedelta if mypy/ruff is strict.
_ = timedelta

register(Rule(
    code=CODE,
    description="done tasks older than 30d should be archived",
    auto_fixable=True,
    check=check,
    fix=fix,
))

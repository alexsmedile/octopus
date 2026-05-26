"""`slug-match` — task file's raw `slug:` field equals the filename stem.

`read_task` derives `Task.slug` from `path.stem`, so the parsed Task can't
detect drift. We inspect the raw frontmatter to compare. Fix re-writes the
file via `write_task`, which drops the unused `slug:` field entirely (slug
is filename-derived in the canonical schema, D-spec).
"""

from __future__ import annotations

import frontmatter

from octopus.fs.io import read_task, write_task
from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "slug-match"


def _raw_slug(path) -> str | None:
    try:
        post = frontmatter.load(path)
    except Exception:  # noqa: BLE001
        return None
    raw = post.metadata.get("slug")
    return str(raw) if raw is not None else None


def check(ctx: RuleContext) -> list[Finding]:
    if ctx.task is None:
        return []
    expected = ctx.path.stem
    raw = _raw_slug(ctx.path)
    if raw is None or raw == expected:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.ERROR,
            path=ctx.path,
            message=f"slug {raw!r} does not match filename stem {expected!r}",
            auto_fixable=True,
            fix_preview={"slug": expected},
        )
    ]


def fix(finding: Finding, ctx: RuleContext) -> bool:
    if ctx.task is None or ctx.body is None:
        return False
    expected = ctx.path.stem
    task, body = read_task(ctx.path)
    task.slug = expected
    # `slug` lives in `extra` (not in TASK_FIELDS) — pop so write_task drops it.
    task.extra.pop("slug", None)
    write_task(ctx.path, task, body)
    return True


register(Rule(
    code=CODE,
    description="slug field equals filename stem",
    auto_fixable=True,
    check=check,
    fix=fix,
))

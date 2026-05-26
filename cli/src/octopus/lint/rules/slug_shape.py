"""`slug-shape` — raw slug matches `^[a-z0-9-]+$`. No spaces, no quotes.

Checks the raw `slug:` frontmatter field (and the filename stem, since the
filename is the canonical slug). If either is malformed, the rule fires.
"""

from __future__ import annotations

import re

import frontmatter

from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, register

CODE = "slug-shape"
_VALID = re.compile(r"^[a-z0-9-]+$")


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
    # Check filename stem (canonical)
    stem = ctx.path.stem
    candidates: list[str] = [stem]
    # Also check raw slug if it's present and differs (otherwise we'd double-report)
    raw = _raw_slug(ctx.path)
    if raw is not None and raw != stem:
        candidates.append(raw)
    bad = [s for s in candidates if not _VALID.fullmatch(s)]
    if not bad:
        return []
    return [
        Finding(
            code=CODE,
            severity=Severity.ERROR,
            path=ctx.path,
            message=(
                f"malformed slug {bad[0]!r} "
                "(allowed: lowercase letters, digits, hyphens)"
            ),
            auto_fixable=False,
        )
    ]


register(Rule(
    code=CODE,
    description="slug uses lowercase letters, digits, hyphens only",
    auto_fixable=False,
    check=check,
))

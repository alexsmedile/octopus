"""Rule registration for `octopus lint`.

Each rule module under `rules/` calls `register()` at import time. The runner
imports `rules` (which imports every rule module) to populate the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from octopus.core.models import Task
from octopus.lint.findings import Finding


@dataclass
class Rule:
    code: str
    description: str
    auto_fixable: bool
    check: Callable[[RuleContext], list[Finding]]
    # fix(finding, ctx) -> applied?  Idempotent; returns True if a change was written.
    fix: Callable[[Finding, RuleContext], bool] | None = None


@dataclass
class RuleContext:
    """Per-file context passed to every rule.

    `task` is None when the file failed to parse — only `corrupt-frontmatter`
    runs against the raw path in that case.
    """

    path: Path
    task: Task | None
    body: str | None
    # All sibling slugs in the same activity, for dangling-blocker etc.
    sibling_slugs: set[str]
    # Activity root (the parent of `.octopus/`).
    activity_root: Path
    # Parse error if the YAML failed (mutually exclusive with task != None).
    parse_error: str | None = None


_RULES: dict[str, Rule] = {}


def register(rule: Rule) -> None:
    if rule.code in _RULES:
        raise ValueError(f"duplicate lint rule code: {rule.code}")
    _RULES[rule.code] = rule


def get(code: str) -> Rule | None:
    return _RULES.get(code)


def all_rules() -> list[Rule]:
    return list(_RULES.values())


def reset() -> None:
    """Test helper — clears the registry."""
    _RULES.clear()

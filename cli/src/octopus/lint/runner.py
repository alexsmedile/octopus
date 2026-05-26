"""Lint runner — walks task files and applies registered rules."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from octopus.fs.io import read_task
from octopus.fs.scaffold import BUCKET_FOLDERS
from octopus.lint.findings import Finding, Severity
from octopus.lint.registry import Rule, RuleContext, all_rules, get


@dataclass
class LintReport:
    findings: list[Finding] = field(default_factory=list)
    scanned: int = 0

    @property
    def counts(self) -> dict[str, int]:
        out = {"error": 0, "warn": 0, "info": 0}
        for f in self.findings:
            out[f.severity.value] += 1
        return out

    @property
    def max_severity(self) -> Severity | None:
        if not self.findings:
            return None
        return max((f.severity for f in self.findings), key=lambda s: s.rank())

    def exit_code(self) -> int:
        sev = self.max_severity
        if sev is None:
            return 0
        return {Severity.INFO: 1, Severity.WARN: 1, Severity.ERROR: 2}[sev]


def _gather_task_files(activity_root: Path) -> list[Path]:
    """Collect every task file under `<activity_root>/.octopus/tasks/`."""
    tasks_dir = activity_root / ".octopus" / "tasks"
    if not tasks_dir.is_dir():
        return []
    out: list[Path] = []
    # Bucket subfolders (folder storage mode).
    for bucket in sorted(BUCKET_FOLDERS):
        bdir = tasks_dir / bucket
        if bdir.is_dir():
            out.extend(sorted(bdir.glob("*.md")))
    # Loose files at the tasks root (fields storage mode).
    out.extend(sorted(tasks_dir.glob("*.md")))
    return out


def _gather_sibling_slugs(task_files: Iterable[Path]) -> set[str]:
    return {p.stem for p in task_files}


def _build_context(path: Path, activity_root: Path, sibling_slugs: set[str]) -> RuleContext:
    try:
        task, body = read_task(path)
        return RuleContext(
            path=path,
            task=task,
            body=body,
            sibling_slugs=sibling_slugs,
            activity_root=activity_root,
        )
    except Exception as exc:  # noqa: BLE001
        return RuleContext(
            path=path,
            task=None,
            body=None,
            sibling_slugs=sibling_slugs,
            activity_root=activity_root,
            parse_error=str(exc),
        )


def _select_rules(rule_codes: list[str] | None) -> list[Rule]:
    if rule_codes is None:
        return all_rules()
    out: list[Rule] = []
    for code in rule_codes:
        r = get(code)
        if r is None:
            raise ValueError(f"unknown rule: {code}")
        out.append(r)
    return out


def lint_paths(
    task_files: list[Path],
    activity_root: Path,
    rule_codes: list[str] | None = None,
) -> LintReport:
    """Lint a specific list of task files. Used by tests and lint_activity."""
    rules = _select_rules(rule_codes)
    sibling_slugs = _gather_sibling_slugs(task_files)
    report = LintReport(scanned=len(task_files))
    for path in task_files:
        ctx = _build_context(path, activity_root, sibling_slugs)
        for rule in rules:
            try:
                report.findings.extend(rule.check(ctx))
            except Exception as exc:  # noqa: BLE001
                # A rule crash is itself a finding (never abort the whole run).
                report.findings.append(
                    Finding(
                        code="rule-crash",
                        severity=Severity.ERROR,
                        path=path,
                        message=f"rule {rule.code!r} crashed: {exc}",
                    )
                )
    return report


def lint_activity(
    activity_root: Path,
    rule_codes: list[str] | None = None,
) -> LintReport:
    """Lint every task in an activity."""
    files = _gather_task_files(activity_root)
    return lint_paths(files, activity_root, rule_codes)


def apply_fix(finding: Finding) -> bool:
    """Apply a single finding's auto-fix. Returns True if a change was written.

    Caller is responsible for confirming with the user beforehand. The fix
    re-loads the file, rewrites the relevant field via the rule's `fix()`,
    and persists via `write_task`. Returns False if the rule has no fix or
    the finding is not auto-fixable.
    """
    if not finding.auto_fixable:
        return False
    rule = get(finding.code)
    if rule is None or rule.fix is None:
        return False
    # Build a fresh context for the single file.
    activity_root = finding.path.parents[2]  # .../<activity>/.octopus/tasks/<bucket>/file.md → activity
    # Walk up to find activity root reliably.
    cur = finding.path.parent
    while cur != cur.parent:
        if (cur / ".octopus").is_dir() or (cur.name == ".octopus" and cur.is_dir()):
            activity_root = cur if (cur / ".octopus").is_dir() else cur.parent
            break
        cur = cur.parent
    sibling_slugs = _gather_sibling_slugs(_gather_task_files(activity_root))
    ctx = _build_context(finding.path, activity_root, sibling_slugs)
    return rule.fix(finding, ctx)


# Eager rule import — ensures every rule module registers itself before runs.
def _autoload_rules() -> None:
    from octopus.lint import rules  # noqa: F401


_autoload_rules()

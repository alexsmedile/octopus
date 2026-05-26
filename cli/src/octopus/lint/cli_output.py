"""Human + JSON output adapters for `octopus lint`."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from octopus.lint.findings import Finding, Severity
from octopus.lint.runner import LintReport

_STYLE = {
    Severity.ERROR: "red",
    Severity.WARN: "yellow",
    Severity.INFO: "dim",
}


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _filter(report: LintReport, min_severity: Severity | None) -> list[Finding]:
    if min_severity is None:
        return report.findings
    floor = min_severity.rank()
    return [f for f in report.findings if f.severity.rank() >= floor]


def print_human(
    report: LintReport,
    *,
    console: Console,
    base: Path,
    min_severity: Severity | None = None,
) -> None:
    findings = _filter(report, min_severity)
    if not findings:
        console.print(f"[green]✓[/] clean ({report.scanned} task(s) scanned)")
        return

    # Group by file for readability.
    by_path: dict[Path, list[Finding]] = {}
    for f in findings:
        by_path.setdefault(f.path, []).append(f)

    for path, group in by_path.items():
        console.print(f"[bold]{_rel(path, base)}[/]")
        for f in group:
            style = _STYLE[f.severity]
            tag = f"[{style}]{f.severity.value:5}[/]"
            console.print(f"  {tag} [cyan]{f.code:20}[/] {f.message}")
            if f.auto_fixable:
                console.print("           [dim]→ fixable with `octopus lint --fix`[/]")
        console.print()

    counts = report.counts
    summary = f"{len(findings)} finding(s) across {report.scanned} task(s): "
    summary += f"[red]{counts['error']} error[/], "
    summary += f"[yellow]{counts['warn']} warn[/], "
    summary += f"[dim]{counts['info']} info[/]"
    console.print(summary)


def print_json(
    report: LintReport,
    *,
    console: Console,
    min_severity: Severity | None = None,
) -> None:
    findings = _filter(report, min_severity)
    payload = {
        "version": 1,
        "scanned": report.scanned,
        "findings": [f.to_dict() for f in findings],
        "summary": report.counts,
    }
    console.print(json.dumps(payload, indent=2))

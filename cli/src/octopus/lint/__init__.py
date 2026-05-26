"""`octopus lint` — corpus hygiene audit.

Read-only by default. Each rule lives under `rules/`, registers itself in
`registry.py`, and may declare an optional `fix()` for `--fix`.

See `.spectacular/requests/42-lint-command/PLAN.md` for the contract.
"""

from octopus.lint.findings import Finding, Severity
from octopus.lint.runner import LintReport, lint_activity, lint_paths

__all__ = ["Finding", "Severity", "LintReport", "lint_activity", "lint_paths"]

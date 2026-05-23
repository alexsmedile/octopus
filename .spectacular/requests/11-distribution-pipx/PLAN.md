---
status: queued
priority: medium
owner: alex
updated: 2026-05-21
summary: "Package for pipx — pyproject finalized, octopus diagnose, logs, --version, basic CI."
related:
  - 08-plugin-claude-code
gates:
  - 03-index-sqlite
---

# Distribution — pipx

## Goal

Polish the v1 release: real `pyproject.toml`, log infrastructure, `octopus diagnose` for bug reports, `--version`, basic GitHub Actions CI.

## Scope summary

- `cli/pyproject.toml` finalized with deps pinned to compatible ranges, classifiers, description, license.
- `octopus --version` prints full version.
- `octopus diagnose` zips relevant logs from `~/.local/share/octopus/logs/`, shows contents before zipping.
- GitHub Actions: lint (ruff), test (pytest), build wheel on tag.
- `pipx install octopus-cli` from local wheel works end-to-end.
- README installation section finalized.

## Detailed PLAN.md to be drafted when this request activates.

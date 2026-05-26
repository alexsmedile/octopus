---
request: 42-lint-command
updated: 2026-05-26
---

# Tasks — 42-lint-command

## Spine
- [x] T1 — Create `cli/src/octopus/lint/` skeleton: `findings.py`, `registry.py`, `runner.py`, `rules/__init__.py`
- [x] T2 — Implement `slug-match` rule end-to-end (check + fix) as the spine reference
- [x] T3 — Wire `octopus lint` as a top-level command in `cli.py` (basic human output, exit codes)
- [x] T4 — Write `cli/tests/lint/conftest.py` + test for `slug-match`

## Rules (one task each — check + test; auto-fix where flagged)
- [x] T5 — `slug-shape` (error, no fix)
- [x] T6 — `bucket-match` (error, fix)
- [x] T7 — `corrupt-frontmatter` (error, no fix)
- [x] T8 — `start-without-now` (warn, no fix)
- [x] T9 — `dangling-blocker` (warn, no fix)
- [x] T10 — `stale-done` (info, fix → `_archive/tasks-<YYYY-MM>/`)
- [x] T11 — `bucket-blocked` (info per D100, no fix)

## Drivers
- [x] T12 — `--fix` driver: per-file diff preview + prompt + `--yes` skip
- [x] T13 — `--json` output adapter
- [x] T14 — `--rule=<code>` and `--severity=<level>` filters

## Smoke
- [x] T15 — Run `octopus lint --all` against live `.octopus/` corpus; verify expected findings on `polish-error-messages-and-rich-output` and zero false-positives elsewhere

## Spec sync
- [x] T16 — Add `lint` entry to `.spectacular/specs/CLI-VERBS.md`
- [x] T17 — Mirror to `skills/octopus/references/cli-verbs.md`
- [x] T18 — Append rule list to `.spectacular/specs/CRITICAL-DEPENDENCIES.md` + skill mirror

## Close
- [x] T19 — CHANGELOG entry under `[Unreleased]`
- [x] T20 — Set `status: done` in `PLAN.md` frontmatter

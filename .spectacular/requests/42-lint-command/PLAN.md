---
status: done
priority: medium
owner: alex
updated: 2026-05-26
summary: "Add `octopus lint` — a read-only audit verb for task / activity hygiene with optional `--fix` for safe auto-repairs. Surfaces drift between filename, slug, bucket, schema, and dates."
related:
  - 30-index-hygiene
  - 41-tui-glyph-audit
gates: []
---

# Lint command

## Goal

Add `octopus lint` — a read-only audit verb that walks all activities (or a single one) and reports hygiene issues across the task corpus. Each finding has a stable rule code, a severity, and (optionally) an auto-fix. Output is human-readable by default and JSON-emittable for hooks and CI.

The first concrete motivator: during the dogfood-tasks cleanup pass on 2026-05-26, two task files had corrupted `slug:` fields (`slug: <name> <stray-note>'`) that went undetected for three days because nothing validates that the slug matches the filename. A lint pass catches both in seconds.

## Why

The `.octopus/` corpus drifts in predictable ways. Today the only signal that something is wrong is a CLI command crashing, or a human noticing during a manual review. Examples found during the 2026-05-26 audit:

- 2 task files with corrupted slugs (slug ≠ filename, introduced by a hand-paste accident on 2026-05-23)
- 1 task with `start_date` set but `bucket: backlog` — the data lies about whether work has begun
- 5 tasks with empty bodies that future-Alex won't be able to interpret six months from now
- `done/` accumulating 7 stale entries from 2026-05-23 that should have been archived
- `pinned: true` was found outside NOW during request 41 work without anyone noticing

Each is trivial individually. Together they erode trust in the corpus and make agent-driven flows brittle (an LLM reading `tasks/now/foo.md` should not have to second-guess whether the bucket field is the source of truth).

`octopus diagnose` already exists for runtime/index introspection. `lint` is the corpus-side equivalent: cheap to run, safe to share, and the natural hook target for pre-commit and CI.

## Scope

### In

- New verb `octopus lint` (read-only by default).
- Per-rule registry: each rule lives in its own module under `cli/src/octopus/lint/rules/`, declares `code`, `severity`, `auto_fixable`, and exposes `check()` + optional `fix()`.
- 8 starter rules (table below).
- `--fix` flag: applies only `auto_fixable: True` rules, shows a diff per file, prompts unless `--yes`.
- `--rule=<code>` flag: run a single rule.
- `--json` flag: emit findings as JSON for tooling.
- Scope flags: bare `octopus lint` audits **the cwd activity** (the activity containing the current directory); `octopus lint --all` audits all indexed activities; `octopus lint <activity>` audits one by token.
- Exit codes: 0 = clean, 1 = warnings only, 2 = errors present.
- Unit tests per rule (fixtures in `cli/tests/lint/fixtures/`).
- Spec sync: `.spectacular/specs/CLI-VERBS.md` + `skills/octopus/references/cli-verbs.md`.

### Out

- Multi-corpus / cross-activity reference lints (e.g. "this `blocked_by:` points to a slug in a different activity"). Add later if the pattern emerges.
- Activity-frontmatter and session-frontmatter linting. Tasks first; sessions/handoffs/memory in a follow-up.
- AI-actor enforcement of D100 (blocked → NEXT for non-human actors). Separate request.
- Pre-commit hook integration. The `--json` output is the seam; `git-guard` consumes it later.
- A TUI-level "lint banner." Once the CLI is stable, the TUI can surface findings.

## Rules (starter set)

| Code | Rule | Severity | Auto-fix |
|---|---|---|---|
| `slug-match` | `slug:` field equals filename stem | error | yes — rewrite `slug:` to match filename |
| `slug-shape` | slug is `^[a-z0-9-]+$`, no spaces, no quotes | error | no — surfaces to user, manual rename |
| `bucket-match` | `bucket:` field equals parent folder name | error | yes — rewrite `bucket:` to match folder |
| `corrupt-frontmatter` | YAML parses cleanly; no unknown legacy fields | error | no — surface raw parse error |
| `start-without-now` | `start_date` set but bucket ≠ `now` | warn | no (asks which side is truth) |
| `stale-done` | bucket = `done`, `end_date` >30d old | info | yes — move to `_archive/tasks-<YYYY-MM>/` |
| `bucket-blocked` | `issue: blocked\|waiting` in NOW/NEXT | **info** (per D100) | no — visibility only |
| `dangling-blocker` | `blocked_by:` references slug that doesn't exist in this activity | warn | no |

Each rule is a separate file. Adding a rule = one new file + one registry entry.

## Output

Default (human):

```
$ octopus lint
.octopus/tasks/backlog/clarify-n-sessions-output-in-reindex.md
  error  slug-match     slug "clarify-... fs-only per v1'" ≠ filename stem
                        → fixable with `octopus lint --fix`

.octopus/tasks/backlog/polish-error-messages-and-rich-output.md
  warn   start-without-now    start_date=2026-05-23 but bucket=backlog

.octopus/tasks/now/wire-up-detail-toggle-binding.md
  info   bucket-blocked       issue=blocked in NOW (allowed per D100)

3 findings across 19 tasks: 1 error, 1 warn, 1 info
```

JSON (`--json`):

```json
{
  "version": 1,
  "scanned": 19,
  "findings": [
    {
      "code": "slug-match",
      "severity": "error",
      "path": ".octopus/tasks/backlog/clarify-n-sessions-output-in-reindex.md",
      "message": "slug \"...\" does not match filename stem \"clarify-n-sessions-output-in-reindex\"",
      "auto_fixable": true,
      "fix_preview": {"slug": "clarify-n-sessions-output-in-reindex"}
    }
  ],
  "summary": {"error": 1, "warn": 1, "info": 1}
}
```

## Module layout

```
cli/src/octopus/lint/
├── __init__.py
├── runner.py            # orchestrates: load tasks, run rules, collect findings
├── findings.py          # Finding dataclass, Severity enum
├── registry.py          # rule registration + lookup
└── rules/
    ├── __init__.py
    ├── slug_match.py
    ├── slug_shape.py
    ├── bucket_match.py
    ├── corrupt_frontmatter.py
    ├── start_without_now.py
    ├── stale_done.py
    ├── bucket_blocked.py
    └── dangling_blocker.py

cli/tests/lint/
├── conftest.py
├── fixtures/
│   ├── corrupt-slug.md
│   ├── bucket-mismatch.md
│   ├── ...
└── test_<rule>.py       # one test file per rule
```

## CLI surface

```
octopus lint                         # audit cwd activity, human output
octopus lint --all                   # audit every indexed activity
octopus lint <activity-token>        # audit one activity
octopus lint --rule=slug-match       # run one rule only
octopus lint --fix                   # apply auto-fixable findings (prompts per file)
octopus lint --fix --yes             # apply without prompting
octopus lint --json                  # JSON output (no fix)
octopus lint --severity=error        # filter output by min severity
```

Exit codes:
- `0` — clean.
- `1` — only warnings or info (no errors).
- `2` — at least one error.

`--fix` exit code reflects state **after** fixes are applied.

## Method

1. Land D100 in `DECISIONS.md` (✓ done).
2. Write this PLAN.md (✓ done).
3. Generate `TASKS.md` for this request.
4. Implement module layout + registry + 1 rule (`slug-match`) end-to-end as the spine. Test.
5. Add remaining 7 rules one at a time, each with tests.
6. Wire `octopus lint` as a top-level command in `cli.py`.
7. Add `--fix` driver (uses `write_task` + frontmatter rewrite per rule; respects `--yes`).
8. Add `--json` output adapter.
9. Run `octopus lint --all` against the live `.octopus/` corpus. Verify the 2 known-corrupt slugs (already fixed) and the `start-without-now` finding on `polish-error-messages-and-rich-output` are detected.
10. Sync `.spectacular/specs/CLI-VERBS.md` + `skills/octopus/references/cli-verbs.md`.
11. Append rule list to `.spectacular/specs/CRITICAL-DEPENDENCIES.md` (so future schema changes update lint rules).
12. Mark this request `status: done`, bump `DECISIONS.md` if any sub-decision needed locking.

## Risks

- **Auto-fix correctness.** `--fix` rewrites task files. Each rule's `fix()` must be idempotent and must produce a diff before writing. Mitigation: always show diff + always prompt (unless `--yes`); never fix multiple rules in one pass without re-validating.
- **Slug-rename cascade.** `slug-match` auto-fix rewrites the `slug:` field but does **not** move the file or update cross-refs. That's intentional — file moves are the existing `set --slug` cascade's job. The lint fix is "make the field match the file" not "make the file match the field." Document this clearly in the rule's message.
- **Performance on large corpora.** With 100+ activities × 100+ tasks each, naive per-file load is fine (we're not querying the index). Defer optimization until it matters.
- **D100 ambiguity.** `bucket-blocked` emits `info`, not `warn`. This is the codification of D100 — if D100 ever flips for AI actors (separate request), this severity goes up to `warn` with an `--actor=ai` gate.

## Deliverables

- `cli/src/octopus/lint/` module (runner, registry, 8 rules)
- `octopus lint` verb in `cli.py`
- `cli/tests/lint/` test suite (≥1 test per rule)
- Updated `.spectacular/specs/CLI-VERBS.md` with `lint` entry
- Updated `skills/octopus/references/cli-verbs.md` mirror
- `.spectacular/requests/42-lint-command/TASKS.md` (created on activation)
- CHANGELOG entry under `[Unreleased]`

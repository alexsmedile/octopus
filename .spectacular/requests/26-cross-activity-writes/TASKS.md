---
request: 26-cross-activity-writes
status: done
updated: 2026-05-24
---

# Tasks — 26-cross-activity-writes

## Group 1 — Lock decisions ✅
- [x] D84 — One-target-axis-per-invocation rule for `set` (mutex + activity-level allowed flags)
- [x] D85 — `add task` / `add activity` semantics
- [x] D86 — `--activity` flag on all write verbs

## Group 2 — `add` Typer sub-app ✅
- [x] `octopus add task "<title>" [--activity <id>] [...]` — full capture flag matrix
- [x] `octopus add activity "<name>" [--type --area --path --id --storage]`
- [x] `add activity --priority` stub-rejects with pointer to #27
- [x] Refactor `capture` to share `_create_task_impl` helper with `add task`
- [x] `--activity` flag added to `capture` itself (D86)

## Group 3 — `set` multi-target refactor ✅
- [x] Variadic positional `slugs: list[str]`
- [x] `--task` / `--activity` list options (repeated + comma-form)
- [x] One-target-axis mutex enforcement (4 rejection branches)
- [x] Activity-level set path with allowed-flag filter
- [x] Task-only flags rejected on `--activity` with offending flag named
- [x] Activity-only flags rejected on task-mode invocations

## Group 4 — `--activity` propagation on other write verbs ✅
- [x] `_load_task` and `_move_bucket` accept optional `activity_token`
- [x] `plan` / `focus` / `park` / `defer`
- [x] `start` / `finish` / `end` / `drop`
- [x] `pin` / `unpin`
- [x] `archive` / `restore`
- [x] `block` / `wait` / `unblock`
- [x] `move` / `mv`
- [x] `promote`

## Group 5 — Tests ✅ (23 new, 531 total)
- [x] `add task` happy paths: with activity, without activity, unknown activity error
- [x] `add task` flag propagation (--now, --priority)
- [x] `add activity` happy paths: default path, --path, nested rejection
- [x] `add activity --priority` stub-rejection
- [x] `set` mutex rules: 4 rejection cases (positional+task, positional+activity, task+activity, no-target, multi-positional)
- [x] `set --activity` rejects task-only flags
- [x] `set` task-mode rejects activity-only flags
- [x] `set --task` multi-target with cwd-resolution
- [x] `set --task` partial-fail (unknown slug exits non-zero, valid one still updated)
- [x] `set` positional outside activity errors clearly
- [x] `set --activity` multi-target status edit from outside both activities
- [x] `set --activity --priority` stub-rejection
- [x] `--activity` flag works on pin, finish, plan (sample of D86 verbs)

## Group 6 — Spec + skill doc sync ✅
- [x] `.spectacular/specs/CLI-VERBS.md` — capture / add / set / `--activity` flag sections
- [x] `skills/octopus/references/cli-verbs.md` — capture / add / set / cross-activity section
- [x] DECISIONS.md D84/D85/D86 appended

## Group 7 — Ship ✅
- [x] CHANGELOG [0.8.0] entry
- [x] `cli/pyproject.toml` 0.7.0 → 0.8.0
- [x] PLAN/TASKS status: queued → done
- [ ] Tag v0.8.0 (manual, next step)

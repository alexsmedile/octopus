---
request: 27-cross-activity-reads-and-dashboards
status: done
updated: 2026-05-24
---

# Tasks — 27-cross-activity-reads-and-dashboards

## Group 1 — Lock decisions ✅
- [x] D87 — Activity priority field (strict enum, same set as task priority)
- [x] D88 — Schema v3 → v4 migration: priority + last_touched_at columns
- [x] D89 — Ranking heuristic R1 (locked weights; configurable deferred)
- [x] D90 — Dashboard / read-verb output conventions (`--json` flag pair, noun-explicit verbs)

## Group 2 — Schema v3 → v4 ✅
- [x] `db/connection.py` bumps SCHEMA_VERSION to 4 + idempotent migration
- [x] `db/schema.sql` adds `priority TEXT` and `last_touched_at DATETIME` columns
- [x] `idx_activities_priority` and `idx_activities_last_touch` indexes
- [x] `upsert_activity(touch=True)` flag — sets last_touched_at to now
- [x] `sync_activity_after_write` and `sync_task_after_write` pass `touch=True`
- [x] Test version assertions bumped to v4 (test_db_upsert, test_adapters)

## Group 3 — Activity priority field ✅
- [x] `Activity` dataclass adds `priority: str | None = None`
- [x] `Activity.validate()` enforces strict enum
- [x] `read_activity` / `write_activity` preserve the field (ACTIVITY_FIELDS)
- [x] `init_activity()` accepts `priority` kwarg with validation
- [x] `add activity --priority X` unblocked (was D85 stub-reject)
- [x] `set --activity --priority X` unblocked (was D85 stub-reject)
- [x] Tests covering both write paths + explicit-default clearing

## Group 4 — Ranking module (R1) ✅
- [x] `core/ranking.py` with `score_task()` + `ScoreBreakdown`
- [x] 21 unit tests in `test_ranking.py` covering each weight contribution
- [x] Exclusion of archived / done / dropped tasks
- [x] Tiebreak by activity `last_touched_at` ascending

## Group 5 — list filter flags + noun-explicit ✅
- [x] `db/queries.list_activities` rewritten with multi-value filters
- [x] `--priority`, `--type`, `--area`, `--has-pinned`, `--has-overdue`, `--has-now`, `--touched-within`, `--include-archived`
- [x] Sort: activity priority → last_touched_at desc → title
- [x] `octopus list tasks [<path-or-id>]` subcommand (path-or-id auto-detect)
- [x] `octopus list activities [filters]` subcommand
- [x] Bare `list` stays context-aware (tasks inside / activities outside)
- [x] Comma-form for multi-value filters

## Group 6 — Rich status + get activity ✅
- [x] `octopus status <path-or-id>` extended with priority chip, last-reviewed, last-touched, now/pinned/overdue previews
- [x] `--limit N` controls preview row count
- [x] `octopus get activity <path-or-id>` (Typer sub-app for future `get task`)
- [x] TTY-aware JSON formatting (pretty | compact)
- [x] `--format` override

## Group 7 — Dashboard / next / impact ✅
- [x] `octopus dashboard` composite view (pinned, overdue, now, blocked, priorities)
- [x] `--json` flag (stdout) + `--json-out <path>` (file)
- [x] `octopus next [--limit N]` (default 3) — ranked top N
- [x] `octopus impact [--limit N] [--show-score]` (default top 20)
- [x] Both `next` and `impact` support `--json` / `--json-out`
- [x] Ranking uses R1 from `core/ranking.py`
- [x] Hides archived activities by default (D83)

## Group 8 — Tests ✅ (44 new total: 21 ranking + 23 reads)
- [x] `test_ranking.py` — 21 unit tests for R1 heuristic
- [x] `test_cross_activity_reads.py` — 23 integration tests
- [x] Both `add activity --priority` and `set --activity --priority` happy paths
- [x] Ranking order verification via `--json` parsing

## Group 9 — Spec + skill docs ✅
- [x] `SCHEMA-ACTIVITY.md` adds priority field (Classification section)
- [x] `skills/octopus/references/schemas/activity.md` mirror updated
- [x] `.spectacular/specs/CLI-VERBS.md` adds "Cross-activity reads & dashboards" section
- [x] `skills/octopus/references/cli-verbs.md` adds dashboards + R1 table

## Group 10 — Ship ✅
- [x] CHANGELOG [0.9.0] entry
- [x] `cli/pyproject.toml` 0.8.0 → 0.9.0
- [x] PLAN/TASKS status: queued → done
- [ ] Tag v0.9.0 (manual, next step)

## Out of scope (deferred)

- Session / memory writes don't touch `last_touched_at` (task writes only). Add later if dashboards need finer signal.
- Configurable ranking weights — algorithm fixed for v1 per D89.
- `get task <slug>` — verb shape is reserved (noun-explicit) but not implemented.
- Sub-activity recursion in `list tasks` — nested activities show up in `list activities`, not in the parent's task list.

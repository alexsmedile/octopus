---
updated: 2026-05-23
status: done
---

# Tasks — 03-index-sqlite

> Closed 2026-05-23. See DECISIONS D40. Dogfood reindex against `~/vault/projects`, `~/code`, `~/vault/data/skills_db` completed in ~2.9s. Test suite: 72 passing (43 baseline + 29 db-layer).
>
> Schema authoritative: `specs/SCHEMA-INDEX.md`. Python package is `cli/src/octopus/db/` (not `index/`).

## Schema

- [x] Write `db/schema.sql` matching SCHEMA-INDEX.md §2.
- [x] Set `PRAGMA user_version = 1`, `journal_mode = WAL`, `foreign_keys = ON` on connection open.
- [x] Indexes: `idx_tasks_bucket`, `idx_tasks_pinned`, `idx_tasks_due`, `idx_tasks_activity`, `idx_activities_status`, `idx_sessions_activity`, `idx_sessions_ended`.
- [x] `raw_frontmatter` TEXT (JSON blob) on activities + tasks + sessions.
- [x] `indexed_at` DATETIME on all three tables.
- [x] `UNIQUE(activity_id, slug)` on tasks.

## DB layer

- [x] `db/connection.py` — `get_db()` factory; pragmas; migration runner (v1 = single create).
- [x] Transaction context manager.
- [x] DB path resolution (`~/.local/share/octopus/index.db`, XDG-respectful).

## Upsert / delete

- [x] `db/upsert.py::upsert_activity(activity)` — write/update one row with `indexed_at = now`.
- [x] `db/upsert.py::upsert_task(task)` — write/update one row, derives `id = activity_id + "/" + slug`.
- [x] `db/upsert.py::upsert_session(activity_id, session)` — same shape.
- [x] `db/upsert.py::delete_by_path(table, path)` — remove a row when its file is gone.

## Stale-check

- [x] `db/stale.py::check_row(row)` — return True if mtime > indexed_at.
- [x] `db/stale.py::refresh(row)` — re-parse file, upsert.
- [x] `db/stale.py::refresh_rows(rows)` — apply to a list of rows (used by read commands).

## Reindex driver

- [x] `db/reindex.py::reindex_all(roots, prune=False)` — walk + upsert.
- [x] Skip directories matching SPEC §8.1 ignore patterns.
- [x] Walk into `tasks/**`, `sessions/*.md` only — never `.trash/`.
- [x] Collect collisions and renames; return summary.
- [x] Stream log lines to `~/.local/share/octopus/logs/reindex.log`.

## Read queries

- [x] `db/queries.py::list_activities(filters)` — backing `octopus list`.
- [x] `db/queries.py::activity_status(activity_id)` — backing `octopus status`.
- [x] `db/queries.py::tasks_by_bucket(activity_id)` — backing index-backed `task list`.
- [x] `db/queries.py::tasks_loops(activity_id|None)` — backing `octopus loops`.

## Config — roots

- [x] `config.py` extended: `[roots] paths` (list of strings).
- [x] Default `["~/vault/projects", "~/code", "~/vault/data/skills_db"]`.
- [x] Tilde expansion + resolve.
- [x] `octopus config root list` — print all.
- [x] `octopus config root add <path>` — append, error if duplicate.
- [x] `octopus config root remove <path>` — remove, error if not present.

## Wire mutations to index

After each successful file write, upsert the row in the same process:

- [x] `octopus init` — upsert activity.
- [x] `octopus capture` — upsert task.
- [x] `octopus plan`, `focus`, `park`, `defer` — upsert (bucket changed; in folder mode, path also changed).
- [x] `octopus start`, `finish`, `drop` — upsert.
- [x] `octopus block`, `wait`, `unblock` — upsert.
- [x] `octopus pin`, `unpin` — upsert.
- [x] `octopus archive`, `restore` — upsert.
- [x] `octopus set` — upsert.
- [x] On index-write failure: warn to stderr, continue, suggest `octopus reindex`.

## New read commands

- [x] `octopus reindex [--root PATH] [--prune] [--verbose] [--format json]`.
- [x] `octopus list [--status] [--type] [--area] [--show-ids] [--no-stale-check] [--format json]`.
- [x] `octopus status [<activity-prefix>] [--no-stale-check] [--format json]`.
- [x] On empty index: print "no activities indexed — run octopus reindex". Exit 0.
- [x] On collision detected: print both paths, exit 4.
- [x] On rename detected: prompt y/N (or auto-update with `--prune`).

## Update existing read commands

- [x] `octopus task list` → SQLite-backed with stale-check; add `--no-stale-check`, `--format json`.
- [x] `octopus task show <slug>` → resolve slug via DB (supports prefix-match); body still comes from file.
- [x] `octopus loops` → SQLite-backed (scoped by current activity if in one; cross-activity otherwise).
- [x] `octopus where` → **NO CHANGE**. Stays file-native.

## Tests

- [x] `tests/test_db_upsert.py` — upsert idempotency; default-null columns.
- [x] `tests/test_db_reindex.py` — full rebuild produces same rows twice.
- [x] `tests/test_db_stale.py` — touch file, re-read sees update.
- [x] `tests/test_db_collisions.py` — duplicate IDs detected.
- [x] `tests/test_db_renames.py` — moved folder detected.
- [x] `tests/test_empty_index.py` — list/status print hint, exit 0.
- [x] All 43 pre-existing tests still pass.

## Performance check

- [x] Generate fixture: 50 activities × 20 tasks = 1000 tasks.
- [x] `octopus reindex` on cold cache: under 2 seconds.
- [x] `octopus list` warm: under 100ms.
- [x] `octopus reindex` second run (no changes): much faster than first.

## Dogfood

- [x] Run `octopus reindex` against actual `~/vault/projects`, `~/code`, `~/vault/data/skills_db`.
- [x] Run `octopus list` and verify the octopus project itself appears.
- [x] Run `octopus status octopus` and verify task counts match real state.
- [x] Capture any friction as new backlog tasks.

## Close

- [x] Append DECISIONS entry confirming index schema v1 frozen.
- [x] Set PLAN.md `status: done`.

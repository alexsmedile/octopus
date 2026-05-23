---
status: done
priority: high
owner: alex
updated: 2026-05-23
summary: "SQLite index — reindex, stale-check-on-read, cross-activity views (list, status, loops with index)."
related:
  - 02-cli-walking-skeleton
  - 05-tui
gates:
  - 02-cli-walking-skeleton
closed: 2026-05-23
closes_decision: D40
---

# SQLite index

## Goal

Build the derived SQLite index at `~/.local/share/octopus/index.db` so cross-activity queries are fast. Add `octopus list`, `octopus status`, `octopus reindex`, `octopus config root *`. Migrate existing read commands to index-backed reads with stale-check.

The authoritative schema is `specs/SCHEMA-INDEX.md`. This request implements it.

## Why

The walking skeleton (request 02, now closed) walks the filesystem on every call. That's fine for single-activity ops but useless for "what's on my plate across all my projects?". The index unlocks `octopus list`, `octopus status`, the TUI (request 05), and every future viewer / adapter.

## Approach

- SQLite via stdlib `sqlite3`.
- Schema per `SCHEMA-INDEX.md` — three tables (`activities`, `tasks`, `sessions`).
- Python package layout: `cli/src/octopus/db/` (NOT `index/` — collides with builtin attribute `list.index`).
- Two sync paths:
  1. **CLI-incremental**: every mutation verb (`capture`, `plan`, `focus`, `park`, `defer`, `start`, `finish`, `drop`, `block`, `wait`, `unblock`, `pin`, `unpin`, `archive`, `restore`, `set`) upserts after the file write, in-process.
  2. **Stale-check-on-read**: read commands compare row `indexed_at` against file `mtime`; stale rows re-parse inline. `--no-stale-check` opts out.
- `octopus reindex` is the full rebuild — walks configured roots, prunes deleted rows, detects collisions and renames.
- `octopus where` stays file-native (deliberate exception; resilience over consistency).
- `reindex` populates the `sessions` table even though no v1 verb reads it (schema exercised; request 04 doesn't need a re-reindex).

## Commands in scope

```
octopus reindex [--root PATH] [--prune] [--verbose] [--format json]
octopus list [--status STATUS] [--type TYPE] [--area AREA] [--show-ids] [--no-stale-check] [--format json]
octopus status [<activity-prefix>] [--no-stale-check] [--format json]
octopus config root list
octopus config root add <path>
octopus config root remove <path>
```

Plus `--format json` and `--no-stale-check` flags added to existing read commands per CLI-VERBS.md "Read-command flags".

## Out of scope

- File watcher (`octopus watch`) — request 12.
- Session/memory/handoff verbs (request 04). The session **schema** lives here; the **verbs** don't.
- Full-text search of memory — v2 (FTS5).
- Updating `octopus where` to use the index — explicit non-goal (it stays file-native).

## Deliverables

- `cli/src/octopus/db/__init__.py`
- `cli/src/octopus/db/schema.sql` — DDL matching SCHEMA-INDEX.md
- `cli/src/octopus/db/connection.py` — `get_db()` factory; pragmas; migration runner (single migration in v1)
- `cli/src/octopus/db/upsert.py` — `upsert_activity`, `upsert_task`, `upsert_session`, `delete_path`
- `cli/src/octopus/db/queries.py` — read-shaped queries (`list_activities`, `get_activity_status`, `filter_tasks`, `count_by_bucket`)
- `cli/src/octopus/db/stale.py` — mtime comparison + targeted re-parse
- `cli/src/octopus/db/reindex.py` — full rebuild driver
- `cli/src/octopus/cli.py` — wire all mutation verbs to upsert; wire read commands to query + stale-check; add `list`, `status`, `reindex`, `config root *`.
- `cli/src/octopus/config.py` — extended with `[roots]` reading/writing.
- Tests: `tests/test_db_upsert.py`, `tests/test_db_stale.py`, `tests/test_db_reindex.py`, `tests/test_db_collisions.py`.

## Acceptance criteria

- `octopus reindex` from an empty DB populates all activities + tasks + sessions across configured roots.
- After `octopus capture`, the row appears in the DB without `reindex` being run.
- After a hand-edit in `$EDITOR`, the next `octopus task show <slug>` reflects the edit (stale-check works).
- `octopus list` lists all indexed activities with task counts per bucket; sub-second response.
- `octopus list` on empty index prints the hint, not blank output.
- `--no-stale-check` returns pure SQLite reads.
- `octopus reindex --prune` removes rows whose source files no longer exist.
- ID collision detection: `reindex` surfaces duplicate IDs with both paths and exits 4.
- Rename detection: if file's `last_known_path` differs from current path, `reindex` prompts (or with `--prune` auto-updates).
- All 43 existing tests still pass (no regression on file-ops layer).
- New tests cover upsert idempotency, stale-check, reindex idempotency, collisions, renames.

## Resolved (formerly open) questions

- **Migration strategy when schema changes** → set `PRAGMA user_version = 1` at creation; v2 schema bumps to 2 and ships a migration runner; v1→v2 is "drop and rebuild" in practice.
- **DB location** → `~/.local/share/octopus/index.db` (system-wide). See SCHEMA-INDEX.md §1.
- **WAL mode** → yes. `PRAGMA journal_mode=WAL` on every connection.
- **Python module name** → `db/` (not `index/` — avoids builtin attribute collision).
- **`registry.json` (legacy concept)** → dropped. `index.db` is the sole derived store.
- **`octopus where` index-backed?** → no; stays file-native.
- **Sessions table populated in v1?** → yes, by `reindex`. No verb reads it until request 04.
- **Empty-index UX?** → hint message, exit 0.

## Specs to reference

- `specs/SCHEMA-INDEX.md` — the authoritative SQLite schema.
- `specs/CLI-VERBS.md` — verb behaviors + `--format json` / `--no-stale-check` scope.
- `specs/CRITICAL-DEPENDENCIES.md` rules P and Q — index consistency + reindex semantics.
- `PRD.md §8` — architectural summary (points at SCHEMA-INDEX.md).

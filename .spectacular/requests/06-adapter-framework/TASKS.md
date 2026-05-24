---
request: 06-adapter-framework
status: active
updated: 2026-05-24
---

# Tasks — 06-adapter-framework

Top-to-bottom; commit per group (or small cluster) so the migration is reviewable.

---

## Group 1 — Lock decisions in DECISIONS.md ✅

- [x] D56 Capability enum: `{PULL, PUSH, NOTIFY, RECONCILE}` atomic verbs only
- [x] D57 Adapter protocol: `status / validate_config / list_groups / peek / pull / push / search`; `link()` removed
- [x] D58 Hybrid config layout: enable in main config, content in `bridges/<name>.toml`
- [x] D59 Multi-list config + flag matrix (`lists=[]` + `--list` + `--capture-all`); per-adapter flag names
- [x] D60 `peek` vs `pull`: peek is read-only display, pull creates files; peek-no-group → discovery
- [x] D61 `octopus bridge search` dedicated verb; fallback peek+filter; no new capability flag
- [x] D62 Stub adapters ship in #06; #07/#09/#21 replace stub bodies
- [x] D63 Pipeline + dedup via `task_external_refs`; schema v2→v3 migration with backfill
- [x] D64 Adapter registry: hardcoded + entry-points overlay; built-in wins on conflict
- [x] D65 Sync journal v1: minimal JSON per adapter (`last_pull/last_push/counts/cursor`)
- [x] D66 Repo layout (flat modules) + exit codes (PRD §5, no new codes); `octopus link` deferred to #07
- Note: NOTIFY/RECONCILE flag-only status documented in D56; pipeline defaults in D63.

## Group 2 — Spec docs

- [ ] `.spectacular/specs/SCHEMA-ADAPTER.md` — new spec file
  - Capability enum
  - Adapter protocol (every method)
  - Data types (`ExternalTask`, `PullResult`, `PushResult`, `AdapterStatus`, `ExternalRef`)
  - Config layout (hybrid: main + per-adapter)
  - `lists` field semantics
  - Registry mechanism
- [ ] `CLI-VERBS.md` — document `octopus bridge {list|enable|disable|status|peek|pull|search}`
  - Per-adapter flag conventions
  - `--list` + `--capture-all` matrix
  - Exit codes
- [ ] `CRITICAL-DEPENDENCIES.md` — new section U for adapter framework
  - validate_config rejection rules
  - Multi-list / capture-all mutual exclusion
  - Pipeline materialization invariants (always sets imported_from/import_date)
  - Dedup invariant (no double-creation on re-pull)
- [ ] `SCHEMA-CONFIG.md` — split adapter config: `enabled` in main, content in bridges/
  - Replaces current `[adapters.obsidian] vault = ...` pattern
  - Documents `lists = []` field
- [ ] `SCHEMA-INDEX.md` — document `task_external_refs` table
- [ ] `PRD.md` §7.1 — sync with new protocol (drop `link()`, add `peek/search/list_groups`)

## Group 3 — Skill mirror

- [ ] `skills/octopus/references/adapter-framework.md` — new file
  - One-paragraph summary of what an adapter does
  - The five-ish useful commands
  - `peek` vs `pull` distinction
  - Per-adapter flag naming convention
- [ ] `skills/octopus/references/cli-verbs.md` — mirror `bridge` verbs
- [ ] `skills/octopus/references/critical-dependencies.md` — mirror new rules (X8-Xn)
- [ ] `skills/octopus/SKILL.md` — add "Bridges (adapters)" section explaining the seam
  - Verb index update — add "Bridges" group
  - When to use peek vs pull
  - How adapter pull integrates with the existing capture/backlog flow

## Group 4 — Code: protocol + data types

- [ ] `cli/src/octopus/adapters/base.py`
  - `Capability` enum
  - `Adapter` Protocol
  - `ExternalRef = str`
  - `ExternalTask`, `PullResult`, `PushResult`, `AdapterStatus` dataclasses
- [ ] `cli/src/octopus/adapters/__init__.py` — exports

## Group 5 — Code: registry + journal

- [ ] `cli/src/octopus/adapters/registry.py`
  - Built-in REGISTRY dict
  - `load_registry()` with entry-point overlay
  - Built-in-wins conflict resolution
- [ ] `cli/src/octopus/adapters/journal.py`
  - JSON read/write at `~/.local/share/octopus/sync/<name>.json`
  - `read_journal(name)`, `update_journal(name, **changes)`
  - Auto-create on first write

## Group 6 — Code: dedup index (schema v3)

- [ ] `cli/src/octopus/db/schema.sql` — add `task_external_refs` table + index
- [ ] `cli/src/octopus/db/connection.py` — v2 → v3 migration
  - CREATE TABLE + populate from existing tasks (scan `external_refs` column)
- [ ] `cli/src/octopus/db/upsert.py`
  - `upsert_task` also writes `task_external_refs` rows
  - On UPDATE: delete + re-insert refs for that task
- [ ] `cli/src/octopus/db/queries.py`
  - `find_by_external_ref(adapter, external_id)` helper

## Group 7 — Code: config layer

- [ ] `cli/src/octopus/config.py`
  - `load_adapter_config(name) -> dict` — reads `bridges/<name>.toml`
  - `write_adapter_config(name, data: dict) -> None` — hand-rolled TOML writer
  - `set_adapter_enabled(name, enabled: bool)` — flips main `config.toml`
  - `is_adapter_enabled(name) -> bool`
  - `list_enabled_adapters() -> list[str]`
- [ ] Default `lists = []` for adapters that support multi-list

## Group 8 — Code: pipeline

- [ ] `cli/src/octopus/adapters/pipeline.py`
  - `materialize_pull_result(activity_root, adapter_name, result: PullResult)` — creates Octopus tasks from `ExternalTask` items
  - Dedup via `task_external_refs`
  - Sets `imported_from`, `import_date`, `actor=human`, `external_refs.<name>`
  - Returns `(new_count, skipped_count, error_count)`
- [ ] Resolve target activity (config `default_activity` → cwd → exit 2)
- [ ] Resolve groups (`--list` / `--capture-all` / config `lists` / discovery)

## Group 9 — Code: CLI verbs

- [ ] `cli/src/octopus/cli.py`
  - `octopus bridge list` — table of registered adapters
  - `octopus bridge enable <name> [adapter-flags]` — dispatches to adapter sub-app
  - `octopus bridge disable <name>` — flips flag, keeps config
  - `octopus bridge status [<name>]` — health check
  - `octopus bridge peek <name> [--list / --capture-all]` — read-only
  - `octopus bridge pull <name> [--list / --capture-all]` — import
  - `octopus bridge search <name> <query> [--list / --capture-all]` — adapter-side search
  - Hidden alias `octopus adapter` → `octopus bridge`
- [ ] Verbose mode (`-v`) for traceback on adapter exceptions
- [ ] Output discipline: summary line + per-task lines on success; clear error on failure

## Group 10 — Code: stub adapters

- [ ] `cli/src/octopus/adapters/obsidian.py`
  - `name = "obsidian"`, `capabilities = {PULL}`
  - All methods return clear NotImplementedError result pointing to #07
- [ ] `cli/src/octopus/adapters/reminders.py`
  - Same pattern; points to #09
- [ ] `cli/src/octopus/adapters/todo_md.py`
  - Same pattern; points to #21
- [ ] Each registered in `REGISTRY` dict

## Group 11 — Tests

- [ ] `cli/tests/test_adapters_base.py`
  - Capability enum has exactly four values
  - Dataclass defaults work
- [ ] `cli/tests/test_adapters_registry.py`
  - Built-in registry populated
  - Entry-point overlay merges
  - Built-in wins on name conflict
  - Broken entry-point doesn't kill loading
- [ ] `cli/tests/test_adapters_journal.py`
  - Read missing journal returns sane defaults
  - Write creates file with XDG path
  - Update merges; counters increment
- [ ] `cli/tests/test_adapters_pipeline.py`
  - Mock adapter returns N items; pipeline creates N tasks
  - Second run with same items → all skipped (dedup)
  - Mixed batch (some new, some known) → counts split correctly
  - `imported_from`, `import_date`, `external_refs` all set correctly
- [ ] `cli/tests/test_cli_bridge.py`
  - `bridge list` shows registered adapters
  - `bridge enable` writes both main config + bridges file
  - `bridge disable` flips flag, keeps config
  - `bridge status` per-name + all
  - `bridge peek` no-group discovery message
  - `bridge pull` no-list error
  - `bridge pull --list X --capture-all` mutual-exclusion error
  - Stub adapter pull returns honest error
- [ ] `cli/tests/test_db_external_refs.py`
  - Schema v3 migration creates table on existing v2 DB
  - upsert_task populates refs
  - find_by_external_ref returns correct task_id
  - delete cascade works

## Group 12 — Smoke test

- [ ] Manual end-to-end against /tmp fixture:
  - `octopus init`
  - `octopus bridge list` (shows 3 stubs)
  - `octopus bridge enable reminders --list "Test"` (stub: should still write config)
  - `octopus bridge status reminders` (reports honest "not implemented")
  - `octopus bridge pull reminders` (reports NotImplementedError clearly)
  - Verify `bridges/reminders.toml` written, `[adapters.reminders] enabled = true` in main config

## Group 13 — Ship

- [ ] Update CHANGELOG.md with 0.4.0 entry (minor — new framework, new commands, new schema)
- [ ] Bump `cli/pyproject.toml` 0.3.0 → 0.4.0
- [ ] Update README.md status line
- [ ] `/update-docs` workflow
- [ ] Tag v0.4.0

---

## Suggested shipment split

- **v0.4.0-alpha:** Groups 1–3 (decisions + schema docs + skill mirror) — contract published
- **v0.4.0-beta:** Groups 4–8 (base + registry + journal + dedup + config + pipeline) — framework callable
- **v0.4.0:** Groups 9–13 (CLI + stubs + tests + ship) — full release

Or one big v0.4.0 ship. Decide before starting Group 4.

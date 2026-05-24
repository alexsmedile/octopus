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

## Group 2 — Spec docs ✅

- [x] `.spectacular/specs/SCHEMA-ADAPTER.md` — new spec file (10 sections, ~330 lines)
  - Capability enum, full protocol, data types, config layout, registry, sync journal, pipeline, stub shape, repo layout
- [x] `CLI-VERBS.md` — new "Bridge verbs" section: `list/enable/disable/status/peek/pull/search`, flag matrix, per-adapter naming, exit codes
- [x] `CRITICAL-DEPENDENCIES.md` — new section U: config rules, capability gating, flag matrix, pipeline invariants, dedup index rules, sync journal, registry
- [x] `SCHEMA-CONFIG.md` — hybrid layout: main config has `enabled` only; new §2b for `bridges/<name>.toml` content + `lists` field
- [x] `SCHEMA-INDEX.md` — `task_external_refs` table + indexes for `kind` and `promoted_to` (carry-over from D46/D48); user_version = 3
- [ ] `PRD.md` §7.1 sync — deferred to ship phase (Group 13)

## Group 3 — Skill mirror ✅

- [x] `skills/octopus/references/adapter-framework.md` — new file (~180 lines)
  - Plain-English explanation
  - All seven commands with examples
  - `peek` vs `pull` distinction (incl. peek-discovery mode)
  - Group selection (config + flags), per-adapter flag naming
  - Pull pipeline behavior (provenance + dedup)
  - Exit codes, when-to-use heuristics, adapter status reference
- [x] `skills/octopus/references/cli-verbs.md` — new "Bridges (adapters)" section: full command reference + flag matrix + capability gating + hidden alias
- [x] `skills/octopus/references/critical-dependencies.md` — new rule X7a covering config, capability gating, flag matrix, pipeline, dedup, journal, registry
- [x] `skills/octopus/SKILL.md`:
  - Verb index — "Bridges" group added
  - Load-on-demand row for `adapter-framework.md`
  - "Bridges (v1 scope)" section rewritten — peek vs pull, three v1 adapters, Claude plugin as client not adapter
  - Version bump 0.3.0 → 0.4.0

## Group 4 — Code: protocol + data types ✅

- [x] `adapters/base.py` — `Capability` enum, `Adapter` Protocol, all dataclasses
- [x] `adapters/__init__.py` — public exports

## Group 5 — Code: registry + journal ✅

- [x] `adapters/registry.py` — hardcoded builtins + entry-point overlay; built-in wins on conflict
- [x] `adapters/journal.py` — JSON r/w at `~/.local/share/octopus/sync/<name>.json`; `read_journal`, `update_journal`, sentinel cursor handling

## Group 6 — Code: dedup index (schema v3) ✅

- [x] `db/schema.sql` — `task_external_refs` table + `idx_task_external_refs_task`
- [x] `db/connection.py` — `SCHEMA_VERSION = 3`; forward-chained v1→v2→v3 migrator with `_backfill_external_refs()`
- [x] `db/upsert.py` — `upsert_task` clears + repopulates `task_external_refs` from frontmatter
- [x] `db/queries.py` — `find_by_external_ref(adapter, external_id)` helper

## Group 7 — Code: config layer ✅

- [x] `config.py` adapter helpers: `bridges_dir`, `adapter_config_path`, `load_adapter_config`, `write_adapter_config`
- [x] `is_adapter_enabled`, `set_adapter_enabled`, `list_enabled_adapters`, `list_all_configured_adapters`
- [x] `_write_full_system_config` extends the canonical writer with `[adapters.*]` sections
- [x] Hand-rolled TOML writer for bridges files (supports str/int/bool/list)

## Group 8 — Code: pipeline ✅

- [x] `adapters/pipeline.py`
  - `materialize_pull_result()` — creates Octopus tasks from `ExternalTask` items via `actions.capture_task`, then merges provenance/classification fields
  - Dedup via `find_by_external_ref` (task_external_refs)
  - Sets `actor=human`, `imported_from`, `import_date`, `kind` (if suggested), `tags` (if suggested), `external_refs.<adapter>`
  - Returns `MaterializeResult` (new_slugs, skipped, errors, source_groups)
- [x] `resolve_target_activity` — `default_activity` → cwd → `PipelineError(exit_code=2)`
- [x] `resolve_groups` — full D59 flag matrix; mutual-exclusion (exit 1); pull/search no-config no-flag (exit 3); peek discovery (returns None)
- [x] `update_journal` called after every pull (last_pull, pull_count, cursor)

## Group 9 — Code: CLI verbs ✅

- [x] `octopus bridge list [-v]` — compact table by default; verbose per-adapter blocks
- [x] `octopus bridge enable <name> [--set k=v ...] [--force]` — validates first (unless --force), writes both main config + bridges/<name>.toml
- [x] `octopus bridge disable <name>` — flips flag, keeps bridges file (preserves settings)
- [x] `octopus bridge status [<name>] [-v]` — health check; all bridges if no name
- [x] `octopus bridge peek <name> [--list / --capture-all]` — discovery when no group + no flag
- [x] `octopus bridge pull <name> [--list / --capture-all]` — materializes via pipeline
- [x] `octopus bridge search <name> <query> [--list / --capture-all]` — adapter-side search
- [x] Hidden alias `octopus adapter` → `octopus bridge` via duplicate `app.add_typer(..., hidden=True)`
- [x] `--set` parser: `lists`/`*_list` keys always coerced to lists; comma → list; true/false → bool; digits → int
- [x] Adapter exception → exit 4 with message; stub errors (in PullResult.errors with no tasks) → exit 4
- [x] Output discipline: "pulled N new · M already-known · K errors" + per-task lines on success

## Group 10 — Code: stub adapters ✅ (landed alongside Group 5)

- [x] `adapters/obsidian.py` — STUB pointing to #07; declares `{PULL}`; all methods return clear "not implemented" errors
- [x] `adapters/reminders.py` — STUB pointing to #09; same shape
- [x] `adapters/todo_md.py` — STUB pointing to #21; same shape (`list_groups() == []` by design — single file)
- [x] All three registered in `REGISTRY` (built-ins)

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

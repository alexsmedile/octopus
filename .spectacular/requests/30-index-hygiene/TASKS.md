---
request: 30-index-hygiene
status: done
updated: 2026-05-24
---

# Tasks — 30-index-hygiene

## Group 1 — Lock decisions ✅
- [x] D83 — `forget activity` semantics + flag matrix + archived-hidden-by-default

## Group 2 — `core/identify.py` (path-or-id resolver) ✅
- [x] `resolve_activity(token) -> dict` accepting path or id/prefix
- [x] Path detection: starts with `/`, `~`, or contains `/`
- [x] Prefix resolution: exact match first, then `slug-%` LIKE
- [x] `ActivityNotFound` / `ActivityAmbiguous` exceptions

## Group 3 — `octopus forget activity` ✅
- [x] `forget_activity(activity, *, archive_files)` action in `actions.py`
- [x] Returns `ForgetResult` with rows-removed counts + archive destination
- [x] `octopus forget activity <target> [--archive] [-y]` CLI verb
- [x] Typer sub-app pattern (`forget_app`) so future `forget task` slots in
- [x] Flag matrix: `--archive`/`-y`/both/neither all behave per D83
- [x] Interactive prompt with both flag-form hints

## Group 4 — Archived-by-default filter ✅
- [x] `list_activities(include_archived=False)` parameter (D83)
- [x] Default excludes `status='archived'` UNLESS explicit `--status archived` filter
- [x] `--include-archived` flag on `octopus list`

## Group 5 — Tests ✅ (19 new, 508 total)
- [x] Resolver: path, prefix, exact-id, ambiguity, unknown, empty
- [x] Resolver: path not in index, path without `.octopus/`
- [x] CLI `forget` happy paths: `-y` alone (no archive), `--archive -y`, by prefix
- [x] CLI `forget` errors: unknown id, already-forgotten, archive-destination collision
- [x] CLI `forget` isolation: forgetting alpha doesn't touch beta
- [x] `list_activities` default hides archived; `include_archived=True` shows
- [x] `--status archived` shows archived only (overrides default)
- [x] CLI `list --include-archived` flag works

## Group 6 — Real-world cleanup pass ✅
- [x] Removed `/tmp/promote-smoke` from `~/.config/octopus/config.toml [roots]`
- [x] `reindex --prune` pruned 489 stale rows
- [x] Bulk-forgot 88 leftover `/tmp/*` and `pytest-*` entries via direct DB deletion
  (one-time hygiene; reveals a separate test-isolation bug — tests writing to the
  real index instead of fully isolating XDG_DATA_HOME. Tracked for a future pass.)
- [x] `octopus list --all` now shows 1 real activity (the octopus repo itself)

## Group 7 — Ship ✅
- [x] CHANGELOG [0.7.0] entry
- [x] `cli/pyproject.toml` 0.6.1 → 0.7.0
- [x] README status line updated
- [x] PLAN/TASKS status: active → done
- [ ] Tag v0.7.0 (next step)

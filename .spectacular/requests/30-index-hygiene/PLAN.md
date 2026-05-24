---
status: done
priority: high
owner: alex
updated: 2026-05-24
summary: "Index hygiene: octopus forget verb, archived-by-default filtering on list --all, one-time /tmp cleanup pass."
related:
  - 26-cross-activity-writes
  - 27-cross-activity-reads-and-dashboards
gates: []
---

# Index hygiene

## Goal

Make the global activity list useful by clearing test/scratch noise and giving the user a verb to drop unwanted entries from the index without touching files. Establishes the foundation for #26/#27 to deliver a clean global view.

## Why

Current state: `octopus list --all` returns 18+ activities, half of which are `/tmp/*` test fixtures (`test-drop-zombies-keep…`, `mutate-smoke`, etc.). The user can't easily see real work; agents can't reason about a "next high-impact action" when the index is full of phantoms.

Three sources of noise:

1. **One-time cleanup needed.** `/tmp/promote-smoke` got added to `[roots]` during early adapter dogfooding. Some smoke-test runs created activities under tmp that the index picked up. Many of those files are gone now but rows persist.
2. **No `forget` verb.** Even when you want to drop an activity from the index without deleting the files (e.g. archived projects, scratch repos), there's no way except hand-editing the SQLite DB.
3. **No archived-filter default.** Activities with `status: archived` show up in `list --all` alongside active ones. Should be hidden by default.

## Scope

### Phase 1 — One-time `/tmp` cleanup

- Remove `/tmp/promote-smoke` from `~/.config/octopus/config.toml [roots] paths`.
- Run `octopus reindex --prune` once. This drops rows whose source files are missing (the bulk of the `/tmp/*` noise).
- Keep `/tmp` discoverable for future test setup (no policy change), but never auto-added.

This is shell-script work — no code changes needed. Documented in the request CHANGELOG entry so anyone replicating the workspace knows what to run.

### Phase 2 — New verb: `octopus forget activity <path-or-id> [--archive] [-y]`

Noun-explicit form. Future-stable: if `forget task` ever becomes useful, the surface is ready for it. v1 ships activity-only.

```
octopus forget activity <path-or-id>
  Removes the activity from the SQLite index. Files on disk are NOT touched
  by default. Optionally moves files to <activity-parent>/_archive/<name>/ if
  --archive (or --also-archive) is passed.

  Path-or-id resolution: same as `octopus status` — accepts an activity ID,
  unambiguous prefix, or an absolute path.

  Flags:
    --archive / --also-archive   Move files to _archive/ as part of forgetting.
    -y                           Skip the interactive prompt (assumes default = yes
                                 on archive prompt when set).

  Without --archive AND without -y, the verb prompts interactively:
    "Also archive files to _archive/? [y/N]"
    "  (or run: octopus forget activity <id> --archive -y to skip this prompt)"
```

Behavior:
- Always: delete the row from `activities` table (CASCADE will drop related `tasks` rows + `task_external_refs` rows).
- With `--archive`: also move the activity folder to its parent's `_archive/<name>/` directory.
- Re-running `forget activity` on an already-forgotten activity errors clearly ("activity not in index").

Activities-only by design. Tasks have their own lifecycle (`archive`/`drop`/`done`). The rare "remove a task from index but keep the file" case can wait for explicit demand — and when it does, the verb shape is `forget task <slug>`.

### Phase 3 — Archived-by-default filter on `list --all`

- Activities with `status: archived` are hidden from `octopus list --all` by default.
- `octopus list --all --include-archived` shows them.
- Same default applies to `octopus dashboard`, `next`, `impact`, `activities` (when those ship in #27).
- `octopus status <archived-id>` and `octopus tasks <archived-id>` still work — the user can always look at an archived activity by name.

This phase touches `db/queries.py` (the activity-listing SQL) to add the filter. The default flips, but the data isn't migrated — existing activities keep their status field as-is.

## Out of scope

- **Task-level `forget`.** Tasks use `archive`/`drop`/`done`. No protocol for the "keep file, remove from index" case yet; defer until real demand.
- **Bulk-forget by prefix glob.** `forget --pattern "test-*"` would be useful for batch cleanup but skirts the "never delete files" rule by accident. v1 is single-target only.
- **Auto-forget on missing source.** `reindex --prune` already does this; no new behavior.

## Approach

1. **D-entry** locking `forget` semantics.
2. **`octopus forget` CLI verb** — new top-level command with path-or-id resolution + interactive prompt.
3. **`activity_status` filter** on `db/queries.py` list helpers — default excludes `archived`.
4. **Update `list --all` (and downstream verbs)** to pass the new filter.
5. **Tests** for `forget` happy paths + edge cases (unknown id, ambiguous prefix, already-forgotten, `--archive` flag combinations).
6. **Manual cleanup pass** documented in CHANGELOG (run `config root remove /tmp/promote-smoke && reindex --prune`).

## Deliverables

- [ ] D83 — `forget` verb semantics; archived hidden by default.
- [ ] `octopus forget <path-or-id> [--archive] [-y]` CLI verb.
- [ ] Path-or-id resolver helper (reusable in #27).
- [ ] `db/queries.py`: `list_activities()` excludes `status='archived'` by default; `include_archived=True` flips it.
- [ ] `cli.py`: `list_cmd` accepts `--include-archived` flag.
- [ ] Tests in `test_forget.py`.
- [ ] CHANGELOG [0.7.0] section.
- [ ] One-time manual cleanup documented in CHANGELOG migration notes.

## Open for grilling

- **Verb name.** `forget` reads good. Alternatives considered: `octopus untrack`, `octopus deindex`, `octopus drop activity`. Reject all — `forget` is the right metaphor.
- **`--archive` destination shape.** Move to `<parent>/_archive/<name>/` (alongside the activity folder)? Or to a global cache like `~/.local/share/octopus/archived/`? My pick: local-to-parent — keeps the archived files near the original location, easy to git-track or browse.
- **Activity-level priority field** lands in #27, not here. `forget` doesn't need it.

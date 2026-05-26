# Critical dependencies — validation reference

When the CLI rejects a write, the error message names the rule. This document maps rule names to their explanation and resolution.

Load this reference when:
- A CLI verb exits non-zero with a validation error mentioning a field.
- You're about to write a frontmatter file by hand and want to confirm it's legal.
- An agent is generating a task/session/memory/handoff and needs to satisfy invariants up front.

## Tasks

### Rule T1 — Terminal buckets require dates

| Bucket | Requires |
|---|---|
| `done` | `start_date` AND `end_date` |
| `dropped` | `end_date` (start_date optional) |

Resolution: set the missing date(s), OR move the task back to a non-terminal bucket.

### Rule T2 — Terminal buckets cannot be pinned

`bucket: done` or `dropped` with `pinned: true` → reject.

Resolution: `octopus unpin <slug>` before finishing, OR unset the bucket.

### Rule T3 — Terminal buckets cannot have impediments

`bucket: done` or `dropped` with `issue: <set>` → reject.

Resolution: clear `issue`, `blocked_by`, `waiting_for` before finishing/dropping.

### Rule T4 — Impediments require their detail field

| `issue` | Requires |
|---|---|
| `blocked` | `blocked_by` (non-empty string) |
| `waiting` | `waiting_for` (non-empty string) |

Resolution: set the detail field, OR clear `issue`.

### Rule T5 — Date ordering

`end_date < start_date` → reject. `end_date` set on non-terminal bucket → reject.

Resolution: fix the date order, OR move to a terminal bucket.

### Rule T6 — Forbidden legacy fields

`status`, `open` in task frontmatter → reject (v1 schema collapse).

`kind` is **NOT** legacy as of D46 (v0.3.0) — it's a v1 work-classification enum (`feat | bug | spec | polish | test | chore`). The earlier "kind is forbidden" rule was reversed when the schema was extended. See rule X4 for the active `kind` semantics.

Resolution: remove `status` and `open` fields. See `schemas/task.md` for replacements.

## Activities

### Rule A1 — Required identity

Missing `id`, `title`, `last_known_path`, or `kind` → reject.

### Rule A2 — `kind` literal

`kind != "activity"` → reject in v1.

### Rule A3 — `spec_version`

`spec_version != 1` → reject until v2 ships.

## Sessions

### Rule S1 — Required timing

Missing `started` → reject. `started` must be parseable as ISO 8601 datetime (with seconds preferred but minute precision tolerated on read).

### Rule S2 — Ended state coherence

| State combination | Allowed? |
|---|---|
| `ended != null` AND `active == true` | ❌ rejected |
| `status == "done"` AND `ended == null` | ❌ rejected |
| `status == "dropped"` AND `active == true` | ❌ rejected |
| `ended < started` | ❌ rejected |

Resolution: setting `ended` should also clear `active` (or set `active: false`). The CLI does this automatically via `session end`; hand-edits must mirror it.

### Rule S3 — Cache authority on mismatch

If `active: true` in frontmatter but the cache says a different session is active, the cache wins. The frontmatter mirror is updated on next CLI write.

Resolution: trust the cache. Run `octopus session show` to see the authoritative active session.

## Memory

### Rule M1 — Activity identity match

`activity` in `memory.md` frontmatter MUST equal `id` in the parent `activity.md`. Mismatch → warning on read, reject on write.

### Rule M2 — Marker presence

The body MUST contain `<!-- octopus-managed-below -->`. If a write encounters a body without the marker, the CLI re-inserts it (above the first canonical section) and emits a stderr warning. This is recovery, not silent fix — surface it to the user.

### Rule M3 — Canonical section order

Sections in the managed zone are written in this order regardless of insertion order: Decisions → Open Questions → Context → Notes → State. The CLI re-orders on append.

### Rule M4 — last_updated bump

Every write must bump `last_updated` to today's date. Hand-edits that forget this surface as a warning (not an error).

## Handoffs

### Rule H1 — Required identity + lifecycle

Missing `title`, `created`, `from_actor`, or `status` → reject.

### Rule H2 — Enum membership

`from_actor`, `to_actor`, `status`, `priority` must be in their declared enums (see `schemas/handoff.md`). Reject otherwise.

### Rule H3 — Lifecycle date coherence

| Date set | Requires status |
|---|---|
| `received_at` | `received` or `resolved` |
| `resolved_at` | `resolved` |

Plus:
- `resolved_at >= received_at` when both set.
- `resolved_at >= created`.

Resolution: set the corresponding status, OR clear the date.

## Cross-cutting

### Rule X1 — Default omission

In FRONTMATTER: writing a field at its default value is rejected on write (tolerated on read).

Defaults that must be omitted from frontmatter:
- `actor: human`
- Task `priority: <normal>` (just don't write the field)
- `pinned: false`, `archived: false`
- Empty lists/dicts: `tags: []`, `external_refs: {}`, `related_tasks: []`

In CLI FLAGS (D80): passing an explicit-default value (`--priority normal`, `--actor human`, `""`, etc.) is **accepted** and **clears the field**. See rule X11 for the full list.

Resolution: remove the field from frontmatter entirely. From flags, use the default value or omit the flag — both work.

### Rule X2 — Body preservation

All CLI verbs that write a file MUST preserve the body byte-for-byte except for documented mutations:
- `session log` appends a dated heading + note to session body.
- `memory append` inserts a dated entry into the targeted section.
- `session end --handoff` appends an auto-note to session body when previous-end is auto-triggered.

Any other write that changes body bytes is a bug. Report it.

### Rule X3 — Filename stability

Filenames are CLI-owned. Hand-renaming a file breaks the index and any cross-refs pointing at the old slug.

For tasks: use `octopus set <slug> --slug <new-slug> [-y]` (D78) — this is the ONLY supported rename path. It cascades the change across all Octopus-managed references. See rule X10 for the full cascade contract.

For sessions and handoffs: slugs are never renamed (timestamps in the slug make rename meaningless).

### Rule X4 — `kind` field validation (D46)

- `kind` is optional. Tasks without it are valid.
- `kind` SHOULD be one of `feat | bug | spec | polish | test | chore`.
- Unknown values log a warning (stderr) but DO NOT abort the write — soft validation v1.
- Indexed in SQLite; queryable via `list --kind <enum>`.
- NOT required to promote.
- Survives promotion. Hidden from default `list` filters by the `done/`-exclusion scope rule. Surface via `--all`, `--promoted`, or `--spec`.

### Rule X5 — `promoted_to` field validation (D47–D48)

- Format MUST match `^<provider>:<identifier>$` (non-empty both sides).
- Provider MUST be registered. v1 providers: `spectacular`.
- For `spectacular:<slug>`, slug MUST resolve to a directory under `.spectacular/requests/` OR `.spectacular/requests/_archive/`. Archived targets are valid.
- Stored value is canonical (long provider name) regardless of CLI input (aliases, defaults, shorthand are input-only).
- Slug-based, not path-based — survives archive moves.

### Rule X6 — `octopus promote` verb invariants (D49–D51)

- Already-promoted task without `--force`/`--revert` → reject with exit 4.
- `--force` repoints `promoted_to` + updates `end_date`. Body NOT re-rewritten (already a stub).
- `--revert` clears `promoted_to` + `end_date`, AND moves the task to `bucket: backlog` (because `bucket: done` requires `end_date` — clearing one without the other fails validation). Body stays stub (full restore via git).
- Multi-task batch is atomic — pre-flight validates every task before any write.
- Multi-task with provider-only shorthand (`--to spec`) → reject with exit 3.
- On promote, body replaced entirely with the hard-coded 3-line stub. `bucket: done` set. File moved to `tasks/done/<slug>.md`. `end_date: <today>` set.
- Scaffolds the request if absent. `promoted_from` records the first listed task. Not cleared on repoint.

### Rule X7a — Adapter framework invariants (D56–D66)

**Config / enable / disable:**
- `[adapters.<name>] enabled = true` requires matching `bridges/<name>.toml` (exit 3 if missing).
- `octopus bridge enable` runs `adapter.validate_config()` first; rejection aborts.
- `octopus bridge disable` flips flag, keeps the bridge config file.
- `bridges/<name>.toml` without main-config section is tolerated (parked settings).

**Capability gating:**
- `peek` / `pull` / `search` require `Capability.PULL` declared by the adapter (exit 1 otherwise).
- `push` requires `Capability.PUSH` (not v1 surface).
- `NOTIFY` / `RECONCILE` are flag-only in v1 — no gating.

**Flag matrix (peek/pull/search):**
- `--list` and `--capture-all` mutually exclusive (exit 1).
- `lists = []` + no flag + `pull`/`search` → exit 3.
- `lists = []` + no flag + `peek` → discovery (list available groups, no error).
- `--list X` where X not in `list_groups()` → exit 3.

**Pull pipeline:**
- Every materialized task sets: `actor=human`, `imported_from=<adapter>`, `import_date=<today>`, `external_refs.<adapter>=<external_id>`.
- `bucket` defaults to `ExternalTask.suggested_bucket` or `"backlog"`.
- Dedup checks `task_external_refs (adapter, external_id)` before creation. Match → skip (not error).
- Target activity: `default_activity` (bridge config) → cwd activity → exit 2.
- Partial-pull continues; all-failed → exit 4.

**Dedup index (schema v3):**
- `upsert_task` keeps `task_external_refs` in sync with frontmatter's `external_refs`.
- On UPDATE: delete + re-insert all refs for that `task_id`.
- v2 → v3 migration backfills from existing tasks.
- `(adapter, external_id)` PK — duplicate insert is integrity error.

**Sync journal:**
- `~/.local/share/octopus/sync/<name>.json` is canonical state per adapter.
- `adapter.status()` reads; pipeline writes after pull/push.
- Cursor is opaque to framework — adapter sets, framework persists.

**Registry:**
- Built-in REGISTRY wins over entry-point contributions with same name.
- Entry-point load exception → log + skip; never aborts registry load.
- Stub adapters (Obsidian/Reminders/TODO.md in #06) return clear "not implemented" errors from every method.

### Rule X7 — Reindex of `related_tasks` (D54)

- `related_tasks:` on request PLAN.md is DERIVED, not authored. Hand-edits are overwritten on next reindex.
- `reindex` scans tasks for `promoted_to: spectacular:<slug>`; regenerates `related_tasks:` on the matching PLAN.md.
- Sorted, deduped, default-omitted when empty.
- Malformed `promoted_to` → warn but don't abort.
- Non-`spectacular:` values are no-op for v1 (other providers ship with their adapters).

### Rule X8 — Tag flag matrix (D76)

- Tags stored with `#` prefix in frontmatter (`tags: ["#bug", "#tui/marquee"]`). Nested via `/`.
- Reader accepts both `#bug` and `bug` for backwards compatibility; the writer always emits `#`.
- Four flag families on `capture` and `set`:
  - `--tag` / `--tags` REPLACE
  - `--add-tag` / `--add-tags` APPEND (dedup)
  - `--remove-tag` / `--remove-tags` REMOVE
  - `--clear-tags` EMPTY
- All accept comma-separated, space-separated (in quotes), or repeated input.
- Singular and plural are aliases.
- Replace is mutually exclusive with any incremental flag; mixing them errors (exit 1).
- Combined incremental flags apply in order: clear → remove → add.
- Filter: `--tag parent` matches `#parent` AND `#parent/*` (prefix on `/` boundary).

### Rule X9 — `set` is frontmatter-only (D77)

- `set` edits frontmatter fields only. It never moves files.
- In folder-mode storage, if `--bucket` changes a value such that the parent directory no longer matches, `set` emits a soft warning pointing at `octopus mv`.
- For physical file moves, use `octopus move <slug> <bucket>` (alias `mv`) — pure file-move + frontmatter update with no date stamps or lifecycle side effects.
- `mv` validates the resulting state — moves that would violate cross-field rules (e.g. `bucket: done` requires `end_date`) are rejected; the error points at `finish`/`drop` for the lifecycle path.

### Rule X10 — Slug rename cascade (D78)

- `octopus set <slug> --slug <new-slug>` is the ONLY supported way to rename a task slug.
- Always auto-fixed:
  - filesystem rename
  - SQLite index (`tasks.slug` + `tasks.id`)
  - `waiting_for: <old>` in other tasks' frontmatter
  - `related_tasks: [..., <old>]` in spectacular PLAN.md
  - `promoted_from: <old>` in spectacular PLAN.md
  - `→ octopus:<old>` arrows in TODO.md files
- Soft-warned (named, not auto-fixed): session bodies, memory body, handoff bodies.
- External tools (Obsidian backlinks, IDE bookmarks, git) are never touched.
- `-y` skips the interactive confirmation prompt.

### Rule X11 — Explicit-default values clear (D80)

- Passing a value equal to a field's default is accepted and clears the field — does not reject.
- Applies to `--priority normal`, `--actor human`, `--energy normal`, `--run-state idle`, `--issue none`, `--kind none`, empty strings on any optional field, etc.
- Result is identical to omitting the flag entirely.

### Rule X12 — Capture defaults (D81, D82)

- `capture --now` sets `bucket: now` but does NOT auto-pin. `pinned` stays orthogonal to bucket. For pinned-and-now, run `pin` after.
- `capture` writes an empty body by default. No more hardcoded `## References` section.

### Rule X13 — Lint rule registry (request #42)

`octopus lint` rules coupled to schema fields. Update both the rule file and this list when schema changes.

| Rule | Severity | Fix | Coupled to |
|---|---|---|---|
| `slug-match` | error | yes | filename ⇄ raw `slug:` |
| `slug-shape` | error | — | `^[a-z0-9-]+$` |
| `bucket-match` | error | yes | parent folder ⇄ `bucket:` |
| `corrupt-frontmatter` | error | — | `TASK_FIELDS` + `LEGACY_FIELDS` |
| `start-without-now` | warn | — | `start_date` + `bucket` |
| `dangling-blocker` | warn | — | `blocked_by` + local slugs |
| `stale-done` | info | yes | `bucket=done` + `end_date` (>30d) |
| `bucket-blocked` | info | — | `issue` + `bucket` (locked at info per D100) |

Exit codes: 0 clean, 1 info/warn, 2 errors.

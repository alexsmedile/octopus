---
status: draft
updated: 2026-05-22
relates_to: SPEC.md, SCHEMA-TASK.md, SCHEMA-ACTIVITY.md, SCHEMA-SESSION.md, SCHEMA-HANDOFF.md, SCHEMA-MEMORY.md, SCHEMA-INDEX.md, CLI-VERBS.md
---

# Critical field dependencies

Validation contract: rules that an implementation MUST enforce across all file types in an `.octopus/` folder.

The first half (rules A-I) covers tasks. The second half (rules J-N) covers activities, sessions, handoffs, and memory.

Three tiers:
- **MUST reject** — the file is invalid; write/import operation fails.
- **MUST clear** — when verb X runs, field Y is cleared automatically.
- **SHOULD warn** — legal but smells; surface a warning, don't reject.

---

## A — Required-field dependencies

Lifecycle is encoded via dates + terminal `bucket` values (no `status` field).

| Rule | Reason |
|---|---|
| `bucket: done` MUST have `start_date` AND `end_date` set. | Done means it started and ended. |
| `bucket: dropped` MUST have `end_date` set. `start_date` MAY be absent (dropped before starting). | Terminal; may or may not have started. |
| `bucket: done` or `dropped` MUST have `issue` absent. | Completed work can't be blocked/waiting. |
| `bucket: done` or `dropped` MUST have `pinned` absent. | Terminal tasks don't occupy attention. |
| `end_date` present MUST have `bucket: done` or `dropped`. | Ended without a terminal bucket is contradictory. |
| `end_date` MUST be ≥ `start_date` (when both set). | Time cannot go backwards. |
| `issue: blocked` MUST have `blocked_by` set. | The whole point of `blocked` is naming the blocker. |
| `issue: waiting` MUST have `waiting_for` set. | The whole point of `waiting` is naming what you wait on. |
| `kind` field absent. | `kind` removed in v1; reject if encountered. |
| `status` field absent. | `status` removed in v1; reject if encountered. |
| `open` field absent. | Renamed to `pinned` in v1; reject if encountered. |

## B — Auto-clear rules (verb side effects)

| Verb | Clears |
|---|---|
| `start` (when resuming from `done`/`dropped`) | `end_date`; bucket → `now` |
| `finish` | `pinned`, `issue`, `blocked_by`, `waiting_for`, `run_state` |
| `drop` | `pinned`, `issue`, `blocked_by`, `waiting_for`, `run_state` |
| `park` | `pinned` |
| `unblock` | `issue`, `blocked_by`, `waiting_for` |
| `unpin` | `pinned` |
| `restore` | `archived` |

## C — Auto-set rules (verb side effects)

| Verb | Sets |
|---|---|
| `capture` | `created: today`, `bucket: backlog` |
| `capture --next` | also `bucket: next` |
| `capture --now` | also `bucket: now`, `pinned: true` |
| `plan` | `bucket: next` |
| `focus` | `bucket: now`, `pinned: true` |
| `park` | `bucket: backlog` |
| `defer` | `bucket: next` (keeps `pinned` as-is) |
| `start` | `start_date: today` (if absent); idempotent if already started; on `done`/`dropped`, also clears `end_date` and moves bucket → `now` |
| `finish` | `bucket: done`, `end_date: today` (if absent), `start_date: today` (if absent — one-shot) |
| `drop` | `bucket: dropped`, `end_date: today` (if absent) |
| `block --reason X` | `issue: blocked`, `blocked_by: X` |
| `wait --for X` | `issue: waiting`, `waiting_for: X` |
| `pin` | `pinned: true` |
| `archive` | `archived: true` |

## D — Mutual exclusion

| Cannot coexist | Resolution |
|---|---|
| `bucket: done` + `bucket: dropped` | impossible — bucket is single-valued |
| `issue: blocked` + `issue: waiting` | impossible — issue is single-valued |
| `bucket: done|dropped` + `pinned: true` | rejected (rule A): pinned cleared on finish/drop |
| `bucket: done|dropped` + `issue: <any>` | rejected (rule A) |

## E — SHOULD-warn smells

These are legal but the CLI should surface a warning at write time:

| Pattern | Warning |
|---|---|
| `bucket: next` + `start_date` absent + `created > 30d ago` | "stale: committed but never started" |
| `start_date` present + `bucket: next` + `pinned` absent + last touched > 14d | "stalled: started but no longer being tracked" |
| `bucket: backlog` + `pinned: true` + (older than 14d) | "haunting idea — promote or drop?" |
| Stale open session (no log activity > 7d) | session-level warning, not task-level |
| `issue: waiting` + `waiting_for` empty | "waiting for what? add a `--for` argument" |
| `run_state: failed` + (older than 7d, no review) | "failed run not reviewed" |
| `run_state: running` + (older than 24h) | "long-running execution — still alive?" |

## F — Folder-mode invariants (when storage mode is `folders`)

| Rule | Reason |
|---|---|
| Task file path's bucket folder MUST match frontmatter `bucket` value. | Defensive redundancy — file movable, frontmatter readable in isolation. |
| Pipeline verbs (`plan`, `focus`, `park`, `defer`) MUST do both: edit frontmatter AND `mv` the file. | Atomic transition. |
| If mismatch detected on read, surface as error with both values. | User intervention required (`octopus storage repair`). |

## G — Order-of-operations rule

When a verb sets multiple fields, the order is:

1. Validate inputs against rules A & D.
2. Apply clears (rule B).
3. Apply sets (rule C).
4. Run smell warnings (rule E).
5. Write file (and `mv` in folder mode, rule F).
6. Update index.

## H — Trash exclusion

- Files under `.octopus/.trash/` MUST be excluded from all retrieval (views, index, `where`, search, cross-reference resolution).
- The reindexer MUST NOT populate `.trash/` contents into SQLite.
- Recovery from trash is via `octopus restore --from-trash <slug>` (verb pending v2 confirmation).

## I — Field aliasing

When task field aliasing is configured (see `SCHEMA-TASK.md` field-name aliasing):

- The implementation MUST read both the canonical and aliased field name.
- The implementation MUST write only one (configured alias, falling back to canonical).
- A file containing **both** the canonical and aliased name for the same logical field MUST be rejected with an unambiguous error message.

The same aliasing rules apply to activity, session, handoff, and memory schemas.

---

# Activity rules

## J — Activity invariants

| Rule | Reason |
|---|---|
| `id` MUST be present and well-formed (`<slug>-<4hex>`). | Identity is load-bearing. |
| `id` MUST be unique across all configured roots. | Cross-references break otherwise. |
| `id` MUST NOT change after creation. | Stable references. Folder renames update `last_known_path`. |
| `kind: activity` is fixed in v1. | Other kinds reserved for v2. |
| `last_known_path` updated only with user confirmation on rename detection. | Prevents silent state drift. |
| `linked_activities` entries MUST resolve to existing activities (prefix or full id). | Dangling references rejected on validation. |

### SHOULD warn

- `status: active` with no task touched in > 60 days.
- `last_reviewed` > 90 days ago.
- `area` near-duplicate of existing area (Levenshtein ≤ 2).
- `linked_activities` references that resolve but to an `archive` status activity.

---

# Session rules

## K — Session invariants

| Rule | Reason |
|---|---|
| `started` MUST be present and valid ISO 8601 datetime. | Lifecycle anchor. |
| Body log entries MUST use second precision (`### YYYY-MM-DD HH:MM:SS`) per D41 Q2. | Distinguishes session log from memory entries (minute precision). |
| `ended`, if present, MUST be ≥ `started`. | Time cannot go backwards. |
| At most one session per activity may have `active: true` in the cache file. | One active per activity (PRD §13.2). |
| Frontmatter `active:` is cache-mirrored; cache is source of truth on conflict. | Avoids fighting between file edits and runtime state. |
| `related_tasks` slugs MUST resolve to tasks in the same activity. | Dangling refs surface on validation. |
| Setting `status: dropped` MUST also set `ended:` to current time (or last log time). | Dropped sessions are terminal. |
| Setting `ended:` MUST set `active: false`. | A closed session cannot be active. |
| `[e]` choice on multi-open `session start` MUST set the previous session's `status: dropped` AND append the auto-note `ended by session start --replace` to its body (second-precision timestamp). | Audit trail for context-switch by replace. |
| `session log` invoked with no active session MUST exit 3 with a hint, not silently no-op. | Per D41 Q6. |

### SHOULD warn

- `ended:` empty and no log activity for > 7 days (stale-session detection). Window is configurable via `[sessions] stale_warn_days` (default 7).
- Multiple sessions with `active: true` in the same activity (cache/file mismatch).
- `status: done` without `ended:` set.
- `related_tasks` slugs that don't exist in the activity's tasks directory.

## K2 — Session cache invariants

The runtime cache `~/.cache/octopus/active-sessions.json` (XDG-respectful via `OCTOPUS_CACHE_HOME` / `XDG_CACHE_HOME`) tracks the active session per activity.

| Rule | Reason |
|---|---|
| Cache shape is `{activity_id: session_filename}` (no `.md` suffix). | Single-key-per-activity invariant. |
| Cache writes MUST be atomic (tmp file + `os.replace`). | Avoid partial writes corrupting the map. |
| Malformed JSON in the cache MUST be tolerated: warn to stderr, treat as empty map, do not crash. | Per D41 — runtime cache is recoverable state, not user data. |
| Cache wins on mismatch with `active:` frontmatter. CLI updates the frontmatter mirror on next write. | One source of truth; mirror is best-effort. |
| Removing an `active:` entry from the cache MUST NOT remove the session file. | Cache is metadata; files are durable. |

---

# Handoff rules

## L — Handoff invariants

| Rule | Reason |
|---|---|
| `from_actor` and `status` MUST be present. | Identity of producer + state are required. |
| `received_at` MAY only be set if `status` is `received` or `resolved`. | State machine consistency. |
| `resolved_at` MAY only be set if `status` is `resolved`. | State machine consistency. |
| `resolved_at` MUST be ≥ `received_at` (when both set). | Time cannot go backwards. |
| `resolved_at` MUST be ≥ `created`. | Time cannot go backwards. |
| `from_session` slug MUST resolve to a session in the same activity. | Dangling refs rejected. |
| `related_tasks` slugs MUST resolve. | Dangling refs rejected. |
| `related_activities` MUST resolve to existing activities. | Dangling refs rejected. |

### SHOULD warn

- `status: open` and `created` > 30 days ago (handoff aging).
- `status: open` with neither `related_tasks` nor `related_activities` (orphan handoff).
- `from_actor: human, to_actor: human, to_owner:` empty (vague handoff).

---

# Memory rules

## M — Memory invariants

The canonical five sections are (per D41): **Decisions / Open Questions / Context / Notes / State**. The default `memory append` target is `## Notes` (changed from `## Log` in D41).

| Rule | Reason |
|---|---|
| `activity` and `last_updated` MUST be present. | Identity + freshness. |
| `last_updated` MUST be bumped on any CLI write. | Stale-memory detection relies on this. |
| The marker `<!-- octopus-managed-below -->` MUST be present whenever any managed-zone section exists. | Contract between user and CLI. |
| If marker is missing on a file with managed-zone sections, CLI MUST re-insert before first managed section AND warn to stderr. | Recovery from deletion. Stderr warning surfaces the recovery; it is not silent. |
| CLI MUST NOT modify content above the marker (except `last_updated` and `summary` via explicit verb). | Sacred user zone. |
| CLI MUST NOT reformat, reorder, or rewrite existing entries below the marker. | Append-only contract. |
| When inserting a new section, it MUST be placed in canonical position regardless of insertion order. | Predictable layout for readers. |
| Body entries MUST use minute precision (`### YYYY-MM-DD HH:MM`). | Distinguishes memory entries from session log entries (second precision). |
| Append with empty or whitespace-only `<note>` MUST be rejected. | No empty entries. |
| Section name resolution MUST accept unambiguous prefixes (e.g. `open` → `Open Questions`). Ambiguous prefix MUST be rejected with the candidate list. | Ergonomics + safety. |
| `## State` is append-only like other sections, but the latest entry is treated as "current state" by `octopus memory state` and the default `memory show` preview. | Per D41 — single section serves history + current. |

### SHOULD warn

- Sections present below the marker not in the canonical five (Decisions / Open Questions / Context / Notes / State).
- Section order differing from canonical.
- `activity` field doesn't match the parent activity's `id`.
- Body appears to contain raw secrets (API keys, tokens, passwords, PII). Auto-scrubbing is not in v1; user is responsible.

## N — Memory zone boundary

- The marker `<!-- octopus-managed-below -->` is the boundary between zones.
- Above: user-owned. CLI may only touch `last_updated` and `summary` frontmatter via explicit verb.
- Below: machine-managed. CLI may only append new entries; never reformat or reorder.

---

# CLI verb rules

## O — `set` verb validation pipeline

The `set` verb is the hand-edit equivalent and accepts any frontmatter field. Validation runs in this order; failure at any step aborts the write:

| Step | Type | Outcome on failure |
|---|---|---|
| 1. Type validation | Hard reject | Exit 1, no write. Value type doesn't match field declaration (e.g. `--due "tomorrow"`). |
| 2. Format validation | Hard reject | Exit 1, no write. Value fails format constraint (malformed ISO date, enum value outside set, empty string in required-non-empty field). |
| 3. Cross-field validation | Hard reject | Exit 1, no write. Resulting state violates a MUST-rule (rules A-D above). |
| 4. Smell check | Soft warn | Exit 0, write succeeds, stderr warning. Triggers any SHOULD-warn rule (rule E). |
| 5. Verb-overlap notice | Informational | Exit 0, write succeeds, stderr tip. A dedicated verb exists for the field being changed. |

Multi-field invocations (`set --bucket now --open true`) are atomic: all validations run against the proposed final state; on any failure, nothing is written.

`set` MUST NOT auto-apply verb side effects (date stamping, log entries, `pinned` flipping). Those are reserved for dedicated verbs. This is by design: `set` is hand-edit equivalence; verbs are state machines.

---

# Index rules

## P — Index ↔ filesystem consistency

The SQLite index is derived; the filesystem is the source of truth (see `SCHEMA-INDEX.md`). These invariants MUST hold after any CLI operation:

| Rule | Reason |
|---|---|
| Every `activities` row MUST point to an existing `.octopus/activity.md` at `path`. | Index never holds dangling references. |
| Every `tasks` row MUST point to an existing file. | Same. |
| `tasks.bucket` MUST match the file's parent folder name in folder mode. | Folder is the contract. |
| `tasks.slug` MUST equal the file basename without `.md`. | Slug is the filename. |
| `tasks.activity_id` MUST resolve to an existing `activities.id`. | Foreign-key integrity. |
| `sessions.activity_id` MUST resolve. | Same. |
| Files under `.octopus/.trash/` MUST NOT appear in any table. | Trash is excluded from retrieval (rule H). |
| `indexed_at` MUST be set on every upsert. | Powers stale-check. |
| Mutation verbs MUST upsert in the same process as the file write. | Index doesn't drift between commands. |
| If the index write fails after a file write, the CLI MUST warn and continue. The next `reindex` reconciles. | Filesystem is source of truth. |

## Q — Reindex semantics

| Rule | Reason |
|---|---|
| `reindex` MUST be idempotent. Two consecutive runs produce the same row set. | Determinism. |
| `reindex` MUST skip directories matching `SPEC.md §8.1` ignore patterns. | Avoid descending into noise. |
| `reindex` MUST detect ID collisions and surface both paths (exit code 4). | Per `SPEC.md §9.5`. |
| `reindex` MUST detect path changes (`path` differs from `last_known_path`). Prompts y/N unless `--prune`. | Per `SPEC.md §9.3`. |
| `reindex --prune` MUST delete rows whose source files no longer exist. | Cleanup. |
| `reindex` MUST populate `sessions` table even though no verb reads it in v1. | Schema exercised; request 04 lands without re-reindex. |
| Read commands invoked on an empty index MUST emit a hint, not silently return empty. | Avoid "is it broken?" UX. |
| `where` is FILE-NATIVE and MUST work without consulting the index. | Resilience: works even when index is missing/stale/broken. |

## R — Index gaps and missing files

| Rule | Reason |
|---|---|
| Stale-check on a row whose source file is GONE MUST warn (stderr) and keep the row. | Silent deletion masks user error (accidental `mv` outside CLI). |
| `reindex --prune` is the ONLY way to delete rows whose source files are missing. | Explicit user intent required. |
| Default `[roots] paths` is `[]` (empty). `reindex` on empty roots errors with exit code 3 and a hint to add one. | No surprise scans of `~`. |
| Roots whose paths don't exist on disk MUST be skipped (not errored). | Tolerate misconfigured / cross-machine config. |
| `reindex` MUST warn at end if any configured root was skipped due to missing path. | Visibility. |
| Interactive (TTY): `reindex` prompts y/N on rename detection. | Default safety. |
| Non-interactive (pipe/agent/CI): `reindex` never prompts. Honors `--prune` flag only. | Agent automation. |
| Context-aware `list` / `task list`: cwd inside an activity → that activity's tasks; cwd outside → cross-activity; `--all` forces cross-activity regardless. | Sensible default for the common case. |

## S — Task `kind` field (D46)

| Rule | Reason |
|---|---|
| `kind` is optional. Tasks without `kind` are valid. | Backward compatibility; not all tasks deserve classification. |
| `kind` value SHOULD be one of `feat`, `bug`, `spec`, `polish`, `test`, `chore`. | Locked enum (D46). |
| Unknown `kind` values MUST log a warning (stderr) but MUST NOT abort the write. | Soft validation v1; allow free strings until the enum proves itself. |
| `kind` is mutable. `octopus set kind=<value>` is valid. | Tasks evolve (`spec` → `feat` is common). |
| Indexed in SQLite. `octopus list --kind <enum>` queries the column. | Filter ergonomics. |
| `kind` is NOT required to promote. | `kind` is optional everywhere, including before `promote`. |
| `kind` SURVIVES promotion. Hidden from default filters because promoted tasks live in `tasks/done/` (default scope excludes done). | Historical fact preservation; surface via `--all` / `--promoted` / `--spec`. |

## T — Task promotion (D47–D51)

### `promoted_to` field validation

| Rule | Reason |
|---|---|
| `promoted_to` value MUST match `^<provider>:<identifier>$` with non-empty provider and identifier. | Namespaced format prevents target confusion as providers grow. |
| Provider MUST be a registered provider in `[providers]` config. v1 registry: `spectacular`. | Unknown providers reject with a clear error. |
| For `spectacular:<slug>`, the slug MUST resolve to a directory under `.spectacular/requests/` OR `.spectacular/requests/_archive/`. | Archived targets remain valid — link doesn't break. |
| Stored value is always **canonical** (long provider name), regardless of CLI input form (aliases, defaults, shorthand). | One canonical form; aliases are display/input ergonomics only. |
| `promoted_to` value MUST be slug-based, not path-based. | Slugs survive archive moves; paths don't. |

### `octopus promote` verb invariants

| Rule | Reason |
|---|---|
| If task already has `promoted_to:` set, `promote` MUST reject with exit 4 unless `--force` or `--revert` is passed. | Promotion is destructive (body rewrite); accidental re-promotion would lose data. |
| `--force` MUST repoint `promoted_to` and update `end_date` but MUST NOT re-rewrite the body (already a stub). | Idempotent for repointing without further data loss. |
| `--revert` MUST clear `promoted_to` and `end_date` but MUST NOT restore the original body. | Soft revert v1; full body restore is via git. |
| Multi-task promotion MUST be atomic: pre-flight validates every task before any write. Any failure aborts the entire batch. | All-or-nothing semantics avoid half-promoted batches. |
| Multi-task promotion (2+ tasks) with provider-only shorthand (`--to spec`) MUST reject (exit 3) as ambiguous. | Each task slug would produce a different request slug. |
| On promote, task body MUST be replaced entirely with the hard-coded stub template (D51). | No partial drift between original body and the PLAN it points to. |
| On promote, `bucket: done` MUST be set and the file moved to `tasks/done/<slug>.md`. | `done` is the terminal bucket from Octopus's perspective. |
| On promote, `end_date: <today>` MUST be set. | Standard lifecycle close. |
| When the target request doesn't exist, `promote` MUST scaffold it with `promoted_from: <first-task-slug>` in PLAN.md frontmatter. | Records origin for posterity (historical, not derived). |
| `promoted_from` on request frontmatter MUST NOT be cleared by `--force` repointing. | Historical fact — what originally scaffolded the request. |

### Reindex of `related_tasks` (D54)

| Rule | Reason |
|---|---|
| `related_tasks:` on a request PLAN.md is **derived, not authored**. Hand-edits are overwritten on next reindex. | Single source of truth: task-side `promoted_to`. |
| `reindex` MUST scan all task files for `promoted_to: spectacular:<slug>` and regenerate `related_tasks:` on the matching request PLAN.md. | Drift impossible by construction. |
| `reindex` MUST sort and dedupe the derived `related_tasks` list. | Determinism; idempotent regen. |
| If no tasks reference a given request, `related_tasks:` MUST be removed from PLAN.md (default-omission). | Schema hygiene. |
| Reindex MUST emit a warning (not abort) on malformed `promoted_to` values (no colon, unknown provider, empty identifier). | Robust to user error; don't kill the index over bad data. |
| Non-`spectacular:` `promoted_to` values are no-op for `related_tasks` regen in v1. | Other providers (github, linear) require their own adapter logic. |

---

## Reference

For full field meanings, see the `SCHEMA-*.md` files.
For verb-by-verb behavior, see `CLI-VERBS.md`.
For structural framing of task state, see `AXIS-MODEL.md`.
For the overall on-disk contract, see `../SPEC.md`.

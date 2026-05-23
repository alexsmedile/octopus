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

`status`, `kind`, `open` in task frontmatter → reject (v1 schema collapse).

Resolution: remove the field. See `schemas/task.md` for the replacement field for each.

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

Writing a field at its default value is rejected on write (tolerated on read).

Defaults that must be omitted:
- `actor: human`
- Task `priority: <normal>` (just don't write the field)
- `pinned: false`, `archived: false`
- Empty lists/dicts: `tags: []`, `external_refs: {}`, `related_tasks: []`

Resolution: remove the field from frontmatter entirely.

### Rule X2 — Body preservation

All CLI verbs that write a file MUST preserve the body byte-for-byte except for documented mutations:
- `session log` appends a dated heading + note to session body.
- `memory append` inserts a dated entry into the targeted section.
- `session end --handoff` appends an auto-note to session body when previous-end is auto-triggered.

Any other write that changes body bytes is a bug. Report it.

### Rule X3 — Filename stability

Filenames are CLI-owned. Hand-renaming a file breaks the index and any cross-refs pointing at the old slug. Use `octopus rename` (tasks) or the relevant lifecycle verb (sessions, handoffs are never renamed).

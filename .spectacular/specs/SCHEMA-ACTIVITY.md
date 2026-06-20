---
status: draft
updated: 2026-05-22
relates_to: SPEC.md §3, CLI-VERBS.md
---

# Activity schema — v1

`activity.md` frontmatter contract. One file per `.octopus/` directory. The identity file of an activity.

Field order is fixed for spatial memory consistency.

---

## Field name aliasing

Same aliasing mechanism as tasks (see `SCHEMA-TASK.md`):

```toml
# ~/.config/octopus/config.toml  or  .octopus/config.toml

[activity.fields]
created       = "creation_date"
last_reviewed = "reviewed_at"
```

---

## Canonical order

```yaml
---
# ── identity ─────────────────────────────────────────────────────────
id:                           # required, string — <slug>-<4hex>      (immutable after init)
title:                        # required, string                       (default: folder name)
created:                      # required, ISO date
kind: activity                # required, fixed value (reserved for future activity kinds)
spec_version: 1               # required, integer

# ── classification ───────────────────────────────────────────────────
type: other                   # required, enum: code | business | content | skill |
                              #                automation | research | personal | inbox | other
status: active                # required, enum: active | next | paused | planning |
                              #                 maintenance | reference | archive | unknown
area:                         # optional, string (free-form with discovery)

# ── lifecycle ────────────────────────────────────────────────────────
last_reviewed:                # optional, ISO date (defaults to `created` on init)

# ── location ─────────────────────────────────────────────────────────
# last_known_path is NOT in activity.md — lives in .octopus/config.local.toml (D110)
source_of_truth: "."          # required, string — "." means this folder
locations: []                 # optional, list of additional paths/URLs

# ── relationships ────────────────────────────────────────────────────
linked_activities: []         # optional, list of activity IDs (full or prefix)

# ── taxonomy ─────────────────────────────────────────────────────────
tags: []                      # optional, list of strings
---
```

---

## Section groups

| Group | Question | Fields |
|---|---|---|
| Identity | What is this and when? | `id`, `title`, `created`, `kind`, `spec_version` |
| Classification | What kind, in what state, in what area? | `type`, `status`, `area` |
| Lifecycle | When was this last reviewed? | `last_reviewed` |
| Location | Where on disk does this live, where else? | `last_known_path`, `source_of_truth`, `locations` |
| Relationships | What other activities does this relate to? | `linked_activities` |
| Taxonomy | How is this tagged? | `tags` |

---

## Field reference

### Identity

#### `id` — required

- Type: string
- Format: `<slug>-<4-hex-hash>` (see SPEC.md §9.1)
- Immutable after creation. Folder renames update `last_known_path`, not `id`.
- Default-hidden in everyday UX (slug only); revealed with `--show-ids`.

#### `title` — required

- Type: string
- Default: derived from folder name at init time.
- Free to change; this is the human display name.

#### `created` — required

- Type: ISO 8601 date.
- Set once at `init`. Never modified.

#### `kind` — required

- Type: enum (fixed)
- Range: `activity`
- Reserved as an enum (not a free literal) so future activity kinds (e.g. `template`, `archetype`) can be added without schema rewrite.

#### `spec_version` — required

- Type: integer
- v1 value: `1`

### Classification

#### `type` — required

- Type: enum
- Range: `code` | `business` | `content` | `skill` | `automation` | `research` | `personal` | `inbox` | `other`
- Default: `other`
- Drives type-based filters and grouping.

#### `status` — required

- Type: enum
- Range:
  - `active` — currently moving or important now
  - `next` — likely to be picked up soon
  - `paused` — intentionally stopped, may resume
  - `planning` — being shaped but not executing
  - `maintenance` — exists, occasionally needs care
  - `reference` — useful material, not an open activity
  - `archive` — no longer active, kept for history
  - `unknown` — found but not yet classified
- Default: `active`

#### `area` — optional

- Type: string (free-form)
- Discovery system warns on near-duplicates (Levenshtein ≤ 2) at reindex.
- Optional strict mode (`[areas] strict = true`) errors on unknown values.

#### `priority` — optional (D87)

- Type: enum
- Range: `low` | `high` | `urgent`
- Default: omitted (treated as "normal"; there is no explicit `priority: normal`)
- Strict enum — unknown values rejected at read time.
- Set via `octopus set --activity <id> --priority X` or
  `octopus add activity --priority X`. Clear via the explicit-default
  values `normal` / `none` / `""` (D80 convention).
- Used by:
  - `octopus list activities --priority X` filter
  - `octopus dashboard` (priority callout section)
  - `octopus next` / `octopus impact` ranking inputs (R1, D89):
    activity priority contributes +20 (urgent) or +10 (high) to every
    task in that activity.

### Lifecycle

#### `last_reviewed` — optional

- Type: ISO 8601 date
- Default: equals `created` at init time.
- Updated by an explicit review verb (`octopus review <slug>` — pending v2) or manually.

### Location

#### `last_known_path` — machine-local, NOT in activity.md (D110)

- Stored in `.octopus/config.local.toml` as `last_known_path = "/absolute/path"`.
- **Not written to `activity.md`** — keeps the activity shareable/committable.
- Read precedence: `config.local.toml` → `activity.md` fallback (backwards compat) → empty.
- Updated on reindex when path differs from current. ID does not change.
- Enables rename detection (see SPEC.md §9.3).
- `octopus init` auto-gitignores `.octopus/config.local.toml` (git repos only). `octopus reindex` self-heals pre-D110 files: strips a stale `last_known_path` from `activity.md` and gitignores the local file. (D110.1)

#### `source_of_truth` — required

- Type: string
- Range: a path or URL. `"."` means this folder is the source of truth.
- Useful when an activity has multiple locations and one is canonical.

#### `locations` — optional

- Type: list of strings
- Range: additional paths/URLs where this activity also lives (other repos, vault folders, websites).
- Default: `[]`

### Relationships

#### `linked_activities` — optional

- Type: list of strings
- Range: activity IDs (full or unambiguous prefix per SPEC.md §8.2)
- Default: `[]`
- Use case: cross-project dependencies, related work streams.

### Taxonomy

#### `tags` — optional

- Type: list of strings
- Range: free-form. No validation.
- Default: `[]`

---

## On hiding activities

Activities have **no separate `archived` boolean** like tasks do. Instead, hidden activities use `status: archive`. The concept is similar to `task.archived: true` (hide from default views) but lives in the status enum because activities have a richer lifecycle (active / paused / planning / etc.) that already covers the use case.

Default views (`octopus list`, `octopus tui`) exclude activities with `status: archive | reference | unknown` unless `--all` is passed.

---

## Activity status vs task bucket

These are different concepts:

- **`activity.status`** = the *operational state of the project as a whole*. "Is this thing alive?"
- **`task.bucket`** = where *individual tasks within an activity* sit in their pipeline.

An activity can be `status: active` with zero tasks in any `now` bucket. An activity can be `status: paused` with old tasks still in `next` (they're just not being worked).

The two axes don't constrain each other.

---

## Validation

### MUST reject

- Missing any required field.
- `type` or `status` values outside their enum.
- `created` or `last_reviewed` malformed.
- `spec_version` greater than supported.

### SHOULD warn

- `status: active` but no task touched in > 60 days (stale activity).
- `last_reviewed` > 90 days ago.
- `area` near-duplicate of existing area (Levenshtein ≤ 2).

### MUST preserve

- Unknown frontmatter fields on read-write cycles.
- Body content byte-for-byte.

---

## Body conventions

The body below frontmatter is free-form markdown. Conventional opening:

```markdown
# <title>

Brief description of the activity, its purpose, its current state in plain language.

## Goals

(optional — what success looks like)

## References

(optional — relevant links, related activities, project docs)
```

None of these sections are required. The CLI does not enforce body structure.

---

## Reference

- `../SPEC.md §3` — authoritative contract.
- `CLI-VERBS.md` — activity-level verbs (`init`, `where`, `rename`, `archive`).
- `CRITICAL-DEPENDENCIES.md` — validation rules.

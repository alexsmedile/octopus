---
status: draft
updated: 2026-05-22
relates_to: SPEC.md §4, CLI-VERBS.md, CRITICAL-DEPENDENCIES.md, AXIS-MODEL.md
---

# Task schema — v1

`tasks/<slug>.md` frontmatter contract. Operated on by the CLI verbs documented in `CLI-VERBS.md`; validated by the rules in `CRITICAL-DEPENDENCIES.md`. Structural framing in `AXIS-MODEL.md`.

**Field order in the file matters.** Frontmatter fields are written in the order below. This optimizes spatial memory — you always look in the same place for the same property.

**Default-omission principle.** Any field that equals its default value is *omitted entirely* from the frontmatter. A normal-priority task has no `priority:` line. A human-actor task has no `actor:` line. The frontmatter only contains fields that carry non-default signal.

---

## Field name aliasing

The default field names below match common Obsidian / Tasks plugin conventions. Teams or projects that prefer different names can remap them via config:

```toml
# ~/.config/octopus/config.toml          (system-wide default)
#   OR
# .octopus/config.toml                   (project override; wins over system-wide)

[task.fields]
created     = "creation_date"            # default: created
due         = "due_date"                 # default: due
scheduled   = "do_date"                  # default: scheduled
start_date  = "started"                  # default: start_date
end_date    = "completed"                # default: end_date
```

Implementations MUST:
- Read both the canonical name and any configured alias.
- Write using the configured name (or canonical if no alias).
- Reject ambiguity (file has both `created` and `creation_date` set) with a clear error.

Aliasing applies only to **field names**, not values or semantics. The axis model is unchanged regardless of names.

---

## Canonical order

```yaml
---
# ── identity ─────────────────────────────────────────────────────────
title:                        # required, string
created:                      # required, ISO date (YYYY-MM-DD)

# ── workflow ─────────────────────────────────────────────────────────
bucket: backlog               # required, enum: backlog | next | now | done | dropped
stage:                        # optional, free-form (per-activity domain workflow)

# ── runtime ──────────────────────────────────────────────────────────
run_state:                    # optional, enum: queued | running | finished | failed   (absent = idle)

# ── attention / impediment / visibility ──────────────────────────────
pinned:                       # optional, boolean: true                                (absent or false = not pinned)
issue:                        # optional, enum: blocked | waiting
blocked_by:                   # required if issue: blocked
waiting_for:                  # required if issue: waiting
archived:                     # optional, boolean: true                                (absent or false = visible)

# ── dates ────────────────────────────────────────────────────────────
due:                          # optional, ISO date — hard deadline
scheduled:                    # optional, ISO date — intended work date
start_date:                   # optional, ISO date — when work began
end_date:                     # optional, ISO date — when bucket → done | dropped

# ── prioritization ───────────────────────────────────────────────────
priority:                     # optional, enum: low | high | urgent                    (absent = normal)
energy:                       # optional, enum: low | mid | high

# ── actors ───────────────────────────────────────────────────────────
actor:                        # optional, enum: human | ai | automation                (absent = human)
owner:                        # optional, string

# ── taxonomy ─────────────────────────────────────────────────────────
tags:                         # optional, list of strings                              (absent = [])

# ── integrations & provenance ────────────────────────────────────────
external_refs:                # optional, map: <adapter-name> → <opaque-string>
import_date:                  # optional, ISO date
imported_from:                # optional, string
---
```

A typical fresh capture writes only the required fields plus the bucket if non-default:

```yaml
---
title: Fix the webhook auth bug
created: 2026-05-22
bucket: next
priority: urgent
---
```

Four lines. Every line carries non-default signal.

---

## Section groups explained

The schema is grouped into seven semantic sections. Each group answers one question:

| Group | Question | Fields |
|---|---|---|
| Identity | What is this? When was it captured? | `title`, `created` |
| Workflow | Where in the pipeline + what domain stage? | `bucket`, `stage` |
| Runtime | Is a machine currently executing this? | `run_state` |
| Attention / impediment / visibility | Is this on my mind? Is it stuck? Should I see it? | `pinned`, `issue`, `blocked_by`, `waiting_for`, `archived` |
| Dates | When does it need to happen? When did it? | `due`, `scheduled`, `start_date`, `end_date` |
| Prioritization | How urgent? How costly? | `priority`, `energy` |
| Actors | Who does it? Who owns it? | `actor`, `owner` |
| Taxonomy | How is it categorized? | `tags` |
| Integrations | Where else does it live? | `external_refs`, `import_date`, `imported_from` |

`actor` and `owner` are deliberately adjacent.

---

## Field reference

### Identity

#### `title` — required

- Type: string
- Range: non-empty. Preserved verbatim (pre-slugification).

#### `created` — required

- Type: ISO 8601 date (`YYYY-MM-DD`)
- Set once at creation. Never modified.
- Matches Obsidian Tasks plugin convention. Aliasable per project.

### Workflow

#### `bucket` — required

- Type: enum
- Range: `backlog` | `next` | `now` | `done` | `dropped`
- Default: `backlog`
- **Definitions**:
  - `backlog` — captured intent, not yet shaped. Parking lot of ideas.
  - `next` — decided and ready. Has a clear next action.
  - `now` — selected for current work block. Small pile.
  - `done` — completed successfully. Terminal. Requires `end_date`.
  - `dropped` — intentionally abandoned. Terminal. Requires `end_date`.
- In **folder mode**, the field value MUST match the parent folder name.

#### `stage` — optional

- Type: string (free-form)
- Default: absent.
- Per-activity domain workflow marker (e.g. `idea`, `draft`, `editing`, `published` for content; `spec`, `impl`, `review` for code).
- No validation in v1 (free-form). Per-activity strict mode is TODO.

### Runtime

#### `run_state` — optional

- Type: enum
- Range: `queued` | `running` | `finished` | `failed`
- Default: absent = idle.
- Captures **machine execution state**, distinct from workflow state (`bucket`) and attention (`pinned`).
- A task can be `bucket: now, run_state: idle` (you're working on it manually) or `bucket: now, run_state: running` (an agent is executing it now).
- Implementations MAY auto-set this when a coding-agent or automation begins/ends a run. The field is informational; verbs don't enforce it.

### Attention / impediment / visibility

#### `pinned` — optional

- Type: boolean
- Range: `true` | (absent)
- Default: absent (not pinned). Field is omitted entirely when not true.
- Auto-set true by: `pin`, `focus`, `capture --now`
- Auto-set false (field removed) by: `unpin`, `finish`, `drop`, `park`
- **Pinned tasks always sort first in list views**, regardless of bucket or other order.
- Semantics: "I want to see this prominently. Marked for attention."

#### `issue` — optional

- Type: enum
- Range: `blocked` | `waiting`
- Default: absent (no impediment).
- MUST be paired with the corresponding context field (`blocked_by` or `waiting_for`).

#### `blocked_by` — required if `issue: blocked`

- Type: string
- Range: free-form description of the internal blocker.

#### `waiting_for` — required if `issue: waiting`

- Type: string
- Range: free-form, OR a task cross-reference `<activity-slug>/<task-slug>`.

#### `archived` — optional

- Type: boolean
- Range: `true` | (absent)
- Default: absent (visible). Field is omitted entirely when not true.
- Hides task from default views; orthogonal to all other state.

### Dates

#### `due` — optional

- Type: ISO 8601 date
- Semantics: hard deadline.

#### `scheduled` — optional

- Type: ISO 8601 date
- Semantics: intended work date. Independent of `due`.

#### `start_date` — optional

- Type: ISO 8601 date
- Set by `start` (if absent). Presence indicates work has begun.
- MUST be present whenever `bucket` is `done` (a done task had to start at some point).
- MAY be absent when `bucket` is `dropped` (you can drop something you never started).

#### `end_date` — optional

- Type: ISO 8601 date
- Set by `finish` and `drop` (if absent).
- MUST be present whenever `bucket` is `done` or `dropped`.
- Cleared by `start` when resuming from a terminal bucket.

### Prioritization

#### `priority` — optional

- Type: enum
- Range: `low` | `high` | `urgent`
- Default: absent (normal). Field is omitted entirely for normal-priority tasks.
- Four effective levels: low / (absent=normal) / high / urgent.

#### `energy` — optional

- Type: enum
- Range: `low` | `mid` | `high`
- Default: absent.
- Required mental effort. Drives "what can I tackle right now" filters.

### Actors

#### `actor` — optional

- Type: enum
- Range: `human` | `ai` | `automation`
- Default: absent = `human`. Field is omitted entirely for human tasks.
- `human` — a person acts.
- `ai` — an LLM/agent (Claude Code, Codex) acts.
- `automation` — a deterministic script or scheduled job acts.

#### `owner` — optional

- Type: string
- Range: free-form (typically a username).

### Taxonomy

#### `tags` — optional

- Type: list of strings
- Range: free-form. No validation.
- Default: absent = empty list. Field is omitted entirely when no tags.

### Integrations & provenance

#### `external_refs` — optional

- Type: map of strings
- Range: keys are adapter names (lowercase, hyphen-allowed); values are opaque strings.
- Implementations MUST preserve unknown keys on read-write cycles.

#### `import_date` — optional

- Type: ISO 8601 date
- Semantics: when imported from another system.

#### `imported_from` — optional

- Type: string
- Range: free-form source identifier (e.g. `apple-reminders`, `notion-export-2025-12`).

---

## Lifecycle through dates, not status

The schema has no `status` field. Lifecycle is encoded purely in:

| Question | Answer |
|---|---|
| "Has this been started?" | `start_date` is present. |
| "Is this currently in flight?" | `start_date` present AND `bucket` NOT IN (`done`, `dropped`). |
| "Is this finished?" | `bucket: done`. |
| "Was this abandoned?" | `bucket: dropped`. |
| "What's unfinished?" (open loops) | `bucket NOT IN (done, dropped) AND NOT archived`. |

The "open loops" query is what `octopus loops` returns.

---

## What's NOT in the v1 schema

Explicitly excluded — see `TODO.md` and `_archive/docs/_task.schema.md`.

- `status` — collapsed into `bucket` (terminal states) + dates (lifecycle).
- `kind` — folder location determines type. Tasks live in `tasks/`, handoffs in `handoffs/`, notes in `memory.md`.
- `recurrence`, `last_run`, `next_run` — routines are deferred (see TODO.md).
- `needs`, `project`, `subtasks`, `parent`, `children`, `see_also`, `ai_status`, `handoff_to`, `handoff_status`, `handoff_at`, `reviewed_at`, `reviewed_by`, `estimate`, `time_spent` — dropped from archive.

---

## Reference

- `../SPEC.md §4` — the canonical contract.
- `CLI-VERBS.md` — verbs that produce these field changes.
- `CRITICAL-DEPENDENCIES.md` — validation rules between fields.
- `AXIS-MODEL.md` — five-axis structural framing.

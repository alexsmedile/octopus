# Task frontmatter — v1

A task lives at `<activity>/.octopus/tasks/<bucket>/<slug>.md` (folder mode, default) or `<activity>/.octopus/tasks/<slug>.md` (field mode, opt-in). Frontmatter contract follows.

## Canonical order

```yaml
---
# identity
title:                    # required, string
created:                  # required, ISO date (YYYY-MM-DD)

# pipeline axis
bucket: backlog           # required, enum (see below). Default backlog.
stage:                    # optional, free-form per activity

# runtime axis
run_state:                # optional, enum

# attention / impediment / visibility
pinned:                   # optional, true (absent = not pinned)
issue:                    # optional, enum (blocked | waiting)
blocked_by:               # optional, required when issue=blocked
waiting_for:              # optional, required when issue=waiting
archived:                 # optional, true (absent = visible)

# dates
due:                      # optional, ISO date
scheduled:                # optional, ISO date
start_date:               # optional, ISO date (set by `octopus start`)
end_date:                 # optional, ISO date (set by `octopus finish`/`drop`)

# prioritization
priority:                 # optional, enum (absent = normal)
energy:                   # optional, enum

# actors
actor:                    # optional, enum (absent = human)
owner:                    # optional, free-form

# taxonomy
tags: []                  # optional, list of strings

# integrations & provenance
external_refs: {}         # optional, dict (e.g. reminders: <id>, github: <url>)
import_date:              # optional, ISO date
imported_from:            # optional, string
---
```

## Enums

| Field | Values |
|---|---|
| `bucket` | `backlog`, `next`, `now`, `done`, `dropped` |
| `run_state` | `queued`, `running`, `finished`, `failed` (absent = idle) |
| `issue` | `blocked`, `waiting` (absent = none) |
| `priority` | `low`, `high`, `urgent` (absent = normal — there is no `medium`/`normal` value) |
| `energy` | `low`, `mid`, `high` |
| `actor` | `human`, `ai`, `automation` (absent = `human`) |

## Default-omission rule

Any field equaling its default value MUST be omitted from the frontmatter. The parser treats absence as default. Writing the default explicitly is rejected by the CLI but tolerated on read.

Defaults that get omitted:
- `actor: human`
- `priority: <normal>` (i.e., never write a priority for a normal-priority task)
- `pinned: false` → write nothing
- `archived: false` → write nothing
- `tags: []`, `external_refs: {}`, `related_tasks: []` → write nothing

A minimal capture is three lines:

```yaml
---
title: Fix the webhook auth bug
created: 2026-05-23
bucket: backlog
---
```

## Required-by-state

- `bucket: done` requires both `start_date` and `end_date`.
- `bucket: dropped` requires `end_date` (`start_date` optional — you can drop before starting).
- `issue: blocked` requires `blocked_by`.
- `issue: waiting` requires `waiting_for`.

## Forbidden in v1

These legacy fields are rejected by the parser (writing them surfaces a hard error):
- `status` — replaced by `bucket` + dates + `run_state`
- `kind` — folder location implies kind
- `open` — replaced by `pinned`

## Cross-field invariants

See `../critical-dependencies.md` for the full validation matrix. Most-cited rules:

- `bucket` in `{done, dropped}` cannot have `pinned: true`.
- `bucket` in `{done, dropped}` cannot have `issue` set.
- `end_date` present requires `bucket` in `{done, dropped}`.
- `end_date >= start_date` when both are set.

## Behavior of `start_date` on resume

`octopus start` is idempotent. On a terminal task, it clears `end_date` and moves the file back to `now/`, preserving the original `start_date` (the resume is not a fresh start).

## Slug

Filename slug (without `.md`) becomes the task's identity. Slugs are generated from `title` by the CLI; collisions get a numeric suffix. Never rename a task file by hand — use `octopus rename` so external refs update.

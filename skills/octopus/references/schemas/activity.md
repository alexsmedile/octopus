# Activity frontmatter — v1

`activity.md` is the marker file that turns a folder into an Octopus activity. It sits at `<activity>/.octopus/activity.md`.

## Canonical order

```yaml
---
# identity
id:                       # required, string (kebab-case, stable, never reused)
title:                    # required, string
created:                  # required, ISO date
kind: activity            # required, literal "activity" in v1

# classification
type: other               # required, enum (see below). Default "other".
status: active            # required, enum. Default "active".
area:                     # optional, free-form (e.g. "work", "personal")
priority:                 # optional enum (D87): low | high | urgent. Omit = normal.
spec_version: 1           # required, integer. v1 = 1.
octopus_version:          # auto-managed (D111): CLI version that last wrote this folder. Never set by hand.

# discovery / linking  (D110: last_known_path NOT in activity.md — see config.local.toml)
source_of_truth: "."      # required, string — usually "." (this folder is canonical)
locations: []             # optional, list of alternate paths (e.g. mirrored copy)
linked_activities: []     # optional, list of activity IDs

# review cadence
last_reviewed:            # optional, ISO date

# taxonomy
tags: []                  # optional
---
```

## Enums

| Field | Values |
|---|---|
| `type` | `code`, `business`, `content`, `skill`, `automation`, `research`, `personal`, `inbox`, `other` |
| `status` | `active`, `next`, `paused`, `planning`, `maintenance`, `reference`, `archive`, `unknown` |
| `kind` | `activity` (literal — no other value is valid in v1) |
| `priority` | `low`, `high`, `urgent` (omit for normal — D87) |

## Identity rules

- `id` is stable across renames/moves. Once assigned, never change it.
- `id` should be kebab-case and unique within the Octopus index (`~/.local/share/octopus/index.db`).
- Slug collisions across activities are allowed; `id` is the disambiguator.

## Path tracking (D110)

`last_known_path` is **not in `activity.md`**. It lives in `.octopus/config.local.toml`:

```toml
last_known_path = "/absolute/path/to/activity"
```

- `octopus reindex` writes this file when it first sees the activity (migration) or when the path changes (rename detection).
- **`octopus init` auto-adds `.octopus/config.local.toml` to `.gitignore`** (git repos only) — no manual step. It's machine-local; never commit it.
- **Self-heal:** if an old `activity.md` still carries a `last_known_path` line, `octopus reindex` strips it (and gitignores the local file). Run `octopus reindex` once on legacy repos to converge them.
- Backwards compat: if `config.local.toml` is absent, reindex reads `last_known_path` from `activity.md` and migrates it.

`locations: []` is for **deliberate** multi-path scenarios (e.g. the same activity exists at `/Users/alex/work/foo` and `/Users/alex/Dropbox/work/foo`). Reindex preserves entries here.

## Version stamp (D111)

`octopus_version` records **which CLI version last wrote the folder**. Auto-managed — never set it by hand.

- Stamped with the running CLI version on *every* `activity.md` write (init, reindex, status/field edits). A stale value is always overwritten.
- Written to **two places** (same split as D110):
  - `activity.md` → shared, committed. "Last version in any clone."
  - `.octopus/config.local.toml` → `octopus_version = "1.6.0"`, machine-local, gitignored. "Last version on this machine."
- **Read precedence:** `config.local.toml` → `activity.md` → `""`.
- See it: `octopus status` shows the row `Octopus version`; `octopus status --json` emits key `octopus_version`. Pre-D111 folders read `""` until their next write.

## Forbidden / reserved

- `kind` must equal `"activity"` literally. Any other value is rejected.
- `spec_version` other than `1` is rejected (until v2 ships).

## Validation summary

The parser hard-rejects:
- Missing `id`, `title`, or `kind`.
- `type` not in enum.
- `status` not in enum.
- `kind != "activity"`.
- `spec_version != 1`.

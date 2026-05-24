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

# discovery / linking
last_known_path:          # required, string — last absolute path Octopus saw the folder at
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
| `type` | `code`, `business`, `content`, `skill`, `automation`, `research`, `personal`, `other` |
| `status` | `active`, `next`, `paused`, `planning`, `maintenance`, `reference`, `archive`, `unknown` |
| `kind` | `activity` (literal — no other value is valid in v1) |
| `priority` | `low`, `high`, `urgent` (omit for normal — D87) |

## Identity rules

- `id` is stable across renames/moves. Once assigned, never change it.
- `id` should be kebab-case and unique within the Octopus index (`~/.local/share/octopus/index.db`).
- Slug collisions across activities are allowed; `id` is the disambiguator.

## Path tracking

`last_known_path` is updated by `octopus reindex` whenever the activity is rediscovered at a new absolute path. Hand-editing is allowed but the next reindex will rewrite it. Don't fight it.

`locations: []` is for **deliberate** multi-path scenarios (e.g. the same activity exists at `/Users/alex/work/foo` and `/Users/alex/Dropbox/work/foo`). Reindex preserves entries here.

## Forbidden / reserved

- `kind` must equal `"activity"` literally. Any other value is rejected.
- `spec_version` other than `1` is rejected (until v2 ships).

## Validation summary

The parser hard-rejects:
- Missing `id`, `title`, `last_known_path`, or `kind`.
- `type` not in enum.
- `status` not in enum.
- `kind != "activity"`.
- `spec_version != 1`.

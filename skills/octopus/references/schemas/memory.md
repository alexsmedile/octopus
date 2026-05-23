# Memory file — v1

`<activity>/.octopus/memory.md` is the activity's accumulated context. It survives across sessions and is the slowest-decaying continuity artifact (sessions log work; handoffs hand off; memory remembers).

## Two-zone structure

The file is split by a marker. Everything *above* the marker is user-owned prose, never touched by the CLI. Everything *below* is CLI-managed (sections, entries, ordering).

```markdown
---
activity: <activity-id>
last_updated: 2026-05-23
summary: |
  One-paragraph stable identity. What this activity is, why it exists.
tags: []
---

# Memory: <activity title>

_(free-form user-written prose — context, intro, anything. CLI never edits this.)_

<!-- octopus-managed-below -->

## Decisions
...

## State
...
```

**The marker `<!-- octopus-managed-below -->` is load-bearing.** If a user deletes it, the next CLI write re-inserts it (with a stderr warning) before the first canonical section.

## Frontmatter

```yaml
---
activity:                 # required, activity ID (must match activity.md `id`)
last_updated:             # required, ISO date. Bumped by every CLI write.
summary:                  # optional, string (use YAML `|` for multi-line). The stable identity.
tags: []                  # optional
---
```

## Five canonical sections (managed zone)

| Section | Purpose | Append default? |
|---|---|---|
| `## Decisions` | Locked choices and *why* | no |
| `## Open Questions` | Unresolved questions; resolve by prepending `RESOLVED: ` to the entry text | no |
| `## Context` | Background, prior art, environment, conventions | no |
| `## Notes` | Catch-all. **Default `memory append` target.** | **yes** |
| `## State` | Append-only "where we are now" — latest entry is treated as current state by readers | no |

Sections are inserted in **canonical order** (the order above) regardless of the order they're first created. The CLI re-orders on append if needed.

## Entry format

Inside a section, each entry is a level-3 heading with **minute-precision** timestamp, followed by free-form markdown:

```markdown
## Decisions

### 2026-05-23 14:32
Chose State-as-section over State-as-frontmatter. Reason: State is append-only with history.

### 2026-05-23 18:00
Locked five canonical memory sections. See DECISIONS D41.
```

Minute precision (not second) — distinguishes memory entries from session log entries at a glance.

## Section name resolution

The CLI accepts prefix matches for `--section` flags:

| Input | Resolves to |
|---|---|
| `decisions`, `dec` | Decisions |
| `open`, `open q`, `o` | Open Questions |
| `context`, `ctx`, `c` | Context |
| `notes`, `n` | Notes |
| `state`, `s` | State |

Ambiguous prefix → error with suggested alternatives.

## Default-show preview

`octopus memory show` (no flags) renders:
- frontmatter `summary` (if set)
- `## State` — latest 3 entries
- `## Open Questions` — latest 3 entries
- `## Decisions` — latest 3 entries

Each previewed section gets a header `(showing latest N of M)` and, if `M > 3`, a footer `[K more — run \`octopus memory show --section <name>\` for all]`.

`## Context` and `## Notes` are NOT in the default preview — too large/noisy. Show them explicitly with `--section`.

## State vs summary

These are easy to confuse:

| | `summary` (frontmatter) | `## State` (section) |
|---|---|---|
| Lifecycle | Updated rarely | Appended often |
| Purpose | Stable identity ("what is this activity") | Current ground state ("where am I now") |
| Reader | First-time visitor | Returning worker |
| Set via | `octopus memory summary set "<text>"` | `octopus memory state set "<text>"` (alias for `append --section state`) |

## Resolution of open questions

Convention only — no separate verb in v1. To mark a question resolved, prepend `RESOLVED:` to the entry text in place:

```markdown
### 2026-05-22 11:00
RESOLVED: Should State be a section or frontmatter? → Section (D41).
```

## Validation

- `activity` must match the parent `activity.md` `id`.
- `last_updated` must be present and parseable as a date.
- Unknown frontmatter keys are preserved on round-trip.
- Body bytes outside the managed zone are preserved byte-for-byte.

## Hand-editing safety

Allowed:
- Adding non-canonical sections (e.g. `## Risks`) anywhere in the managed zone. CLI ignores them on writes but preserves their position.
- Editing entry text in place.
- Reordering entries within a section.

NOT allowed (will surface as a warning or hard error):
- Renaming a canonical section heading (the CLI will create a fresh one and the renamed one becomes orphan).
- Removing the `<!-- octopus-managed-below -->` marker (re-inserted with stderr warn).
- Removing the frontmatter.

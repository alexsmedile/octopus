---
status: draft
updated: 2026-05-23
relates_to: SPEC.md §7, CLI-VERBS.md
---

# Memory schema — v1

`memory.md` contract. One per activity. The slow-decay layer: accumulated context that survives sessions, decisions made, open questions, useful background.

Memory is **append-only via CLI** in the managed zone. The user-curated `summary:` frontmatter field is the human-facing entry point.

---

## Field name aliasing

```toml
[memory.fields]
last_updated = "modified"
summary      = "tldr"
```

---

## Two-zone structure

```markdown
---
activity: shift-a3f9
last_updated: 2026-05-22
summary: |
  The Shift project is the rebrand of the office automation product.
  Pre-launch — landing in Astro, pricing tier 3 still pending.
tags: []
---

# Memory: Shift

(free-form user-authored intro paragraph)

<!-- octopus-managed-below -->

## Decisions

### 2026-05-18 18:45
Switched landing framework from Webflow to Astro.

## Open Questions

### 2026-05-20 11:08
Pricing tier 3 needs validation with two customers.

## Context

(empty)

## Notes

(empty)

## State

### 2026-05-22 14:32
Paused while waiting on legal sign-off for token storage. Picking back up
needs: re-read the auth migration doc, ping Sarah re: token format.
```

### Above the marker: user-curated

- Frontmatter (CLI may update only `last_updated` and `summary` via explicit verbs)
- `# Memory: <title>` heading
- Free-form intro paragraph(s)

CLI MUST NOT modify any other content above the marker.

### Below the marker: machine-managed

- Five canonical sections (see below)
- Dated entries appended by `octopus memory append`
- CLI MAY append new entries; MUST NOT reformat or rewrite existing entries

---

## Frontmatter schema

```yaml
---
activity:                     # required, string — activity id (or unambiguous slug)
last_updated:                 # required, ISO date
summary:                      # optional, string (single line or YAML block scalar)
---
```

### `activity` — required

- Type: string
- Range: the parent activity's `id` (or unambiguous slug).
- Cross-file grep-ability: enables `grep -r "activity: shift-a3f9"` across the index.

### `last_updated` — required

- Type: ISO 8601 date
- Updated by the CLI on any write (frontmatter or body).
- Manual edits bump this on the next CLI write.

### `summary` — optional

- Type: string (single-line or multi-line via YAML block scalar `|`)
- Range: free-form markdown allowed.
- Default: absent.
- Set via `octopus memory summary set "<text>"` (one-line) or `octopus memory summary set` (opens $EDITOR).

---

## The marker

```
<!-- octopus-managed-below -->
```

- Literal string, on its own line.
- Separates the user-curated zone from the machine-managed zone.
- MUST be preserved on any CLI write.
- If removed by the user, next CLI append re-inserts it before the first managed section heading and emits a stderr warning.
- The marker is invisible in rendered markdown (HTML comment) — it doesn't clutter the visible doc.

---

## Canonical sections (below the marker)

Exactly five, in this order. Implementations create them lazily on first append.

| Heading | Purpose | Default append target |
|---|---|---|
| `## Decisions` | Choices made and why. | — |
| `## Open Questions` | Unresolved questions. Convention: prefix entry with `RESOLVED: ...` when answered. | — |
| `## Context` | Background, history, dependencies. | — |
| `## Notes` | Catch-all jottings. | ✓ (default for `memory append`) |
| `## State` | Current paused state — append-only; the latest entry is the active state. | — |

> History note: an earlier draft had `## Log` as the fifth section + default
> append target. It was dropped because it overlapped with `octopus session log`
> (per-session work log). `## State` replaces it. The append-only contract is
> unchanged; the latest `## State` entry is treated as "current" by readers.
> Default `memory append` target moved from Log to Notes. Locked in DECISIONS D41.

---

## Entry format

Each entry is a level-3 heading with a datetime, followed by free-form body:

```markdown
### 2026-05-22 14:32
<entry body — markdown, multi-line, anything>
```

### Datetime format

- `YYYY-MM-DD HH:MM` (local time, **minute precision, no seconds, no timezone suffix**).
- Implementations MUST use exactly this format on write.
- Note: this is intentionally lower-precision than session frontmatter (`YYYY-MM-DDTHH:MM:SS`). Memory entries are journal-style; minute precision is sufficient.
- Entries within a section are chronological (newest at the bottom).

---

## CLI verbs (memory-specific)

```
octopus memory append "<note>"                       # appends to ## Notes (default)
octopus memory append "<note>" --section decisions   # appends to ## Decisions
octopus memory append "<note>" --section open        # appends to ## Open Questions
octopus memory append "<note>" --section context     # appends to ## Context
octopus memory append "<note>" --section notes       # explicit ## Notes
octopus memory append "<note>" --section state       # appends to ## State

octopus memory show                                  # summary + State/Open/Decisions previews
octopus memory show --section decisions              # full section
octopus memory show --all                            # entire file rendered
octopus memory summary                               # print frontmatter summary
octopus memory summary set "<text>"                  # set summary (one-line)
octopus memory summary set                           # set summary ($EDITOR)

octopus memory state                                 # alias for `memory show --section state`
octopus memory state set "<text>"                    # convenience: `memory append --section state`
octopus memory state set                             # opens $EDITOR for a State entry
```

Partial section names accepted (`--section open` matches "Open Questions"; `s` is ambiguous so use `state` or `summary` explicitly).

### Default `memory show` output

When invoked with no flags, `memory show` renders a preview of the three
high-signal sections — **State**, **Open Questions**, **Decisions** — each
showing the latest 3 entries with a header `(showing latest 3 of N)`. When
N > 3, a dim footer `[N-3 more — run \`octopus memory show --section <name>\` for all]`
is appended. `## Context` and `## Notes` are omitted from the default view;
use `--section <name>` or `--all` to surface them.

---

## Append behavior

Every append:

1. Load file (create with scaffold if missing).
2. Validate `<note>` is non-empty.
3. Locate `## <Section>` heading below the marker.
4. If section heading absent, create it before appending.
5. Append a dated entry at the bottom of that section:
   ```markdown

   ### YYYY-MM-DD HH:MM
   <note body>
   ```
6. Update `last_updated:` in frontmatter to today.
7. Write file.

Implementations MUST NOT:
- Reformat existing entries.
- Reorder existing entries.
- Move entries between sections.
- Touch anything above the marker (except `last_updated` and `summary` via explicit verb).

---

## Hand-editing

Users are free to hand-edit the file. Implementations MUST respect:

- New entries written by hand in any section → preserved on next CLI append.
- Section headings renamed by user (e.g. `## Decisions` → `## Key Decisions`) → CLI re-creates `## Decisions` on next append; warns about possible duplication on reindex.
- Section order changed by user → CLI appends to whatever heading matches the requested section, preserving the user's order.
- User-added sections (e.g. `## Risks`) → preserved; CLI warns on reindex but doesn't touch them.
- Marker deleted → re-inserted with stderr warning on next append.

---

## Validation

### MUST reject

- Missing `activity` or `last_updated`.
- `last_updated` not parseable as ISO 8601 date.
- Append with empty `<note>` argument.

### SHOULD warn

- Sections present below the marker that are not in the canonical five.
- Section order differing from canonical.
- Marker missing on a memory.md with body content.
- `activity` field doesn't match the parent activity's `id`.

### MUST preserve

- Unknown frontmatter fields.
- All body content byte-for-byte except the targeted section on append.

---

## What memory is NOT

- **Not a task tracker.** Tasks live in `tasks/`.
- **Not a session log.** Sessions live in `sessions/`. Memory captures cross-session context.
- **Not a handoff.** Handoffs are deliberate transfers; memory is passive accumulation.
- **Not the activity body.** `activity.md` describes *what* the activity is; memory describes *how* it has evolved.

---

## Indexing

Not indexed in v1. SQLite tracks only file existence and `mtime`. `octopus memory show` reads the file directly.

v2 may add FTS5 full-text search across all memory files for `octopus memory search "<query>"`.

---

## Reference

- `../SPEC.md §7` — authoritative contract.
- `CLI-VERBS.md` — memory verbs (`memory append`, `summary set`, `show`).
- `CRITICAL-DEPENDENCIES.md` — validation rules.

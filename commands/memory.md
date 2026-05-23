---
description: Show or append to the activity memory.
argument-hint: "[section: decisions|open|context|notes|state] [text]"
allowed-tools:
  - Bash(octopus *)
---

# /octopus:memory

Read or write the activity's accumulated memory.

## Modes

**Read (default)** — no arguments:
- Run `octopus memory show` for the default preview (summary + State + last 3 Decisions + last 3 Open Questions).

**Read a specific section** — first arg matches a section name:
- Run `octopus memory show --section <section>`.

**Append** — args look like `<section> <text>` or just `<text>`:
- If section omitted, default is `notes`.
- Run `octopus memory append "<text>" --section <section>`.

## Canonical sections

| Section | Purpose |
|---|---|
| `decisions` | Locked choices (what we decided and why) |
| `open` (`Open Questions`) | Unresolved questions; resolve by prepending `RESOLVED:` to the entry |
| `context` | Background, prior art, environment |
| `notes` | Catch-all; default append target |
| `state` | Append-only journal of "where we are right now" — latest entry = current state |

## Notes

- `summary:` (frontmatter) is the stable identity. Set with `octopus memory summary set "<text>"`.
- `state` differs from `summary`: state changes session to session; summary should stay relatively stable.

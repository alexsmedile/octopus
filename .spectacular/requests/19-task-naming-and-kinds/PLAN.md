---
status: backlog
priority: medium
owner: alex
updated: 2026-05-23
summary: "Lock the task title formula (imperative verb result) AND explore task kinds + area as first-class schema fields. Surface chips in chat + TUI."
related:
  - 05-tui
  - 06-adapter-framework
gates: []
---

# Task naming + kinds

## Goal

Make task titles **reliable to read at a glance** and add structured metadata (kind, area) that the TUI and the chat skill can surface as visible chips — without baking it into the title string.

## Why

Audit on 2026-05-23 showed 11 live tasks across four different naming styles:

- `Add Apple Reminders pull adapter (request 09)` — verb + noun + parenthetical
- `Decide forget verb semantics` — verb + noun (no result)
- `Friction: titles with 'request NN' duplicate metadata in slugs` — type-prefix bug report
- `Polish error messages and rich output styling` — verb + noun
- `Verify run_state semantics with a real automation` — verb + noun + qualifier

No way to filter "all bugs" or "all CLI changes" without a grep+squint pass. Some titles carry kind in a prefix (`Friction:`), some in a parenthetical (`(request NN)`), most carry nothing.

## Scope

### Phase 1 — Naming formula (decided)

Lock **F1 pure imperative**:

```
verb result
```

Examples (renaming the 11 audit cases):

| Old | New |
|---|---|
| Add Apple Reminders pull adapter (request 09) | pull apple reminders into backlog |
| Decide forget verb semantics | define forget verb semantics |
| Friction: titles with 'request NN' duplicate metadata in slugs | drop "(request NN)" suffix from task titles |
| Polish error messages and rich output styling | polish error messages + rich output |
| Verify run_state semantics with a real automation | verify run_state in a real automation |

Rules:
- Start with an imperative verb. Common set: `build / fix / drop / polish / verify / define / wire / migrate / port / pull / push / refactor / lint / document`.
- No `(request NN)` suffix — the request link belongs in a frontmatter field (`request_id`?) or `tags`.
- No `Friction:` / `Bug:` / `Feat:` prefix — kind goes in frontmatter, rendered as a chip.
- Lowercase by default. Sentence case only if the word naturally takes it (proper nouns).
- ~50-character soft cap; truncate to fit Focus quadrant width when displayed.

### Phase 2 — Task kinds (open)

Explore whether `kind` deserves a first-class enum field or stays in `tags`.

#### Candidate enum

| `kind` | When to use | Example |
|---|---|---|
| `feat` | new capability shipped to users | pull apple reminders into backlog |
| `bug` | something is broken | drop "(request NN)" suffix from task titles |
| `spec` | a decision needs locking before code | define forget verb semantics |
| `polish` | UX/output quality, not behavior | polish error messages + rich output |
| `test` | verification work (manual or automated) | verify run_state in a real automation |
| `chore` | maintenance, cleanup, deps, refactor | port CLI verbs to octopus.actions |
| `doc` | README / changelog / reference updates | document mascot animation flow |

7 kinds is on the high end. Possible compressions to consider:
- Merge `polish` into `feat`? (no — polish has lower urgency signal)
- Merge `chore` + `doc`? (probably yes — call it `chore`)
- Drop `spec`? (no — pre-implementation thinking is a real category in this project)

#### Open questions to resolve before locking

1. **Required or optional?** Probably optional v1; titles without `kind` render with no chip.
2. **One value or many?** Probably one. Tasks rarely cross categories cleanly.
3. **Mutable?** Yes — a `spec` task often becomes a `feat` task once decided. Allow `octopus set kind=feat`.
4. **Does the index store it?** Yes — needed to query `octopus list --kind bug`.

### Phase 3 — Area / component (open)

Whether area gets its own enum or stays in `tags`.

#### Candidate areas (project-aware enum)

`cli`, `tui`, `tasks`, `sessions`, `memory`, `handoffs`, `index`, `reminders`, `obsidian`, `claude`, `tests`, `docs`, `build`

But these grow as the project does. **Risk:** locking an `area` enum means PRs to add fields every time a new adapter lands. Vs. `tags` which is free-form.

**Recommendation:** keep area in `tags` (free-form), with a soft convention that the *first* tag is the primary area. Skill + TUI render it as a chip if present.

### Phase 4 — Rendering (TUI + skill)

Once `kind` is locked:

- **TUI row:** `▸ pull apple reminders into backlog  [feat] [reminders]`
- **Chat skill:** chips after the title in compact list:
  ```
  backlog (9)
    ▢ [feat] pull apple reminders into backlog       · reminders
    ▢ [bug]  drop "(request NN)" suffix              · tasks
    ▢ [spec] define forget verb semantics            · cli
  ```
- **`octopus list --kind bug`:** new filter flag on the CLI verb.

## Approach

1. Decide kind enum (Phase 2) via grilling.
2. Update `SCHEMA-TASK.md` with the new field.
3. Mirror to `skills/octopus/references/schemas/task.md` (skill-sync rule).
4. Add `kind` migration logic to reindex (read frontmatter, populate column).
5. Add `--kind` filter to `octopus list`.
6. Update TUI row renderer to show chip.
7. Update skill to include chip in chat layouts.
8. Bulk-rename the 11 existing tasks per F1 + assign kinds.

## Out of scope (v1)

- Multi-kind tasks (a task is one kind).
- Auto-inferring kind from title verb (`fix` → `bug`). Cute but brittle.
- `area` as a first-class enum (stays in `tags`).
- Title length validation in the CLI (soft convention, not enforced).

## Deliverables

- `SCHEMA-TASK.md` updated with `kind` field + enum.
- `skills/octopus/references/schemas/task.md` mirrored.
- `octopus list --kind <enum>` filter wired.
- TUI renders `[kind]` chip in task rows.
- Skill renders `[kind]` chip in chat layouts (per F1 naming + chip rendering rules).
- Existing 11 tasks renamed + kind-assigned in one commit.
- D-entry in `DECISIONS.md` locking naming formula, kind enum, area-stays-in-tags.

## Open for grilling

- Final kind enum (7 vs 6 vs 5).
- Whether `kind` blocks adoption — i.e. whether old task files without `kind` should backfill on next edit or stay un-chipped forever.
- Whether the chip belongs in the title display or as a separate column in TUI rows.
- Whether F1 needs an enforced verb list (CLI warns?) or stays a convention.

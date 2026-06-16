---
id: "47"
slug: subtasks
title: "Subtasks — 1-level-deep parent/child tasks"
status: done
created: 2026-06-05
gates: []
relates_to:
  - SCHEMA-TASK.md
  - specs/TODO-MD-FORMAT.md
  - specs/TUI-GLYPHS.md
  - specs/TUI-KEYS.md
  - DECISIONS.md D104 (pending)
---

# Request 47 — Subtasks

## Why

Tasks often decompose into a small cluster of steps that belong together but
aren't worth tracking as separate activities. Right now the only option is to
add prose to the task body or capture each step as a sibling task — both lose
the structural relationship. Users reach for subtasks naturally in TODO.md
(indented checkboxes), expect the TUI to reflect that grouping, and need the
parent/child relationship in the frontmatter for agent traversal.

The archive explicitly dropped `subtasks`, `parent`, `children` from v1
(SCHEMA-TASK.md "What's NOT in v1"). This request introduces them as a
**deliberately constrained feature**: exactly one level deep, no recursive
nesting, parent is always a task file, children are always task files in the
same activity.

---

## Scope

### In scope

1. **Schema extension** — two new optional fields on Task:
   - `parent: <task-slug>` — present on child tasks only
   - `subtasks: [<slug>, ...]` — present on parent tasks only (auto-maintained)
   Both fields absent = regular standalone task (default-omission applies).

2. **TODO.md Layer 2 extension** — indented checkboxes become subtasks:
   ```markdown
   - [ ] Parent task ~next
     - [ ] Sub-step one
     - [ ] Sub-step two !high
       > Optional body block on sub-items.
   ```
   - Sub-items inherit parent's bucket and section_map defaults unless explicitly overridden by their own sigils.
   - Sub-items are imported as separate task files with `parent:` set.

3. **CLI verbs** — minimal additions:
   - `octopus capture "..." --parent <slug>` — create a child task.
   - `octopus set <slug> --parent <parent-slug>` — attach an existing task as a
     child. `octopus set <slug> --parent ""` (empty string) — detach (unlink).
     Note: `octopus link` is reserved for the Obsidian adapter (#07); we use
     `set --parent` instead of a dedicated link/unlink verb.
   - `octopus subtasks <slug>` — list children of a parent.
   - `octopus finish <slug>` on a parent: warn if open subtasks remain; requires
     `--force` to proceed. `--cascade` finishes all open children first, then
     the parent.
   - `octopus drop <slug>` on a parent: warn if open subtasks remain; requires
     `--force`. With `--cascade`, drops all open children first, then the
     parent. After a forced drop without cascade, children are orphaned — their
     `parent:` points to a dropped task; `lint` warns the user to run
     `--cascade` or detach manually.

4. **TUI visualization** — parent task rows show a child-count chip + expand
   toggle; expanded view shows indented child rows inline (Focus + Board).
   Glyph: `⊕` (expand) / `⊖` (collapse) — or use the existing collapse
   vocabulary if already assigned.

5. **Validation** — lint rule: child with a `parent:` pointing to a
   non-existent slug → error. Circular reference → error (trivially impossible
   at 1-level, but guard anyway).

### Out of scope

- Recursive nesting (2+ levels deep) — explicitly forbidden. Lint flags any
  `parent` pointing to a task that itself has a `parent`.
- Cross-activity subtasks — children must live in the same activity as the parent.
- Subtask-specific bucket independently of parent — children inherit parent's
  bucket as default but may have their own (e.g. a done sub-step while parent
  is still next). The parent is NOT auto-finished when all children are done.
- UI for reordering subtasks — display-only ordering (creation order) in v1.
- Dedicated `octopus unlink` verb — `set --parent ""` covers detach; `octopus
  link` is already reserved for the Obsidian adapter (#07).

---

## Design decisions to lock

### D104 — Subtask schema: `parent` / `subtasks` fields

**Resolved:**

**`parent:` field (child tasks)**
- Type: slug string only. No free-form text, no activity prefix.
  Cross-activity children are out of scope — slug is always local to the
  current activity.
- Source of truth for the relationship. Written once at creation; mutable only
  via `octopus link` / `octopus unlink` (or direct frontmatter edit).
- **Manual insertion supported**: a human may add `parent: <slug>` directly to
  a task's `.md` file. The CLI and `reindex` both pick this up on next run.
  No special command required — editing the field is the canonical path.

**`subtasks:` field (parent tasks)**
- Type: list of slug strings. Never free-form text.
- **Storage: file + index (managed).** Written to the parent task's `.md` file
  by the CLI and by `reindex`. It is a derived index of all tasks whose
  `parent:` points to this slug — never hand-edited. If a human adds `parent:`
  to a child, `octopus reindex` rebuilds the parent's `subtasks:` list.
- The CLI keeps it in sync on every write path (capture, link, unlink, drop,
  delete). `reindex` is the recovery path for any divergence.
- Omitted when empty (default-omission rule). A task with no children never
  has `subtasks:` in its file.
- Field order in canonical frontmatter: after `tags`, before `external_refs`.

**Error checking:**
- `parent:` points to a non-existent slug in the same activity → `lint` error.
- `parent:` points to a task that itself has `parent:` (depth > 1) → `lint`
  error: "nesting depth exceeds 1 level."
- `subtasks:` list contains a slug not found on disk → `lint` warning: "stale
  subtask reference; run `octopus reindex` to repair."
- `subtasks:` diverges from the actual set of `parent:` pointers (e.g. after a
  manual `parent:` edit without reindex) → `lint` info: "subtasks index out of
  sync; run `octopus reindex`."
- Cross-activity `parent:` value (contains `/`) → `lint` error: "cross-activity
  subtasks are not supported."

**Rejected alternative:** store subtask slugs only in the parent and derive
children by scanning. Rejected because agents traversing a child need to find
their parent without a full scan; having `parent:` on the child is O(1).

### D105 — TODO.md Layer 2: indented checkboxes = subtasks

**Proposed:**
- A `  - [ ] ...` line (2- or 4-space indent, or 1 tab) immediately following
  a top-level `- [ ] ...` line is treated as a subtask of the item above it.
- Sub-items support the full Layer 2 sigil + body + YAML syntax.
- Sub-items inherit: `bucket`, `kind`, `actor`, `stage`, `priority`, `energy`
  from the parent item's resolved values (after sigils + YAML + section_map)
  unless the sub-item's own sigils/YAML override.
- Sub-items do NOT inherit: `pinned`, `issue`, `blocked_by`, `waiting_for`,
  `due`, `scheduled` — those are per-item only.
- The `→ octopus:<slug>` MARK_PULLED arrow is written on the sub-item line
  (not the parent) when the sub-item is successfully pulled.
- The parent's arrow is written only after all its sub-items are also pulled.

**Rejected alternative:** use a `subtasks:` YAML block on the parent item to
list children inline. Rejected: loses native markdown editability; a user
can't checkbox a sub-item in Obsidian without restructuring the YAML.

### D106 — TUI: collapsed/expanded parent rows

**Proposed:**
- Parent task title displays a branch icon (`⎇` or `╴`) immediately followed
  by a small subtask count: e.g. `⎇3`. This inline decoration is always
  visible regardless of expand/collapse state — the user can see at a glance
  that a task has children without needing to open it.
- Subtasks are **visible by default** under their parent, expanded inline.
  Toggle: `Space` on the focused parent row collapses/expands. Collapsed state
  shows only the parent row with the `⎇N` count. Expanded state shows children
  as indented rows directly below, using a tree prefix (`├─` / `└─`).
- Expand/collapse state is per-task and persists in the UI view-state cache
  (same mechanism as cursor position per D44/D94). Default on first render:
  expanded.
- In Focus view: children are selectable as independent cursor targets when
  expanded. In Board view: children are shown as indented non-selectable lines
  (columns too narrow for independent selection).
- Parent completion indicator: if all subtasks are `done`, the parent row gains
  a `✓ all` badge. Not auto-finished — user still runs `octopus finish <slug>`
  (permissive path: warns about open subtasks, proceeds with `--force` or
  `--cascade`).
- Glyph assignment: `⎇` (branch, U+2387) for the parent count decoration.
  Confirm no slot conflict in TUI-GLYPHS.md before implementation.

### D107 — Parent drop behavior, list output, and slug collision strategy

**Drop a parent with open subtasks:**
- `octopus drop <parent>` with open children: warn, list open children, require
  `--force` to proceed without cascade. After forced drop without `--cascade`,
  children are orphaned — `parent:` points to a now-dropped task. `lint` emits
  a warning: "parent task is terminal; run `octopus drop --cascade <slug>` or
  detach children with `octopus set <child> --parent \"\"`."
- `octopus drop --cascade <parent>`: drops all open children first (each gets
  `end_date`, `bucket: dropped`), then drops the parent. Children's `parent:`
  field is preserved as a historical link to the dropped parent — the
  relationship survives in the archive for audit/context.
- `octopus finish --cascade <parent>`: same pattern for finish.

**`octopus list` output with subtasks:**
- Default list view: parent rows visible; children visible and indented under
  their parent (`├─` / `└─`), matching TUI default-expanded behavior. A
  `--collapsed` flag hides children (shows only parent rows with `⎇N` count).
- `--all` includes all tasks in flat list (no tree grouping, as today).
- `octopus subtasks <slug>`: dedicated command, lists only the children of one
  parent, flat.

**Slug collision strategy:**
- Slugs are activity-scoped (not bucket-scoped) per D4. The `-2`/`-3` counter
  handles collisions within an activity regardless of parent/child status.
- Additional risk: a child title could slugify identically to its own parent
  (e.g. capture "Fix auth" as child of `fix-auth`). The counter resolves this
  to `fix-auth-2` — no ambiguity at the file level.
- Prefix-match resolution (D4) already handles cross-refs, so `fix-auth`
  unambiguously resolves to the parent; `fix-auth-2` to the child.
- No subtask-specific slug logic needed beyond what D4 already specifies.
  Document explicitly in CRITICAL-DEPENDENCIES.md: slug uniqueness is
  activity-scoped; `parent:` and `subtasks:` use exact slugs, not prefix match.

---

## Deliverables

- [ ] Lock D104, D105, D106, D107 in DECISIONS.md
- [ ] SCHEMA-TASK.md — add `parent` and `subtasks` to canonical order and
      field reference; remove from "What's NOT in v1" list
- [ ] TODO-MD-FORMAT.md — add "Subtasks (indented checkboxes)" section to
      Layer 2; add to parse walk step 2b; add to complete example
- [ ] TUI-GLYPHS.md — assign `[+N]`/`[-]` subtask-count slots
- [ ] TUI-KEYS.md — document Space (Focus) / Tab (Board) expand toggle
- [ ] CRITICAL-DEPENDENCIES.md — add validation rules:
      (a) child `parent:` must resolve to existing slug in same activity
      (b) parent of a parent = error (depth > 1 forbidden)
      (c) `subtasks` list must match inverse of all `parent:` pointers
- [ ] CLI implementation:
      - `capture --parent <slug>` flag
      - `set --parent <slug>` attach; `set --parent ""` detach (unlink)
      - `subtasks <slug>` subcommand
      - `finish` + `drop` parent guards: warn + `--force`; `--cascade` variant
      - `list` default shows tree (parent + indented children); `--collapsed`
        hides children; `--all` flat
      - `todo_md.py` — indented sub-item parser
      - `pipeline.py` — wire `parent` / `subtasks` into materialized files
- [ ] Skill reference sync — update matching files under
      `skills/octopus/references/` per sync rule in CLAUDE.md
- [ ] Tests — parser, pipeline, CLI verbs, lint rules
- [ ] CHANGELOG entry

---

## Notes

- The "What's NOT in v1" section in SCHEMA-TASK.md must be amended — it
  explicitly lists `subtasks`, `parent`, `children`. This is intentional
  revision, not a contradiction: the v1 omission was to avoid unbounded
  nesting; this request adds a **constrained** 1-level variant.
- `children` is intentionally renamed to `subtasks` — clearer intent, avoids
  confusion with activity nesting.
- `subtasks:` is a managed field written by the CLI and `reindex`. Never
  hand-edited. Manual linking = edit `parent: <slug>` in the child file;
  `reindex` reconciles the parent's list.
- No dedicated `unlink` verb — `octopus link` is reserved for the Obsidian
  adapter (#07). Detach via `set --parent ""` (CLI) or delete `parent:` from
  the child file (manual). Both paths trigger `reindex` reconciliation.
- Finish and drop guards are permissive (warn + `--force`). `--cascade`
  propagates the verb to all open children before the parent. No strict-blocked
  mode in v1.
- After `--cascade drop`: children keep their `parent:` field as a historical
  link to the dropped parent. The relationship is preserved for audit.
- TUI default: subtasks expanded inline under parent. `⎇N` decoration always
  visible on the parent title. Space toggles collapse/expand per task;
  state persists in view-state cache.
- Slug collisions: fully handled by D4's activity-scoped counter. `parent:`
  and `subtasks:` use exact slugs only (no prefix match). Document in
  CRITICAL-DEPENDENCIES.md.
- `⎇` (U+2387) glyph for branch decoration — confirm no slot conflict in
  TUI-GLYPHS.md before implementation.

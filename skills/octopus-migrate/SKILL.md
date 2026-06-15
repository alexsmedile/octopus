---
name: octopus-migrate
description: |
  Migrate any existing project folder to the Octopus standard. Initializes .octopus/, rewrites TODO.md to Layer 2 format (sigils + body blocks + YAML blocks + section_map), pulls tasks via the todo-md bridge, and archives the old vault/tasks entry if one exists. Use when the user wants to "convert a project to octopus", "octopus-ify a project", "init octopus on X", or "migrate tasks from TODO.md".
when_to_use: |
  - User says "migrate project X to octopus" or "convert X"
  - User says "octo init on <folder>" and there's a TODO.md to import
  - User says "bring tasks from <project> into octopus"
  - User wants to turn an unstructured TODO.md into tracked octopus tasks
version: 1.5.1
category: productivity
status: active
tags: [octopus, migration, todo-md, init, bridge]
---

# Octopus Project Migration

Migrate any project folder to the Octopus standard. The workflow is:
1. Discover the project
2. Init `.octopus/`
3. Rewrite `TODO.md` to Layer 2 format
4. Write `.octopus/config.toml` with section_map
5. Enable the todo-md bridge
6. Peek, then pull
7. Archive old vault/tasks entry if one exists

---

## Prerequisites

- Octopus CLI installed and on PATH (`octopus` or `octo`).
- The project must be a folder with at least a `TODO.md` file (or be ready to have one created).
- Know the project's `--type` and `--area` before running `init`.

---

## Step 0 — Discover and confirm

Before touching anything, gather:

```
project_root   = absolute path to the project folder
title          = human name (default: folder name, capitalized)
type           = automation | business | code | content | other | personal | research | skill
area           = free-form (e.g. design, dev, marketing)
vault_entry    = path to vault/tasks/active/<slug>.md if one exists (check ~/vault/tasks/active/)
```

Read the existing `TODO.md` to understand the section structure. Ask the user to confirm title/type/area before proceeding if they haven't specified them.

---

## Step 1 — Check for existing `.octopus/`

```bash
ls <project_root>/.octopus/
```

- If `.octopus/` already exists → skip `init`, go to Step 3.
- If not → run `init`.

---

## Step 2 — Init

```bash
cd <project_root>
octopus init --title "<title>" --type <type> --area <area>
```

Verify the output confirms the activity was created and the id that was assigned.

---

## Step 3 — Rewrite TODO.md to Layer 2

**Read the existing `TODO.md` first.** Then rewrite it in Layer 2 format. Rules:

### Subtask support (D105)

Indented checkboxes in TODO.md are automatically imported as child tasks:

```markdown
- [ ] Parent task title ~next
  - [ ] Child task one
  - [ ] Child task two
```

- Any checkbox indented under a top-level item becomes a child task with `parent: <parent-slug>`.
- Section headings reset the parent context — an indented item after a new `##` heading is NOT a child of the last item in the previous section.
- Depth is 1-level max (D104). Deeper indentation maps to the last top-level item, not the nearest ancestor.
- After pull, each child has `parent: <slug>` in its frontmatter; the parent's `subtasks:` list is managed automatically by the CLI.

When rewriting TODO.md to Layer 2, preserve the indentation of subtasks — the indented structure is what the adapter reads.

---

### Layer 2 format rules

Every checkbox item becomes:

```markdown
- [ ] Task title @owner ~bucket !priority 📅 YYYY-MM-DD #tag
  > One-line or multi-line description (blockquote body block).
  ```yaml
  kind: feat|bug|spec|polish|test|chore
  actor: human|ai|automation
  stage: spec|...
  energy: low|mid|high
  issue: blocked|waiting|...
  blocked_by: other-slug
  pinned: true
  ```
```

**Sigil reference:**

| Sigil | Field | Shorthands |
|---|---|---|
| `@word` | owner | — |
| `~word` | bucket | `~b`=backlog `~n`=next `~!`=now |
| `!word` | priority | `!l`=low `!h`=high `!!`=urgent |
| `📅`/`🗓️`/`📆` + date | due | YYYY-MM-DD or DD-MM-YYYY |
| `#tag` | tags | — |

**YAML block:** use for `kind`, `actor`, `stage`, `energy`, `issue`, `blocked_by`, `waiting_for`, `pinned`. Omit if none apply.

**Body block:** `> text` lines immediately after the checkbox. Captures the description. Use for anything that was prose in the original — context, links, references.

**Precedence (high → low):** sigils/emoji → YAML block → section_map defaults.

**What to preserve:**
- All open `- [ ]` items → rewrite in Layer 2.
- Already-done `- [x]` items → keep as-is (they won't be imported unless `include_checked = true`).
- Section headings → preserve exactly (they drive section_map lookup).
- Any freeform prose not in a checkbox → keep as-is.

**What to infer from content:**
- If a task is tagged as a bug/fix → `kind: bug`.
- If a task is clearly an idea/someday → `~backlog !low`.
- If a task has a dependency described in prose → `blocked_by:` or `issue: blocked`.
- If a task is marked "low priority" in prose → `!l`.
- If a task mentions "next" or "first" → `~next`.

---

## Step 4 — Write `.octopus/config.toml`

Create (or update) `.octopus/config.toml` with section_map entries matching the `##` headings in the TODO.md:

```toml
[bridges.todo-md]
path = "TODO.md"
include_checked = false

[bridges.todo-md.section_map.<section-slug>]
kind = "feat"

[bridges.todo-md.section_map.infrastructure]
kind = "chore"
priority = "low"
```

**Section slug** = lowercase heading text, spaces → hyphens, punctuation stripped (same as `_slugify_heading()`).

**Allowed keys per section:** `bucket` · `kind` · `priority` · `energy` · `actor` · `stage`.

Section_map values are the lowest-precedence defaults — they only fill fields that sigils and YAML didn't set. Assign sensible defaults based on the heading semantics (e.g. `## Infrastructure` → `kind: chore, priority: low`; `## Features` → `kind: feat`; `## Bugs` → `kind: bug`).

---

## Step 5 — Enable the bridge

```bash
cd <project_root>
octopus bridge enable todo-md
```

---

## Step 6 — Peek (dry run)

```bash
cd <project_root>
octopus bridge peek todo-md
```

Verify the item count and titles look right. If the count is wrong:
- Check if the global `~/.config/octopus/bridges/todo-md.toml` has a `section_filter` — clear it if it's filtering unexpectedly.
- Check that `→ octopus:` arrows aren't already present (those items are skipped on re-pull).

---

## Step 7 — Pull

```bash
cd <project_root>
octopus bridge pull todo-md
```

Confirm the output: `pulled N new · M already-known · 0 errors`.

---

## Step 8 — Archive vault/tasks entry (if one exists)

If there's a `~/vault/tasks/active/<slug>.md` file for this project:

1. Add `archived: <today>` and `migrated_to: <relative-path>/.octopus` to its frontmatter.
2. Update `status: archived`.
3. Move the file: `mv ~/vault/tasks/active/<slug>.md ~/vault/tasks/archive/<slug>.md`.

---

## Step 9 — Verify

Spot-check a few imported tasks:

```bash
cat <project_root>/.octopus/tasks/next/<slug>.md
cat <project_root>/.octopus/tasks/backlog/<slug>.md
```

Confirm that YAML fields (kind, priority, actor, stage, blocked_by) landed correctly from the Layer 2 parsing.

If the TODO.md had indented checkboxes, verify subtask wiring:

```bash
# A parent task should have subtasks: [child-slug, ...]
grep -A5 "^subtasks:" <project_root>/.octopus/tasks/<bucket>/<parent-slug>.md

# A child task should have parent: <parent-slug>
grep "^parent:" <project_root>/.octopus/tasks/<bucket>/<child-slug>.md
```

Run lint to catch any wiring issues:

```bash
cd <project_root>
octopus lint
```

`subtask-orphan` warnings indicate a child whose parent wasn't imported (e.g. parent was `[x]` done and skipped). Either pull with `include_checked = true` for that session or manually set `parent:` after the fact.

---

## Common issues

| Problem | Cause | Fix |
|---|---|---|
| `octopus bridge peek` returns "no items" | Global `section_filter` in `~/.config/octopus/bridges/todo-md.toml` is filtering | Clear or comment out `section_filter` in that file |
| Tasks missing YAML fields (kind=None) | YAML block fence not closed, or indentation wrong | Verify closing ` ``` ` is present; body lines use `  > ` (2-space indent or 0–3 spaces) |
| Body not captured | `> text` has >3 leading spaces, or no space after `>` | Use `  > text` (2 spaces + `> ` is fine; `>text` without space also works) |
| "not inside an activity" error | CLI not run from within the project root | `cd <project_root>` before all bridge commands |
| Duplicate tasks on re-pull | The `→ octopus:` arrows weren't written (pull failed mid-run) | Check `.octopus/tasks/` for the files; if present, re-pull is safe — dedup index prevents double-creates |
| `subtask-orphan` lint warnings | Indented child's parent was `[x]` done → not imported | Pull again with `include_checked = true` temporarily, or set `parent: <slug>` manually on the orphaned child |
| Children not linked after pull | Indented items have > 3 spaces (too deep), or parent was in a different section | Keep indent exactly 2 spaces; section headings reset parent context |

---

## Layer 2 quick reference

```markdown
- [ ] Task title @owner ~bucket !priority 📅 2026-05-16 #tag
  > Description. What it is, why it matters.
  ```yaml
  kind: feat
  actor: ai
  stage: spec
  energy: low
  issue: blocked
  blocked_by: other-activity/other-task
  pinned: true
  tags: [tag1, tag2]
  ```
```

Supported YAML keys: `bucket` · `stage` · `pinned` · `issue` · `blocked_by` · `waiting_for` · `due` · `scheduled` · `priority` · `energy` · `actor` · `owner` · `kind` · `tags`.

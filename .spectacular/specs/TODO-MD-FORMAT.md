---
status: draft
updated: 2026-11-26
relates_to: SCHEMA-TASK.md, CLI-VERBS.md §bridge, DECISIONS.md D72–D75, D103, OTF 0.1.0
---

# TODO.md format — OTF 0.1.0 Inline + Octopus extended standard

Two layers. Both valid. Layer 2 is fully additive — a plain GFM file is
already a valid Layer 2 file. `TODO.md` may declare OTF 0.1.0 once in its file-level
frontmatter (`otf_version: "0.1.0"`, `otf_profile: "inline"` alongside OPF's
`schema: make-a-change/todo/v1` and array `extensions: [octopus:all]`). Bound items carry
`<!-- otf:UUID -->` and inherit `otf_version` without repeating a per-item `yaml` fence.
Octopus reads both; unknown syntax is silently preserved, never errors.

---

## Layer 1 — Plain GFM (baseline)

Standard GitHub Flavored Markdown checkboxes. Works in every markdown viewer.

```markdown
## Section name

- [ ] Task title
- [x] Completed task
- [/] In-progress task
```

**Checkbox state → bucket:**

| Marker | `bucket`  | Notes                                      |
|--------|-----------|--------------------------------------------|
| `[ ]`  | `backlog`  |                                           |
| `[/]` or `[-]` | `now` |                                    |
| `[x]` or `[X]` | `done` | Skipped unless `include_checked = true` |
| `[!]`  | —         | Cancelled — always skipped                 |
| `[?]`  | `backlog`  | Treated as unchecked                       |

**Obsidian Tasks emoji (D72) — already implemented:**

| Emoji | Field | Example |
|-------|-------|---------|
| `🔺` `⏫` | `priority: urgent` | `- [ ] Title ⏫` |
| `🔽` `⏬` | `priority: low` | `- [ ] Title 🔽` |
| `📅` + date | `due` | `- [ ] Title 📅 2026-07-01` |
| `⏳` + date | `scheduled` | |
| `🛫` + date | `start_date` | |
| `#tag` | `tags` | `- [ ] Title #design` |

**Handoff arrow (D73 — updated for OTF 0.1.0):**

```markdown
- [ ] Title → octopus:task-slug <!-- otf:550e8400-e29b-41d4-a716-446655440000 -->
```

Lines with `→` are skipped — already imported/promoted. Octopus writes `→ octopus:<slug>` on
successful pull (D74) and **MUST keep the checkbox unchecked `[ ]`** (never tick `[x]` on pull;
`[x]` is reserved strictly for delivered `status: done`). Legacy `- [x] Title → octopus:...`
lines remain read-tolerated as already-imported. Users may hand-write `→` to exclude items from import.

**Sections:**

`## Heading` sets the current `source_group` for all items below it. The
heading slug (lowercase, hyphens) is used by `section_filter` config and the
`section_map` config block.

---

## Layer 2 — Octopus-extended

Layer 1 plus three additions: **shorthand sigils**, a **body block**, and a
**YAML expansion block**. All are optional per item; mix freely.

### Shorthand sigils (inline, on the checkbox line)

```markdown
- [ ] Task title #tag @owner ~bucket !priority %kind 📅 2026-05-16
```

| Sigil | Field | Values | Shorthand |
|-------|-------|--------|-----------|
| `#word` | `tags` | any | — (already Layer 1) |
| `@word` | `owner` | any string | — |
| `~word` | `bucket` | `backlog` `next` `now` | `~b` `~n` `~!` |
| `!word` | `priority` | `low` `high` `urgent` | `!l` `!h` `!!` |
| `%word` | `kind` | `feat` `bug` `spec` `chore` `refactor` `polish` `test` `docs` `idea` | — (full names only) |
| `📅` `🗓️` `📆` + date | `due` | see date formats below | — |

**Date formats accepted** (all three calendar emoji):

```
📅 2026-05-16      ISO (preferred)
📅 16-05-2026      DD-MM-YYYY
📅 16/05/2026      DD/MM/YYYY
```

Natural language dates (`tomorrow`, `next week`) are out of scope for now.

**`!` note:** `!` as a state marker only appears inside `[!]` (cancelled
checkbox). In the line body, `!word` is unambiguously a priority sigil — the
checkbox marker has already been extracted before body parsing runs.

### Body block

Blockquote lines (`> ...`) immediately after the checkbox line are captured
as the task body. Standard markdown viewers render them as a blockquote.

```markdown
- [ ] Task title ~next !low
  > Description. What it is, why it matters.
  > Continues on additional lines.
  > Links: see `path/to/file.md`.
```

Rules:
- Lines MUST start with `> ` (no indentation required, consistent with GFM
  blockquote syntax).
- Body continues until a line that is neither `>` nor blank.
- A blank line between the checkbox and `> ` block is NOT allowed — body
  must immediately follow.
- Body text is written verbatim into the task file body section.

### YAML expansion block

A fenced `yaml` code block immediately after the checkbox line (or after the
body block) sets any Task frontmatter field not covered by sigils.

````markdown
- [ ] Task title ~next
  > Optional description.
  ```yaml
  kind: feat
  energy: low
  actor: ai
  stage: spec
  scheduled: 2026-07-15
  issue: blocked
  blocked_by: carousel-studio/fix-export-sizing
  tags: [design, tool]
  ```
````

Rules:
- The opening fence MUST be ` ```yaml ` on its own line.
- The closing fence MUST be ` ``` ` on its own line.
- Keys are Task field names verbatim (see supported keys below).
- The block is parsed as YAML; malformed YAML produces a skip warning.
- Unknown keys are silently ignored — forward-compatible.

**Supported YAML keys (OTF 0.1.0 core + `extensions.octopus.core` / `otf.*` DLCs):**

| Key | Target | Type / enum |
|-----|--------|-------------|
| `description` | OTF core | optional concise summary string |
| `status` | OTF core | `open` \| `in_progress` \| `done` \| `cancelled` |
| `stage` | OTF core | free-form string |
| `kind` | OTF core | open (conv: `feat` \| `bug` \| `spec` \| `polish` \| `test` \| `chore` \| `docs` \| `research` \| `idea`) |
| `priority` | OTF core | `none` \| `low` \| `medium` \| `high` \| `urgent` |
| `assignees` | OTF core | list of actor refs |
| `labels` | OTF core | list of strings; merged with `#tag` sigils |
| `scheduled` | OTF core | ISO date `"YYYY-MM-DD"` |
| `due` | OTF core | ISO date `"YYYY-MM-DD"` or RFC 3339 datetime |
| `impediment` | OTF core | `blocked` \| `waiting` |
| `impediment_reason` | OTF core | nonblank string (paired with `impediment`) |
| `depends_on` | OTF core | list of task UUIDs |
| `extensions.otf.*` | Standard DLCs | `otf.agile` (`cycle`, `milestone`, `estimate`, `unit`), `otf.schedule`, `otf.relations` |
| `extensions.octopus.core` | Octopus profile | `bucket` (`inbox` \| `backlog` \| `next` \| `now` \| `someday`), `owner`, `actor`, `run_state`, `pinned`, `energy` |

Legacy v1 keys (`bucket`, `owner`, `actor`, `pinned`, `energy`, `issue`, `blocked_by`, `waiting_for`, `tags`) remain read-tolerated on migration; writers emit the OTF 0.1.0 keys above.

### Subtasks (indented checkboxes) — D105

An indented checkbox line (2+ spaces or 1 tab) immediately following a top-level checkbox is treated as a subtask of the item above it.

```markdown
- [ ] Parent task ~next
  - [ ] Sub-step one
  - [ ] Sub-step two !high
    > Optional body block on the sub-item.
```

**Inheritance:** sub-items inherit `bucket`, `kind`, `actor`, `stage`, `priority`, `energy` from the resolved parent (after sigils + YAML + section_map) unless the sub-item's own sigils/YAML override them.

**Not inherited:** `pinned`, `issue`, `blocked_by`, `waiting_for`, `due`, `scheduled` — per-item only.

**Pull annotation:** the `→ octopus:<slug>` arrow is written on the sub-item line when pulled. The parent's arrow is written only after all its sub-items are also pulled.

**`suggested_parent`:** the parser sets `suggested_parent` on each `ExternalTask` to the slug of the most recently seen top-level item. The pipeline creates the child with `parent: <slug>` and updates the parent's `subtasks:` index on next `reindex`.

---

## Precedence (high → low)

1. **Sigils / emoji** on the checkbox line
2. **YAML block** (for fields not set by sigils)
3. **`section_map`** config defaults (lowest — applies to all items in section)

---

## Section map (config)

`.octopus/config.toml` maps section slugs to default field values. Applied to
every item in that section unless overridden by sigil or YAML block.

```toml
[bridges.todo-md.section_map.skills]
kind = "feat"

[bridges.todo-md.section_map.library]
kind = "chore"

[bridges.todo-md.section_map.study-pipeline-audit]
kind = "bug"

[bridges.todo-md.section_map.performance-tracking]
priority = "low"

[bridges.todo-md.section_map.friction]
bucket = "backlog"
```

Allowed keys: `bucket`, `kind`, `priority`, `energy`, `actor`, `stage`.
Impediment fields (`issue`, `blocked_by`, `waiting_for`) and `pinned` are
per-item only — not settable via section_map.

Global defaults: `~/.config/octopus/bridges/todo-md.toml`.
Per-activity override: `.octopus/config.toml` (wins over global).

---

## Pull behaviour — parser walk

1. `## Heading` → sets `source_group`; slug used for `section_filter` and `section_map`.
2. `- [X] title sigils...` → parse checkbox state → bucket; extract sigils from body. Track indent level: indent > 0 = sub-item; set `suggested_parent` to the most recently seen top-level item's slug (D105).
3. Immediately following `> ...` lines → captured as `body`.
4. Immediately following ` ```yaml ` ... ` ``` ` block → parsed as YAML overrides.
5. `section_map` defaults applied last (lowest precedence).
6. Items with `→ arrow` skipped (already pulled — D73).
7. `[!]` cancelled → skipped.
8. `[x]` checked → skipped unless `include_checked = true`.
9. Result: one `ExternalTask` per importable item, with body and all
   `suggested_*` fields populated.

---

## Complete example

````markdown
## Skills

- [ ] /verify skill ~next !low #skill
  > Holistic QA gate before export. Runs on exported PNGs + deck JSON.
  > Checks cover clarity, CTA discipline, native feel. Returns go/fix verdict.
  ```yaml
  kind: feat
  actor: ai
  stage: spec
  ```

- [ ] /publish skill #skill
  > Final pre-publish pass. Sits after /verify, closes the pipeline.
  ```yaml
  kind: feat
  actor: ai
  ```

## Infrastructure

- [ ] Library integrity check script !low @alex
  > `scripts/check-integrity.py`: runs all checks plus cross-validates
  > `downloaded.json` entries against actual disk folders.
  ```yaml
  kind: chore
  energy: low
  ```

- [ ] Unify classification state !low
  > Split between carousel-study/ and carousel-studio/library/. No single
  > source of truth. Prerequisite for performance tracking.
  ```yaml
  kind: spec
  stage: spec
  issue: blocked
  blocked_by: library integrity check script
  ```
````

---

## Render compatibility

| Viewer | Sigils | Body block | YAML block |
|--------|--------|------------|------------|
| GitHub | Visible (stripped from title on import) | Renders as blockquote | Renders as fenced code block |
| Obsidian | Visible | Renders as blockquote | Renders as fenced code block |
| VS Code preview | Visible | Renders as blockquote | Renders as fenced code block |
| Plain text | Visible | Visible as `> ...` | Visible as ` ```yaml ``` ` |

All extensions are non-destructive. A Layer 2 file is valid, readable
Markdown in every context. Octopus is the only reader that acts on the
extended syntax.

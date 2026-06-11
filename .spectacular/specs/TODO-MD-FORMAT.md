---
status: draft
updated: 2026-06-05
relates_to: SCHEMA-TASK.md, CLI-VERBS.md §bridge, DECISIONS.md D72–D75, D103
---

# TODO.md format — octopus extended standard

Two layers. Both valid. Layer 2 is fully additive — a plain GFM file is
already a valid Layer 2 file. Octopus reads both; unknown syntax is silently
skipped, never errors.

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

**Handoff arrow (D73) — already implemented:**

```markdown
- [x] Title → octopus:task-slug
```

Lines with `→` are skipped — already imported. Octopus writes this on
successful pull (D74). Users may hand-write it to exclude items from import.

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

**Supported YAML keys:**

| Key | Task field | Type / enum |
|-----|-----------|-------------|
| `bucket` | `bucket` | `backlog` \| `next` \| `now` \| `done` \| `dropped` |
| `stage` | `stage` | free-form string |
| `pinned` | `pinned` | `true` |
| `issue` | `issue` | `blocked` \| `waiting` |
| `blocked_by` | `blocked_by` | free-form or `activity/task-slug` |
| `waiting_for` | `waiting_for` | free-form or `activity/task-slug` |
| `due` | `due` | ISO date `YYYY-MM-DD` |
| `scheduled` | `scheduled` | ISO date `YYYY-MM-DD` |
| `priority` | `priority` | `low` \| `high` \| `urgent` |
| `energy` | `energy` | `low` \| `mid` \| `high` |
| `actor` | `actor` | `human` \| `ai` \| `automation` |
| `owner` | `owner` | free-form string |
| `kind` | `kind` | `feat` \| `bug` \| `spec` \| `polish` \| `test` \| `chore` |
| `tags` | `tags` | list or comma-separated string; merged with sigil tags |

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
2. `- [X] title sigils...` → parse checkbox state → bucket; extract sigils from body.
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

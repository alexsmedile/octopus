---
status: done
priority: high
owner: alex
updated: 2026-06-05
summary: "TODO.md Layer 2: shorthand sigils (@owner ~bucket !priority 🗓️ date), body block (> text), YAML expansion block, section_map config, and full ExternalTask field parity with Task schema."
related:
  - 22-todo-md-format
  - 21-adapter-todo-md
  - 06-adapter-framework
gates:
  - 22-todo-md-format
---

# TODO.md extended format — Layer 2

## Goal

Extend the TODO.md adapter beyond plain GFM (Layer 1 / request #22) to support
a richer, still-readable shorthand that maps directly to every non-provenance
Task frontmatter field.

Full spec: `specs/TODO-MD-FORMAT.md`. Decision locked in D103.

## Why

Layer 1 covers title, bucket (via checkbox state), priority (emoji), due/scheduled
(emoji), and tags (`#tag`). Everything else — owner, actor, energy, kind, stage,
issue/blocked_by/waiting_for, pinned, body — has no capture path. Users are forced
to edit task files directly after import or leave fields blank.

The extended format closes that gap with:
1. **Shorthand sigils** — `@owner`, `~bucket`, `!priority` inline on the title line.
   Also extends date parsing to accept `🗓️` / `📆` aliases and `DD-MM-YYYY` format.
2. **Body block** — `> text` lines immediately after the checkbox, captured as task body.
3. **YAML expansion block** — fenced ` ```yaml ``` ` for any field sigils can't express
   (`kind`, `energy`, `actor`, `stage`, `issue`, `blocked_by`, `waiting_for`, `pinned`).
4. **Section map config** — per-activity `.octopus/config.toml` maps section slugs to
   field defaults (e.g. `## Skills` → `kind: feat`).
5. **ExternalTask field parity** — `suggested_*` fields added to cover every new key,
   so the pipeline can materialize them without a second read-write pass.

## Precedence (high → low)

Sigils/emoji on title line → YAML block → section_map config defaults.

## Approach

### 1. `adapters/base.py` — expand `ExternalTask`

Add `suggested_*` fields for every Task field not already covered:

```python
suggested_stage: str | None = None
suggested_pinned: bool | None = None
suggested_issue: str | None = None
suggested_blocked_by: str | None = None
suggested_waiting_for: str | None = None
suggested_scheduled: date | None = None
suggested_energy: str | None = None
suggested_actor: str | None = None
suggested_owner: str | None = None
```

(`suggested_bucket`, `suggested_kind`, `suggested_priority`, `suggested_due`,
`suggested_tags` already exist.)

### 2. `adapters/todo_md.py` — extended parser

**New sigil parsing in `_parse_inline_metadata`:**
- `@word` → `owner`
- `~word` → `bucket` (with shorthand: `~b`=backlog, `~n`=next, `~!`=now)
- `!word` → `priority` (with shorthand: `!l`=low, `!h`=high, `!!`=urgent)
- `🗓️` / `📆` as aliases for `📅` (due date)
- Date formats: `YYYY-MM-DD` (existing), `DD-MM-YYYY`, `DD/MM/YYYY`

**New body block parsing in `_parse_todo_md`:**
After a checkbox line, consume consecutive `> ...` lines as body text.

**New YAML block parsing in `_parse_todo_md`:**
After the checkbox (and optional body block), detect ` ```yaml ` fence, parse
content as YAML, map keys to `suggested_*` fields. Stop at closing ` ``` `.
Malformed YAML → skip with warning (never error).

**Section map application:**
Read `[bridges.todo-md.section_map.<section-slug>]` from per-activity config.
Apply as lowest-precedence defaults after sigils and YAML block.

### 3. `adapters/pipeline.py` — wire new fields

In the re-open pass after `capture_task()`, apply all new `suggested_*` fields:

```python
if et.suggested_stage:    task.stage = et.suggested_stage
if et.suggested_pinned:   task.pinned = True
if et.suggested_issue:    task.issue = et.suggested_issue
if et.suggested_blocked_by:   task.blocked_by = et.suggested_blocked_by
if et.suggested_waiting_for:  task.waiting_for = et.suggested_waiting_for
if et.suggested_scheduled:    task.scheduled = et.suggested_scheduled
if et.suggested_energy:   task.energy = et.suggested_energy
if et.suggested_actor:    task.actor = et.suggested_actor
if et.suggested_owner:    task.owner = et.suggested_owner
```

### 4. Config schema update

`SCHEMA-CONFIG.md` and `specs/TODO-MD-FORMAT.md` already document the
`[bridges.todo-md.section_map.*]` shape. No code change needed beyond
reading it in the adapter.

## Deliverables

- [x] `adapters/base.py` — 9 new `suggested_*` fields on `ExternalTask`
- [x] `adapters/todo_md.py` — sigil parsing (`@`, `~`, `!`, extra emoji + date formats), body block, YAML block, section_map application
- [x] `adapters/pipeline.py` — wire all new `suggested_*` fields in re-open pass
- [x] `tests/adapters/test_todo_md.py` — 28 new tests; 98 total passing
- [x] `CHANGELOG` — entry under [Unreleased]
- [x] D103 already locked in `DECISIONS.md`

## Out of scope

- Natural language date parsing (`tomorrow`, `next week`) — deferred.
- `~` shorthand for `stage` (free-form field, no safe abbreviation set).
- Mutation verbs (`bridge add` with sigil syntax) — #23 scope.
- Reminders or Obsidian adapter updates — separate requests.

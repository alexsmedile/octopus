# Adapter framework — v1

Adapters bridge Octopus to external systems (Obsidian, Apple Reminders, TODO.md, future GitHub). Octopus owns the canonical task files; adapters read/write what's in the external system.

This file is the operational skill reference. For the formal contract, see `.spectacular/specs/SCHEMA-ADAPTER.md`.

---

## What an adapter does (plain English)

An adapter is a translator between Octopus and one external system. In v1, every adapter is **pull-only** — it imports stuff into Octopus, doesn't push back out.

| Capability | What it means | v1? |
|---|---|---|
| `PULL` | adapter can fetch items from external | ✓ |
| `PUSH` | adapter can write Octopus tasks to external | flag only |
| `NOTIFY` | adapter can wake Octopus on external change | flag only (#12) |
| `RECONCILE` | adapter has a conflict-resolution policy | flag only (#10) |

v1 adapters: `obsidian` (viewer via symlinks), `reminders` (Apple Reminders pull), `todo-md` (read `TODO.md` files). Each ships as a stub in #06; their actual implementations live in #07 / #09 / #21.

---

## The commands

Reading + lifecycle:

```
octopus bridge list                  # show all registered adapters
octopus bridge enable <name> [...]   # configure + turn on
octopus bridge disable <name>        # turn off (settings persist)
octopus bridge status [<name>]       # health check

octopus bridge peek <name>           # READ-ONLY view — no files created
octopus bridge pull <name>           # import as Octopus tasks (deduped)
octopus bridge search <name> <q>     # adapter-side search
```

Mutation (D75, MARK_PULLED-capable adapters only — currently just `todo-md`):

```
octopus bridge add <name> "title" --priority urgent --due 2026-06-30 --tag work --section friction
octopus bridge complete <name> <match> [--first]
octopus bridge uncomplete <name> <match> [--first]
```

Hidden alias: `octopus adapter` ≡ `octopus bridge`.

### peek vs pull

- **`peek`** — display only. Safe; nothing changes on disk. Use to explore what's in an external system before deciding to import.
- **`pull`** — imports as `.octopus/tasks/backlog/<slug>.md` files. Deduped on re-pull (no double-creates).

If you don't know what's there, **`peek`** first.

### `peek` discovery mode

If the adapter has no default list configured (`lists = []` in `bridges/<name>.toml`) AND no `--list` flag, `peek` lists **available groups** instead of erroring:

```
$ octopus bridge peek reminders
no default list configured. Available lists:
  - Inbox
  - Octopus Capture
  - Errands

Specify --list <name> to peek into one, or --capture-all for everything.
```

`pull` with the same state errors instead — it would create unbounded files.

---

## Selecting groups (lists, repos, calendars)

Most adapters have multiple groups (Apple Reminders lists, GitHub repos, ICS calendars). Pulling "everything from the adapter" is rarely what you want.

### Config defaults

```toml
# ~/.config/octopus/bridges/reminders.toml
lists = []                       # no default — must pass --list or --capture-all
# lists = ["Inbox"]              # single default
# lists = ["Inbox", "Errands"]   # multiple defaults
```

### Per-invocation flags

```
--list <name>                    # single group
--list <name1>,<name2>           # multiple groups (comma-separated)
--capture-all                    # every group adapter.list_groups() returns
```

`--list` and `--capture-all` are mutually exclusive (exit 1 if both passed).

### Per-adapter flag naming

The flag is named after the adapter's native concept:

| Adapter | Flag |
|---|---|
| Reminders | `--list <name>` |
| GitHub (future) | `--repo <owner>/<name>` |
| ICS (future) | `--calendar <name>` |
| TODO.md | (none — single file) |

`octopus bridge pull reminders --help` shows what flags Reminders accepts.

---

## What `pull` does on disk

For each external item the adapter returns, the pipeline:

1. Checks the dedup index (`task_external_refs` table) for `(adapter, external_id)`.
2. **If match found** → skip (already imported, recorded as skipped in output, not an error).
3. **If no match** → create a new task with:
   - `actor: human`
   - `imported_from: <adapter_name>`
   - `import_date: <today>`
   - `bucket: backlog` (or `ExternalTask.suggested_bucket` if the adapter set one)
   - `kind: <if adapter suggested>`
   - `external_refs.<adapter_name>: <external_id>`
4. Updates the sync journal at `~/.local/share/octopus/sync/<adapter>.json`.

Output:
```
$ octopus bridge pull reminders --list "Octopus Capture"
pulled 3 new · 7 already-known · 0 errors
  + buy milk
  + schedule dentist
  + reply to alex about Q4 plan
```

---

## Sync journal

One JSON file per adapter at `~/.local/share/octopus/sync/<name>.json`:

```json
{
  "adapter": "reminders",
  "last_pull": "2026-05-24T10:23:00",
  "last_push": null,
  "pull_count": 3,
  "push_count": 0,
  "cursor": null
}
```

Read by `adapter.status()` to populate health output. Written by the framework after every pull/push. v1 keeps a minimal counter+timestamp file; #10 (sync modes addendum) may grow it into event-level history.

---

## Exit codes

| Scenario | Exit |
|---|---|
| Success (any items processed, even 0) | 0 |
| Bridge not configured / disabled / target activity unresolvable | 3 or 2 |
| Adapter doesn't declare required capability | 1 |
| `--list X --capture-all` together | 1 |
| Adapter unhealthy or raises exception | 4 |

Standard PRD §5 conventions.

---

## TODO.md format (D72–D74, D103)

Two layers. Both valid. Layer 2 is fully additive — a plain GFM file is already a valid Layer 2 file.

### Layer 1 — Plain GFM (baseline)

**Checkbox state → bucket:**

| Mark | Bucket | Notes |
|---|---|---|
| `- [ ]` or `- [?]` | `backlog` | |
| `- [/]` or `- [-]` | `now` | |
| `- [x]` / `- [X]` | `done` | skipped unless `include_checked=true` |
| `- [!]` | — | cancelled, always skipped |

**Obsidian Tasks emoji (inline):**

| Emoji | Field |
|---|---|
| `🔺` / `⏫` | `priority: urgent` |
| `🔽` / `⏬` | `priority: low` |
| `📅` / `🗓️` / `📆` + date | `due` |
| `⏳` + date | `scheduled` |
| `🛫` + date | `start_date` |
| `#tag` | `tags` |

Date formats accepted everywhere: `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`.

**Octopus arrow (D73):** `→ <provider>:<slug>` means "handed off — skip on import." On pull, Octopus writes this arrow itself: `- [ ] foo` → `- [x] foo → octopus:<task-slug>`.

**Carry-over prefixes:** `BUG:` → `kind:bug` · `HACK:` → `kind:chore` · `TODO:`/`FIXME:` stripped · `NOTE:` skipped.

---

### Layer 2 — Octopus-extended (D103)

Three additions per item, all optional, all non-destructive in any markdown viewer.

#### Shorthand sigils (inline on the checkbox line)

```
- [ ] Task title @owner ~bucket !priority %kind 📅 2026-05-16 #tag
```

| Sigil | Field | Shorthand |
|---|---|---|
| `@word` | `owner` | — |
| `~word` | `bucket` | `~b`=backlog `~n`=next `~!`=now |
| `!word` | `priority` | `!l`=low `!h`=high `!!`=urgent |
| `%word` | `kind` | `%feat` `%bug` `%spec` `%chore` `%refactor` `%polish` `%test` `%docs` `%idea` |

Sigils take **highest precedence** — they override YAML block and section_map.

#### Body block

`> text` lines immediately after the checkbox are captured as the task body. Renders as a blockquote in all markdown viewers.

```markdown
- [ ] Task title ~next !low
  > Description. What it is, why it matters.
  > Links: see `path/to/file.md`.
```

#### YAML expansion block

Fenced ` ```yaml ``` ` after the checkbox (or body block) sets any Task field sigils can't express. Unknown keys silently ignored; malformed YAML silently skipped.

````markdown
- [ ] Task title
  > Optional description.
  ```yaml
  kind: feat
  energy: low
  actor: ai
  stage: spec
  scheduled: 2026-07-15
  issue: blocked
  blocked_by: other-activity/other-task
  pinned: true
  tags: [tag1, tag2]
  ```
````

Supported keys: `bucket` · `stage` · `pinned` · `issue` · `blocked_by` · `waiting_for` · `due` · `scheduled` · `priority` · `energy` · `actor` · `owner` · `kind` · `tags`.

**Precedence (high → low):** sigils/emoji → YAML block → section_map config.

#### Section map (per-activity config)

`.octopus/config.toml` sets default fields for all tasks under a heading section:

```toml
[bridges.todo-md.section_map.skills]
kind = "feat"

[bridges.todo-md.section_map.infrastructure]
kind = "chore"
priority = "low"
```

Allowed keys: `bucket` · `kind` · `priority` · `energy` · `actor` · `stage`.

#### Subtasks — indented checkboxes (D105)

Indented checkboxes (2+ spaces or 1 tab) immediately under a top-level checkbox become subtasks of that item:

```markdown
- [ ] Parent task ~next
  - [ ] Sub-step one
  - [ ] Sub-step two !high
    > Optional body on the sub-item.
```

Sub-items inherit `bucket`, `kind`, `actor`, `stage`, `priority`, `energy` from the resolved parent unless their own sigils/YAML override. `pinned`, `issue`, `blocked_by`, `waiting_for`, `due`, `scheduled` are per-item only and not inherited.

The parser sets `suggested_parent` on each sub-item `ExternalTask`; the pipeline creates it with `parent: <slug>`. The parent's `subtasks:` index is rebuilt by `octopus reindex`.

---

**Full Layer 2 example:**

```markdown
## Skills

- [ ] /verify skill ~next !low @alex #skill
  > Holistic QA gate before export. Checks cover clarity and CTA discipline.
  ```yaml
  kind: feat
  actor: ai
  stage: spec
  ```

## Infrastructure

- [ ] Library integrity check 📅 15-07-2026
  > Cross-validates downloaded.json against actual disk folders.
  ```yaml
  kind: chore
  energy: low
  ```
```

## When to use this skill

The user mentions:
- "Pull/import/sync from Apple Reminders / GitHub / TODO / Obsidian"
- "What's in my Apple Reminders inbox?"
- "Show me my GitHub issues" / "what's in my TODO.md"
- "Search across my bridges" / "find that note about X across systems"
- "Configure/enable/disable a bridge/adapter"

Match the verb:
- "Show me" / "what's in" → `peek` (or `peek --list` if they name a group)
- "Pull" / "import" / "bring into Octopus" → `pull`
- "Search for X" → `search`
- "Set up" / "configure" → `enable`

If the user describes wanting to *bring stuff in*, `peek` first to verify, then `pull` to commit.

---

## Adapter status reference (v1)

| Adapter | Status | Notes |
|---|---|---|
| `obsidian` | stub | #07 |
| `reminders` | stub | #09 — pull-only via osascript |
| `todo-md` | stub | #21 — reads `TODO.md` from activity root |

A stub responds to all CLI verbs with a clear "not implemented — see request #NN" error. The framework is testable end-to-end; the adapter bodies are the next step.

---

## Reference

- `SCHEMA-ADAPTER.md` — formal protocol contract
- `CLI-VERBS.md §Bridge verbs` — full CLI surface
- `CRITICAL-DEPENDENCIES.md §U` — validation invariants
- `DECISIONS.md D56–D66` — locked design rationale

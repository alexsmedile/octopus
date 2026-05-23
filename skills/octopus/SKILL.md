---
name: octopus
description: Use when capturing, planning, focusing, starting, finishing, dropping, blocking, or reviewing tasks; querying open loops, stuck items, or the current activity; managing the .octopus/ folder system on disk; recording sessions; writing memory or handoffs. Folder-native, CLI-driven (octopus / octo); prefer verbs over hand-editing.
version: 0.3.0
category: productivity
status: active
tags: [activities, tasks, sessions, memory, handoffs, local-first, agents, cli, folder-native]
---

# Octopus

A folder-native task and continuity system. Any folder containing `.octopus/activity.md` is an **activity** — with tasks, sessions, handoffs, and accumulated memory stored as plain markdown next to the work.

The CLI (`octopus`, alias `octo`) is the primary surface. Hand-editing files is allowed but bypasses validation and side-effects — **prefer the verbs**.

This skill is self-contained. References under `references/` are loaded on demand (see "Load on demand" below). Do not search the wider repo for spec content — the references here are the operating contract.

---

## Hard rules — ALWAYS in context

These are non-negotiable; never bypass them, never load a reference to confirm them:

1. **Never delete files.** Use `archive` (hides from default views). Soft-delete to `.trash/` is a v2 feature.
2. **Don't write `.octopus/` files outside the CLI** during normal operation. Validation lives in the verbs. Hand-edits are an escape hatch, not the default.
3. **Walk up to find the activity.** From any folder, walk parents until you hit `.octopus/activity.md`. If none, the user is not in an activity — either `octopus init` or work elsewhere.
4. **Legacy fields are rejected.** `status`, `kind`, `open` are not v1 fields. If you see them in a file, they will surface as parse errors. See `references/critical-dependencies.md` rule T6.
5. **Filenames are CLI-owned.** Never rename a task/session/handoff file by hand. Use `octopus rename` (tasks); session and handoff slugs are never renamed.
6. **Live user task data lives elsewhere.** The vault user's real task data is at `/Users/alex/vault/tasks`. The Octopus repo (where this skill ships from) is the *development workspace*, not a task database.
7. **Default-omission.** Never write a field at its default value. `actor: human`, `pinned: false`, `tags: []` etc. must be absent, not set explicitly.

---

## The system in 60 seconds

**Activities** are folders containing `.octopus/activity.md`. They have tasks, sessions, memory, and handoffs.

**Tasks** are markdown files with frontmatter. They move through five buckets (`backlog → next → now → done | dropped`) and are described along five orthogonal axes (pipeline, domain workflow, runtime, attention, impediment) — there is no `status` field; lifecycle is derived from dates + bucket.

**Sessions** are timestamped recordings of work blocks. Multiple can be open per activity; one is "active" (tracked in a runtime cache).

**Memory** is an append-only journal per activity, with five canonical sections (Decisions / Open Questions / Context / Notes / State) and a curated `summary` in frontmatter.

**Handoffs** are deliberate context-transfer notes — *routers* to existing artifacts, not duplicates. They link back to the session that produced them.

### Folder layout

```
<activity>/.octopus/
├── activity.md
├── tasks/
│   ├── backlog/   next/   now/   done/   dropped/
├── sessions/         # flat, YYYY-MM-DD-<slug>.md
├── handoffs/         # flat, YYYY-MM-DD-<slug>.md
├── memory.md         # two-zone, marker-managed
└── config.toml       # per-activity overrides
```

Pipeline verbs move task files between bucket folders atomically with frontmatter edits.

---

## CLI surface — verb index

This is a verb directory only. For flags, exit codes, and full examples, load `references/cli-verbs.md`.

| Group | Verbs |
|---|---|
| Init & navigation | `init`, `where` |
| Capture & pipeline | `capture`, `plan`, `focus`, `park`, `defer` |
| Lifecycle | `start`, `finish` (alias `end`), `drop` |
| Impediment | `block`, `wait`, `unblock` |
| Attention & visibility | `pin`, `unpin`, `archive`, `restore` |
| Editing | `set`, `rename`, `mv` |
| Promotion | `promote` (Octopus → Spectacular and other targets) |
| Inspection | `show`, `task list`, `task show` |
| Views | `loops`, `today`, `stuck`, `stale`, `context`, `list --kind/--promoted/--spec` |
| Sessions | `session start`, `log`, `end`, `switch`, `list`, `show`, `prune` |
| Memory | `memory show`, `append`, `summary`, `summary set`, `state`, `state set` |
| Handoffs | `handoff new`, `list`, `show` |
| Index | `reindex`, `config root add/list/remove` |

---

## Load on demand

When the user's request crosses any threshold below, read the named reference **before** acting. Do not work from memory of the contract — use the file.

| When you need to... | Read |
|---|---|
| Hand-edit or generate task frontmatter | `references/schemas/task.md` |
| Hand-edit or generate `activity.md` | `references/schemas/activity.md` |
| Read/write session files or log entries | `references/schemas/session.md` |
| Read/write `memory.md` | `references/schemas/memory.md` |
| Draft a handoff body or fill handoff frontmatter | `references/schemas/handoff.md` |
| Choose a CLI verb or flag, or interpret an exit code | `references/cli-verbs.md` |
| Debug a CLI validation error or check an invariant before writing | `references/critical-dependencies.md` |

Triggers:

- **"Hand-edit"** means any operation that produces or modifies file bytes outside a CLI verb — generating a file template, fixing a parser error, batch-rewriting, demonstrating the format.
- **"Validation error"** means any non-zero exit from a write verb where the message mentions a field or rule name.
- **"Choose a verb"** means before suggesting a command line to the user that you haven't recently composed in the current session.

If multiple references apply, load all of them up front rather than re-loading mid-task.

---

## Agent workflow

1. **Locate the activity.** Walk up from cwd to find `.octopus/activity.md`. If none, decide: is this a place to `octopus init` (probably not, ask the user) or is the user in the wrong folder?

2. **Use verbs, not file edits.** Pipeline transitions, dates, side-effects, and validation all live in the CLI. If a verb exists for what you want, use it. The `set` verb is the validated escape hatch when no dedicated verb fits.

3. **Read the relevant reference before writing.** Especially for memory.md (two-zone marker is fragile) and handoffs (body principles matter).

4. **Preserve continuity.** When wrapping a work block, prefer `session end --handoff` over a bare `session end` — the symmetric backlink turns the session+handoff into one auditable transfer.

5. **Be terse.** A session log entry is one line about what changed. A memory append is one paragraph. A handoff body is 30–60 lines. Length is a smell.

6. **Ask before destructive moves.** Even "non-destructive" archives and renames have downstream effects (external refs, cross-activity handoffs). Confirm scope before bulk operations.

---

## Task naming — F1 imperative

Every task title is **`verb result`** in lowercase, imperative voice. No prefixes (`Friction:`, `Bug:`), no parenthetical suffixes (`(request NN)`), no trailing qualifiers.

### Rules
- Start with a concrete imperative verb. Common set: `build / wire / port / pull / push / migrate / refactor / fix / drop / polish / verify / define / clarify / document / lint / link / add`.
- **Don't over-use `add`.** It's the fallback when nothing more specific applies. If you can say `wire`, `build`, `pull`, `port`, `link`, or `migrate`, pick the sharper verb — it tells the reader what *kind* of work it is. `add` is correct when the task really is "make a new thing appear" with no transformation of existing pieces (e.g. a new flag, a new column, a new section).
- Lowercase by default. Sentence case only for proper nouns or identifiers in backticks.
- ~50-character soft cap. If you can't fit, split the task.
- Use backticks around CLI verbs, flag names, or schema field names: `` `run_state` ``, `` `--activity-relative` ``.
- Drop noise words: "and styling", "with a real", "to associate", "between section content and next section heading" — say what changes, not how.

### Examples (good)

```
build apple reminders pull adapter
wire obsidian symlink bridge
add `--activity-relative` scoped view filter
fix duplicate timestamps in rapid session log entries
clarify "N sessions" output in `reindex`
polish error messages + rich output
verify `run_state` in a real automation
drop "(request NN)" suffix from task titles
```

### Examples (avoid)

```
Add Apple Reminders pull adapter (request 09)       ← parenthetical link belongs in frontmatter, not title
Friction: titles with 'request NN' duplicate…       ← "Friction:" is a kind label; goes in metadata
Decide forget verb semantics                         ← prefer concrete verb: "define"
Consider an --activity-relative scoped view…        ← "consider" hides the actual action
Memory show: missing blank line between section…    ← burying the verb behind a noun-phrase prefix
```

Kind/area metadata (bug, feat, polish, etc.) is **out of scope for the title** — it lives in the `kind` frontmatter field (D46), rendered as a `[kind]` chip in TUI rows and chat layouts. See "Task `kind`" below.

---

## Task `kind` (D46)

Optional work-classification field on every task. Soft enum:

| `kind` | When to use |
|---|---|
| `feat` | new capability shipped to users |
| `bug` | something is broken |
| `spec` | a decision needs locking before code |
| `polish` | UX/output quality, not behavior |
| `test` | verification work |
| `chore` | maintenance, cleanup, deps, refactor, docs |

Rules:
- Optional. Tasks without `kind` render with no chip — fully backward-compatible.
- One value per task. Mutable via `octopus set <slug> --kind=<value>`.
- Soft validation — unknown values log a warning, don't reject.
- Indexed. Filter via `octopus list --kind <enum>` (comma-sep for multi).
- Survives promotion. Hidden from default scope (because promoted tasks live in `done/`); surface via `--all`, `--promoted`, or `--spec`.

---

## Task promotion (D47–D54)

When an Octopus task graduates to a Spectacular request (or another external target), promote it — don't duplicate it.

```
octopus promote <slug> [<slug>...] --to <target>     # promote
octopus promote <slug> --to <target> --force         # repoint already-promoted
octopus promote <slug> --revert                      # soft-clear (returns to backlog)
```

### When to use

- A backlog idea has matured enough that you're ready to write a real spec for it.
- A small task naturally folds into a larger build that needs a PLAN.md + decisions.
- Multiple related tasks should be addressed in one cohesive request — promote them all to the same target.

### When NOT to use

- The task is small and self-contained — just `finish` it.
- You're not ready to write the spec yet — leave it in `backlog/`.
- The work doesn't need Spectacular-style ceremony (PLAN, decisions, deliverables).

### `--to` input forms

| Form | Meaning |
|---|---|
| `--to spectacular:20-task-promotion` | explicit existing/new request |
| `--to spec:20-task-promotion` | chip alias accepted |
| `--to 20-task-promotion` | uses `[providers.default]` (= `spectacular`) |
| `--to spec` | single-task only — uses task slug as request slug |
| `--to spec:new --slug 21-foo` | explicit new request |

If the target request doesn't exist, `promote` scaffolds it. If `auto_number` is on (default), the slug gets a leading `NN-` based on the next free integer.

### What promote does

1. Sets `promoted_to: <provider>:<id>` on the task.
2. Sets `end_date: <today>` and `bucket: done`.
3. Moves the file to `tasks/done/<slug>.md`.
4. Replaces the body with a 3-line stub pointing at the PLAN.md.
5. Scaffolds `.spectacular/requests/<slug>/PLAN.md` if absent, with `promoted_from: <task-slug>`.
6. Reindex regenerates `related_tasks:` on the request side (read-only, derived).

### Idempotency

Already-promoted tasks reject with exit 4 unless `--force` (repoint) or `--revert` (soft-clear). The PLAN.md and `promoted_from` field are **historical** — never cleared on repoint.

### Multi-task

`octopus promote A B C --to spec:obsidian-bridge` folds three tasks into one request atomically. Pre-flight validates everything before any write. Provider-only shorthand (`--to spec`) is rejected with 2+ tasks (ambiguous).

### Reverse flow

If a shipped request leaves stragglers, those become **new** Octopus tasks linking back via `promoted_to`. Promotion is one-way; reverse promotion (request → task) is not a thing.

---

## Presenting tasks in chat

When the user asks to see their tasks (overview, status, what's in backlog, focus view, board, kanban, etc.), render them as **ASCII layouts** that mirror the `octopus tui` glyphs and structure — not generic markdown lists. Visual continuity with the TUI is part of the brand.

### Sourcing
- Always pull from `octopus list` (or read `.octopus/tasks/<bucket>/*.md` directly when the CLI isn't enough). Never invent rows.
- For counts, prefer `octopus status` output. For per-task chips, read frontmatter (`pinned`, `run_state`).

### Glyphs (match the TUI exactly)
- `▢` task row · `▸` cursor (only if you're highlighting a specific task)
- `⚐` pinned · `⏸` blocked · `✓` done · `✗` dropped
- `●` NOW · `○` NEXT (bucket headers)
- `[kind]` work-classification chip (cyan in TUI; plain in chat)
- `→ chip:id` promotion arrow on tasks with `promoted_to` (dim in TUI; plain in chat)
- `…N more` when truncating

### Chip + arrow rendering rules
- **`[kind]` chip:** show in compact list and Focus quadrants. In Board (narrow columns), omit if it forces title truncation past the 50% mark.
- **Promotion arrow:** only show in `--all` / `--promoted` / `--spec` scopes. Use the configured chip alias (`spec:` not `spectacular:`).
- Both chips are inline AFTER the title in compact list (`▢ pull apple reminders into backlog [feat] · reminders`), or as a right-aligned suffix in quadrant/board cells when space permits.

### Layout routing

Pick the layout based on the user's phrasing — don't ask, just match.

| User phrasing contains… | Use layout |
|---|---|
| "focus", "overview", "what should I work on", "active" | **Focus quadrants (A)** |
| "board", "kanban", "all buckets", "everything" | **Board kanban (B)** |
| "backlog", "what's in X", "list", default | **Compact list (C)** |

### Layout A — Focus quadrants (BACKLOG | NOW/NEXT)

```
┌─ BACKLOG ──────────────────────────┬─ ● NOW ────────────────────────────┐
│   ▢ wire obsidian symlink bridge   │   ▢ ship the TUI                   │
│   ⚐ polish error messages          │   ⏸ verify run_state semantics     │
│   ▢ apple reminders pull adapter   ├─ ○ NEXT ───────────────────────────┤
│   …5 more                          │   ▢ build sqlite migrations        │
└────────────────────────────────────┴────────────────────────────────────┘
  9 backlog · 2 now · 1 next · 1 blocked
```

### Layout B — Board kanban (four columns)

```
┌─ BACKLOG ──────┬─ ○ NEXT ───────┬─ ● NOW ────────┬─ ✓ DONE ───────┐
│ ▢ wire obsid…  │ ▢ verify run…  │ ▢ ship the…    │ ✓ add textual… │
│ ⚐ polish err…  │                │ ⏸ build sqli…  │ ✓ build sqli…  │
│ ▢ apple remi…  │                │                │ ✓ implement…   │
│ …5 more        │                │                │ …2 more        │
└────────────────┴────────────────┴────────────────┴────────────────┘
```

### Layout C — Compact list (default)

```
backlog (9)
  ▢ [feat] wire obsidian symlink bridge
  ⚐ [polish] polish error messages and rich output
  ▢ [feat] pull apple reminders into backlog
  …6 more — ask to see all

next (1)
  ▢ [test] verify run_state in a real automation

now (0)
  (empty — use m from next to activate)
```

If the user asked for `--promoted` or `--spec <slug>`, append the arrow:

```
promoted (2)
  ✓ [chore] drop "(request NN)" suffix → spec:20-task-promotion
  ✓ [feat]  wire obsidian symlink bridge → spec:20-task-promotion
```

### Rendering rules
- Truncate titles to fit the column. Use `…` to indicate truncation; never wrap.
- Cap each column at **5 rows** in chat — append `…N more` if exceeded. Show the full list only when the user explicitly asks ("show all", "everything in backlog").
- One blank line between buckets in layout C.
- Strip the "(request NN)" suffix from titles when it crowds the column.
- Wrap the block in a code fence so monospace renders correctly.
- After the block, add **one short sentence** of context (next action, what's blocked) — not a re-summary of what's already on screen.

---

## Bridges (v1 scope)

- **Obsidian**: `octopus link` symlinks `.octopus/` into a configured vault location. Read-only viewing layer.
- **Apple Reminders**: pull-only import in v1. No two-way sync.
- **Claude Code plugin**: this repo IS the plugin. Slash commands (`/octopus:start`, `/octopus:end`, `/octopus:handoff`, `/octopus:where`, `/octopus:memory`, `/octopus:log`) wrap the CLI.

Two-way external sync (Reminders, GitHub, ICS) is v2.

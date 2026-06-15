---
name: octopus
description: Use when capturing, planning, focusing, starting, finishing, dropping, blocking, or reviewing tasks; querying open loops, stuck items, dashboards, or the current activity; managing the .octopus/ folder system on disk; recording sessions; writing memory or handoffs; routing user intent like "what should I do" or "what's going on" to the right verb. Folder-native, CLI-driven (octopus / octo); cross-activity write and read verbs let agents work from any cwd.
version: 1.5.0
category: productivity
status: active
tags: [activities, tasks, sessions, memory, handoffs, local-first, agents, cli, folder-native, dashboard, ranking]
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
4. **Legacy fields are rejected.** `status` and `open` are not v1 fields — they surface as parse errors. (Note: `kind` IS a v1 field as of D46, used as a work-classification enum: `feat | bug | spec | polish | test | chore`. The earlier "kind is forbidden" rule is obsolete.)
5. **Filenames are CLI-owned.** Never rename a task file by hand. Use `octopus set <slug> --slug <new-slug> [-y]` for slug renames — it cascades the change to every Octopus-managed reference. Session and handoff slugs are never renamed.
6. **Live user task data lives elsewhere.** The vault user's real task data is at `/Users/alex/vault/tasks`. The Octopus repo (where this skill ships from) is the *development workspace*, not a task database.
7. **Default-omission.** Never write a field at its default value. `actor: human`, `pinned: false`, `tags: []` etc. must be absent, not set explicitly. Passing an explicit-default value (`--priority normal`, `--actor human`, empty string, etc.) is accepted and clears the field (D80).
8. **Tags are stored with `#` prefix** in frontmatter to match Obsidian (`tags: ["#bug", "#tui/marquee"]`). Nested via `/`. Reader accepts both `#bug` and `bug` (silent normalization on write). Flag values accept with or without `#`.
9. **`set` is frontmatter-only.** `set --bucket next` changes the field but does NOT move the file (D77). For physical moves, use `octopus mv <slug> <bucket>`.
10. **Never `forget` or cascading slug rename without explicit confirmation.** `octopus forget activity <id>` removes from the index (and with `--archive` moves files); `octopus set <slug> --slug <new>` cascades the rename across every Octopus-managed ref. Both are powerful and surprising — confirm with the user every time, even when they look reversible.
11. **Cross-activity writes use `--activity <id>` (D86).** When the user names a target ("add to project X", "finish task Y in Z"), pass `--activity` explicitly. Do NOT silently assume the cwd activity is the target when the user's words say otherwise. Every task-mutation verb accepts `--activity` (path, id, or unambiguous prefix).
12. **When intent is ambiguous, ASK or fall back to an inbox.** If the user says "add this idea" with no clear target, ask which activity. Do NOT pick arbitrarily and do NOT default to the cwd activity if the user's intent suggests something else.

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
| Init & navigation | `init`, `where`, `add activity` (sibling of `init`) |
| Capture & pipeline | `capture`, `add task` (cross-activity sibling of capture), `plan`, `focus`, `park`, `defer` |
| Lifecycle | `start`, `finish` (alias `end`), `drop` |
| Impediment | `block`, `wait`, `unblock` |
| Attention & visibility | `pin`, `unpin`, `archive`, `restore` |
| Editing | `set` (frontmatter-only — supports `--task`/`--activity` multi-target), `set --slug <new>` (cascading rename), `move` / `mv` (file move), `forget activity` |
| References | `refs find <slug> [--all]` |
| Promotion | `promote` (Octopus → Spectacular and other targets) |
| Bridges | `bridge list / enable / disable / status / peek / pull / search / add / complete / uncomplete` |
| Inspection | `show`, `task list`, `task show`, `status <path-or-id>` (rich), `get activity <path-or-id>` (JSON) |
| Cross-activity views | `dashboard`, `next`, `impact`, `list activities`, `list tasks <path-or-id>` |
| Curated views | `loops`, `today`, `stuck`, `stale`, `context` |
| Sessions | `session start`, `log`, `end`, `switch`, `list`, `show`, `prune` |
| Memory | `memory show`, `append`, `summary`, `summary set`, `state`, `state set` |
| Handoffs | `handoff new`, `list`, `show` |
| Index | `reindex`, `forget activity`, `config root add/list/remove` |

### Cross-activity flag — `--activity <id>` (D86)

Every task-mutation verb accepts `--activity <id>` to redirect the operation to a specific activity without `cd`. The token is a filesystem path (starts with `/`, `~`, or contains `/`) or an activity id / unambiguous prefix.

```
octopus add task "review PR" --activity octopus
octopus finish ship-it --activity ~/code/octopus
octopus pin focus-this --activity /Users/alex/projects/work
```

Apply this whenever the user names a target activity, even when cwd is elsewhere.

### Capture and edit at a glance (v0.6.0)

```
# Rich capture
octopus capture "ship it" \
    --priority high --due 2026-07-01 \
    --tag work,urgent --add-tag p0 \
    --energy mid --actor ai --owner alex --stage draft

# Tag mutations (all four families accept comma/space/repeated input)
octopus set ship-it --add-tag p0,review        # append
octopus set ship-it --remove-tag urgent        # remove
octopus set ship-it --clear-tags               # empty
octopus set ship-it --tags release,launch      # replace
# --tag/--tags is mutually exclusive with --add-tag/--remove-tag/--clear-tags

# Frontmatter-only vs physical move
octopus set ship-it --bucket next              # frontmatter only (warns about mismatch)
octopus mv ship-it next                        # physical file move + frontmatter

# Slug rename with cascading auto-fix
octopus set old-name --slug new-name -y        # -y skips prompt

# Find every reference
octopus refs find old-name [--all]
```

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
| Set up, peek into, pull from, or search a bridge/adapter | `references/adapter-framework.md` |
| Migrate an existing project folder to Octopus (init + TODO.md rewrite + pull) | use `/octopus-migrate` skill |
| Run a morning review / EOD / inbox triage / weekly stale / cross-project sweep | `references/triage-rituals.md` |
| Render tasks in chat as ASCII layouts (Focus / Board / Compact) | `references/chat-rendering.md` |
| Respond to "what should I work on" / top tasks / tomorrow | `references/prompts/next-tasks.md` |
| Respond to "what's going on" / dashboard / overview | `references/prompts/dashboard.md` |
| Respond to "how's [project]" / project status | `references/prompts/project-status.md` |
| Respond to "what did I work on" / recent activity | `references/prompts/recent-activity.md` |
| Respond to "what's blocked" / stuck | `references/prompts/blocked-stuck.md` |
| Name a task, set kind/tags, rename slug, use capture flags, promote, or use bridges | `references/write-mechanics.md` |

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

## Proactive behaviors — user intent → verb routing

Octopus is the agent's task-management protocol. When the user asks open-ended questions about their work, route to the right verb instead of grepping or listing manually.

| User says | Run | Then offer |
|---|---|---|
| "what should I do" / "what's next" / "what's on my plate" / "top tasks for tomorrow" | `octopus next --json` then translate `why` breakdown into plain English — "pinned + overdue = do this first"; if the user mentioned time or energy, filter the list before presenting | `octopus impact --json` for the full ranked list |
| "what's going on" / "dashboard" / "overview" / "give me the picture" | `octopus dashboard` | drill into top-priority activity via `octopus status <id>` |
| "what's the status of \<project\>" / "how's \<project\>" | `octopus status <project>` (rich view with path-or-id) | `octopus list tasks <project>` for the full task list |
| "show me everything across all projects" | `octopus list activities` (card layout, priority-sorted) | filter flags as needed |
| "add a task to \<project\>" / "remind me to X for \<project\>" | `octopus add task "X" --activity <project>` | no `cd` needed |
| "add this idea" with no project named | **ASK** "which activity?" — do not pick arbitrarily (Rule 12) | propose the most recently-touched activity if helpful |
| "what's overdue" | `octopus list activities --has-overdue` | drill in with `octopus status <id>` |
| "what's pinned" | `octopus list activities --has-pinned` | or `octopus dashboard` (pinned section) |
| "what's blocked" | `octopus stuck` | the dashboard's `BLOCKED` section also surfaces these |
| "what did I touch recently" / "what was I working on" | `octopus list activities --touched-within 7` | `octopus status <id>` on the freshest |
| "give me JSON of \<project\>" / "pipe this to jq" | `octopus get activity <project>` (TTY → pretty, pipe → compact) | `--format compact` to force |
| "quick status of \<project\>" for agent decision-making | `octopus status <project> --json` (lean: metadata + counts + now/pinned/overdue chips) | lighter than `get activity` — no full task arrays |
| "I'm starting on \<project\>" | `octopus status <project>` first (read), then any writes | use `--activity` on every write that follows |

Three rules that frame everything above:
- **Read before write.** When the user names a project, `status` it first to confirm the target resolves.
- **JSON for agents, rich text for humans.** Use `octopus get` / `--json` when the output feeds into your next decision. Use `octopus status` / `dashboard` (rich) when the user is watching.
- **Never grep what a verb knows.** `octopus dashboard`, `octopus next`, `octopus impact`, `octopus list --has-*` exist precisely so you don't have to glue together `list --all | grep`.

---

## Response templates

Each common request type has a dedicated prompt file. Load only the one that matches.

| Request | Load |
|---|---|
| "what to work on" / top tasks / tomorrow | `references/prompts/next-tasks.md` |
| "what's going on" / dashboard / overview | `references/prompts/dashboard.md` |
| "how's [project]" / project status | `references/prompts/project-status.md` |
| "what did I work on" / recent activity | `references/prompts/recent-activity.md` |
| "what's blocked" / stuck | `references/prompts/blocked-stuck.md` |

---

## Triage rituals

Morning review · end of day · inbox triage · weekly stale check · cross-project sweep.
Load `references/triage-rituals.md` when the user asks for any of these patterns.

---

## Choosing the right verb (decision trees)

### Adding a task

```
User wants to add a task.
  ├─ cwd inside the target activity, no other project named?
  │     → octopus capture "<title>" [flags]
  │     → octopus add task "<title>" [flags]   (equivalent — pick either)
  ├─ User named a specific project, cwd elsewhere?
  │     → octopus add task "<title>" --activity <id-or-path> [flags]
  └─ No clear target?
        → ASK "which activity?" (Rule 12)
        → If you have an inbox convention configured, propose it; don't auto-route
```

### Editing a task

```
User wants to edit task fields.
  ├─ Single task, cwd inside its activity?
  │     → octopus set <slug> --field X
  ├─ Multiple tasks in the current activity?
  │     → octopus set --task t1 --task t2 --field X
  │     → octopus set --task t1,t2,t3 --field X     (comma-form is equivalent)
  ├─ Activity-level field (priority, status, title, type, area)?
  │     → octopus set --activity <id> --field X     (works from anywhere)
  ├─ Multiple activities at once?
  │     → octopus set --activity a1 --activity a2 --status paused
  └─ Renaming the slug?
        → octopus set <slug> --slug <new> [-y]      (confirm — Rule 10)
```

D84 axes are **mutually exclusive**: positional + `--task` / positional + `--activity` / `--task` + `--activity` all error. Pick one shape per invocation.

### Moving a task between buckets

```
Goal of the move?
  ├─ Lifecycle (real start/finish/drop with date stamps)?
  │     → octopus start | finish | drop
  ├─ Promote/demote in the pipeline (with verb side effects)?
  │     → octopus plan | focus | park | defer
  ├─ Just relocate the file + frontmatter, no lifecycle side effects?
  │     → octopus mv <slug> <bucket>
  └─ Just change the frontmatter bucket without moving the file?
        → octopus set <slug> --bucket <name>   (warns on folder mismatch — D77)
```

### Reading a project

```
What does the user want to see?
  ├─ Quick "what's the state of X" for a human?
  │     → octopus status <path-or-id>
  ├─ JSON for programmatic consumption (lean — metadata + counts + previews)?
  │     → octopus status <path-or-id> --json
  ├─ JSON with full task arrays (all fields, every task)?
  │     → octopus get activity <path-or-id>
  ├─ Just the tasks in X?
  │     → octopus list tasks <path-or-id>
  ├─ Composite cross-project view?
  │     → octopus dashboard
  ├─ "What should I focus on next?"
  │     → octopus next                (top 3)
  │     → octopus impact              (full ranked list)
  └─ Activity catalog with filters?
        → octopus list activities [filter flags]
```

---

## Reading vs writing — never blow up the user's data

- **Always read first.** Before any non-trivial write, `octopus status` or `octopus get` to confirm the target.
- **Never `octopus init` or `octopus add activity` without explicit confirmation.** Creating a new activity reshapes the user's workspace.
- **Never `octopus forget activity` without explicit confirmation.** Even though it doesn't touch files by default, the index removal is surprising.
- **Never `--slug` (cascading rename) without explicit confirmation and `-y`.** It rewrites every Octopus-managed reference. Reversible only with another rename.
- **Bulk writes (`set --task t1 t2 t3` or `set --activity a1 a2`) get explicit confirmation.** The leverage is real.
- **JSON output is for the agent's next decision.** Don't dump JSON to the user unless they asked; use `octopus status` or `dashboard` (rich) when the user is watching.

---

## Write mechanics

Task naming · kind · tags · slug renames · set vs mv · capture flags · promotion · bridges.
Load `references/write-mechanics.md` when: naming a new task, setting kind/tags, renaming a slug, using capture flags, promoting a task, or working with bridge adapters.

---

## Presenting tasks in chat

Render as ASCII layouts (Focus / Board / Compact) matching the TUI glyphs — not generic markdown lists.
Load `references/chat-rendering.md` before rendering any task layout in chat.

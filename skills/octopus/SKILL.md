---
name: octopus
description: Use when capturing, planning, focusing, starting, finishing, dropping, blocking, or reviewing tasks; querying open loops, stuck items, dashboards, or the current activity; managing the .octopus/ folder system on disk; recording sessions; writing memory or handoffs; routing user intent like "what should I do" or "what's going on" to the right verb. Folder-native, CLI-driven (octopus / octo); cross-activity write and read verbs let agents work from any cwd.
version: 1.1.0
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
| "what should I do" / "what's next" / "what's on my plate" | `octopus next` | `octopus impact` for the full ranked list |
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
| "I'm starting on \<project\>" | `octopus status <project>` first (read), then any writes | use `--activity` on every write that follows |

Three rules that frame everything above:
- **Read before write.** When the user names a project, `status` it first to confirm the target resolves.
- **JSON for agents, rich text for humans.** Use `octopus get` / `--json` when the output feeds into your next decision. Use `octopus status` / `dashboard` (rich) when the user is watching.
- **Never grep what a verb knows.** `octopus dashboard`, `octopus next`, `octopus impact`, `octopus list --has-*` exist precisely so you don't have to glue together `list --all | grep`.

---

## Triage rituals

Recurring patterns the agent should suggest or run autonomously when the user invites them:

### Morning review
1. `octopus dashboard` — what's loud right now.
2. `octopus next` — the top 3 things the heuristic surfaces.
3. Drill into the top item: `octopus status <slug>` or `octopus get activity <id>` for full context.
4. Pick one, `octopus start <slug>` (use `--activity` if running from outside).

### End of day
1. `octopus list activities --touched-within 1` — what got worked on today.
2. For each touched activity, `octopus memory append <id> "<one-line>"` for what changed.
3. If a work block needs continuity: `octopus session end --handoff` to leave a router note.

### Inbox triage
1. `octopus bridge pull --all` — drain TODO.md, Reminders, etc.
2. `octopus list activities --has-now --has-pinned` — see where the pulled items landed.
3. Promote anything that's really a project, not a task: `octopus promote <slug> --to spectacular:<slug>`.

### Weekly stale check
1. `octopus stale` (default: next-bucket tasks not touched in >14 days).
2. For each, decide: `octopus park <slug>` (back to backlog), `octopus archive <slug>` (hide), or `octopus drop <slug>` (acknowledge it's not happening).
3. `octopus list activities --include-archived --touched-within 60` to spot zombies.

### Cross-project sweep
- `octopus impact --limit 0 --show-score` — full ranked list.
- `octopus list activities --priority urgent` — the projects that should be loudest.
- Mismatch (urgent project with no high-priority tasks)? → review whether the priority is still right.

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
  ├─ JSON for programmatic consumption?
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

## Tags (D76)

Tags are stored with leading `#` in frontmatter to match Obsidian:

```yaml
tags:
  - "#bug"
  - "#tui/marquee"        # nested via /
  - "#release/p0"
```

The reader accepts both `#bug` and `bug` (silent normalization on write). All tag flag values accept input with or without `#`.

### Tag flag matrix

The same four flag families exist on both `capture` and `set`:

| Flag | Behavior |
|---|---|
| `--tag <X>` / `--tags <X[,Y…]>` | **Replace** the tag list |
| `--add-tag <X>` / `--add-tags <X[,Y…]>` | **Append** (dedup) |
| `--remove-tag <X>` / `--remove-tags <X[,Y…]>` | **Remove** (no-op if absent) |
| `--clear-tags` | **Empty** the tag list |

Singular and plural are aliases. All accept three input forms, interchangeable:
- comma-separated: `--tag X,Y,Z`
- space-separated within quotes: `--tag "X Y Z"`
- repeated invocation: `--tag X --tag Y --tag Z`

**Mutex:** `--tag/--tags` (replace) cannot be combined with `--add-tag/--remove-tag/--clear-tags` (incremental). Mixing them errors with a clear message. When combining incremental flags, the apply order is `clear → remove → add`.

### Tag filtering

`octopus list --tag parent` matches both `#parent` and any `#parent/*` (prefix match on `/` boundary, Obsidian convention).

---

## Slug renames and references (D78, D79)

Slugs are filenames — they're CLI-owned. To change one safely, use `octopus set <old> --slug <new>`. This is the **only** way to rename a task.

The rename cascades automatically:
- Filesystem rename (`tasks/<bucket>/<old>.md` → `tasks/<bucket>/<new>.md`)
- SQLite index update
- `waiting_for: <old>` rewrites in any other task's frontmatter
- `related_tasks: [..., <old>, ...]` and `promoted_from: <old>` rewrites in spectacular PLAN.md files
- `→ octopus:<old>` arrow rewrites in any TODO.md the activity has

User-prose bodies are NOT auto-fixed but ARE named in the warning:
- session bodies, memory body, handoff bodies

Without `-y`, the rename prompts with a full preview. Pass `-y` to skip.

**Companion verb:** `octopus refs find <slug>` is a read-only grep over every Octopus-managed text file in the activity (`--all` for cross-activity). Splits output into managed refs and user-prose mentions. Useful after a rename to spot residual references, or just to answer "where does this slug appear?"

---

## `set` vs `mv` vs lifecycle verbs (D77)

These three categories overlap on `bucket`, and the boundary is intentional:

| Use this when… | Verb | Side effects |
|---|---|---|
| You want to change frontmatter only — no file move | `set --bucket <x>` | Frontmatter only. Soft warning if folder mismatches in folder-mode storage. |
| You want to physically move the file (and update frontmatter) | `octopus move <slug> <bucket>` / `mv` | File move + frontmatter. **No date stamps, no other side effects.** |
| You want lifecycle side effects (date stamps, clearing pinned/issue/run_state) | `start` / `finish` (alias `end`) / `drop` | File move + frontmatter + lifecycle bookkeeping. |

`mv` will reject a move to `done`/`dropped` without the required dates and points the user at `finish`/`drop`.

---

## Capture flag surface (v0.6.0)

`octopus capture <title>` accepts:

| Flag | Field set |
|---|---|
| `--next` / `--now` | `bucket` (mutually exclusive). `--now` does **NOT** auto-pin (D81). |
| `--slug <x>` | Override the auto-generated slug |
| `--priority <urgent\|high\|low>` | `priority` (use `normal`/`none`/`""` to clear) |
| `--due <YYYY-MM-DD>` | `due` |
| `--scheduled <YYYY-MM-DD>` | `scheduled` |
| `--start-date <YYYY-MM-DD>` | `start_date` (does NOT trigger the `start` verb) |
| `--end-date <YYYY-MM-DD>` | `end_date` (validation will reject this without a terminal bucket) |
| `--actor <ai\|automation>` | `actor` (use `human`/`""` to clear — human is the default) |
| `--energy <low\|mid\|high>` | `energy` |
| `--owner <name>` | `owner` |
| `--stage <text>` | `stage` (per-activity workflow stage) |
| `--tag/--tags/--add-tag/...` | full tag flag matrix (see above) |

Empty body by default (D82) — no more hardcoded `## References`.

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

Adapters bridge Octopus to external systems. v1 ships pull-only. Operating via the `octopus bridge` verb group (`list / enable / disable / status / peek / pull / search`).

Two distinct verbs for reading:
- **`peek`** — read-only display, no files created. Safe exploration.
- **`pull`** — imports as Octopus task files, deduped via `task_external_refs`.

When the user wants to "see what's there" → `peek`. When they want to "bring it in" → `pull`. For full operational guidance, see `references/adapter-framework.md`.

### Adapters shipping with v1

- **Obsidian** (#07): viewer via symlinks. `octopus link` symlinks `.octopus/` into a configured vault location. Read-only.
- **Apple Reminders** (#09): pull-only via `osascript`. Pulls from configured `lists`.
- **TODO.md** (#21): pull-only. Reads `- [ ]` lines from `TODO.md` at activity root.
- **Claude Code plugin**: NOT an adapter — it's a *client* of Octopus. Slash commands (`/octopus:start`, `/octopus:end`, `/octopus:handoff`, `/octopus:where`, `/octopus:memory`, `/octopus:log`) wrap the CLI.

Two-way external sync (Reminders push, GitHub, ICS) is v2.

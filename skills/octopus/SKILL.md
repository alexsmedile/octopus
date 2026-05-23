---
name: octopus
description: Use when capturing, planning, focusing, starting, finishing, dropping, blocking, or reviewing tasks; querying open loops, stuck items, or the current activity; managing the .octopus/ folder system on disk; recording sessions; writing memory or handoffs. Folder-native, CLI-driven (octopus / octo); prefer verbs over hand-editing.
version: 0.2.0
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
| Inspection | `show`, `task list`, `task show` |
| Views | `loops`, `today`, `stuck`, `stale`, `context` |
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

## Bridges (v1 scope)

- **Obsidian**: `octopus link` symlinks `.octopus/` into a configured vault location. Read-only viewing layer.
- **Apple Reminders**: pull-only import in v1. No two-way sync.
- **Claude Code plugin**: this repo IS the plugin. Slash commands (`/octopus:start`, `/octopus:end`, `/octopus:handoff`, `/octopus:where`, `/octopus:memory`, `/octopus:log`) wrap the CLI.

Two-way external sync (Reminders, GitHub, ICS) is v2.

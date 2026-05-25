# CLAUDE.md — Octopus

Guidance for agents working on the Octopus project.

## Identity

Octopus is an autonomous folder-native project and task orchestration system.

It is an AI-native project operations layer for local-first workflows: a filesystem-native activity and project management agent that coordinates Obsidian task notes, Apple Reminders, local project folders, session handoffs, and coding agents.

## Source of Truth

This folder is the source workspace for Octopus project/design work:

- `/Users/alex/vault/data/skills_db/octopus`

The live task database remains separate:

- `/Users/alex/vault/tasks`

Do not move real task records into this project folder unless Alessandro explicitly asks.

## Repo layout

```
octopus/
├── README.md                       # public entry point
├── CLAUDE.md                       # this file — agent rules
├── AGENTS.md                       # repo-wide agent rules
│
├── .spectacular/                   # design workspace + shipped specs
│   ├── PRD.md                      # canonical product spec (single source of truth)
│   ├── SPEC.md                     # the .octopus/ folder contract (versioned, frozen)
│   ├── STACK.md                    # locked language/library choices
│   ├── DECISIONS.md                # append-only decisions log (D1, D2, …)
│   ├── AGENTS.md                   # agent rules for spectacular work
│   ├── config.yaml                 # spectacular project config
│   ├── specs/                      # spec breakouts (authoritative companions to SPEC.md)
│   │   ├── SCHEMA-TASK.md
│   │   ├── SCHEMA-ACTIVITY.md
│   │   ├── SCHEMA-SESSION.md
│   │   ├── SCHEMA-HANDOFF.md
│   │   ├── SCHEMA-MEMORY.md
│   │   ├── AXIS-MODEL.md
│   │   ├── CLI-VERBS.md
│   │   └── CRITICAL-DEPENDENCIES.md
│   └── requests/                   # one folder per request (PLAN.md, TASKS.md)
│
├── skills/                         # standalone skills
│   └── octopus/
│       └── SKILL.md                # agent-facing compressed operating skill
│
└── _archive/                       # legacy design docs (read-only, kept for history)
```

## Where the specs live

All design specs live under `.spectacular/`. There is no separate `specs/` or `docs/` at the project root.

| What you need | Where to find it |
|---|---|
| Product spec / vision / scope | `.spectacular/PRD.md` |
| `.octopus/` folder contract (top-level) | `.spectacular/SPEC.md` |
| Task frontmatter schema | `.spectacular/specs/SCHEMA-TASK.md` |
| Activity frontmatter schema | `.spectacular/specs/SCHEMA-ACTIVITY.md` |
| Session schema | `.spectacular/specs/SCHEMA-SESSION.md` |
| Handoff schema | `.spectacular/specs/SCHEMA-HANDOFF.md` |
| Memory schema | `.spectacular/specs/SCHEMA-MEMORY.md` |
| Four-axis task model | `.spectacular/specs/AXIS-MODEL.md` |
| CLI verbs & views | `.spectacular/specs/CLI-VERBS.md` |
| TUI glyph dictionary | `.spectacular/specs/TUI-GLYPHS.md` |
| TUI keybinding schema | `.spectacular/specs/TUI-KEYS.md` |
| Validation rules across all schemas | `.spectacular/specs/CRITICAL-DEPENDENCIES.md` |
| Language/library choices | `.spectacular/STACK.md` |
| Locked decisions log | `.spectacular/DECISIONS.md` |

## Read order before editing

1. Read this file.
2. Read `.spectacular/PRD.md` for product context.
3. Read `.spectacular/DECISIONS.md` to see what's already locked.
4. Read `.spectacular/SPEC.md` for the on-disk contract.
5. If touching a schema, read the relevant `.spectacular/specs/SCHEMA-*.md`.
6. If activating or working on a request, read its `.spectacular/requests/<slug>/PLAN.md` and `TASKS.md`.
7. If touching `/Users/alex/vault/tasks`, also read `/Users/alex/vault/tasks/AGENTS.md`.

## Authority hierarchy

When two docs disagree, this is the order of authority:

1. `.spectacular/DECISIONS.md` — locked decisions win over speculative text.
2. `.spectacular/specs/*.md` — the detailed contract.
3. `.spectacular/SPEC.md` — conceptual map; should track the schema docs.
4. `.spectacular/PRD.md` — product spec; older than schema docs in some places.

If you find a conflict, surface it to Alessandro before resolving. Do not silently rewrite.

## Working rules

- Treat Octopus as a project/skill, not as the live task database.
- Keep project docs, prompts, schemas, examples, and scripts here.
- Keep live user tasks in `/Users/alex/vault/tasks`.
- Preserve links and old-path compatibility when moving docs.
- Prefer small, explicit changes over broad rewrites.
- If changing routing or schema, update **both** the schema doc and `DECISIONS.md`.
- **Skill-reference sync rule**: when editing any spec under `.spectacular/specs/SCHEMA-*.md`, `CLI-VERBS.md`, or `CRITICAL-DEPENDENCIES.md`, also update the matching file under `skills/octopus/references/` (or `references/schemas/` for schema specs). The skill must remain self-contained — agents installing the plugin do not get access to `.spectacular/`. Mapping:
  | Spec changed | Update |
  |---|---|
  | `SCHEMA-TASK.md` | `skills/octopus/references/schemas/task.md` |
  | `SCHEMA-ACTIVITY.md` | `skills/octopus/references/schemas/activity.md` |
  | `SCHEMA-SESSION.md` | `skills/octopus/references/schemas/session.md` |
  | `SCHEMA-MEMORY.md` | `skills/octopus/references/schemas/memory.md` |
  | `SCHEMA-HANDOFF.md` | `skills/octopus/references/schemas/handoff.md` |
  | `CLI-VERBS.md` | `skills/octopus/references/cli-verbs.md` |
  | `TUI-GLYPHS.md` | `skills/octopus/references/tui-glyphs.md` |
  | `TUI-KEYS.md` | `skills/octopus/references/tui-keys.md` |
  | `CRITICAL-DEPENDENCIES.md` | `skills/octopus/references/critical-dependencies.md` |
  References are *rewritten for the skill context* (operational, terse), not verbatim copies. Update both files in the same commit when content overlaps. If drift becomes recurrent, escalate to a pre-commit hook.
- Do not run install/sync/deploy commands unless Alessandro explicitly asks.
- Never delete files. Move to `_archive/` instead.

## Request workflow (spectacular)

Each request in `.spectacular/requests/<slug>/` has:
- `PLAN.md` — goal, why, approach, deliverables.
- `TASKS.md` — checkable task list, created when the request becomes active.

When activating a request:
1. Read its `PLAN.md`.
2. Confirm gates (other requests listed in `gates:` are done).
3. Generate `TASKS.md` if not present.
4. Work top-to-bottom, marking tasks as you go.
5. When done, set `status: done` in `PLAN.md` frontmatter and update `DECISIONS.md` if any decision was locked.

## Authority on safety

This is a design + implementation project for a system that will eventually manage Alessandro's real task data. Code changes in `cli/` (when it exists) and `plugin/` (when it exists) are not destructive at this stage; care is required when scripts are later run against `/Users/alex/vault/tasks` or other live folders. Default to dry-run, prompt before mutation, never delete.

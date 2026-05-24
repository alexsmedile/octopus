# Repo layout

A map of where things live in the Octopus repo. Most of this is for contributors and the curious — daily users only need `cli/` and the `octopus` command.

```
octopus/
├── README.md                       ← entry point
├── CLAUDE.md                       ← agent rules + spec navigation map
├── AGENTS.md                       ← repo-wide agent rules
├── TODO.md                         ← deferred ideas (mind-view, routines, …)
├── CHANGELOG.md                    ← release history
│
├── cli/                            ← the Python CLI itself
│   ├── pyproject.toml
│   ├── src/octopus/                ← cli.py, core/, fs/, db/, config.py, tui/
│   └── tests/
│
├── skills/octopus/                 ← standalone Claude Code skill
│   ├── SKILL.md
│   └── references/                 ← schemas, verbs, deps — rewritten for skill context
│
├── plugin/                         ← Claude Code + Codex plugin
│   ├── commands/                   ← /octopus:* verbs
│   ├── agents/                     ← orchestrator + helpers
│   └── hooks/
│
├── docs/                           ← human docs (this folder)
│   ├── REPO-LAYOUT.md              ← you are here
│   ├── TUI.md                      ← full TUI keymap + behavior
│   ├── ROADMAP.md                  ← release history + what's next
│   └── assets/                     ← README SVGs + version snapshots
│
├── .spectacular/                   ← design workspace + shipped specs
│   ├── PRD.md                      ← product vision
│   ├── SPEC.md                     ← the .octopus/ folder contract
│   ├── STACK.md                    ← Python 3.11+, Typer, Textual, SQLite
│   ├── DECISIONS.md                ← every locked decision, dated
│   ├── specs/                      ← SCHEMA-*.md, CLI-VERBS.md, AXIS-MODEL.md
│   └── requests/                   ← PLAN.md / TASKS.md per build phase
│
└── _archive/                       ← old design drafts (kept, not active)
```

## Where to look for what

| If you want… | Read |
|---|---|
| Product vision and scope | [`.spectacular/PRD.md`](../.spectacular/PRD.md) |
| The on-disk `.octopus/` contract | [`.spectacular/SPEC.md`](../.spectacular/SPEC.md) |
| Task frontmatter schema | [`.spectacular/specs/SCHEMA-TASK.md`](../.spectacular/specs/SCHEMA-TASK.md) |
| Activity / session / memory / handoff schemas | [`.spectacular/specs/SCHEMA-*.md`](../.spectacular/specs/) |
| The four-axis task model | [`.spectacular/specs/AXIS-MODEL.md`](../.spectacular/specs/AXIS-MODEL.md) |
| All CLI verbs and views | [`.spectacular/specs/CLI-VERBS.md`](../.spectacular/specs/CLI-VERBS.md) |
| Locked decisions, dated | [`.spectacular/DECISIONS.md`](../.spectacular/DECISIONS.md) |
| What we built and when | [`docs/ROADMAP.md`](ROADMAP.md) |
| TUI key bindings | [`docs/TUI.md`](TUI.md) |
| Stack choices and rationale | [`.spectacular/STACK.md`](../.spectacular/STACK.md) |

## Conventions

- `_archive/` folders are kept for history. Never delete; move stale work here.
- `docs/assets/_versions/` holds timestamped snapshots of README SVGs.
- Schema work updates **both** the `.spectacular/specs/SCHEMA-*.md` file and the matching `skills/octopus/references/schemas/*.md` — the skill must stay self-contained for installs.

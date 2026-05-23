---
status: done
priority: medium
owner: alex
updated: 2026-05-23
closed: 2026-05-23
closed_note: "Scaffold shipped in v0.1.0 (6 slash commands, 3 agents, 2 hooks, .claude-plugin/ + .codex-plugin/ + .agents/plugins/marketplace.json). Install assistant, session-start hook, and bundle polish deferred to a follow-up when the repo goes public."
summary: "Claude Code plugin — skill, agents, command, install assistant, session-start hook, bundle commands."
related:
  - 07-adapter-obsidian
gates:
  - 03-index-sqlite
---

# Claude Code plugin

## Goal

Thin markdown + shell wrapper that teaches Claude how to use the `octopus` CLI (PRD §10, §13.8). No Python, no bundled venv.

## Scope summary

- `plugin/.claude-plugin/plugin.json` with `requires.octopus-cli >= <version>`.
- `plugin/skills/octopus/SKILL.md` — decision tree, CLI-first execution rules, anti-pattern guard.
- `plugin/agents/` — `octopus-triage.md`, `octopus-reviewer.md`, `octopus-scanner.md`.
- `plugin/commands/octopus.md` — `/octopus` passthrough.
- `plugin/hooks/on-session-start.sh` — injects `octopus context --format json`.
- Install assistant via `octopus-setup` command for missing/outdated CLI.
- New CLI bundle commands: `octopus context`, `octopus daily`, `octopus suggest`.

## Detailed PLAN.md to be drafted when this request activates.

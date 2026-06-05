# AGENTS.md — Octopus

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

## Read First

Before editing:

1. Read this file.
2. Read `README.md` for product context.
3. Read `CLAUDE.md` for project-specific agent rules (spec navigation, skill-reference sync rule, request workflow, authority hierarchy).
4. Read `.spectacular/PRD.md` for vision, `.spectacular/DECISIONS.md` for locked decisions, and `.spectacular/SPEC.md` for the on-disk contract.
5. If touching a schema or behavior covered by a companion spec, read the relevant file under `.spectacular/specs/`.
6. If activating or working on a request, read its `.spectacular/requests/<slug>/PLAN.md` and `TASKS.md`.
7. If touching `/Users/alex/vault/tasks`, also read `/Users/alex/vault/tasks/AGENTS.md`.

## Working Rules

- Treat Octopus as a project/skill, not as the live task database.
- Keep project docs, prompts, schemas, examples, and scripts here.
- Keep live user tasks in `/Users/alex/vault/tasks`.
- Preserve links and old-path compatibility when moving docs.
- Prefer small, explicit changes over broad rewrites.
- If changing routing or schema, update the authoritative spec document(s) and `DECISIONS.md`.
- For governed spec changes (`SCHEMA-*`, `CLI-VERBS`, `TUI-GLYPHS`, `TUI-KEYS`, or `CRITICAL-DEPENDENCIES`), update the matching `skills/octopus/references/*` file in the same change per the sync rule in `CLAUDE.md`.
- Do not run install/sync/deploy commands unless Alessandro explicitly asks.
- Never delete files. Move to `_archive/` instead.

## Good Next Files

- `CLAUDE.md` — full agent operating rules (more detailed than this file)
- `.spectacular/PRD.md` — product vision
- `.spectacular/SPEC.md` — `.octopus/` folder contract overview
- `.spectacular/specs/` — schemas, CLI verbs, validation rules, axis model
- `.spectacular/DECISIONS.md` — every locked decision, dated
- `.spectacular/requests/<slug>/PLAN.md` — active build phases
- `skills/octopus/SKILL.md` — the agent-facing compressed operating skill (router; loads from `references/` on demand)
- `skills/octopus-migrate/SKILL.md` — project-migration skill: init + TODO.md Layer 2 rewrite + bridge pull + vault/tasks archive
- `CHANGELOG.md` — release history
- `TODO.md` — deferred ideas (routines, mind-view, soft-delete, …)

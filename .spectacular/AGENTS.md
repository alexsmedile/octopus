# Agent operating instructions — Octopus

This file governs how AI agents (Claude Code, Codex, others) work inside the Octopus project.

## Project identity

- Octopus is a Python CLI + adapter framework for folder-native task/activity management.
- Source of truth: this folder (`/Users/alex/vault/data/skills_db/octopus/`).
- Live user task database (separate concern): `/Users/alex/vault/tasks`. **Do not move real tasks into this folder.**

## Read order before editing

1. `.spectacular/PRD.md` — current product spec.
2. `.spectacular/DECISIONS.md` — what's already locked.
3. `.spectacular/STACK.md` — language/library choices.
4. The PLAN.md of the current request.
5. Any AGENTS.md / CLAUDE.md in the folder you're about to touch.

## Hard rules

- **Never delete files.** Move to `_archive/` instead.
- **Never modify `.obsidian/`** anywhere.
- **Confirm before**: file deletion, moves, bulk edits (>5 files), restructuring, schema changes.
- **Preserve frontmatter and wikilinks** when editing markdown.
- **PRD §13 decisions are load-bearing.** If a request would conflict with §13, surface the conflict first — do not silently override.

## Request workflow

Each request in `.spectacular/requests/<slug>/` has:
- `PLAN.md` — goal, why, approach, deliverables.
- `TASKS.md` — checkable task list, created when the request becomes active.

When activating a request:
1. Read its PLAN.md.
2. Confirm gates (other requests listed in `gates:` are done).
3. Generate TASKS.md if not present.
4. Work top-to-bottom, marking tasks as you go.
5. When done, set `status: done` in PLAN.md frontmatter and update `DECISIONS.md` if any decision was locked.

## Status taxonomy for PLAN.md frontmatter

- `queued` — captured, not started.
- `active` — currently in progress.
- `paused` — intentionally stopped.
- `done` — shipped.
- `blocked` — waiting on something external; note what in the body.

## Token economy

For any task touching `.octopus/` folders elsewhere on the filesystem, **prefer calling the `octopus` CLI** over reading/writing files directly. The CLI is the protocol; direct file edits bypass validation and indexing.

In this project, the CLI doesn't exist yet — file edits are expected. Once `02-cli-walking-skeleton` ships, this rule activates.

## When asking the user

- Use AskUserQuestion for branching decisions.
- For grilling open design questions, use the `grill-me` skill — one question at a time, recommendation first.

## Safety summary

This is a design + implementation project for a system that will eventually manage Alessandro's real task data. Code changes here are not destructive; but care is required when scripts in `cli/` are later run against `/Users/alex/vault/tasks` or other live folders. Default to dry-run, prompt before mutation, never delete.

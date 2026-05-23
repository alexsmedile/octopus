---
status: queued
priority: medium
owner: alex
updated: 2026-05-21
summary: "Apple Reminders pull-only — import capture list to backlog tasks with external_refs.reminders populated."
related:
  - 06-adapter-framework
  - 10-sync-modes-addendum
gates:
  - 06-adapter-framework
---

# Apple Reminders adapter — pull only

## Goal

Second adapter — one-way import of a capture list into Octopus backlog (PRD §7.5). Validates the adapter framework with a non-symlink integration.

## Scope summary

- `adapters/reminders.py` — wraps `osascript` / `shortcuts run` for list reads.
- `octopus reminders pull` — read configured capture list, create backlog tasks in target activity (configured or prompt-each-time).
- Populates `external_refs.reminders` so future two-way work has the ID handy.
- **No push.** No completion sync. No two-way.

## Detailed PLAN.md to be drafted when this request activates.

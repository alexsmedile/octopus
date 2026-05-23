---
status: queued
priority: medium
owner: alex
updated: 2026-05-21
summary: "Textual TUI — activity list / task list / detail panes. Daily driver."
related:
  - 03-index-sqlite
  - 04-sessions-memory
gates:
  - 04-sessions-memory
---

# Textual TUI

## Goal

`octopus tui` — full-screen Textual app over the SQLite index. The intended daily driver before any web view exists.

## Scope summary

Panes: activity list (left) / tasks for selected activity (center) / detail pane (right).
Keys: `j/k` navigate, `Enter` open in `$EDITOR`, `n` new task, `s` start session, `/` filter, `g` reindex, `?` help.
Reads from SQLite via the same layer as CLI. No new write paths.

## Detailed PLAN.md to be drafted when this request activates.

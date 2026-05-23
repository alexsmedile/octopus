---
status: queued
priority: low
owner: alex
updated: 2026-05-21
summary: "First two-way adapter — validates the sync-modes addendum on real Reminders data."
related:
  - 09-adapter-reminders-pull
  - 10-sync-modes-addendum
gates:
  - 10-sync-modes-addendum
---

# Apple Reminders — two-way (v1.5)

## Goal

Push side: mirror Octopus tasks matching a config rule into a target Reminders list; round-trip completion state.

Validates everything decided in request 10. If the addendum is right, this is mostly mechanical.

## To be expanded when activated.

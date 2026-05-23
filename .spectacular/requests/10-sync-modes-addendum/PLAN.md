---
status: queued
priority: high
owner: alex
updated: 2026-05-21
summary: "PRD addendum — resolve sync mode taxonomy, conflict policy, identity dedup, sync journal semantics."
related:
  - 09-adapter-reminders-pull
  - 14-adapter-reminders-twoway
gates:
  - 09-adapter-reminders-pull
---

# Sync modes — PRD addendum

## Goal

Pure design exercise, no code. Resolve the open questions PRD §7.6 deferred. Produces an addendum to `PRD.md` (or a sibling `PRD-sync.md`) that the v1.5 two-way adapters can implement against.

## Why this comes after request 09

The addendum reflects what was actually learned from running pull-only Reminders in production for a few weeks. Designing it earlier produces speculation; designing it after produces reality.

## Scope summary — open questions to answer

- Conflict policy per adapter: `octopus_wins | external_wins | newest_wins | ask` defaults and per-field overrides.
- Sync triggers: manual, scheduled (cron-like), reactive (on-mutation). Which is default? Which is allowed?
- Identity dedup: when the same task is created twice (Octopus + Reminders, near-simultaneous), how is it reconciled?
- Sync journal format: what's persisted in `~/.local/share/octopus/sync/`, how recovery works after a crashed sync.
- Privacy disclaimer wording for cloud adapters.

## Out of scope

- Any code. This is design only.
- Specific adapter implementations beyond what the framework requires.

## Detailed PLAN.md to be drafted when this request activates.

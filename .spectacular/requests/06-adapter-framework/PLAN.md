---
status: queued
priority: medium
owner: alex
updated: 2026-05-21
summary: "Adapter protocol, capability enum, external_refs active, config-driven enable/disable, sync journal scaffold."
related:
  - 07-adapter-obsidian
  - 09-adapter-reminders-pull
gates:
  - 03-index-sqlite
---

# Adapter framework

## Goal

The shared protocol every adapter implements (PRD §7.1). Lays scaffolding for sync journal, capability gating, config-per-adapter. Critical that this lands *before* any adapter is built — designing the framework around one hardcoded bridge produces the wrong abstractions.

## Scope summary

- `adapters/base.py` — `Adapter` protocol, `Capability` enum, `AdapterStatus`, `ExternalTask`, `ExternalRef`.
- `config.py` — load `~/.config/octopus/bridges/<name>.toml`, enable/disable per adapter.
- `octopus bridge list | enable | disable | status` commands.
- Sync journal scaffold at `~/.local/share/octopus/sync/` (unused in v1, structure defined).

## Detailed PLAN.md to be drafted when this request activates.

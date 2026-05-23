---
status: queued
priority: medium
owner: alex
updated: 2026-05-21
summary: "Symlink farm, octopus link, generated octopus-*.base files, target registration with backups."
related:
  - 06-adapter-framework
gates:
  - 06-adapter-framework
---

# Obsidian adapter

## Goal

First adapter — read-only viewing layer for Obsidian users (PRD §7.4, §13.6).

## Scope summary

- `adapters/obsidian.py` — symlink management, `.base` file generation.
- Commands: `octopus link`, `octopus unlink`, `octopus bridge target add/remove`, `octopus bridge backups list/restore`.
- Generated files use `octopus-` prefix exclusively unless target explicitly registered.
- Backups on every overwrite of a registered target file.
- `BRIDGE.md` generated in link directory.

## Detailed PLAN.md to be drafted when this request activates.

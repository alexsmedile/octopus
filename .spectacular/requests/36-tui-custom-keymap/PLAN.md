---
status: idea
priority: low
owner: alex
updated: 2026-05-25
summary: "User-configurable keymap with verb aliases (finish→done, drop→cancel). Load from .octopus/keymap.toml at TUI startup; fall back to defaults."
related:
  - 34-tui-key-schema
gates: []
---

# Custom keybindings & verb aliases

## Goal

Let users override default keybindings and rename verbs without touching code. Two layers:

1. **Key remap** — bind any action to any key. `e: edit_inline` → `i: edit_inline`.
2. **Verb aliases** — rename the action label shown in the keymap bar and toasts. `finish` → `done`, `drop` → `cancel`. The underlying state machine is unchanged.

## Why

Personal preference is the entire reason. Alessandro prefers "done" over "finish", "cancel" over "drop". Hardcoding aliases pollutes the codebase; a config file keeps the canonical verb set stable and lets the surface vocabulary flex.

## Shape

- New file: `.octopus/keymap.toml` per activity (or global default at `~/.config/octopus/keymap.toml`).
- TUI loads at boot, merges over defaults, validates (unknown actions → warn + skip).
- Footer/help/toast text use alias when present.

## Non-goals

- Macros / chords / multi-key sequences.
- Per-screen overrides (one keymap for both Focus and Board).

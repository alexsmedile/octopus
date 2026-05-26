---
status: idea
priority: low
owner: alex
updated: 2026-05-25
summary: "Preview-row UX improvements: dwell-based auto-expand on hover, expand-all toggle, smarter collapse heuristics."
related:
  - 33-tui-visual-redesign
gates: []
---

# Preview row — expand controls

## Goal

Two additions to the inline 1-row preview that already exists (Enter to toggle):

1. **Dwell auto-expand** — after the cursor sits on a row for ~250ms, auto-expand the preview. Move within that window → no expand. Avoids the jitter of expand-on-every-highlight while still feeling fluid.
2. **Expand-all toggle** — one keystroke to expand previews on every row in the focused panel (or every panel). Toggle off restores compact view.

## Why

Enter-to-expand is fine for spot inspection but slow when triaging. Power users want the at-a-glance grid; casual users want it quiet. Both modes should be reachable without re-architecting.

## Open questions

- Dwell or no dwell by default? Probably **off** — opt in via config. Auto-expand is divisive.
- Expand-all keybinding: `Z`? `Shift+Enter`? (`E` taken by edit-external.)
- Does expand-all apply per-panel (focused only) or globally? Per-panel is less surprising.

## Risks

- Auto-expand causes layout shift on nav, which can disorient. Mitigation: keep row height stable (preview slot reserved but invisible when collapsed), OR animate.
- Expand-all on a 50-task backlog blows up the panel height. Mitigation: cap expanded rows or scroll-clip.

## Non-goals

- Multi-row previews (still exactly 1 row of properties).
- Configurable per-bucket properties (separate request if it ever lands).

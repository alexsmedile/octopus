---
status: done
priority: high
owner: alex
updated: 2026-05-25
summary: "Audit every glyph used in the TUI against TUI-GLYPHS.md spec. Catalog drift, decide spec-vs-code as source of truth per case, reconcile. Gate for v1.0.0 release."
related:
  - 33-tui-visual-redesign
  - 34-tui-key-schema
gates: []
---

# Glyph audit & reconciliation

## Goal

`tui_glyphs.md` defines the canonical glyph dictionary. Code in `icons.py`, status renderers, chips, and ad-hoc strings in `focus.py` / `board.py` have drifted. Specifically:

- Status glyphs vs bucket coloring vs blocked indicator: some overlap visually.
- Cursor `▸`, pinned `★`, blocked `▲` (or `■`? — verify) — confirm each is used consistently.
- Chip glyphs (`[kind]`, `→ provider`, urgent markers) — check spacing and Unicode width on real terminals (some terminals render `★` as 2-cell, breaks layouts).
- Bucket header glyphs: `○ NEXT`, `● NOW`, `✓ DONE`, `✗ DROPPED`, BACKLOG (no glyph). Spec match? Consistency with status glyphs?

## Why

The TUI has reached a point where it looks polished but a careful pass would surface ~half-a-dozen small inconsistencies. Each is trivial alone; together they make the surface feel "off" in a way users can't articulate.

## Method

1. Read `.spectacular/specs/TUI-GLYPHS.md` end-to-end.
2. Grep code for every literal Unicode glyph (`grep -P '[\x{2500}-\x{2BFF}]'`).
3. Build a side-by-side table: glyph | spec definition | code usage | drift.
4. Decide spec-or-code wins per row.
5. Reconcile in one commit per category (status / chips / borders / cursors).
6. Update both spec and `skills/octopus/references/tui-glyphs.md` per the sync rule in CLAUDE.md.

## Risks

- Unicode width quirks across terminals (iTerm2 vs Alacritty vs Ghostty). Audit with all three.
- Changing a status glyph changes muscle memory. Prefer spec-wins only when the code glyph is genuinely worse.

---
status: active
updated: 2026-05-25
---

# Tasks — 41-tui-glyph-audit

## Phase 1 — Audit

- [x] Read `TUI-GLYPHS.md` end-to-end.
- [x] Grep every literal Unicode glyph across `cli/src/octopus/tui/*.py`.
- [ ] Produce `AUDIT.md` in this folder with the drift table: glyph | spec | code | verdict.
- [ ] Cross-check `skills/octopus/references/tui-glyphs.md` against spec (it may be stale too).

## Phase 2 — Decisions

- [ ] Per drift row, mark **spec-wins** or **code-wins**.
- [ ] Surface contentious calls to Alessandro before reconciling.

## Phase 3 — Reconciliation

- [ ] Update code per spec-wins decisions.
- [ ] Update `.spectacular/specs/TUI-GLYPHS.md` per code-wins decisions.
- [ ] Sync `skills/octopus/references/tui-glyphs.md`.
- [ ] Update `DECISIONS.md` with any new locked glyph allocations (e.g. retirements, reservations).
- [ ] Run full test suite; verify TUI renders cleanly in iTerm2 / Alacritty / Ghostty.

## Phase 4 — v1.0.0 wrap-up

- [ ] Mark this request `status: done` in PLAN.md.
- [ ] Run `/wrap-up v1.0.0`.

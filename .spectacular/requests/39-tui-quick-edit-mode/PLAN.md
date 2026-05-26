---
status: idea
priority: medium
owner: alex
updated: 2026-05-25
summary: "Modeless inline quick-edit: Enter on expanded row → enter edit mode, arrow keys flip property values + bucket (icon preview), Enter confirms. No modal."
related:
  - 38-tui-expand-controls
  - 24-capture-edit-polish
gates:
  - 38-tui-expand-controls
---

# Quick-edit mode (inline, modeless)

## Goal

A second Enter on an expanded row enters **quick-edit mode** on that row. While in quick-edit:

- `←` / `→` cycles values of the focused property (e.g. priority: low → med → high → urgent).
- `↑` / `↓` moves between editable properties on the row.
- Bucket changes show an **icon preview** of the target bucket inline (no full re-render until confirm).
- `Enter` confirms the staged changes.
- `Esc` discards staged changes and returns to expanded-but-not-editing state.

The row stays in its place; no modal opens, no popup. The full `e` edit modal remains for body / freeform fields.

## Why

Triage is 80% bucket flips and priority bumps. Opening a modal for each is too heavy. A modeless quick-flip turns a 4-keystroke modal dance into a 2-keystroke inline poke.

## Why this is hard

- Two-stage Enter (expand → quick-edit) conflicts with current "Enter toggles preview" semantics. Either redefine Enter (Enter on expanded row → quick-edit; Esc/second-Enter-on-collapsed-row → noop) or use a separate key.
- Visual indication of edit mode must be unmistakable (border color? cursor glyph swap? inverse video on the row?) or users won't realize arrow keys mean something different.
- Staged-vs-confirmed state must survive cursor moves within the row.
- Undo on Esc means buffering changes — pulls in transient row state.

## Properties worth quick-editing

Priority, bucket, scheduled (date picker?), pinned (toggle), kind. Body, title → modal-only.

## Gate

Build on top of 38 (expand-controls) — quick-edit only makes sense once auto-expand and expand-all are sorted, since the row needs to be in expanded state to enter edit mode.

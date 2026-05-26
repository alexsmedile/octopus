---
status: idea
priority: low
owner: alex
updated: 2026-05-25
summary: "Replace centered modals (move-picker, block reason, confirm) with popovers anchored next to the source row instead of screen-center."
related:
  - 39-tui-quick-edit-mode
gates: []
---

# Anchored popovers

## Goal

Pickers and prompts (move, bucket-picker, confirm-drop, block-reason) currently open as centered modals. Replace with **popovers anchored to the source row** — same visual gravity as the action, less context loss.

## Why

A centered modal hides the row it acts on. The user has to remember which task they were on. An anchored popover (right of the row, or below) keeps the row visible and signals "this menu is about THAT thing".

## Shape

- Textual supports absolute-positioned widgets via `offset` and `layer`.
- Compute anchor: row's screen rect + small offset (8 cols right, 0 rows down by default; flip to left if it would clip the viewport).
- Use the same ConfirmModal / BucketPickerModal logic — just change positioning.
- Esc / Enter behavior unchanged.

## Risks

- Tight panels (board pages) leave little horizontal room. Mitigation: render below the row instead of beside it when there's no room.
- Anchored popovers can clip on small terminals. Fall back to centered modal when terminal < 80 cols.

## Non-goals

- Theming overhaul of modal chrome (already shipped in v0.9.4).
- Anchoring the EditModal — too large to anchor sensibly, stays centered.

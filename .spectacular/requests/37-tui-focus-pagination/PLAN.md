---
status: idea
priority: medium
owner: alex
updated: 2026-05-25
summary: "Add pagination to Focus view via fixed-slot panels + content swap (NOT widget reparenting). 3 pages mirroring board, pipeline-ordered slot layout."
related:
  - 33-tui-visual-redesign
gates: []
---

# Focus view pagination

## Goal

Mirror the Board's 3-page sliding window in Focus, but with Focus's 3-quadrant layout (1 tall left + 2 stacked right) preserved per page. Pipeline-ordered slot fill:

- Page 0: `backlog | next / now`  (today's default — same as current)
- Page 1: `next    | now  / done`
- Page 2: `now     | done / dropped`

Detail pane stays as a side pane on the right of the page.

## Why

Done/dropped are currently only reachable from Board. Focus users (the daily-driver view) can't review what was shipped or cancelled without switching modes. Pagination keeps Focus's tight 3-panel cognitive layout while extending its reach.

## Architectural constraint (learned the hard way)

**Do not reparent widgets.** Prior attempt (reverted in this session) used `remove()` + `mount()` to move ListViews into different slots — this orphaned widgets from the DOM, broke binding propagation, and made page 2 unreachable.

Correct model: **3 fixed slot panels with stable IDs** (`#focus-slot-left`, `#focus-slot-rt`, `#focus-slot-rb`) that NEVER move. Each owns a slot-keyed ListView. A `_page` index (0–2) drives which 3 buckets fill which slots. On page change, repopulate slot ListView contents from the new bucket triplet, update panel titles, restore highlight.

All current bucket-indexed access (`self._lists[bucket]`, `self._active`, captures) becomes slot-indexed via a `slot_to_bucket(_page, slot)` lookup.

## Bindings to add

- `]` / `[` — slide page (priority binding)
- Extend `→`/`Tab` past rightmost slot → slide forward; past last page → reset to page 0
- `←`/`Shift+Tab` at leftmost slot of page 0 → hard stop

## Out of scope

- Responsive Kanban column count on Board (separate request, deferred earlier).

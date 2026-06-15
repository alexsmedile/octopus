# D106 — TUI subtask display: expand/collapse inline under parent

- Child rows render inline under their parent in all quadrant lists (Focus + Board).
- Parents that have children show `⎇N` (U+2387 + count) appended to their title in grey — always visible regardless of expand state.
- Children default to **expanded** (visible). `Space` on a parent row toggles expand/collapse per-slug; state is persisted in `_subtask_expanded: dict[str, bool]` for the session.
- Child rows use tree prefix glyphs: `├─` for non-last children, `└─` for last child. Children are non-selectable (disabled `ListItem`).
- Child rows that have no parent in the current quadrant are rendered as regular selectable `_TaskListItem` rows.

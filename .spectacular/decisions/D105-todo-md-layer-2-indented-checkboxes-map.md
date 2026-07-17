# D105 — TODO.md Layer 2: indented checkboxes map to subtasks

- Indented checkbox lines (`  - [ ] ...`) in TODO.md are parsed as children of the last top-level checkbox encountered in the same section.
- Only **1-level** of nesting is recognized. Deeper indentation is treated as a child of the most-recent top-level item (not the nearest indented ancestor).
- Section headings reset the parent-tracking state — an indented item after a new `##` heading has no implicit parent.
- `ExternalTask.suggested_parent` carries the adapter slug-key of the parent item.
- The pull pipeline performs a **second pass** after all tasks are materialized to wire `attach_subtask(child, parent)`. If the parent was skipped (already imported or errored), a non-fatal error is recorded and the child is left parentless.

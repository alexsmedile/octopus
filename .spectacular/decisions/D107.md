# D107 — Orphan / drop behavior for subtask children

- When a parent is dropped with `--cascade`, children are dropped first (bucket=dropped, end_date set). Children **keep** their `parent:` field as a historical reference.
- When a parent is dropped with `--force`, only the parent is dropped; children remain untouched with their `parent:` field intact (orphaned but not corrupted).
- `subtask-orphan` lint rule fires WARN when `parent:` points to a non-existent sibling slug — covers the post-force-drop case.
- There is no automatic cleanup of orphaned children on reindex; the lint rule is the signal.

# D32 — Bucket absorbs lifecycle; status field dropped

- Bucket is now five-valued: `backlog | next | now | done | dropped`.
- Lifecycle (started/finished/abandoned) is encoded via `start_date`, `end_date`, and terminal bucket values.
- `status` field removed entirely. Files containing it are rejected.
- Implementation simplification: `_folder_for()` helper removed; file location = `bucket`.

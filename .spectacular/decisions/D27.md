# D27 — Cross-reference resolution semantics across states

- Refs to archived tasks/activities: resolve with warning.
- Refs to `.trash/` files: MUST fail resolution.
- Refs to deleted files: MUST fail resolution as integrity error.
- Folder renames don't break refs (refs use `id`, not path).
- See `SPEC.md §8.2.1`.

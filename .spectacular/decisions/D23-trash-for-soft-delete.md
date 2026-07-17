# D23 — `.trash/` for soft delete

- `octopus forget <slug>` (draft, pending v2) moves to `.octopus/.trash/`.
- Trash is excluded from all retrieval (views, index, search).
- Use `archive` for v1 — `forget` semantics still in draft.

# D108 — TODO.md Layer 2: `%kind` inline sigil


**Locked.** Extends D103 with a `%word` sigil for the `kind` field.

- Sigil: `%word` — e.g. `%feat`, `%bug`, `%spec`, `%chore`, `%refactor`, `%polish`, `%test`, `%docs`, `%idea`
- Shorthands: full names only — single-letter shorthands intentionally omitted (opaque in plain text without knowing octopus internals)
- Character chosen: `%` — not a markdown special character in this context; visually distinct from `#` `@` `~` `!`
- Precedence: sigil wins over YAML block, YAML block wins over `section_map` (same as all other sigils, D103)
- Implementation: `KIND_SIGIL_RE` + `_KIND_SHORTHANDS` in `todo_md.py`; `kind` field on `InlineMetadata`; wired into `suggested_kind` on `ExternalTask` before YAML overlay runs

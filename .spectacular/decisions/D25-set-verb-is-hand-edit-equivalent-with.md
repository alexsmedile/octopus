# D25 — `set` verb is hand-edit equivalent with strict type/format/cross-field validation

- `set` accepts any frontmatter field, including those with dedicated verbs.
- Validation pipeline (hard reject → soft warn → informational tip), in order:
  1. Type validation: hard reject.
  2. Format validation: hard reject.
  3. Cross-field validation against `CRITICAL-DEPENDENCIES.md` MUST-rules: hard reject.
  4. Smell check (SHOULD-warn rules): write succeeds with stderr warning.
  5. Verb-overlap notice: informational only.
- `set` does NOT auto-apply verb side effects (date stamping, log entries, `open` flipping). Those remain verb-only.
- See `specs/CLI-VERBS.md` and `specs/CRITICAL-DEPENDENCIES.md` rule O.

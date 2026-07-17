# D29 — Activities use `status: archive`, not separate `archived` boolean

- Tasks have a boolean `archived` field for visibility.
- Activities use `status: archive` (one of 8 status enum values) for the same concept.
- Two different patterns because activities have a richer lifecycle.
- See `specs/SCHEMA-ACTIVITY.md` "On hiding activities".

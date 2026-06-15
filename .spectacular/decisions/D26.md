# D26 — Symmetric `start_date` / `end_date` / `status` rules

- `status: doing` MUST have `start_date` set.
- `status: done` MUST have both `start_date` and `end_date`.
- `status: dropped` MUST have `end_date`; `start_date` only if work began.
- `end_date` present MUST have terminal status (`done` or `dropped`).
- See `specs/CRITICAL-DEPENDENCIES.md` rule A.

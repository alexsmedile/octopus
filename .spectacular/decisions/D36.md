# D36 — Added run_state field (runtime axis)

- Optional, enum: `queued | running | finished | failed`. Absent = idle.
- Captures machine execution state, distinct from human workflow (`bucket`).
- Enables AI agents and automation to signal their state without touching pipeline axis.
- `finished` is distinct from `bucket: done`: a run can finish without the task itself being done.

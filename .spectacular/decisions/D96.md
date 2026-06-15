# D96 — Slot-1 exception triggers follow schema

- Code reads the **canonical schema field** for each exception:
  - `! blocked`  ← `issue=blocked` (legacy `run_state=blocked` still honored).
  - `? waiting`  ← `issue=waiting` (legacy `run_state=waiting` still honored).
  - `+ migrated` ← `promoted_to` is set (was incorrectly checking `run_state=migrated` or `migrated` field).
- Schema field aliases stay as the source of truth. See `SCHEMA-TASK.md`.

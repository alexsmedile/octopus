---
request: 09-adapter-reminders-pull
status: done
updated: 2026-05-24
---

# Tasks — 09-adapter-reminders-pull

## Group 1 — Lock decisions ✅

- [x] D67 — remindctl is the supported binary; osascript path dropped
- [x] D68 — Authorization cached in journal `auth_state`; re-shell only when "Not Determined"
- [x] D69 — external_id = bare EventKit UUID
- [x] D70 — Full field mapping table (priority, due, notes, listName, completionDate, etc.)
- [x] D71 — Cursor unused (no native resume token)

## Group 2 — remindctl wrapper ✅

- [x] `adapters/_reminders_io.py` — pure subprocess + JSON parse layer
- [x] `which_remindctl()`, `auth_status()`, `list_lists()`, `show_list()`
- [x] Typed `RemindersList`/`RemindersItem` dataclasses
- [x] 5-second subprocess timeout
- [x] `RemindctlError` / `RemindctlNotInstalled` exception hierarchy

## Group 3 — Adapter implementation ✅

- [x] `adapters/reminders.py` — replaces stub with full implementation
- [x] `validate_config` — schema validation + remindctl + auth probe
- [x] `status()` — missing-binary, denied, or healthy + last_pull
- [x] `list_groups()` — degrades gracefully on RemindctlError → []
- [x] `peek/pull/search` — uses `groups` arg or `lists` config; clear error when neither
- [x] `push()` — pull-only error
- [x] `_reminder_to_external_task(item)` — D70 mapping
- [x] **Framework change:** `ExternalTask.suggested_priority` + `suggested_due` added; pipeline propagates them on materialization

## Group 4 — Tests ✅ (35 new in `test_adapter_reminders.py`)

- [x] `_iso_to_date` edge cases: Z suffix, offset, date-only, malformed, None
- [x] `_parse_list_row` + `_parse_item_row`: minimal + full + completed shapes
- [x] D70 mapping: every priority value, due date passthrough, notes → body, empty notes omitted, source_group = listName, bare UUID, default bucket=backlog
- [x] `validate_config`: happy, missing-binary, denied auth, bad types (each field)
- [x] `status()`: missing-binary, full-access (healthy), denied (unhealthy)
- [x] `list_groups()`: parses titles, degrades to [] on error
- [x] `push()`: pull-only error message
- [x] `peek()` multi-list aggregation: 2 lists → combined result with per-item source_group
- [x] `peek()` no lists configured: clear error
- [x] `peek()` missing binary: clear error
- [x] `search()`: title-substring filter on mocked items
- [x] `groups` param overrides config `lists`

## Group 5 — Ship ✅

- [x] CHANGELOG [0.4.2] entry written
- [x] `cli/pyproject.toml` 0.4.1 → 0.4.2
- [x] README status line updated
- [x] PLAN/TASKS status: active → done
- [x] Manual smoke against live Apple Reminders: 3 items from Default list, multi-list with Default+Shift verified, re-pull idempotent via UUID dedup
- [ ] Tag v0.4.2 (next step)

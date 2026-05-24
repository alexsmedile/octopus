---
status: done
priority: medium
owner: alex
updated: 2026-05-24
summary: "Apple Reminders pull adapter via remindctl. Pull-only v1. Multi-list support. Stable EventKit UUIDs for dedup; native priority/dueDate mapping."
related:
  - 06-adapter-framework
  - 10-sync-modes-addendum
  - 14-adapter-reminders-twoway
gates:
  - 06-adapter-framework
---

# Apple Reminders pull adapter

## Goal

Second real adapter — one-way import of one or more Apple Reminders lists into Octopus backlog/now buckets (per PRD §7.5). Validates the adapter framework with a non-symlink integration that has stable external IDs and richer metadata than TODO.md (due dates, priority, completion state, notes).

## Why `remindctl` instead of `osascript`

The PRD sketched `osascript` / `shortcuts run`. After research (openclaw's [apple-reminders skill](https://github.com/openclaw/openclaw/blob/main/skills/apple-reminders/SKILL.md), [steipete/remindctl](https://github.com/steipete/remindctl), and local probing), `remindctl` is the better path:

- **Stable EventKit UUIDs.** Every reminder has a `id: "DF95D91C-..."` UUID. Maps directly to `external_refs.reminders` — no title-hashing required (unlike TODO.md which had to use slugs).
- **Structured JSON.** `--json` returns a parseable array; no fragile string parsing of osascript output.
- **Multi-list discovery built in.** `remindctl list --json` returns every list with name + ID + counts. Native fit for `list_groups()`.
- **Maintained, public EventKit APIs.** MIT-licensed; same access path osascript would use, with less surface area.
- **`remindctl status`** is a one-line authorization check.

The cost is a hard dep on a separate brew package. We mitigate via clear `status()` reporting + install hint.

## remindctl contract (verified against `remindctl 0.1.1` locally)

### Lists

```
$ remindctl list --json
[
  {"id": "E3A9D562-...", "title": "Default", "reminderCount": 3, "overdueCount": 0},
  {"id": "32982493-...", "title": "Master List", "reminderCount": 70, "overdueCount": 0},
  ...
]
```

### Reminders in a list

```
$ remindctl show all --list "Default" --json
[
  {
    "id": "DF95D91C-7F56-47E4-8AAD-07335A5DC086",
    "title": "Cypher 007",
    "isCompleted": false,
    "listID": "E3A9D562-...",
    "listName": "Default",
    "priority": "none",                          // none | low | medium | high
    "dueDate": "2024-06-16T22:00:00Z",          // optional ISO 8601 UTC
    "completionDate": "2024-07-13T11:41:26Z",   // present when isCompleted=true
    "notes": "https://..."                       // optional
  },
  ...
]
```

### Filters

`show today` (default, no arg) · `show tomorrow` · `show week` · `show overdue` · `show upcoming` · `show completed` · `show all` · `show 2026-01-04`. The framework v1 only needs `show all` (we filter Python-side by `isCompleted`).

### Status

```
$ remindctl status
Reminders access: Full access | Denied | Not Determined
```

## Locked decisions

| # | Decision |
|---|---|
| Q1 | **Hard-require `remindctl`** on PATH. `status()` reports `healthy=False` with brew install hint when missing. |
| Q2 | **Authorization check** runs once on `octopus bridge enable reminders` (writes `auth_state` to the journal); `status()` reads from journal — only re-shells `remindctl status` if cache says "Not Determined". |
| Q3 | **`lists` config field** matches the framework convention: `lists = ["Inbox", "Octopus Capture"]` in `bridges/reminders.toml`. Names match Apple's terminology exactly. Multi-list pull aggregates into one `PullResult`. |
| Q4 | **`external_id` = bare EventKit UUID** (`DF95D91C-...`). No path-prefix like TODO.md needed — UUIDs are globally unique. |
| Q5 | **Completion filtering:** default skip `isCompleted: true`. Config opt-in `include_completed = false` mirrors TODO.md's `include_checked`. When false, also skip items whose `completionDate` is non-null even if `isCompleted` is somehow false. |
| Q6 | **Priority mapping** — Apple → Octopus: `none` → no priority (default omission); `low` → `priority: low`; `medium` → no priority (Octopus has no medium per existing spec); `high` → `priority: high`. |
| Q7 | **Due date mapping** — `dueDate` ISO 8601 UTC → `due` ISO date (YYYY-MM-DD) in task frontmatter. Time portion dropped (Octopus is date-granularity by design). |
| Q8 | **Notes mapping** — `notes` field becomes the task body. Multi-line preserved. Empty → no body. URL-only notes pass through verbatim (no link parsing). |
| Q9 | **Bucket assignment** — incomplete items default to `bucket: backlog`. No automatic `now` mapping (Apple Reminders has no "in-progress" state). |
| Q10 | **Sync journal cursor** unused — `remindctl` has no resume-token API. We always re-pull the full list and rely on `task_external_refs` for dedup. |

## Scope

### Phase 1 — Read-only via remindctl

- `cli/src/octopus/adapters/reminders.py` replaces the stub.
- Subprocess to `remindctl list --json` for `list_groups()`.
- Subprocess to `remindctl show all --list <name> --json` for `peek()` / `pull()` per configured group.
- Multi-list: loop, aggregate into one `PullResult`.
- `search(query)` does `peek()` then filters by title/notes substring (`remindctl` has no native search).

### Phase 2 — Config

```toml
# ~/.config/octopus/bridges/reminders.toml
lists = []                          # default: no list configured
                                    # ["Inbox"]            = single
                                    # ["Inbox", "Errands"] = multiple
include_completed = false           # default: skip completed items
default_activity = ""               # falls back to cwd activity
```

### Phase 3 — Dedup + provenance

- `external_refs.reminders: <uuid>` on every materialized task — framework's pipeline writes this automatically (D63).
- Re-pull is idempotent — UUID match via `task_external_refs` skips.
- Provenance fields (`actor: human`, `imported_from: reminders`, `import_date`) set by the pipeline.

### Phase 4 — Status + authorization

- `validate_config(data)` checks `remindctl` is on PATH + reports `remindctl status` if available.
- `status()` reads journal for `auth_state` + `last_pull`. If auth state is `"Not Determined"` or missing, re-shell `remindctl status`.
- Caches results; doesn't re-check on every CLI call.

## Out of scope (v1, this request)

- **Push.** No completing reminders from Octopus. No creating reminders. Two-way is #14.
- **Filtered date ranges.** `remindctl show today` etc. are available but `pull --today` is not v1. Add when needed.
- **Reminder updates.** If a reminder's title changes in Apple, the existing Octopus task isn't updated on re-pull. v1.5 reconciliation territory.
- **Subtasks.** Apple Reminders supports subtasks; we ignore them in v1 (flat import only). The hierarchy can be re-modeled in Octopus if needed.
- **Recurrence rules.** `recurrenceRule` field is dropped; recurring reminders import as a single backlog task. v2.
- **Location reminders.** `locationTrigger` ignored.
- **Push notifications / watch mode.** NOTIFY capability flag deferred to #12.

## Approach

1. **Lock D-entries** for the new framework-touching decisions (Q4–Q10). Q1–Q3 already implied by framework D58/D60.
2. **`remindctl` wrapper module** — `adapters/_reminders_io.py` (private): `list_lists()`, `show_list(name, include_completed)`, `auth_status()`. Pure subprocess + JSON parse. Tiny.
3. **Replace `reminders.py` stub** with real adapter calling the wrapper.
4. **Mapping layer** in the adapter: `_reminder_to_external_task(json_row)`.
5. **Tests:**
   - Unit: parse remindctl JSON, map every field, priority/due edge cases, completion filter.
   - Adapter: `list_groups`, `status` (with/without remindctl, with/without auth), `validate_config`.
   - Integration: mocked subprocess returns fixture JSON; verify `PullResult` shape.
   - Skip the "real-system" E2E in CI (CI doesn't have remindctl or Reminders); document a manual smoke command.
6. **Update skill** — `references/adapters/reminders.md` (or fold into `adapter-framework.md`).
7. **Ship v0.4.2.**

## Deliverables

- [ ] `cli/src/octopus/adapters/_reminders_io.py` — remindctl wrapper
- [ ] `cli/src/octopus/adapters/reminders.py` — real adapter (replaces stub)
- [ ] D-entries in `DECISIONS.md` for Q1–Q10
- [ ] Tests: `tests/test_adapter_reminders.py`
- [ ] CHANGELOG [0.4.2] entry
- [ ] Version bump 0.4.1 → 0.4.2
- [ ] README status line
- [ ] Manual smoke command documented in CHANGELOG

## Manual smoke command

```bash
# Verify remindctl is installed and authorized
remindctl status                                          # → "Full access"

# Inside an activity:
octopus bridge enable reminders --set lists=Default,Inbox --force
octopus bridge status reminders                           # → healthy + auth_state
octopus bridge peek reminders                             # → JSON rows, no files
octopus bridge pull reminders                             # → creates backlog tasks
octopus bridge pull reminders                             # → "N already-known"
octopus task list --kind ''  # any                         # → tasks visible
```

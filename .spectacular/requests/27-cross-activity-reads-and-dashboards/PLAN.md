---
status: queued
priority: high
owner: alex
updated: 2026-05-24
summary: "Cross-activity read verbs + dashboard composite views. Activity priority field. Filter flags on list --all. JSON output for agents."
related:
  - 26-cross-activity-writes
  - 29-skill-proactive-behavior
gates:
  - 30-index-hygiene
---

# Cross-activity reads + dashboards

## Goal

Make Octopus a real "what's going on across all my work" tool by adding composite cross-activity views (`dashboard`, `next`, `impact`) and JSON-shaped read verbs (`status`, `tasks`, `get`) that accept either an activity ID or a filesystem path.

Adds the activity-level `priority` field that #26 stubs out, with a ranking heuristic that powers `next` and `impact`.

## Why

#26 lets agents WRITE from anywhere. This request lets agents READ from anywhere — and synthesize what the user should look at first. Without this, "what should I work on" requires the user (or agent) to manually grep through `list --all`, `status <each>`, and individual task lists.

The dashboard view is also the foundation for #29's proactive-agent skill upgrade: a verb the agent can run when the user asks open-ended status questions.

## Locked decisions

| # | Locked |
|---|---|
| 1 | `octopus status <path-or-id>` — auto-detects path (starts with `/` or `~` or contains `/`) vs activity ID/prefix. |
| 2 | Same for `octopus tasks <path-or-id>` and `octopus get <path-or-id>`. |
| 3 | `octopus get <path-or-id>` outputs **JSON to stdout by default**. Pipe to file if needed. No auto-file output. |
| 4 | Activity gains a `priority` field — author-assigned, same enum as tasks (`low`/`high`/`urgent`). Default = normal-absent. |
| 5 | `dashboard` is the dashboard verb (`open` was rejected for verb-overload). |
| 6 | `next` shows top **3** tasks across activities. `impact` shows the full ranked list. |
| 7 | Ranking heuristic for `next`/`impact`: **fixed for v1**, configurable in a future request. Algorithm documented in this PLAN. |
| 8 | Filter flags on `list --all`: `--status`, `--priority`, `--type`, `--area`, `--has-pinned`, `--has-overdue`, `--has-now`, `--touched-within <days>`. |
| 9 | Archived activities hidden by default in all list-shaped views (per #30); `--include-archived` to show them. |

## Scope

### Phase 1 — Activity `priority` field

`activity.md` frontmatter gains:

```yaml
priority: urgent | high | low      # optional; absent = normal
```

Same enum as task priority for consistency. Used by:
- `octopus set --activity <id> --priority X` (from #26).
- `octopus list --all --priority urgent` filter.
- `dashboard` / `next` / `impact` ranking inputs.

Schema:
- `SCHEMA-ACTIVITY.md` adds the field.
- SQLite `activities` table gains a `priority` column.
- Migration: schema v3 → v4. Backfill: existing activities get NULL (= normal).

### Phase 2 — Path-or-id resolver

Shared helper used by `status`, `tasks`, `get`, `forget` (#30), `add task --activity`, etc.

```python
def resolve_activity(token: str) -> Activity:
    """Resolve a token to an Activity row from the index.

    If `token` starts with `/` or `~` or contains `/` → treat as path.
        Walk-up from the path; reject if no .octopus/ found.
    Else → treat as activity ID prefix.
        Match against `activities.id`. Reject on ambiguity (list candidates).
    """
```

Locked centrally so the rule is identical everywhere.

### Phase 3 — `octopus list tasks <path-or-id>` and the context-aware `list`

Locked naming model (noun-explicit, context-aware default):

```
GLOBAL CONTEXT (cwd outside any .octopus/)
  octopus list               → activities (default)
  octopus list activities    → explicit form
  octopus list tasks         → cross-activity tasks (rare; needs filters)

INSIDE AN ACTIVITY (cwd has .octopus/ above)
  octopus list               → tasks in this activity (default)
  octopus list tasks         → explicit form
  octopus list activities    → still works — shows all activities
```

`octopus list tasks <path-or-id>` reaches into a specific activity by id or path.

```
octopus list tasks [<path-or-id>] [--bucket B] [--kind K] [--all]
                                  [--promoted] [--spec S] [--tag T]
                                  [--status S] [--priority P] [--has-overdue]
```

All existing `task list` filter flags carry over. Default scope still excludes `done`/`dropped` unless `--all`.

`octopus list activities [<filter-flags>]` is the dashboard-style activity list (see Phase 7).

**Sub-activity behavior:** if an activity contains nested `.octopus/` folders, those are separate activities. `list tasks` does NOT recurse into nested activities — they appear in `list activities` instead. This matches the "folder = activity = atomic" model.

### Phase 4 — `octopus status <path-or-id>` (richer)

Current `status <prefix>` shows bucket counts. Extend to show:

- Activity metadata: title, type, area, status, priority, last reviewed.
- Bucket counts (existing).
- `now` task titles (up to 5).
- Pinned tasks (up to 5).
- Overdue tasks (count + first 3 titles).
- Active session (filename + started timestamp).
- Last activity touch date (most recent task/session/memory write).
- TODO.md adapter status if active.

This is the "what's going on with this project" agent-facing view.

### Phase 5 — `octopus get activity <path-or-id>`

JSON-shaped programmatic access. Same data as `status --rich` but as a single JSON document.

Noun-explicit form: `get activity <path-or-id>`. Future-stable for `get task <slug>` (symmetric task-level JSON, not v1 scope).

```json
{
  "activity": { "id": "...", "title": "...", "priority": "high", "..." },
  "buckets": { "backlog": 3, "next": 1, "now": 2, "done": 5, "dropped": 0 },
  "now_tasks": [{ "slug": "...", "title": "...", "kind": "..." }],
  "pinned_tasks": [...],
  "overdue_tasks": [...],
  "active_session": { "filename": "...", "started": "..." },
  "last_touched": "2026-05-24T14:23:00",
  "adapters": [{ "name": "todo-md", "enabled": true, "last_pull": "..." }]
}
```

TTY default: JSON pretty-printed. Non-TTY (piped): JSON one-line for grep/jq. `--format pretty` / `--format compact` to override.

### Phase 6 — `octopus list --all` filter flags

Add to the existing `list --all`:

```
--status <active|on_hold|done|cancelled|archived>    Filter by activity status.
--priority <urgent|high|low>                          Filter by activity priority.
--type <code|business|content|...>                    Filter by type.
--area <name>                                         Filter by area.
--has-pinned                                          Only activities with ≥1 pinned task.
--has-overdue                                         Only activities with overdue tasks.
--has-now                                             Only activities with ≥1 task in `now`.
--touched-within <N>                                  Activities touched in last N days.
--include-archived                                    Override #30 default (hide archived).
```

These are AND'd together. Multi-value via comma: `--status active,on_hold`.

### Phase 7 — Composite views: `dashboard`, `activities`, `next`, `impact`

#### `octopus dashboard`

The composite "what's going on" view. Default: rich text rendering of:

```
DASHBOARD — 2026-05-24

⚐ PINNED ACROSS ALL ACTIVITIES                           (5)
  octopus/wire-obsidian-bridge        ⏫ #obsidian
  shift/q4-planning                    📅 2026-05-30
  ...

📅 OVERDUE                                                (2)
  shift/late-invoice                   2 days overdue
  ...

● NOW (across activities)                                (3)
  octopus/triage-friction
  ...

⏸ BLOCKED                                                 (1)
  octopus/build-reminders-pull         waiting_for: spec-09

⏰ SESSIONS OPEN > 7 DAYS                                 (1)
  octopus/2026-05-15-debug

ACTIVITY PRIORITIES
  urgent     shift                     (3 now · 1 overdue)
  high       octopus                   (2 now · 0 overdue)
  ...

next 3 tasks to consider: octopus next
full ranked list:          octopus impact
```

`--format json` for the agent-consumable shape.

#### `octopus activities`

Dashboard-style **per-activity card layout**:

```
ACTIVITIES (4 active, 1 on_hold, 0 archived)

[urgent]  shift                  (kind: business · area: client-work)
          3 now · 5 next · 12 backlog · last touched today
          next: q4-planning (📅 2026-05-30)

[high]    octopus                (kind: code · area: dev)
          2 now · 2 next · 18 backlog · last touched 1h ago
          next: triage-friction

[ ]       weekly-review          (kind: personal)
          0 now · 1 next · 4 backlog · last touched 3d ago
          next: review-this-week

[on_hold] paused-project         (kind: code)
          last touched 14d ago
```

Sorted by priority (urgent → high → normal → low) then by last_touched descending.

#### `octopus next`

The top 3 tasks across all activities, ranked. Single column output, one line per task:

```
NEXT 3 TASKS

1. octopus/wire-obsidian-bridge       ⚐⏫ pinned · urgent
2. shift/late-invoice                  📅 2 days overdue
3. octopus/triage-friction             ● now
```

#### `octopus impact`

The full ranked list (default top 20, `--limit N` to change). Same shape as `next` but with rank score visible (`--show-score`).

### Phase 8 — Ranking heuristic (locked v1)

Each task gets a numeric score; higher = more impact. The score is the sum of:

```
PINNED        100  (D43 — pinned tasks always rank highly)
OVERDUE       80 + 1 per day overdue (cap at 30)
NOW BUCKET    40  (you've already committed to doing it)
DUE_SOON      30 - days_until_due  (only when due_in_7_days, else 0)
URGENT        50
HIGH          25
ACTIVITY_URGENT  20  (the activity itself is marked urgent)
ACTIVITY_HIGH    10
BLOCKED       -30  (you can't act on it)
ARCHIVED      -∞   (hidden entirely)
DONE/DROPPED  -∞   (hidden entirely)
```

Ties broken by `last_touched` ascending (older = stale = bubble up).

Documented as Rule R1 in the request's DECISIONS entry. Configurable weights deferred to a future request.

## Out of scope

- **Configurable ranking weights** — locked algorithm for v1.
- **Per-user dashboard layout** — fixed structure.
- **Activity-level inbox / "default" activity** — future enhancement.
- **Cross-activity TUI mode** — separate request later.
- **Skill teaching agents to use these verbs proactively** — that's #29.

## Approach

1. **D-entries** for: path-or-id resolver, activity priority field, ranking heuristic, dashboard verb set.
2. **Schema v3 → v4 migration:** add `activities.priority` column.
3. **`SCHEMA-ACTIVITY.md` updated** with priority field.
4. **Resolver helper** in `core/refs.py` or `core/identify.py` (new).
5. **`octopus tasks <path-or-id>`** — new verb, reuses existing list rendering.
6. **`octopus status <path-or-id>`** — extend existing status; add the rich fields.
7. **`octopus get <path-or-id>`** — new JSON-shaped read verb.
8. **`list --all` filter flags** — extend `db/queries.py` list_activities.
9. **`octopus activities`** — new card-layout verb.
10. **`octopus dashboard`** — composite verb. Reuses pinned/overdue/now queries.
11. **`octopus next` and `impact`** — ranking + render.
12. **Tests** — every new verb, every filter, ranking algorithm unit tests.
13. **Spec doc updates** for all the new verbs.

## Deliverables

- [ ] D-entries for priority field, path-or-id resolver, ranking heuristic.
- [ ] Schema v3 → v4 migration in `db/connection.py`.
- [ ] `SCHEMA-ACTIVITY.md` adds priority field.
- [ ] Path-or-id resolver helper module.
- [ ] `octopus tasks <path-or-id>` verb.
- [ ] `octopus status <path-or-id>` extended with rich fields.
- [ ] `octopus get <path-or-id>` JSON verb.
- [ ] `list --all` gains `--status/--priority/--type/--area/--has-pinned/--has-overdue/--has-now/--touched-within`.
- [ ] `octopus activities` card-layout verb.
- [ ] `octopus dashboard` composite verb.
- [ ] `octopus next` (top 3).
- [ ] `octopus impact` (top 20, `--limit N`).
- [ ] Ranking unit tests + integration tests.
- [ ] `CLI-VERBS.md` updated for all new/changed verbs.
- [ ] CHANGELOG [0.8.0] section.

## Open for grilling

- **Output format for `dashboard`.** Plain rich text by default, `--format json` for agents. Or always JSON with `--format pretty` for TTY? My pick: text by default; JSON by flag. Reads as "for humans" first.
- **Priority field on activities — strict or soft enum?** Same as task `kind` (D46): soft, warn on unknown values, don't reject. Lock?
- **`next` top-N count.** Locked at 3. Useful to make it configurable via `--limit N`?
- **What counts as "last touched" for an activity?** Most-recent of: any task write, any session write, any memory write. Reindex tracks this; needs an `activities.last_touched_at` column.

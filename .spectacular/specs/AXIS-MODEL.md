---
status: stable
updated: 2026-05-22
relates_to: SPEC.md §4, SCHEMA-TASK.md, CLI-VERBS.md
---

# The five-axis task model

This document explains the structural framing of task state in Octopus. The contract lives in `SCHEMA-TASK.md`; this document explains *why* the schema has the fields it has.

If you're implementing a verb or designing a view, read this first.

---

## Axes overview

Octopus models task state along **five orthogonal axes**. Each axis answers exactly one question. No two axes carry the same information.

```
AXIS 1 — PIPELINE         bucket: backlog | next | now | done | dropped
                          "Where in my workflow does this live?"

AXIS 2 — DOMAIN WORKFLOW  stage: <free-form>
                          "What sub-stage within this kind of work?"

AXIS 3 — RUNTIME          run_state: <absent> | queued | running | finished | failed
                          "Is a machine actively executing this?"

AXIS 4 — ATTENTION        pinned: <absent> | true
                          "Should this sort to the top of every view?"

AXIS 5 — IMPEDIMENT       issue: <absent> | blocked | waiting
                          "Is anything stuck?"
```

Plus one non-axis visibility flag:

```
VISIBILITY                archived: <absent> | true
                          "Should I see this at all?"
```

`archived` is not an axis — it short-circuits all queries: archived tasks are invisible regardless of any other state.

Lifecycle (started / finished / dropped) is **not** an axis. It is derived from dates (`start_date`, `end_date`) and from terminal `bucket` values.

---

## Axis 1 — PIPELINE

```
   ◯ ───── ◯ ───── ◯ ───── ◯
   backlog next    now     done
                    \
                     \─── ◯ dropped
```

| Value | Definition |
|---|---|
| `backlog` | Captured intent, not yet shaped. May not have a clear next action. Default for new captures. |
| `next` | Decided and ready. Has a clear next action. |
| `now` | Selected for current work block. Small pile. |
| `done` | Completed successfully. Terminal. Requires `end_date`. |
| `dropped` | Intentionally abandoned. Terminal. Requires `end_date`. |

Happy-path progression: `backlog → next → now → done`. Side exit: `dropped` from anywhere.

Verbs `plan`, `focus`, `defer`, `park`, `finish`, `drop` move tasks along this axis.

Pipeline absorbs what was previously a separate lifecycle axis. The `done` and `dropped` buckets ARE the terminal lifecycle states — there is no separate `status` field.

---

## Axis 2 — DOMAIN WORKFLOW

```
   ◯ ───── ◯ ───── ◯ ───── ◯
   <free-form values per activity>
   e.g. idea | draft | editing | published
```

| Value | Definition |
|---|---|
| (absent) | No domain workflow tracked. Default. |
| (free-form) | A user-defined stage label. |

This axis is **optional and per-activity**. Activities that have sub-stages (content writing, code review, multi-step deliverables) use it. Activities without (simple bug fixes, errands) leave it empty.

The `stage` field is free-form in v1 — no validation. Per-activity strict mode is deferred (see `TODO.md`).

No dedicated verbs in v1. Set via `octopus set <slug> --stage editing`.

---

## Axis 3 — RUNTIME

```
   ◯ ───── ◯ ───── ◯ ───── ◯ ───── ◯
   (idle)  queued  running finished failed
```

| Value | Definition |
|---|---|
| (absent) | Idle. No machine activity on this task. Default. |
| `queued` | Scheduled to run, waiting in line. |
| `running` | An agent or automation is executing this task right now. |
| `finished` | Last run completed successfully. (Distinct from `bucket: done` — the *task* may not be finished even if the *run* is.) |
| `failed` | Last run errored or aborted. Needs attention. |

This axis is **separate from workflow**. A task can be `bucket: now, run_state: running` (an agent is doing it for you), or `bucket: now, run_state: idle` (you're doing it yourself), or `bucket: backlog, run_state: queued` (scheduled for later automated execution).

This axis exists to support AI agents (Claude Code) and automation (cron jobs, GitHub Actions, scheduled scripts) that need to signal their execution state without affecting the human workflow axis.

`finished` and `bucket: done` are distinct: a run of an iterative task can finish without the task itself being done. The next run starts and `run_state` returns to `running`.

---

## Axis 4 — ATTENTION

```
   ◯ ─────────── ◯
   (absent)      true
```

| Value | Definition |
|---|---|
| (absent / false) | Not specially marked. Default. |
| `true` | Marked for prominence. Sorts to top of every list view. |

The attention axis is **independent of all others**. A task can be `bucket: backlog, pinned: true` (an idea you want kept visible) or `bucket: now, pinned: false` (in focus but not specially flagged).

**Pinned tasks always sort first in any list view**, regardless of pipeline bucket, priority, or date. This is the field's whole purpose: surface-to-top.

Auto-set true by: `pin`, `focus`, `capture --now`.
Auto-set absent by: `unpin`, `finish`, `drop`, `park`.

The "open loop" concept (everything unfinished and weighing on you) is **not** the attention axis. It is a derived view (`octopus loops`) computed from `bucket NOT IN (done, dropped) AND NOT archived`. Open loops show everything that's alive. Pinned shows everything that's been marked for attention.

---

## Axis 5 — IMPEDIMENT

```
   ◯ ───── ◯
   blocked waiting
```

| Value | Definition |
|---|---|
| (absent) | No impediment. Default. |
| `blocked` | Cannot proceed; internal blocker. Requires `blocked_by`. |
| `waiting` | Cannot proceed; external dependency. Requires `waiting_for`. |

Carries only problems. Absence is the normal state.

`blocked` vs `waiting`: a blocker is something you could resolve yourself (need to learn, configure, decide); a wait is something someone else has to do.

Verbs `block`, `wait`, `unblock` move tasks along this axis.

---

## Visibility (not an axis)

```
   archived: true   ──── HIDDEN FROM ALL DEFAULT VIEWS
```

`archived: true` short-circuits every view filter. Doesn't matter what bucket, pinned, etc. The task disappears unless `--all` is passed.

Use `archive` and `restore` verbs.

---

## Lifecycle: dates, not state

The schema has **no `status` field**. Lifecycle is fully encoded by:

```
                         ┌── start_date set ──┐
                         │                     │
   created               │                     │             end_date set
      │                  ↓                     ↓                  │
      └── (idle) ── start ── (in flight) ── finish/drop ──────────┘
                                              │
                                              ↓
                                       bucket: done | dropped
```

| Lifecycle state | Schema fact |
|---|---|
| Not started | `start_date` absent. |
| In flight | `start_date` present AND `bucket` NOT IN (`done`, `dropped`). |
| Finished | `bucket: done` (implies `end_date` present). |
| Abandoned | `bucket: dropped` (implies `end_date` present). |
| Resumed | `start` on a `done`/`dropped` task: clears `end_date`, bucket → `now`. |

Lifecycle never gets its own field because dates + terminal buckets already encode every state perfectly.

---

## Derived views and queries

| View | Filter | Use |
|---|---|---|
| `loops` | `bucket NOT IN (done, dropped) AND NOT archived` | "What's unfinished?" |
| `now` | `bucket: now AND NOT archived` | "Current focus pile." |
| `next` | `bucket: next AND NOT archived` | "Committed queue." |
| `backlog` | `bucket: backlog AND NOT archived` | "Parking lot." |
| `done` | `bucket: done` | "Finished, for review." |
| `dropped` | `bucket: dropped` | "Abandoned, for review." |
| `stuck` | `issue IN (blocked, waiting) AND NOT archived` | "What's blocked?" |
| `today` | `bucket: now OR (next AND scheduled <= today) OR start_date present` | "What's actually happening today." |
| `running` | `run_state: running` | "What machines are executing." |
| `failed` | `run_state: failed AND NOT archived` | "What needs attention from a failed run." |
| `stale` | `bucket: next AND start_date absent AND created > 30d ago` | "Committed but never started." |

**Sort rule**: every list view applies a stable sort. `pinned: true` always sorts first. Then `priority: urgent`, then `high`, then `low`, then by view-specific secondary key.

---

## Why this many axes

Each axis carries information that cannot be derived from any other axis.

- **Pipeline** carries workflow position. No other field tells you "this is in backlog vs now."
- **Domain workflow** carries activity-internal stages. No other field knows about `editing` vs `published`.
- **Runtime** carries machine state. No other field signals "an agent is running."
- **Attention** carries user-curated surfacing. Distinct from "is it in flight" (dates) and "is it in focus" (bucket).
- **Impediment** carries problem markers, paired with context fields.

Adding a sixth axis would mean another orthogonal concern. Today, none exists. If routines land later (see TODO.md), they may introduce a sixth.

---

## Reference

- `SCHEMA-TASK.md` — full field reference with value ranges.
- `CLI-VERBS.md` — verbs that move tasks along these axes.
- `CRITICAL-DEPENDENCIES.md` — validation rules between axes.
- `../SPEC.md §4` — the authoritative contract.

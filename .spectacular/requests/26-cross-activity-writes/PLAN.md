---
status: done
priority: high
owner: alex
updated: 2026-05-24
summary: "Cross-activity write verbs: octopus add task/activity, multi-target set with --task/--activity flags. Lets agents write from anywhere without cd."
related:
  - 30-index-hygiene
  - 27-cross-activity-reads-and-dashboards
  - 29-skill-proactive-behavior
gates:
  - 30-index-hygiene
---

# Cross-activity write verbs

## Goal

Make every write verb usable **from any directory**, not just from inside the target activity. Agents working with a global terminal must be able to add a task, set a priority, or move a task without `cd`-ing first.

Two surface changes:

1. **`octopus add task / add activity`** — the canonical "from anywhere" verbs.
2. **`--task <slug>...` / `--activity <id>...` flags on `set`** (and on every write verb that needs them) — explicit multi-target via flag, with backwards-compatible positional shorthand for the cwd case.

## Why

Current state: `octopus capture`, `set`, `pin`, `plan`, `focus`, etc. all start with `_require_activity()`. They cannot run from outside an activity. Agents and global-shell users have to `cd` first, then run the verb. Two steps.

After #30 ships the index hygiene, the global `list --all` view is clean. But the user still can't say "add this idea to project X" from anywhere — they have to navigate. This request closes that.

## Locked resolution rules (the mental model)

**Mental model:** positional = "this activity, one." `--task` = "this activity, multiple." `--activity` = "anywhere, multiple."

One target axis per invocation. Mixing axes errors.

```
octopus set <slug> --priority high
  ✅ cwd inside activity → resolves slug against current activity
  ❌ cwd outside activity → errors with "not inside an activity; specify --task or --activity"
  ❌ Single target only (multi-positional without --task/--activity rejected)

octopus set --task t1 t2 t3 --priority high
  ✅ cwd inside activity → multi-target tasks within the CURRENT activity only
  ❌ cwd outside activity → errors ("specify which activity with --activity or cd into one")
  ❌ Ambiguous slug → lists candidate slugs in this activity, exits 1

octopus set --activity a1 a2 a3 --priority high
  ✅ Anywhere — multi-target activities by id (or unambiguous prefix)
  ❌ Task-level flags rejected (--bucket, --due, --kind, etc. — list the offending flag)

octopus set <slug> --task other-slug
  ❌ Rejected — positional and --task are mutually exclusive

octopus set <slug> --activity a1
  ❌ Rejected — positional and --activity are mutually exclusive

octopus set --task t1 --activity a1
  ❌ Rejected — --task and --activity are mutually exclusive (mixing target types)

octopus set --priority high
  ❌ Rejected — no target specified
```

Cross-activity task mutation (e.g. "update task X in project A from project B") is **not v1 scope**. Users do that by `cd`-ing or by going through activity-level fields. Avoids the "wrong project's task" foot-gun.

## Scope

### Phase 1 — `octopus add task`

```
octopus add task "<title>" [--activity <id>] [...full task-flag matrix from #24...]
```

- When `--activity` is omitted: cwd-walk-up. Same behavior as `capture`.
- When `--activity` is specified: resolves by prefix or full ID. Errors on ambiguous match.
- Accepts the same flags as `capture` (#24's v0.6.0 surface): `--next/--now`, `--priority`, `--due`, `--scheduled`, `--start-date`, `--end-date`, `--actor`, `--energy`, `--owner`, `--stage`, `--tag/--tags/--add-tag/...`.

`capture` stays. `add task` is the "from anywhere" variant. Two verbs, same task-creation semantics; the difference is which one is ergonomic in which context.

### Phase 2 — `octopus add activity`

```
octopus add activity "<name>" [--type <kind>] [--area <name>] [--priority <enum>]
                              [--path <directory>]
```

- Creates a new activity at `<path>` (defaults to cwd if omitted).
- Equivalent to `octopus init` (which exists) but in the `add` family for discoverability.
- Could be implemented as a thin wrapper around `init`, or `init` becomes the alias.

NOTE: `--priority` requires the activity priority field to exist. That field ships in **#27**, not here. If #26 lands first, `add activity --priority` rejects with "activity priority not implemented yet — see #27". Or we add the field in #26's scope. Decision: **add the field in #27 to keep #26 focused on write-verb plumbing.** `add activity --priority` will land later.

### Phase 3 — `set` with multi-target via `--task` / `--activity`

The big mechanical change.

Current `set`:
```python
def set_(slug: str, ...): ...   # one positional, cwd-resolved
```

New `set`:
```python
def set_(
    slugs: list[str] | None = typer.Argument(None),
    task: list[str] = typer.Option([], "--task"),
    activity: list[str] = typer.Option([], "--activity"),
    ...
):
```

Resolution:

1. If `slugs` is non-empty AND `--task`/`--activity` are both empty → cwd-resolve (single target). Errors if cwd is outside an activity.
2. If `slugs` is empty AND `--task` is non-empty → multi-target tasks **within the current activity**. Errors if cwd is outside an activity.
3. If `slugs` is empty AND `--activity` is non-empty → multi-target activities (anywhere).
4. Any other combination → reject with a clear error.

For task multi-target (`--task t1 t2 t3`), each slug is resolved against the current activity's task list. Ambiguous matches print the candidate slugs in this activity and exit 1.

For activity multi-target (`--activity a1 a2 a3`), each id is matched by exact id or unambiguous prefix against the index. Ambiguous matches print candidates and exit 1.

### Phase 4 — `--activity` flag on other write verbs

Lower priority than `set`, but the pattern is the same. Add `--activity <id>` to:
- `octopus capture` (in addition to the new `add task`).
- `octopus pin / unpin`.
- `octopus plan / focus / park / defer`.
- `octopus start / finish / drop`.
- `octopus archive / restore`.
- `octopus mv / move`.
- `octopus block / wait / unblock`.
- `octopus promote`.

Behavior: when `--activity` is omitted, cwd-walk-up (current behavior). When specified, **redirect the operation to that activity** — the task is resolved within the named activity, not the cwd one.

These verbs stay **single-target on tasks**. Only `set` gets multi-target shapes (and `set --task` stays scoped to the current activity per the resolution matrix above). `set --activity a1 a2 a3` is the only multi-target form that crosses activity boundaries, and it operates on activity-level fields only.

### Phase 5 — Activity-level fields on `set`

When `set --activity <id>` is used, the available flags are different — there are no buckets, no `--start-date`, no `--issue` on activities. Only activity-level fields:

- `--title` (activity title)
- `--status <active|on_hold|done|cancelled|archived>`
- `--type <enum>`
- `--area <name>`
- `--priority <enum>` (lands once #27 adds the field)
- `--tags` (same matrix as tasks)
- `--last-reviewed <date>`

`set --activity X --bucket next` is **rejected**: that's a task-level field. Clear error message.

## Out of scope

- **Activity priority field itself** — that's #27. `set --activity --priority` will error in this request and start working when #27 ships.
- **Cross-activity read verbs** (`status`, `tasks`, `get` with path-or-id) — that's #27.
- **Dashboard / next / impact** — that's #27.
- **Skill update teaching agents the new verbs** — that's #29.

## Approach

1. **D-entry** locking the one-target-axis-per-invocation rule + cross-cutting `--activity` flag.
2. **Path-or-id resolver from #30** — reused here for `--activity` argument parsing.
3. **`octopus add task` and `octopus add activity`** — new `add` Typer sub-app.
4. **`set` refactor** — accept `slugs: list[str]`, `--task`, `--activity`. Enforce mutex. Branch into task-set vs activity-set logic.
5. **Activity-level set** — new code path that loads `activity.md`, applies updates, writes back, syncs index. Rejects task-only flags.
6. **`--activity` flag on remaining write verbs** — mechanical; reuses the same resolver.
7. **Tests** for every resolution branch and rejection case.

## Deliverables

- [ ] D-entries: one-target-axis mutex, `add task/activity` semantics, activity-level set.
- [ ] `octopus add task "<title>" [--activity <id>] [...]` Typer command.
- [ ] `octopus add activity "<name>" [...]` Typer command (priority flag stub-rejected until #27).
- [ ] `set` refactored: `slugs: list[str]` positional, `--task`/`--activity` flags, mutex enforcement.
- [ ] Activity-level set path with allowed flags + clear rejection of task-only flags.
- [ ] `--activity <id>` flag on: `capture`, `pin`, `unpin`, `plan`, `focus`, `park`, `defer`, `start`, `finish`, `drop`, `archive`, `restore`, `mv`, `move`, `block`, `wait`, `unblock`, `promote`.
- [ ] Tests in `test_cross_activity_writes.py`.
- [ ] Spec docs: `CLI-VERBS.md` updated for every changed verb.
- [ ] Skill docs: `cli-verbs.md` mirror.
- [ ] CHANGELOG [0.7.0] section.

## Open for grilling

- **`add` Typer app naming.** `octopus add task` vs `octopus add-task` (hyphenated single verb)? Typer sub-app reads more like English. My pick: sub-app.
- **What happens if `--activity octopus` resolves to one activity but you mean another?** Same answer as `status` today: errors on ambiguity, lists candidates. Locked, no new behavior needed.
- **Cross-activity refs after `set` writes.** If the target task has cross-references (e.g. `waiting_for`), no special handling needed — `set` just updates the named task. Refs in OTHER tasks pointing AT the changed task are unaffected.

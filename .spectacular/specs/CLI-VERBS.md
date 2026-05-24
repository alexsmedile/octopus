---
status: draft
updated: 2026-05-23
relates_to: SPEC.md §4, SCHEMA-TASK.md, CRITICAL-DEPENDENCIES.md
---

# CLI verbs & views — v1 surface

The full set of verbs and views the `octopus` CLI exposes. The verbs are the **primary user interface**; field-level edits are an escape hatch. The frontmatter schema (`SCHEMA-TASK.md`) is the contract that verbs operate on.

Both `octopus` and `octo` are valid entry points (identical behavior).

---

## Capture verbs (v1)

```
octopus capture "<title>"
  intent : drop something into the parking lot, no thinking required
  delta  : new file
           bucket: backlog
           created: today
  side   : --edit opens $EDITOR for body; default no.

octopus capture "<title>" --next
  shortcut: capture + immediately plan
  delta   : bucket: next

octopus capture "<title>" --now
  shortcut: capture + immediately focus
  delta   : bucket: now
            pinned: true
```

## Pipeline verbs (v1)

```
octopus plan <slug>
  intent : promote → next (commit to do it)
  delta  : bucket: next

octopus focus <slug>
  intent : promote → now, mark for attention
  delta  : bucket: now
           pinned: true

octopus park <slug>
  intent : demote → backlog, clear attention
  delta  : bucket: backlog
           pinned: <cleared>

octopus defer <slug>
  intent : demote → next; still planned (does not clear pinned)
  delta  : bucket: next
```

## Lifecycle verbs (v1)

```
octopus start <slug>
  intent : mark work as begun. Idempotent.
  delta  :
    if start_date absent (no terminal bucket) → start_date: today
    if start_date present, bucket non-terminal → no-op (warn "already started")
    if bucket: done | dropped → resume:
        - clear end_date
        - bucket → now
        - start_date stays if set; set to today if absent

octopus finish <slug>          [aliases: octopus end <slug>]
  intent : mark complete
  delta  : bucket: done
           end_date: today (if absent)
           start_date: today (if absent — one-shot task)
           pinned: <cleared>
           issue, blocked_by, waiting_for: <cleared>
           run_state: <cleared>

octopus drop <slug>
  intent : intentionally abandon
  delta  : bucket: dropped
           end_date: today (if absent)
           pinned: <cleared>
           issue, blocked_by, waiting_for: <cleared>
           run_state: <cleared>
```

Note: `start` no longer moves bucket. To both start AND move to `now`, use `octopus focus <slug>` then `octopus start <slug>` — or just `octopus capture --now "..."` for new captures.

## Impediment verbs (v1)

```
octopus block <slug> --reason "<text>"
  intent : flag an internal blocker
  delta  : issue: blocked
           blocked_by: "<text>"
  side   : (v2) may append a dated entry to memory.md ## Notes; not auto-appended in v1

octopus wait <slug> --for "<text-or-cross-ref>"
  intent : flag an external dependency
  delta  : issue: waiting
           waiting_for: "<text-or-cross-ref>"
  side   : (v2) may append a dated entry to memory.md ## Notes; not auto-appended in v1

octopus unblock <slug>
  intent : remove impediment (block or wait)
  delta  : issue, blocked_by, waiting_for: <cleared>
```

## Attention verbs (v1)

```
octopus pin <slug>
  intent : surface task to top of every list view
  delta  : pinned: true

octopus unpin <slug>
  intent : remove top-sort flag
  delta  : pinned: <cleared>
```

Pinned tasks always sort first in any list view, regardless of bucket / priority / date.

## Visibility verbs (v1)

```
octopus archive <slug>
  intent : hide from default views; not deleted
  delta  : archived: true

octopus restore <slug>
  intent : bring back from archive
  delta  : archived: <cleared>
```

## Promotion verbs (v1)

```
octopus promote <slug> [<slug>...] --to <provider>:<id>
                                   [--slug <new-slug>]
                                   [--force]
octopus promote <slug> [<slug>...] --revert

  intent : promote one or more Octopus tasks into a Spectacular request
           (or other external target), making the request the new source of
           truth. Pure rewrite — task body becomes a 3-line stub pointer.
  delta  : promoted_to: <canonical-provider>:<id>
           end_date: <today>
           bucket: done (file moved to tasks/done/)
           body: replaced with hard-coded stub
  side   : if target doesn't exist, scaffolds a new spec request from template
           with promoted_from: <first-task-slug>.
           reindex regenerates related_tasks: on the request side from
           scanning task files (read-only, derived).

input forms (--to):
  --to <provider>:<id>      explicit provider + identifier
  --to <chip>:<id>          chip alias accepted; canonical stored
  --to <id>                 uses [providers.default]:<id>
  --to <provider>           shorthand: <provider>:<task-slug> (single-task only)
  --to <provider>:new       force scaffold; requires --slug <id>

idempotency:
  octopus promote X --to ... --force         repoints already-promoted task
  octopus promote X --revert                 soft-clear: removes promoted_to
                                             and end_date; body stays stub

multi-task:
  octopus promote A B C --to spec:obsidian-bridge
    atomic; pre-flight validates all tasks before any write
    all share one target; --force/--revert apply uniformly
    provider-only shorthand (--to spec) rejected with 2+ tasks (exit 3)

exit codes:
  0  success
  2  task not found
  3  --to target invalid (unknown provider, malformed id, ambiguous shorthand)
  4  task already promoted; use --force to repoint or --revert to unlink
```

See `D47`–`D51` in `DECISIONS.md` for the full model.

## Forget verb — pending decision

```
octopus forget <slug>         [DRAFT — soft-delete to .trash]

  Proposed behavior:
    - Moves file to .octopus/.trash/<original-path>.
    - Excluded from all retrieval.
    - Recoverable via `octopus restore --from-trash <slug>` (not yet specified).

  Status: kept pending until v2 confirms behavior. Use `archive` for v1.
```

## Storage verbs (v1)

```
octopus storage repair
  intent : scan, find frontmatter-vs-folder mismatches, fix them
  delta  : prompts per-conflict; --to-folder | --to-field | --dry-run flags

octopus storage convert --to folders | fields
  intent : flip the project's storage mode
  delta  : moves files; updates .octopus/config.toml
```

## Property-direct verb (v1 escape hatch)

```
octopus set <slug> --priority urgent
octopus set <slug> --due 2026-06-01
octopus set <slug> --scheduled 2026-05-25
octopus set <slug> --energy low
octopus set <slug> --stage editing
octopus set <slug> --run-state running
octopus set <slug> --tags work,client-acme
octopus set <slug> --owner alex
octopus set <slug> --actor ai
octopus set <slug> --bucket now              # works; verb-overlap tip emitted
octopus set <slug> --pinned                  # works; verb-overlap tip emitted

  intent : edit any frontmatter field directly (hand-edit equivalent)
  delta  : the specified field(s)
  notes  : `set` accepts any frontmatter field. Validation is strict on types
           and cross-field rules; lenient on verb-overlap (tips, not errors).
```

### `set` validation pipeline

When `set` runs, the CLI applies these checks in order. Failure at any step **aborts the write**:

1. **Type validation** — value matches field's declared type? (ISO date, enum, boolean, string)
2. **Format validation** — value satisfies format constraints?
3. **Cross-field validation** — resulting state satisfies `CRITICAL-DEPENDENCIES.md` MUST-rules? (`--bucket done` without `--end-date` → rejected.)
4. **Smell check (SHOULD-warn)** — write succeeds; stderr warning.
5. **Verb-overlap notice** — informational only; never blocks.

Multi-field invocations atomic: all validations against proposed final state; any failure → no write.

`set` MUST NOT auto-apply verb side effects (date stamping, memory log entries, `pinned` flipping). Those are reserved for dedicated verbs.

## Inspection verbs (v1)

```
octopus show <slug>
  intent : print task frontmatter + body
  flag   : --format json for machine-readable output

octopus where
  intent : walk up from cwd; show current activity summary
  output : activity slug, path, area, type, task counts per bucket, pinned items
  notes  : FILE-NATIVE, not index-backed. Works even when index is missing/stale.

octopus status [<activity-prefix>]
  intent : detailed activity view from the index (any activity, not just cwd)
  output : full activity record + task breakdown + open sessions + pinned items
  notes  : index-backed; uses stale-check on the activity's rows.

octopus list [--all] [--kind <enum>] [--promoted] [--spec <slug>]
  intent : list activities / tasks. CONTEXT-AWARE.
  scope  : if cwd is inside an activity → lists that activity's tasks (like task list)
           if cwd is NOT inside an activity → lists all indexed activities
           --all forces cross-activity listing regardless of cwd
  flags  : --all, --status STATUS, --type TYPE, --area AREA,
           --bucket BUCKET, --show-ids, --no-stale-check, --format json,
           --kind <enum>, --promoted, --spec <slug>
  notes  : if index is empty (no activities found), prints
           "no activities indexed — run `octopus reindex`".

octopus task list [--all] [--kind <enum>] [--promoted] [--spec <slug>]
  intent : list tasks. CONTEXT-AWARE (same scope rules as `list`).
  scope  : if cwd is inside an activity → that activity's tasks (default)
           --all → tasks across every indexed activity
  flags  : --all, --bucket BUCKET, --no-stale-check, --format json,
           --kind <enum>, --promoted, --spec <slug>
```

### New filter flags (v1)

`--kind <enum>` — filter by `kind` field. Comma-separated for multi: `--kind bug,polish`. Unknown values pass through (soft validation).

`--promoted` — scope override: show only tasks with `promoted_to:` set. Since promoted tasks live in `tasks/done/`, this flag implicitly includes that bucket. Combine with `--kind` for views like "all promoted bugs."

`--spec <slug>` — scope override: show only tasks with `promoted_to: spectacular:<slug>`. Useful for "what tasks did this request originate from?"

Scope rules:

| Flag combination | Buckets included |
|---|---|
| (default) | `backlog`, `next`, `now` |
| `--all` | all buckets (`done`, `dropped`, promoted) |
| `--promoted` | only tasks with `promoted_to:` set (overrides default scope) |
| `--spec <slug>` | only tasks with `promoted_to: spectacular:<slug>` (overrides default scope) |

See `D52` in `DECISIONS.md`.

## Session verbs (v1)

Sessions record blocks of work. Multiple may be open per activity; one is "active" at a time (tracked in `~/.cache/octopus/active-sessions.json`).

```
octopus session start [--title "<text>"]
  intent : begin a new session in the current activity
  scope  : current activity (errors exit 2 if not in one)
  delta  : new sessions/YYYY-MM-DD-<slug>.md with started: now, active: true (cache)
  prompts: if other sessions open in this activity, four-way prompt (D41 Q4):
           [c]ontinue existing  [n]ew alongside  [e]nd previous + start new  [a]bort
  side   : on [e], previous session: status: dropped, body auto-note
           "### YYYY-MM-DD HH:MM:SS ended by session start --replace"

octopus session log "<note>"
  intent : append a timestamped entry to the active session body
  scope  : current activity, active session
  delta  : appends "### YYYY-MM-DD HH:MM:SS\n<note>" to body (second precision per D41 Q2)
  errors : exit 3 with hint if no active session

octopus session end [<slug>] [--summary "<text>"] [--status done|dropped]
                    [--handoff [--handoff-title "<t>"] [--handoff-to-actor <a>]
                                [--handoff-to-owner "<n>"] [--handoff-summary "<s>"]
                                [--non-interactive]]
  intent : close a session
  scope  : defaults to active session; explicit slug closes any session
  delta  : ended: now, status: done (default) or dropped, active: false
  side   : --handoff creates paired handoff (see handoff new). Writes
           session.related_handoff AND handoff.from_session symmetrically.
           Interactive prompts for title/to_actor/to_owner/summary unless
           --non-interactive (which requires --handoff-title).

octopus session switch <slug>
  intent : change the active session pointer
  delta  : cache.active = slug (and frontmatter mirror updated)
  errors : exit 1 if slug doesn't exist or isn't open

octopus session list [--all] [--open|--closed]
  output : table of sessions in the activity (default hides closed > 30 days old)
  flags  : --all (include all closed), --open (only open), --closed (only closed)

octopus session show [<slug>]
  intent : show session metadata + body
  scope  : defaults to active; if none, falls back to most-recent
           (ended desc, started desc) per D41 Q7

octopus session prune [--dry-run] [--days N]
  intent : close sessions still open after N days as status: dropped
  side   : auto-note appended to each pruned session's body
  flags  : --days N (overrides config [sessions] prune_days, default 14)
           --dry-run (preview only)
```

## Memory verbs (v1)

Activity memory: append-only journal with 5 canonical sections + frontmatter `summary`.

Canonical sections: **Decisions / Open Questions / Context / Notes / State**. Default append target is `## Notes` (per D41).

```
octopus memory show [--section <name>]
  intent : read activity memory
  output (no flag) : summary + State (latest 3) + Open Questions (latest 3) + Decisions (latest 3)
                     Each previewed section: header "(showing latest N of M)" + footer if M > 3:
                     "[K more — run `octopus memory show --section <name>` for all]"
  output (--section) : full content of one section
  section: accepts canonical names or unambiguous prefixes (e.g. `open` → `Open Questions`)

octopus memory append "<note>" [--section <name>]
  intent : append a dated entry to a section
  default: --section notes (catch-all)
  delta  : appends "### YYYY-MM-DD HH:MM\n<note>" to the section (minute precision)
           bumps frontmatter last_updated
  side   : lazily creates the section if absent (in canonical position)
           re-inserts <!-- octopus-managed-below --> marker if user deleted it (+ stderr warn)
  errors : empty <note> rejected; unknown section rejected with candidate list

octopus memory summary
  output : current frontmatter summary

octopus memory summary set ["<text>"]
  intent : update the frontmatter summary
  delta  : sets frontmatter summary (uses YAML `|` block if multi-line)
  ergon  : no arg → opens $EDITOR with current value

octopus memory state
  output : latest ## State entry (treated as "current state")

octopus memory state set "<text>"
  intent : append a new State entry (alias for `memory append --section state`)
```

## Handoff verbs (v1)

Handoffs are *routers* to existing artifacts — deliberate context-transfer notes for the next picker-upper. Persistent in-activity (`<activity>/.octopus/handoffs/`), not ephemeral.

```
octopus handoff new "<title>" [--from-session <slug>] [--from-actor <a>]
                              [--to-actor <a>] [--to-owner "<name>"]
                              [--priority high|medium|low] [--summary "<text>"]
                              [--related-task <slug> ...]
  intent : create a new handoff
  scope  : current activity (errors exit 1 if not in one, per D41 Q8)
  delta  : new handoffs/YYYY-MM-DD-<slug>.md with status: open
  body   : default template includes TL;DR / What's done / What's next /
           Suggested next actions (machine-actionable octopus commands) /
           Open questions / References

octopus handoff list [--status open|received|resolved|stale]
  output : table (slug, title, created, status, from → to, priority)
  filter : --status restricts; no filter shows all

octopus handoff show <slug>
  output : frontmatter + body
```

Lifecycle verbs (`handoff receive`, `handoff resolve`, `handoff stale`) are deferred to v2; v1 supports manual frontmatter edits via `octopus set`.

## Index management verbs (v1)

```
octopus reindex
  intent : walk configured roots, rebuild SQLite index from filesystem
  flags  : --root PATH (override configured roots)
           --prune (delete rows whose source no longer exists)
           --verbose, --format json
  output : summary — activities found, tasks found, sessions found, rows pruned,
           collisions detected, renames detected
  side   : prompts y/N on rename detection unless --prune is set

octopus config root list
octopus config root add <path>
octopus config root remove <path>
  intent : manage the [roots] paths array in ~/.config/octopus/config.toml
  notes  : `add` errors on duplicate; `remove` errors if not present
```

---

## Bridge verbs (v1) — adapter framework

External integrations (Obsidian, Apple Reminders, TODO.md, future GitHub) are reached via **adapters**. The `octopus bridge` subcommand group operates them generically. See `SCHEMA-ADAPTER.md` for protocol, data types, and registry mechanism.

```
octopus bridge list [--verbose|-v]
  intent : show all registered adapters with enabled status + health
  output : table — name, enabled, capabilities, status
           -v adds: config path, last pull, last push, error (if any)

octopus bridge enable <name> [adapter-specific-flags]
  intent : enable an adapter; write its config
  delta  : main config [adapters.<name>] enabled = true
           AND writes/updates ~/.config/octopus/bridges/<name>.toml
  side   : adapter.validate_config() runs first; rejection aborts (exit 3)
  notes  : per-adapter Typer sub-app; flags are adapter-specific
           (e.g. --vault for obsidian, --capture-list for reminders)

octopus bridge disable <name>
  intent : disable an adapter; keep its config
  delta  : main config [adapters.<name>] enabled = false
  side   : bridges/<name>.toml is NOT deleted — re-enable is one command

octopus bridge status [<name>] [--verbose|-v]
  intent : health check
  scope  : no name = table of all; name = full per-adapter block
  output : healthy, last pull, last push, capabilities, error if unhealthy

octopus bridge peek <name> [--list NAME[,NAME...]] [--capture-all]
  intent : READ-ONLY display of what the adapter currently sees
  side   : NO files created, NO dedup, NO index changes — pure read
  flags  : --list takes one or more comma-separated group names
           --capture-all uses every group adapter.list_groups() returns
           --list + --capture-all together → exit 1
  notes  : with no configured `lists` in bridge config AND neither flag,
           peek goes into DISCOVERY mode: prints available groups
           ("no default list configured. Available lists: …")

octopus bridge pull <name> [--list NAME[,NAME...]] [--capture-all]
  intent : import external items as Octopus tasks
  delta  : new task files in target activity's tasks/<bucket>/
           pipeline dedup via task_external_refs (no duplicates)
  output : "pulled N new · M already-known · K errors" + per-task lines
  side   : sync journal updated (last_pull, pull_count, cursor)
  flags  : same as peek
  notes  : with no configured `lists` AND neither flag → exit 3
           (refuses to create unbounded files)

octopus bridge search <name> <query> [--list NAME] [--capture-all]
  intent : adapter-side search of the external system
  side   : NO imports; same shape as peek
  notes  : adapters with native search APIs use them
           adapters without fall back to peek() + Python filter internally

octopus bridge add <name> <title> [--priority X] [--due YYYY-MM-DD]
                                  [--tag T...] [--section S] [--state STATE]
  intent : append a new item to the adapter's source (D75)
  delta  : NEW checkbox line in source file; NO Octopus task created
  side   : adapter must declare MARK_PULLED capability
  flags  : --priority urgent|low (encoded as Obsidian Tasks emoji)
           --due (encoded as 📅)
           --tag (repeatable; appended as #tag)
           --section (heading slug; defaults to first section_filter entry)
           --state open|in-progress (marker [ ] or [/])

octopus bridge complete <name> <match> [--first]
  intent : toggle a matching open item to checked, in place (D75)
  delta  : `- [ ]` → `- [x]` in source file; NO Octopus task affected
  notes  : substring match against open items; --first picks top hit
           if multiple. Exit 1 if no match or ambiguous match.

octopus bridge uncomplete <name> <match> [--first]
  intent : reverse complete — `- [x]` → `- [ ]` (D75)
  delta  : also strips any `→ <provider>:<slug>` arrow on the line
  notes  : same matching semantics as complete
```

### Flag matrix for peek / pull / search

| Configured `lists` | `--list` flag | `--capture-all` | Behavior |
|---|---|---|---|
| `[]` | none | none | `peek` → discovery; `pull` → exit 3; `search` → exit 3 |
| `["A"]` | none | none | use `["A"]` |
| `["A","B"]` | none | none | use both |
| any | `--list X` | none | use `["X"]` (override) |
| any | `--list X,Y` | none | use `["X","Y"]` (override) |
| any | none | `--capture-all` | use `adapter.list_groups()` |
| any | `--list X` | `--capture-all` | exit 1 (mutually exclusive) |

### Per-adapter flag naming

The framework uses `--list` in this doc as the canonical example, but each adapter exposes the flag named after its native concept:

| Adapter | Flag |
|---|---|
| Reminders | `--list <name>` |
| GitHub (future) | `--repo <owner>/<name>` |
| ICS (future) | `--calendar <name>` |
| TODO.md | (none — single file, no concept of groups) |
| Obsidian | (n/a — viewer, not a pull source) |

Dispatched via per-adapter Typer sub-apps; `octopus bridge pull reminders --help` shows what flags Reminders accepts.

### Exit codes

| Scenario | Exit |
|---|---|
| Success (any items processed) | 0 |
| Successful with skipped (dedup) | 0 |
| Adapter not configured (`bridges/<name>.toml` missing) | 3 |
| Adapter disabled in main config | 3 |
| `--list X` value not found in `list_groups()` | 3 |
| `lists = []` + no flag + `pull`/`search` | 3 |
| Adapter doesn't declare required capability | 1 |
| `--list X --capture-all` (mutually exclusive) | 1 |
| Adapter `status()` unhealthy | 4 |
| Adapter raises uncaught exception | 4 |
| All items failed (no successful materialization) | 4 |
| Target activity unresolvable (no `default_activity`, no cwd activity) | 2 |

### Hidden alias

`octopus adapter` resolves to `octopus bridge` (muscle memory either way works; not advertised in help).

### `octopus link`

NOT a bridge verb. Obsidian-specific top-level command; ships with #07.

---

## Views (v1)

Each view filters the index and groups results. **All views sort pinned tasks first** (regardless of bucket / priority / date).

```
octopus today
  filter : bucket: now
        OR (bucket: next AND scheduled <= today)
        OR (bucket NOT IN (done, dropped) AND start_date present)
  exclude: archived, bucket: done, bucket: dropped

octopus now
  filter : bucket: now AND NOT archived

octopus next
  filter : bucket: next AND NOT archived

octopus backlog
  filter : bucket: backlog AND NOT archived

octopus loops
  filter : bucket NOT IN (done, dropped) AND NOT archived
  use    : "what's mentally alive / unfinished?" — open-loops surface

octopus stuck
  filter : issue IN (blocked, waiting) AND NOT archived
  use    : "what's not moving and why?"

octopus stale
  filter : bucket: next AND start_date absent AND created > 30 days ago

octopus done
  filter : bucket: done
  order  : end_date desc

octopus dropped
  filter : bucket: dropped
  order  : end_date desc

octopus running
  filter : run_state: running AND NOT archived
  use    : "what machines are actively executing?"

octopus failed
  filter : run_state: failed AND NOT archived
  use    : "what crashed/errored and needs attention?"
```

## v2 candidate views

```
octopus mind         (TODO — see TODO.md)
octopus inbox        filter: backlog AND created within 7d
octopus archive      filter: archived: true
octopus review       composite dashboard view
```

---

## Global flags (v1)

```
--root <path>            override cwd as starting point
--quiet / -q
--verbose / -v
--no-dates               do not auto-set start_date / end_date on lifecycle verbs
--edit                   open $EDITOR after create/edit
```

### Read-command flags (applies to inspection + view + list verbs)

```
--format json|table      machine vs human output  (default: table)
--no-stale-check         skip mtime check, read from SQLite only
--show-ids               reveal full activity IDs with hash
```

Read commands that accept these flags: `show`, `status`, `list`, `task list`,
`task show`, `loops`, `today`, `now`, `next`, `backlog`, `stuck`, `stale`,
`done`, `dropped`, `running`, `failed`, `reindex` (json only).

`where` accepts `--show-ids` but NOT `--no-stale-check` (it's file-native; no index involved).

---

## State-transition rules summary

Verbs encapsulate the rules in `CRITICAL-DEPENDENCIES.md`. The CLI MUST enforce:

- `start` is idempotent: stamps `start_date` if absent; warns and no-ops otherwise; resumes from terminal.
- `finish` sets `bucket: done`, `end_date`, and `start_date` (if absent for one-shot tasks). Clears pinned, issue, run_state.
- `drop` sets `bucket: dropped`, `end_date`. Clears pinned, issue, run_state. `start_date` only set if work had begun.
- `finish`/`drop`/`park` clear `pinned`.
- `start`/`focus`/`pin`/`capture --now` set `pinned: true`.
- `block` requires `--reason`; `wait` requires `--for`.
- `unblock` clears both `blocked_by` and `waiting_for`.

---

## Design principles (locked)

1. **Verbs are the primary surface.** Users think in actions, not field edits.
2. **The schema serves the verbs.** If a verb can't be expressed cleanly, the schema is wrong.
3. **Verbs encapsulate side effects.** Date stamping, `pinned` flipping, body log entries all happen automatically.
4. **`set` is the escape hatch.** Reserved for fields no verb covers, or compound edits.
5. **Views map to intent.** Users say "today", "stuck", "loops" — not raw filter clauses.
6. **Pinned always wins.** Pinned tasks surface to top in every view.
7. **Default-omission.** Frontmatter only contains fields with non-default values.

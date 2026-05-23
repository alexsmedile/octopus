# CLI verbs — v1

`octopus` (alias `octo`) is the primary user interface. Every verb is callable both as a subcommand (`octopus task start <slug>`) and, where natural, as a shortcut at the top level (`octopus start <slug>`).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | User error (bad args, missing file, invalid input) |
| 2 | Not inside an activity (no `.octopus/activity.md` found by walking up) |
| 3 | Config / state error (e.g. no active session when one was required) |

## Global flags

| Flag | Effect |
|---|---|
| `--version` | Print version, exit |
| `--no-stale-check` | Skip the SQLite stale-check-on-read before listing |

## Initialization & navigation

```
octopus init [--title "<text>"] [--type <type>]
  Initialize the current folder as an activity. Creates .octopus/activity.md.
  --type defaults to "other"; accepts code|business|content|skill|automation|research|personal|other.

octopus where
  Show current activity ID, title, pinned-task count, active session.
  Exit 2 if not inside an activity.
```

## Capture & pipeline

```
octopus capture "<title>" [--next] [--now] [--bucket <name>]
  Capture a new task. Defaults to bucket: backlog.
  --next is shorthand for --bucket next; --now for --bucket now.

octopus plan <slug>       # backlog → next
octopus focus <slug>      # next → now
octopus park <slug>       # now → next
octopus defer <slug>      # any → backlog
octopus start <slug>      # set start_date, move to now (resumes terminal tasks)
octopus finish <slug>     # set end_date, bucket: done
octopus drop <slug>       # set end_date, bucket: dropped
octopus pin <slug>        # pinned: true
octopus unpin <slug>      # pinned: false (omit field)
octopus archive <slug>    # archived: true (hides from default lists)
octopus unarchive <slug>  # archived: false
```

## Listing & viewing

```
octopus list [--all] [--bucket <name>] [--pinned] [--archived]
             [--kind <enum>] [--promoted] [--spec <slug>]
  Tasks grouped by bucket. Context-aware: scoped to current activity if inside one,
  cross-activity otherwise. --all forces cross-activity even from inside.

  --kind <enum>   filter by kind (feat/bug/spec/polish/test/chore). Comma-separated for multi.
  --promoted      scope override: only tasks with promoted_to: set (overrides default scope).
  --spec <slug>   scope override: only tasks promoted to spectacular:<slug>.

octopus show <slug>
  Full task content (frontmatter + body).

octopus task list [--bucket <name>] [--pinned] [--kind <enum>] [--promoted] [--spec <slug>]
octopus task show <slug>
```

### Scope rules

| Flag | Buckets included |
|---|---|
| (default) | `backlog`, `next`, `now` |
| `--all` | all buckets including `done`, `dropped`, promoted |
| `--promoted` | only tasks with `promoted_to:` set |
| `--spec <slug>` | only tasks with `promoted_to: spectacular:<slug>` |

## Curated views

```
octopus loops               # open loops: bucket NOT IN (done, dropped) AND NOT archived
octopus today               # tasks with scheduled = today
octopus stuck               # tasks with issue set
octopus stale               # next-bucket tasks not touched in >14 days
octopus context             # current activity + active session + memory summary
```

## Set / rename / move

```
octopus set <slug> <field>=<value> [<field>=<value> ...]
  Direct frontmatter edit with validation. Multi-field allowed.

octopus rename <slug> <new-slug>
  Rename a task. Updates external refs (when index implements them).

octopus mv <slug> <bucket>
  Move a task to a different bucket explicitly (bypasses pipeline verbs).
```

## Promotion

```
octopus promote <slug> [<slug>...] --to <provider>:<id>
                                   [--slug <new-slug>]
                                   [--force]
octopus promote <slug> [<slug>...] --revert
  Promote one or more Octopus tasks into a Spectacular request (or other
  external target). One-way; pure rewrite — task body becomes a stub pointer
  to the new source of truth.

  --to forms:
    --to <provider>:<id>      explicit
    --to <chip>:<id>          chip alias accepted; canonical stored
    --to <id>                 uses [providers.default]:<id>
    --to <provider>           shorthand: <provider>:<task-slug> (single-task only)
    --to <provider>:new       force scaffold; requires --slug <id>

  --force        repoint an already-promoted task to a new target
  --revert       soft-clear: removes promoted_to and end_date; body stays stub
  --slug <id>    explicit slug when scaffolding new request

  Side effects (on promote):
    - promoted_to: <canonical> on task
    - end_date: <today>
    - bucket: done (file moved to tasks/done/)
    - body replaced with 3-line stub pointing at PLAN.md
    - if target doesn't exist, scaffolds .spectacular/requests/<slug>/PLAN.md
      with promoted_from: <first-task-slug>
    - reindex regenerates related_tasks: on the request (read-only, derived)

  Multi-task semantics:
    Atomic pre-flight: all listed tasks validated before any write.
    All share one --to target. --force/--revert apply uniformly.
    Provider-only shorthand (--to spec) rejected with 2+ tasks (exit 3).

  Exit codes:
    0  success
    2  task not found
    3  --to target invalid (unknown provider, malformed id, ambiguous shorthand)
    4  already promoted; use --force to repoint or --revert to unlink
```

## Sessions

```
octopus session start [--title "<text>"]
  Start a new session in current activity. Prompts if other sessions are open:
    [c]ontinue active  [n]ew alongside  [e]nd previous + start new  [a]bort

octopus session log "<note>"
  Append timestamped entry to active session body.
  Exit 3 if no active session.

octopus session end [<slug>] [--summary "<text>"] [--status done|dropped] [--handoff [...]]
  End a session. Defaults to active. --handoff also creates a paired handoff:
    --handoff-title "<text>"
    --handoff-to-actor human|ai|both
    --handoff-to-owner "<name>"
    --handoff-summary "<text>"
    --non-interactive    # require all handoff flags; fail rather than prompt

octopus session switch <slug>
  Change active session pointer in cache.

octopus session list [--all] [--open] [--closed]
  Default hides closed older than 30 days. --all overrides.

octopus session show [<slug>]
  Show session metadata + body. Defaults to active, falls back to most-recent if none active.

octopus session prune [--dry-run] [--days N]
  Close sessions still open after N days as status: dropped with auto-note.
  --days defaults to config [sessions] prune_days (14).
```

## Memory

```
octopus memory show [--section <name>]
  No flag: default preview (summary + State + last 3 Decisions + last 3 Open Questions).
  --section: full content of one section.

octopus memory append "<note>" [--section <name>]
  Default --section is "notes". Sections: decisions, open, context, notes, state.
  Section names accept prefix matches.

octopus memory summary
  Print current summary (frontmatter).

octopus memory summary set "<text>"
  Set frontmatter summary. Opens $EDITOR if no arg given.

octopus memory state
  Print latest State entry (treated as "current state").

octopus memory state set "<text>"
  Alias for `memory append --section state "<text>"`.
```

## Handoffs

```
octopus handoff new "<title>" [--from-session <slug>] [--from-actor <a>]
                              [--to-actor <a>] [--to-owner "<name>"]
                              [--priority high|medium|low] [--summary "<text>"]
                              [--related-task <slug> ...]
  Creates handoff file with default body template. Exit 1 if not inside an activity.

octopus handoff list [--status open|received|resolved|stale]
  Tabular list. Empty status filter = all.

octopus handoff show <slug>
  Frontmatter + body.
```

## Indexing

```
octopus reindex [--prune] [--root <path>]
  Full rebuild of ~/.local/share/octopus/index.db.
  --prune removes orphan rows (deleted files) and auto-accepts renames.
  --root scopes to one root; default reindexes all configured roots.

octopus config root add <path>
octopus config root list
octopus config root remove <path>
```

## Config

```
octopus config show [--section <name>]
  Read merged config (system + per-activity).

octopus config set <section>.<key> <value>
  Edit ~/.config/octopus/config.toml.
```

## Flag conventions

- `<slug>` arguments always refer to task slugs unless under `session`/`handoff` subcommands.
- Multi-value flags are repeated: `--related-task a --related-task b`.
- Boolean flags have no negation; omit them to disable.
- All write verbs upsert the SQLite index after the file write (unless `--no-index-sync` for debug).

## Common patterns

| Goal | Verb sequence |
|---|---|
| Capture and immediately focus | `octopus capture "<title>" --now` (or `capture` + `focus`) |
| Resume an abandoned task | `octopus start <slug>` (works on any bucket including terminal) |
| Drop with a reason | `octopus drop <slug>` then `octopus set <slug> end_note="<reason>"` |
| Wrap a day | `octopus session end --handoff` (with prompts) or `--non-interactive` + flags |
| Pick up tomorrow | `octopus where && octopus memory show && octopus handoff list --status open` |

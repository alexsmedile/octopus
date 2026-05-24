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
octopus capture "<title>" [--next | --now] [--slug <override>]
                          [--priority <urgent|high|low>] [--energy <low|mid|high>]
                          [--due <YYYY-MM-DD>] [--scheduled <YYYY-MM-DD>]
                          [--start-date <YYYY-MM-DD>] [--end-date <YYYY-MM-DD>]
                          [--actor <ai|automation>] [--owner <name>] [--stage <text>]
                          [TAG-FLAGS — see "Tag flag matrix" below]
  Capture a new task. Defaults to bucket: backlog. Empty body by default (D82).
  --next is shorthand for --bucket next; --now for --bucket now.
  --now does NOT auto-pin (D81). For pinned-and-now, run `pin` after.

  D80: explicit-default values clear instead of rejecting.
    --priority normal/none/""    → cleared
    --actor human                → cleared (human is the default)
    --energy normal/none/""      → cleared
    etc.

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
octopus restore <slug>    # archived: false (clears the flag)
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

## Set / rename / move (D76, D77, D78)

```
octopus set <slug> [--field <value> ...]
  Frontmatter-only escape hatch. Multi-field is atomic.

  Workflow:
    --bucket <name>          changes the FIELD only (D77); does NOT move the file.
                             Soft warning fires if folder no longer matches.
    --stage <text>           per-activity workflow stage
    --title <text>           change displayed title (does NOT change the slug)
    --slug <new-slug> [-y]   D78: rename the slug with cascading auto-fix
                             (filesystem + index + waiting_for + related_tasks
                             + promoted_from + TODO.md → octopus: arrows).
                             Prompts unless -y. Soft warning for session/memory/
                             handoff prose.

  Attention / impediment:
    --pinned / --no-pinned       (overlap with pin/unpin)
    --issue blocked|waiting      (overlap with block/wait/unblock)
    --blocked-by <text>          required when issue=blocked
    --waiting-for <text>         required when issue=waiting
    --archived / --no-archived   (overlap with archive/restore)

  Runtime / classification / actors:
    --run-state queued|running|finished|failed   (or idle/none/"" to clear)
    --priority urgent|high|low                    (or normal/none/"" to clear)
    --energy low|mid|high                         (or normal/none/"" to clear)
    --actor ai|automation                         (or human/"" to clear)
    --owner <name>
    --kind feat|bug|spec|polish|test|chore        (soft validation; "" to clear)

  Dates (or "" to clear):
    --due / --scheduled / --start-date / --end-date  (ISO YYYY-MM-DD)

  Tag flag matrix (D76):
    --tag, --tags                REPLACE the tag list
    --add-tag, --add-tags        APPEND (dedup)
    --remove-tag, --remove-tags  REMOVE (no-op if absent)
    --clear-tags                 EMPTY
  All four families accept comma-separated, space-separated (in quotes),
  or repeated invocation. --tag/--tags (replace) is mutually exclusive
  with --add/--remove/--clear. Tags stored with `#` prefix.

octopus move <slug> <bucket>      # D77: physical file move + frontmatter
octopus mv <slug> <bucket>        # alias of `move`
  Pure file-move. No date stamps, no lifecycle side effects.
  Validates the resulting state (mv to done/dropped without dates → exit 1
  with a hint to use finish/drop instead).
```

### Tag input forms (capture + set, D76)

```
--tag bug                              # one tag
--tag bug,tui,release                  # comma-separated
--tag "bug tui release"                # space-separated within quotes
--tag bug --tag tui --tag release      # repeated
--tag tui/marquee                      # nested (Obsidian convention)
--tag "#bug"                           # explicit # is accepted; the normalizer is idempotent
```

### Tag filter

`octopus list --tag parent` matches `#parent` AND any `#parent/*` (prefix match on `/` boundary).

## References

```
octopus refs find <slug> [--all]
  Read-only grep for a slug across every Octopus-managed text file in the
  current activity (or all activities with --all).

  Splits output into:
    Octopus-managed refs (tasks, spectacular PLAN.md, TODO.md) — auto-fixed
      by `set --slug` rename.
    User-prose mentions (sessions, memory, handoffs) — soft warning only;
      user updates manually.

  Useful after a slug rename to spot residuals, or just to answer
  "where does this slug appear?"
```

## Bridges (adapters)

```
octopus bridge list [--verbose|-v]
  Show all registered adapters with enabled status + health.

octopus bridge enable <name> [adapter-flags]
  Enable an adapter; write its config. Per-adapter flags
  (--vault, --list, --repo, etc.) dispatched via sub-app.
  validate_config() runs first; bad config → exit 3.

octopus bridge disable <name>
  Disable; keep settings. Re-enable is one command.

octopus bridge status [<name>] [--verbose|-v]
  Health check. No name = all bridges (table). With name = full block.

octopus bridge peek <name> [--list NAME[,NAME...]] [--capture-all]
  READ-ONLY display of what the adapter sees. No files created.
  No default list AND no flag → discovery mode (lists available groups).

octopus bridge pull <name> [--list NAME[,NAME...]] [--capture-all]
  Import as Octopus tasks. Deduped via task_external_refs.
  No default list AND no flag → exit 3 (would create unbounded files).

octopus bridge search <name> <query> [--list NAME] [--capture-all]
  Adapter-side search. No imports. Adapters with API use it;
  others fall back to peek + filter.

octopus bridge add <name> <title> [--priority urgent|low] [--due YYYY-MM-DD]
                                  [--tag T...] [--section S] [--state open|in-progress]
  Append a new item to the source. No Octopus task created.
  Adapter must declare MARK_PULLED capability.

octopus bridge complete <name> <match> [--first]
  Toggle a matching open item to [x] in place. No Octopus task affected.

octopus bridge uncomplete <name> <match> [--first]
  Reverse — [x] → [ ]. Strips any `→ provider:slug` arrow.
```

### TODO.md format (D72–D73)

The `todo-md` adapter parses:
- **GFM checklist:** `- [ ]`, `- [x]`, `- [/]` / `- [-]` (in-progress), `- [!]` (cancelled).
- **Obsidian Tasks emoji:** `⏫`/`🔺` urgent, `🔽`/`⏬` low, `📅 YYYY-MM-DD` due, `⏳` scheduled, `🛫` start, `#tag`.
- **Octopus arrow:** `→ <provider>:<slug>` — items with arrows are excluded from import (already handed off).
- **Carry-over prefixes:** `BUG:` → `kind: bug`, `HACK:` → `kind: chore`, `NOTE:` skipped.

On pull, the adapter rewrites `- [ ] thing` lines to `- [x] thing → octopus:<slug>` in place. The file becomes an at-a-glance map of what's in Octopus.

### Group flag matrix (peek / pull / search)

| Config `lists` | Flag | Result |
|---|---|---|
| `[]` | none | peek → discovery; pull/search → exit 3 |
| `["A"]` | none | use `["A"]` |
| `["A","B"]` | none | use both |
| any | `--list X` | use `["X"]` (override) |
| any | `--list X,Y` | use both |
| any | `--capture-all` | use everything `list_groups()` returns |
| any | `--list X --capture-all` | exit 1 (mutually exclusive) |

### Per-adapter flag names

`--list` for Reminders, `--repo` for GitHub, `--calendar` for ICS. TODO.md has no flag (single file). Each adapter's Typer sub-app advertises its flags via `octopus bridge pull <name> --help`.

### Capability gating

| Capability | Verb requires it |
|---|---|
| `PULL` | `peek`, `pull`, `search` |
| `PUSH` | `push` (not in v1 CLI surface) |
| `NOTIFY` | flag-only in v1 |
| `RECONCILE` | flag-only in v1 |

Missing capability → exit 1.

### Hidden alias

`octopus adapter ...` resolves to `octopus bridge ...`. Not advertised.

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

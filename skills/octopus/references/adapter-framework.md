# Adapter framework — v1

Adapters bridge Octopus to external systems (Obsidian, Apple Reminders, TODO.md, future GitHub). Octopus owns the canonical task files; adapters read/write what's in the external system.

This file is the operational skill reference. For the formal contract, see `.spectacular/specs/SCHEMA-ADAPTER.md`.

---

## What an adapter does (plain English)

An adapter is a translator between Octopus and one external system. In v1, every adapter is **pull-only** — it imports stuff into Octopus, doesn't push back out.

| Capability | What it means | v1? |
|---|---|---|
| `PULL` | adapter can fetch items from external | ✓ |
| `PUSH` | adapter can write Octopus tasks to external | flag only |
| `NOTIFY` | adapter can wake Octopus on external change | flag only (#12) |
| `RECONCILE` | adapter has a conflict-resolution policy | flag only (#10) |

v1 adapters: `obsidian` (viewer via symlinks), `reminders` (Apple Reminders pull), `todo-md` (read `TODO.md` files). Each ships as a stub in #06; their actual implementations live in #07 / #09 / #21.

---

## The seven commands

```
octopus bridge list                  # show all registered adapters
octopus bridge enable <name> [...]   # configure + turn on
octopus bridge disable <name>        # turn off (settings persist)
octopus bridge status [<name>]       # health check

octopus bridge peek <name>           # READ-ONLY view — no files created
octopus bridge pull <name>           # import as Octopus tasks (deduped)
octopus bridge search <name> <q>     # adapter-side search
```

Hidden alias: `octopus adapter` ≡ `octopus bridge`.

### peek vs pull

- **`peek`** — display only. Safe; nothing changes on disk. Use to explore what's in an external system before deciding to import.
- **`pull`** — imports as `.octopus/tasks/backlog/<slug>.md` files. Deduped on re-pull (no double-creates).

If you don't know what's there, **`peek`** first.

### `peek` discovery mode

If the adapter has no default list configured (`lists = []` in `bridges/<name>.toml`) AND no `--list` flag, `peek` lists **available groups** instead of erroring:

```
$ octopus bridge peek reminders
no default list configured. Available lists:
  - Inbox
  - Octopus Capture
  - Errands

Specify --list <name> to peek into one, or --capture-all for everything.
```

`pull` with the same state errors instead — it would create unbounded files.

---

## Selecting groups (lists, repos, calendars)

Most adapters have multiple groups (Apple Reminders lists, GitHub repos, ICS calendars). Pulling "everything from the adapter" is rarely what you want.

### Config defaults

```toml
# ~/.config/octopus/bridges/reminders.toml
lists = []                       # no default — must pass --list or --capture-all
# lists = ["Inbox"]              # single default
# lists = ["Inbox", "Errands"]   # multiple defaults
```

### Per-invocation flags

```
--list <name>                    # single group
--list <name1>,<name2>           # multiple groups (comma-separated)
--capture-all                    # every group adapter.list_groups() returns
```

`--list` and `--capture-all` are mutually exclusive (exit 1 if both passed).

### Per-adapter flag naming

The flag is named after the adapter's native concept:

| Adapter | Flag |
|---|---|
| Reminders | `--list <name>` |
| GitHub (future) | `--repo <owner>/<name>` |
| ICS (future) | `--calendar <name>` |
| TODO.md | (none — single file) |

`octopus bridge pull reminders --help` shows what flags Reminders accepts.

---

## What `pull` does on disk

For each external item the adapter returns, the pipeline:

1. Checks the dedup index (`task_external_refs` table) for `(adapter, external_id)`.
2. **If match found** → skip (already imported, recorded as skipped in output, not an error).
3. **If no match** → create a new task with:
   - `actor: human`
   - `imported_from: <adapter_name>`
   - `import_date: <today>`
   - `bucket: backlog` (or `ExternalTask.suggested_bucket` if the adapter set one)
   - `kind: <if adapter suggested>`
   - `external_refs.<adapter_name>: <external_id>`
4. Updates the sync journal at `~/.local/share/octopus/sync/<adapter>.json`.

Output:
```
$ octopus bridge pull reminders --list "Octopus Capture"
pulled 3 new · 7 already-known · 0 errors
  + buy milk
  + schedule dentist
  + reply to alex about Q4 plan
```

---

## Sync journal

One JSON file per adapter at `~/.local/share/octopus/sync/<name>.json`:

```json
{
  "adapter": "reminders",
  "last_pull": "2026-05-24T10:23:00",
  "last_push": null,
  "pull_count": 3,
  "push_count": 0,
  "cursor": null
}
```

Read by `adapter.status()` to populate health output. Written by the framework after every pull/push. v1 keeps a minimal counter+timestamp file; #10 (sync modes addendum) may grow it into event-level history.

---

## Exit codes

| Scenario | Exit |
|---|---|
| Success (any items processed, even 0) | 0 |
| Bridge not configured / disabled / target activity unresolvable | 3 or 2 |
| Adapter doesn't declare required capability | 1 |
| `--list X --capture-all` together | 1 |
| Adapter unhealthy or raises exception | 4 |

Standard PRD §5 conventions.

---

## When to use this skill

The user mentions:
- "Pull/import/sync from Apple Reminders / GitHub / TODO / Obsidian"
- "What's in my Apple Reminders inbox?"
- "Show me my GitHub issues" / "what's in my TODO.md"
- "Search across my bridges" / "find that note about X across systems"
- "Configure/enable/disable a bridge/adapter"

Match the verb:
- "Show me" / "what's in" → `peek` (or `peek --list` if they name a group)
- "Pull" / "import" / "bring into Octopus" → `pull`
- "Search for X" → `search`
- "Set up" / "configure" → `enable`

If the user describes wanting to *bring stuff in*, `peek` first to verify, then `pull` to commit.

---

## Adapter status reference (v1)

| Adapter | Status | Notes |
|---|---|---|
| `obsidian` | stub | #07 |
| `reminders` | stub | #09 — pull-only via osascript |
| `todo-md` | stub | #21 — reads `TODO.md` from activity root |

A stub responds to all CLI verbs with a clear "not implemented — see request #NN" error. The framework is testable end-to-end; the adapter bodies are the next step.

---

## Reference

- `SCHEMA-ADAPTER.md` — formal protocol contract
- `CLI-VERBS.md §Bridge verbs` — full CLI surface
- `CRITICAL-DEPENDENCIES.md §U` — validation invariants
- `DECISIONS.md D56–D66` — locked design rationale

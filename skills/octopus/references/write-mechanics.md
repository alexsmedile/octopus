# Write mechanics reference

Load this when: naming a new task, setting kind/tags, renaming a slug, capturing with flags, promoting a task, or working with bridges.

---

## Task naming — F1 imperative

Every task title is **`verb result`** in lowercase, imperative voice. No prefixes (`Friction:`, `Bug:`), no parenthetical suffixes (`(request NN)`), no trailing qualifiers.

### Rules
- Start with a concrete imperative verb. Common set: `build / wire / port / pull / push / migrate / refactor / fix / drop / polish / verify / define / clarify / document / lint / link / add`.
- **Don't over-use `add`.** It's the fallback when nothing more specific applies. If you can say `wire`, `build`, `pull`, `port`, `link`, or `migrate`, pick the sharper verb.
- Lowercase by default. Sentence case only for proper nouns or identifiers in backticks.
- ~50-character soft cap. If you can't fit, split the task.
- Use backticks around CLI verbs, flag names, or schema field names: `` `run_state` ``, `` `--activity-relative` ``.
- Drop noise words: "and styling", "with a real", "to associate" — say what changes, not how.

### Examples (good)
```
build apple reminders pull adapter
wire obsidian symlink bridge
add `--activity-relative` scoped view filter
fix duplicate timestamps in rapid session log entries
clarify "N sessions" output in `reindex`
polish error messages + rich output
verify `run_state` in a real automation
drop "(request NN)" suffix from task titles
```

### Examples (avoid)
```
Add Apple Reminders pull adapter (request 09)       ← parenthetical link belongs in frontmatter
Friction: titles with 'request NN' duplicate…       ← "Friction:" is a kind label; goes in metadata
Decide forget verb semantics                         ← prefer concrete verb: "define"
Consider an --activity-relative scoped view…        ← "consider" hides the actual action
Memory show: missing blank line between section…    ← burying the verb behind a noun-phrase prefix
```

Kind/area metadata (bug, feat, polish, etc.) is **out of scope for the title** — it lives in the `kind` frontmatter field (D46).

---

## Task `kind` (D46)

Optional work-classification field. Soft enum:

| `kind` | When to use |
|---|---|
| `feat` | new capability shipped to users |
| `bug` | something is broken |
| `spec` | a decision needs locking before code |
| `polish` | UX/output quality, not behavior |
| `test` | verification work |
| `chore` | maintenance, cleanup, deps, refactor, docs |

- Optional. Tasks without `kind` render with no chip.
- One value per task. Mutable via `octopus set <slug> --kind=<value>`.
- Soft validation — unknown values log a warning, don't reject.
- Indexed. Filter via `octopus list --kind <enum>` (comma-sep for multi).
- Survives promotion. Surface via `--all`, `--promoted`, or `--spec`.

---

## Tags (D76)

Tags are stored with leading `#` in frontmatter to match Obsidian:

```yaml
tags:
  - "#bug"
  - "#tui/marquee"        # nested via /
  - "#release/p0"
```

The reader accepts both `#bug` and `bug` (silent normalization on write). All tag flag values accept input with or without `#`.

### Tag flag matrix

The same four flag families exist on both `capture` and `set`:

| Flag | Behavior |
|---|---|
| `--tag <X>` / `--tags <X[,Y…]>` | **Replace** the tag list |
| `--add-tag <X>` / `--add-tags <X[,Y…]>` | **Append** (dedup) |
| `--remove-tag <X>` / `--remove-tags <X[,Y…]>` | **Remove** (no-op if absent) |
| `--clear-tags` | **Empty** the tag list |

All accept: comma-separated `--tag X,Y,Z`, space-quoted `--tag "X Y Z"`, repeated `--tag X --tag Y`.

**Mutex:** `--tag/--tags` (replace) cannot combine with `--add-tag/--remove-tag/--clear-tags`. Apply order when combining incrementals: `clear → remove → add`.

### Tag filtering

`octopus list --tag parent` matches both `#parent` and any `#parent/*` (prefix match on `/` boundary).

---

## Slug renames and references (D78, D79)

Slugs are filenames — CLI-owned. To rename safely: `octopus set <old> --slug <new>`. This is the **only** way.

The rename cascades automatically:
- Filesystem rename (`tasks/<bucket>/<old>.md` → `tasks/<bucket>/<new>.md`)
- SQLite index update
- `waiting_for: <old>` rewrites in any other task's frontmatter
- `related_tasks:` and `promoted_from:` rewrites in spectacular PLAN.md files
- `→ octopus:<old>` arrow rewrites in any TODO.md the activity has

User-prose bodies (session, memory, handoff) are NOT auto-fixed but ARE named in the warning.

Without `-y`, prompts with a full preview. Pass `-y` to skip.

**Companion verb:** `octopus refs find <slug>` — read-only grep over every Octopus-managed text file (`--all` for cross-activity). Splits into managed refs and user-prose mentions.

---

## `set` vs `mv` vs lifecycle verbs (D77)

| Use this when… | Verb | Side effects |
|---|---|---|
| Change frontmatter only — no file move | `set --bucket <x>` | Frontmatter only. Soft warning on folder mismatch. |
| Physically move the file + frontmatter | `octopus mv <slug> <bucket>` | File move + frontmatter. No date stamps. |
| Lifecycle side effects (date stamps, clearing fields) | `start` / `finish` / `drop` | File move + frontmatter + lifecycle bookkeeping. |

`mv` rejects moves to `done`/`dropped` without required dates — points at `finish`/`drop`.

---

## Capture flag surface (v0.6.0)

`octopus capture <title>` accepts:

| Flag | Field set |
|---|---|
| `--next` / `--now` | `bucket` (mutually exclusive). `--now` does **NOT** auto-pin (D81). |
| `--slug <x>` | Override the auto-generated slug |
| `--priority <urgent\|high\|low>` | `priority` (use `normal`/`none`/`""` to clear) |
| `--due <YYYY-MM-DD>` | `due` |
| `--scheduled <YYYY-MM-DD>` | `scheduled` |
| `--start-date <YYYY-MM-DD>` | `start_date` (does NOT trigger the `start` verb) |
| `--end-date <YYYY-MM-DD>` | `end_date` (validation rejects without a terminal bucket) |
| `--actor <ai\|automation>` | `actor` (use `human`/`""` to clear — human is the default) |
| `--energy <low\|mid\|high>` | `energy` |
| `--owner <name>` | `owner` |
| `--stage <text>` | `stage` (per-activity workflow stage) |
| `--tag/--tags/--add-tag/...` | full tag flag matrix (see above) |

Empty body by default (D82) — no hardcoded `## References`.

---

## Task promotion (D47–D54)

When an Octopus task graduates to a Spectacular request, promote it — don't duplicate it.

```
octopus promote <slug> [<slug>...] --to <target>     # promote
octopus promote <slug> --to <target> --force         # repoint already-promoted
octopus promote <slug> --revert                      # soft-clear (returns to backlog)
```

### When to use
- A backlog idea has matured enough to write a real spec.
- A small task folds into a larger build needing PLAN.md + decisions.
- Multiple related tasks addressed in one cohesive request.

### When NOT to use
- The task is small and self-contained — just `finish` it.
- Not ready to write the spec yet — leave it in `backlog/`.
- The work doesn't need Spectacular-style ceremony.

### `--to` input forms

| Form | Meaning |
|---|---|
| `--to spectacular:20-task-promotion` | explicit existing/new request |
| `--to spec:20-task-promotion` | chip alias accepted |
| `--to 20-task-promotion` | uses `[providers.default]` (= `spectacular`) |
| `--to spec` | single-task only — uses task slug as request slug |
| `--to spec:new --slug 21-foo` | explicit new request |

If the target request doesn't exist, `promote` scaffolds it. `auto_number` (default on) adds a leading `NN-`.

### What promote does

1. Sets `promoted_to: <provider>:<id>` on the task.
2. Sets `end_date: <today>` and `bucket: done`.
3. Moves the file to `tasks/done/<slug>.md`.
4. Replaces the body with a 3-line stub pointing at the PLAN.md.
5. Scaffolds `.spectacular/requests/<slug>/PLAN.md` if absent, with `promoted_from: <task-slug>`.
6. Reindex regenerates `related_tasks:` on the request side (read-only, derived).

### Idempotency

Already-promoted tasks reject with exit 4 unless `--force` (repoint) or `--revert` (soft-clear). PLAN.md and `promoted_from` are historical — never cleared on repoint.

### Multi-task

`octopus promote A B C --to spec:obsidian-bridge` folds three tasks into one request atomically. Provider-only shorthand (`--to spec`) is rejected with 2+ tasks (ambiguous).

Promotion is one-way — reverse promotion (request → task) is not a thing.

---

## Bridges (v1 scope)

Adapters bridge Octopus to external systems. v1 ships pull-only. Verb group: `octopus bridge list / enable / disable / status / peek / pull / search`.

- **`peek`** — read-only display, no files created. Safe exploration.
- **`pull`** — imports as Octopus task files, deduped via `task_external_refs`.

When the user wants to "see what's there" → `peek`. When they want to "bring it in" → `pull`. For full operational guidance, see `references/adapter-framework.md`.

### Adapters shipping with v1

- **Obsidian** (#07): viewer via symlinks. `octopus link` symlinks `.octopus/` into a configured vault location. Read-only.
- **Apple Reminders** (#09): pull-only via `osascript`. Pulls from configured `lists`.
- **TODO.md** (#21): pull-only. Reads `- [ ]` lines from `TODO.md` at activity root.
- **Claude Code plugin**: NOT an adapter — it's a *client* of Octopus. Slash commands (`/octopus:start`, `/octopus:end`, `/octopus:handoff`, `/octopus:where`, `/octopus:memory`, `/octopus:log`) wrap the CLI.

Two-way external sync (Reminders push, GitHub, ICS) is v2.

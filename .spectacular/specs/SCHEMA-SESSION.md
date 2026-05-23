---
status: draft
updated: 2026-05-22
relates_to: SPEC.md §5, CLI-VERBS.md
---

# Session schema — v1

`sessions/<file>.md` frontmatter contract. Captures continuity — what happened in a chunk of focused work, what was learned, what's next.

Filenames are date-prefixed: `YYYY-MM-DD-<slug>.md`.

---

## Field name aliasing

```toml
[session.fields]
started = "start_time"
ended   = "end_time"
```

---

## Canonical order

```yaml
---
# ── identity ─────────────────────────────────────────────────────────
title:                        # required, string
started:                      # required, ISO 8601 datetime
ended:                        # optional, ISO 8601 datetime    (absent = session is OPEN)

# ── lifecycle ────────────────────────────────────────────────────────
active: false                 # optional, boolean              (cache-mirrored; see below)
status:                       # optional, enum: doing | done | dropped  (absent = open)

# ── relationships ────────────────────────────────────────────────────
related_tasks: []             # optional, list of task slugs (within this activity)
related_handoff:              # optional, string — handoff file slug (if this session closed with a handoff)

# ── content metadata ─────────────────────────────────────────────────
summary:                      # optional, string — one-line summary of the session
---
```

---

## Section groups

| Group | Fields |
|---|---|
| Identity | `title`, `started`, `ended` |
| Lifecycle | `active`, `status` |
| Relationships | `related_tasks`, `related_handoff` |
| Content metadata | `summary` |

---

## Field reference

### Identity

#### `title` — required

- Type: string
- Default: filename slug (everything after `YYYY-MM-DD-`).
- Free-form short name for the session.

#### `started` — required

- Type: ISO 8601 datetime (`YYYY-MM-DDTHH:MM:SS`, local time, no timezone suffix in v1).
- Set automatically by `octopus session start`.

#### `ended` — optional

- Type: ISO 8601 datetime
- **Absence is meaningful**: empty/null means the session is OPEN. Populated means CLOSED.
- Set automatically by `octopus session end`.

### Lifecycle

#### `active` — optional

- Type: boolean
- Range: `true` | `false`
- Default: `false`
- **Cache-mirrored**. The runtime active-session pointer lives in `~/.cache/octopus/active-sessions.json`. This frontmatter field is a courtesy mirror for users who grep/inspect files directly. The cache is the source of truth.
- If cache and frontmatter disagree, the cache wins. The CLI MAY refresh the frontmatter to match.

#### `status` — optional

- Type: enum
- Range: `doing` | `done` | `dropped`
- Absence: session is open and not explicitly classified.
- Semantics mirror task `status`:
  - `doing` — work in progress (default for newly-started session)
  - `done` — session ended naturally with goals reached
  - `dropped` — session abandoned (interrupted, scrapped, no longer relevant)
- The distinction between "session ended" (has `ended:`) and "session status" exists because *how* a session ended is different from *that* it ended.

### Relationships

#### `related_tasks` — optional

- Type: list of strings
- Range: task slugs within the same activity (just `<task-slug>`, no activity prefix needed since session is activity-scoped).
- Default: `[]`
- Populated automatically when verbs reference tasks in the active session.

#### `related_handoff` — optional

- Type: string
- Range: a filename in the same activity's `handoffs/` directory (without `.md`).
- Set when a session ends with a handoff written.

### Content metadata

#### `summary` — optional

- Type: string
- Range: one-line summary of what happened. Free-form.
- Set by `octopus session end --summary "<text>"` or interactive prompt.

---

## Storage mode

Sessions are **always stored flat** in `.octopus/sessions/`, regardless of the activity's storage mode (folders vs fields).

Rationale:
- Sessions are machine-readable artifacts, not user-navigated piles.
- Sessions are date-ordered (chronological), not bucket-ordered.
- The natural query is "what did I work on this week", not "show me all dropped sessions" (which is a frontmatter filter, not a pile).

---

## Open vs closed vs active

Three distinct concepts:

| Concept | Field | Meaning |
|---|---|---|
| Open / closed | `ended:` empty or populated | Has the session been formally ended? |
| Active | cache file (mirrored to `active:`) | Of the open sessions in this activity, which one am I currently in? |
| Status | `status:` | Was the session productive (`doing` / `done`) or abandoned (`dropped`)? |

A typical lifecycle:
1. `session start` → `started: now`, `ended: empty`, `active: true` (one per activity), `status: doing` (implicit).
2. `session switch <other>` → previous session: `active: false`. New session: `active: true`.
3. `session end` → `ended: now`, `active: false`, `status: done` (default) or `dropped` (with flag).
4. `session prune` (for stale opens) → `ended: <last_log_time>`, `status: dropped`, plus auto-generated note.

### Multi-open prompt outcomes

When `session start` is invoked and one or more sessions are already open in the activity, the CLI prompts the user with four choices (per D41 Q4):

| Choice | Effect |
|---|---|
| `[c]ontinue` | Abort the new-session creation. Keep working in the currently-active session. |
| `[n]ew` | Create a new session alongside the existing open ones. The new session becomes active. |
| `[e]nd previous + start new` | End the previously-active session as `status: dropped` and append the auto-note `ended by session start --replace` to its body (second-precision timestamp). Then create the new session as active. |
| `[a]bort` | Cancel entirely. No session created. |

`[e]` is destructive of session continuity (the previous session ends with `dropped` status, not `done`), so it requires explicit user choice — never default.

---

## Body conventions

Free-form markdown. Recommended structure:

```markdown
# <title>

## Goal
What I'm trying to accomplish in this session.

## Notes
Chronological notes, code snippets, decisions reached.

## Next
What to pick up next time. Often promoted into a handoff or new task.
```

The body MUST be preserved byte-for-byte across CLI writes. `session log "<note>"` appends to the bottom of the body with a **second-precision** timestamp (per D41 Q2):

```markdown
### 2026-05-22 14:32:17
<note text>
```

Second precision distinguishes session log entries from memory entries (which use minute precision). Multiple log entries in the same minute remain individually addressable.

---

## Validation

### MUST reject

- Missing `title` or `started`.
- `started` or `ended` not parseable as ISO 8601 datetime.
- `ended` earlier than `started`.
- `status` not in enum.

### MUST clear

- When `status: dropped` is set, `active` MUST become `false`.
- When `ended` is set, `active` MUST become `false`.

### SHOULD warn

- Sessions with `ended:` empty and no append activity for > 7 days (stale-session detection). Surface in `octopus where` and `octopus session list`.
- Multiple sessions with `active: true` in the same activity — should be impossible, but if file mismatch with cache, warn.
- `status: done` without `ended:` set — contradictory.
- `related_tasks` referencing slugs that don't exist in the activity's `tasks/`.

### MUST preserve

- Unknown frontmatter fields.
- Body content byte-for-byte.

---

## Reference

- `../SPEC.md §5` — authoritative contract.
- `CLI-VERBS.md` — session verbs (`session start`, `log`, `end`, `switch`, `prune`).
- `CRITICAL-DEPENDENCIES.md` — validation rules.

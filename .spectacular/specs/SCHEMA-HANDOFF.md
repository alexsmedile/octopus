---
status: draft
updated: 2026-05-22
relates_to: SPEC.md §6, CLI-VERBS.md
---

# Handoff schema — v1

`handoffs/<slug>.md` frontmatter contract. A handoff is a deliberate context-transfer note: where work stopped, where to pick up, who else can take over.

Handoffs differ from sessions: a session is a *recording* of work that happened; a handoff is a *deliberate package* of context for future-you or another agent.

---

## Field name aliasing

```toml
[handoff.fields]
created = "creation_date"
```

---

## Canonical order

```yaml
---
# ── identity ─────────────────────────────────────────────────────────
title:                        # required, string
created:                      # required, ISO date

# ── origin & destination ─────────────────────────────────────────────
from_session:                 # optional, string — session filename (without .md) this handoff closes
from_actor: human             # required, enum: human | ai | both     (default human — who is handing off)
to_actor:                     # optional, enum: human | ai | both     (who picks up; absent = unspecified)
to_owner:                     # optional, string                       (named recipient if known)

# ── relationships ────────────────────────────────────────────────────
related_tasks: []             # optional, list of task slugs
related_activities: []        # optional, list of activity IDs (cross-activity handoffs)

# ── lifecycle ────────────────────────────────────────────────────────
status: open                  # required, enum: open | received | resolved | stale  (default open)
received_at:                  # optional, ISO date — when recipient acknowledged
resolved_at:                  # optional, ISO date — when work resumed/completed

# ── content metadata ─────────────────────────────────────────────────
summary:                      # optional, string — one-line TL;DR
priority: medium              # optional, enum: high | medium | low      (default medium)
tags: []                      # optional, list of strings
---
```

---

## Section groups

| Group | Fields |
|---|---|
| Identity | `title`, `created` |
| Origin & destination | `from_session`, `from_actor`, `to_actor`, `to_owner` |
| Relationships | `related_tasks`, `related_activities` |
| Lifecycle | `status`, `received_at`, `resolved_at` |
| Content metadata | `summary`, `priority`, `tags` |

---

## Field reference

### Identity

#### `title` — required

- Type: string

#### `created` — required

- Type: ISO 8601 date
- Set once at creation.

### Origin & destination

#### `from_session` — optional

- Type: string
- Range: a filename in the same activity's `sessions/` directory (without `.md`).
- Populated when `octopus session end --handoff` creates a handoff at session close.

#### `from_actor` — required

- Type: enum
- Range: `human` | `ai` | `both`
- Default: `human`
- Who is producing this handoff.

#### `to_actor` — optional

- Type: enum
- Range: `human` | `ai` | `both`
- Absent: recipient unspecified (open to whoever picks up).
- Useful for `human → ai` handoffs ("AI, take this from here") and reverse.
- **All four combinations of `from_actor` × `to_actor` are valid.** `ai → ai` handoffs are meaningful (one agent passing context to another). The "vague handoff" smell warning applies only to `human → human` without a named `to_owner`.

#### `to_owner` — optional

- Type: string
- Range: free-form (typically a username).
- Use when handoff is to a specific person, not just "anyone."

### Relationships

#### `related_tasks` — optional

- Type: list of strings
- Range: task slugs in this activity (or cross-refs `<activity>/<task>` for cross-activity).
- Default: `[]`

#### `related_activities` — optional

- Type: list of strings
- Range: activity IDs (full or prefix).
- Default: `[]`
- Used for handoffs that span multiple activities (e.g. "starting work on the Shift project requires context from Carousel-Studio").

### Lifecycle

#### `status` — required

- Type: enum
- Range:
  - `open` — handoff written, not yet picked up. Default.
  - `received` — recipient has acknowledged but not yet acted.
  - `resolved` — work has been resumed or the context absorbed.
  - `stale` — handoff is no longer relevant (intent abandoned, info outdated).
- Default: `open`

#### `received_at` — optional

- Type: ISO 8601 date
- Set when `status` transitions to `received`.

#### `resolved_at` — optional

- Type: ISO 8601 date
- Set when `status` transitions to `resolved`.

### Content metadata

#### `summary` — optional

- Type: string
- Range: one-line TL;DR. Free-form.

#### `priority` — optional

- Type: enum
- Range: `high` | `medium` | `low`
- Default: `medium`

#### `tags` — optional

- Type: list of strings
- Default: `[]`

---

## Body conventions

Free-form markdown. Recommended structure:

```markdown
# <title>

## TL;DR
One paragraph: where we are, where to go next.

## What's done
- Bulleted list of completed work.

## What's next
- [ ] Concrete next checkbox steps.

## Suggested next actions
_Machine-actionable. The picker-upper should be able to skim and execute._
- [ ] `octopus task start <slug>`
- [ ] `octopus memory show --section open`
- [ ] `/<skill-name>` if a specific skill is the right next move.

## Open questions
- Things to resolve before continuing.

## References
- [[related-task-slug]]
- `sessions/2026-05-23-<filename>`
- Links, paths, external resources.
```

### Principles

**Reference, don't restate.** If a PRD, decision (`DECISIONS.md` Dn), task, or session
already captures the context, link to it — don't copy it. The handoff is a *router*
to existing artifacts, not a replacement for them.

**Make it executable.** The `## Suggested next actions` block should contain real
commands the recipient can run. A handoff that requires the recipient to *figure out
what to do* has half-failed.

**Persistent in-activity, not ephemeral.** Handoffs live in
`<activity>/.octopus/handoffs/` and accumulate as part of the activity's history.
This differs from Pocock-style "write to $TMPDIR and forget" handoffs — Octopus
handoffs are audit-trail artifacts, not scratch breadcrumbs.

---

## Handoff lifecycle (state machine)

```
              ┌─── received_at set ────┐
              ↓                         │
   created → open ─→ received ─→ resolved
              │                         ↑
              └─── (no pickup) ───→ stale
                    (manual or auto)
```

Transitions are driven by:

- `octopus handoff new <title>` → status: open
- `octopus handoff receive <slug>` → status: received, received_at: today
- `octopus handoff resolve <slug>` → status: resolved, resolved_at: today
- `octopus handoff stale <slug>` or auto (e.g. > 60 days open) → status: stale

These verbs are pending v2 — v1 may only support manual frontmatter edits via `octopus set`.

---

## Validation

### MUST reject

- Missing `title`, `created`, `from_actor`, or `status`.
- `status` not in enum.
- `from_actor` or `to_actor` not in enum.
- `received_at` set but `status` not in `received | resolved`.
- `resolved_at` set but `status` not `resolved`.
- `resolved_at` earlier than `received_at` (when both set).
- `resolved_at` earlier than `created`.

### SHOULD warn

- `status: open` and `created` > 30 days ago (handoff aging).
- `status: open` and no `related_tasks` and no `related_activities` (orphan handoff — what's it about?).
- `from_actor: human, to_actor: human, to_owner` empty (vague handoff — who's it for?).
- Body appears to contain raw secrets (API keys, tokens, passwords, PII). Auto-generated
  handoffs (e.g. from `session end --handoff`) SHOULD scrub before writing. v1 does not
  auto-scrub; the picker-upper is responsible. v2 may hook a redactor.

### MUST preserve

- Unknown frontmatter fields.
- Body byte-for-byte.

---

## Handoff vs session vs memory

These three are easy to confuse. Differences:

| Type | Purpose | Lifecycle |
|---|---|---|
| **Session** | Recording of a work block | Open → closed (mostly auto-managed) |
| **Handoff** | Deliberate context transfer | Open → received → resolved (or stale) |
| **Memory** | Accumulated context across all sessions | Append-only; no terminal state |

A session can produce a handoff. A handoff can prompt a memory entry. Memory is the slowest-decaying of the three.

---

## Reference

- `../SPEC.md §6` — authoritative contract.
- `CLI-VERBS.md` — handoff verbs (`handoff new`, future: `receive`, `resolve`, `stale`).
- `CRITICAL-DEPENDENCIES.md` — validation rules.

# Handoff frontmatter + body — v1

A handoff is a **deliberate context-transfer note**. It says: "here's where I stopped, here's how the next worker (human or AI) picks up."

Handoffs differ from sessions and memory:
- **Session** = recording of a work block (open → closed)
- **Handoff** = deliberate package of context for the next picker-upper (open → received → resolved | stale)
- **Memory** = accumulated context across all sessions (append-only, no terminal)

File location: `<activity>/.octopus/handoffs/<YYYY-MM-DD>-<slug>.md`. Filename is generated; never rename by hand.

## Canonical frontmatter

```yaml
---
# identity
title:                    # required, string
created:                  # required, ISO date

# origin & destination
from_session:             # optional, string — paired session filename (without .md)
from_actor: human         # required, enum. Default "human".
to_actor:                 # optional, enum (absent = unspecified)
to_owner:                 # optional, string (named recipient)

# relationships
related_tasks: []         # optional, list of task slugs (cross-activity: "<activity>/<task>")
related_activities: []    # optional, list of activity IDs

# lifecycle
status: open              # required, enum. Default "open".
received_at:              # optional, ISO date — set when recipient acknowledges
resolved_at:              # optional, ISO date — set when work resumes/completes

# content metadata
summary:                  # optional, string — one-line TL;DR
priority: medium          # optional, enum. Default "medium".
tags: []                  # optional
---
```

## Enums

| Field | Values |
|---|---|
| `from_actor`, `to_actor` | `human`, `ai`, `both` |
| `status` | `open`, `received`, `resolved`, `stale` |
| `priority` | `high`, `medium`, `low` |

All four `from_actor × to_actor` combinations are valid; `ai → ai` is meaningful (one agent passing context to another).

## Body conventions

Free-form markdown. The CLI generates a default body on `handoff new`; the user (or an agent like `octopus-handoff-writer`) fills it in.

Recommended structure:

```markdown
# <title>

## TL;DR
One paragraph. Where we are, where to go next.

## What's done
- Link to existing artifacts: `[[task-slug]]`, `sessions/<filename>`, commit hashes.
- Pointers, not summaries.

## What's next
- [ ] Concrete checkbox steps, small enough to do in <30min each.

## Suggested next actions
_Machine-actionable. Pick one and run it._
- [ ] `octopus task start <slug>`
- [ ] `octopus session start --title "<resume>"`
- [ ] `/<skill-name>` if a skill applies.

## Open questions
- Unresolved. Tag with owner if known.

## References
- `[[task-slug]]`, `sessions/<filename>`, paths, URLs.
```

## Body principles

1. **Reference, don't restate.** If a PRD, decision, task, or session already captures the context, link to it. The handoff is a *router* to existing artifacts, not a replacement for them. A handoff that duplicates a task body is a bug.

2. **Make it executable.** The `## Suggested next actions` section should contain real commands the recipient can run. A handoff that requires the recipient to figure out what to do has half-failed.

3. **Persistent in-activity.** Handoffs live in `<activity>/.octopus/handoffs/` and accumulate as part of the activity's history. (This differs from ephemeral-tempdir handoffs in some other systems — Octopus handoffs are audit-trail artifacts.)

## Cross-field invariants

- `received_at` set requires `status` in `{received, resolved}`.
- `resolved_at` set requires `status == resolved`.
- `resolved_at >= received_at` when both set.
- `resolved_at >= created`.

## SHOULD-warn smells

These don't reject but the CLI surfaces a warning:

- `status: open` and `created > 30 days ago` (aging handoff).
- `status: open` and both `related_tasks: []` and `related_activities: []` (orphan — what's it about?).
- `from_actor: human, to_actor: human, to_owner: <empty>` (vague — who's it for?).
- Body appears to contain raw secrets (API keys, tokens, passwords, PII). v1 does not auto-scrub; the picker-upper is responsible for redaction before writing. v2 may hook a redactor.

## Symmetric session link

When created via `octopus session end --handoff`, two fields are written symmetrically:

- session frontmatter: `related_handoff: <handoff-slug>`
- handoff frontmatter: `from_session: <session-filename>`

Hand-creating one side without the other is allowed but breaks the audit trail. Prefer the verb.

## Lifecycle state machine

```
created → open ─→ received ─→ resolved
           │                       ↑
           └─ (no pickup) ──→ stale
              (manual or auto)
```

Transitions in v1:
- `handoff new <title>` → status: open
- Manual frontmatter edit + `octopus set` → received/resolved/stale (lifecycle verbs `receive`, `resolve`, `stale` are pending v2)

## Validation

The parser hard-rejects:
- Missing `title`, `created`, `from_actor`, or `status`.
- Enum fields not in their allowed set.
- `received_at` set with status not in {received, resolved}.
- `resolved_at` set with status != resolved.
- `resolved_at < received_at`.
- `resolved_at < created`.

The parser preserves on round-trip:
- Unknown frontmatter keys.
- Body byte-for-byte.

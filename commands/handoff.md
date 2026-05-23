---
description: End the active session AND create a paired handoff document.
argument-hint: "[handoff title]"
allowed-tools:
  - Bash(octopus *)
  - Read
  - Write
---

# /octopus:handoff

Wrap up the active session and write a handoff for whoever picks this work up next.

A handoff is a *router*, not a duplicate — link to existing artifacts (tasks, sessions, PRDs) rather than re-summarizing them. Make it executable: every "what's next" item should be a concrete command the recipient can run.

## Steps

1. Verify we're inside an Octopus activity.
2. Gather inputs (prompt only what's missing from `$ARGUMENTS`):
   - **Title** — what is the handoff *about*?
   - **To actor** — `human` | `ai` | `both` | skip
   - **To owner** — named recipient if known | skip
   - **Summary** — one-line TL;DR (defaults to the session summary if set)
3. Run `octopus session end --handoff --non-interactive \
       --handoff-title "<title>" \
       [--handoff-to-actor <actor>] \
       [--handoff-to-owner <owner>] \
       [--handoff-summary "<summary>"]`.
4. Open the created handoff file (`.octopus/handoffs/<slug>.md`) and offer to flesh out the body:
   - `## TL;DR` — where we are, where to go next
   - `## What's done` — link to session log entries, tasks marked done, files touched
   - `## What's next` — concrete checkbox steps
   - `## Suggested next actions` — machine-actionable `octopus ...` / `/<skill>` commands
   - `## Open questions` — unresolved
   - `## References` — link to tasks (`[[task-slug]]`), sessions, PRDs, URLs
5. Redact any obvious secrets before saving (API keys, tokens, PII).
6. Report the handoff filename and symmetric backlink to the session.

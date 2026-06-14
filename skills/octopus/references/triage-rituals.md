# Triage Rituals

Recurring patterns the agent should suggest or run autonomously when the user invites them.

## Morning review
1. `octopus dashboard` — what's loud right now.
2. `octopus next` — the top 3 things the heuristic surfaces.
3. Drill into the top item: `octopus status <slug>` or `octopus get activity <id>` for full context.
4. Pick one, `octopus start <slug>` (use `--activity` if running from outside).

## End of day
1. `octopus list activities --touched-within 1` — what got worked on today.
2. For each touched activity, `octopus memory append <id> "<one-line>"` for what changed.
3. If a work block needs continuity: `octopus session end --handoff` to leave a router note.

## Inbox triage
1. `octopus bridge pull --all` — drain TODO.md, Reminders, etc.
2. `octopus list activities --has-now --has-pinned` — see where the pulled items landed.
3. Promote anything that's really a project, not a task: `octopus promote <slug> --to spectacular:<slug>`.

## Weekly stale check
1. `octopus stale` (default: next-bucket tasks not touched in >14 days).
2. For each, decide: `octopus park <slug>` (back to backlog), `octopus archive <slug>` (hide), or `octopus drop <slug>` (acknowledge it's not happening).
3. `octopus list activities --include-archived --touched-within 60` to spot zombies.

## Cross-project sweep
- `octopus impact --limit 0 --show-score` — full ranked list.
- `octopus list activities --priority urgent` — the projects that should be loudest.
- Mismatch (urgent project with no high-priority tasks)? → review whether the priority is still right.

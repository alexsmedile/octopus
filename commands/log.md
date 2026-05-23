---
description: Append a timestamped entry to the active session.
argument-hint: "<note>"
allowed-tools:
  - Bash(octopus *)
---

# /octopus:log

Quick-capture a note into the active session's log.

## Steps

1. Verify we're inside an Octopus activity with an active session.
2. If `$ARGUMENTS` is empty, ask: "What happened?" (one line).
3. Run `octopus session log "<note>"`.
4. Confirm: report the session filename + timestamp.

## When to use

- Just shipped something: "tests passing for handoffs module"
- Hit a blocker: "blocked by missing Reminders entitlement"
- Made a non-obvious call: "chose State-as-section over State-as-frontmatter; see DECISIONS D41"
- Anything you'd want to remember a week from now

If there's no active session, the CLI errors with a hint to run `/octopus:start` first.

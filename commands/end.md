---
description: End the active Octopus session.
argument-hint: "[summary]"
allowed-tools:
  - Bash(octopus *)
---

# /octopus:end

End the active session in the current activity.

## Steps

1. Verify we're inside an Octopus activity.
2. If `$ARGUMENTS` is provided, treat it as the session summary.
3. Otherwise, ask: "One-line summary of what got done?" (allow empty).
4. Ask: "Status — done or dropped?" (default `done`).
5. Run `octopus session end [--summary "<text>"] [--status done|dropped]`.
6. If the user also wants a handoff, suggest `/octopus:handoff` next.
7. Report the closed session filename.

## Notes

- If multiple sessions are open, defaults to the active one. Pass a slug to end a specific session.
- Use `dropped` if the session was abandoned without meaningful output.

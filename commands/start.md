---
description: Start a new Octopus session in the current activity.
argument-hint: "[session title]"
allowed-tools:
  - Bash(octopus *)
---

# /octopus:start

Start a new session in the current activity.

## Steps

1. Check if we're inside an Octopus activity (cwd has `.octopus/activity.md` somewhere up the tree). If not, tell the user and stop.
2. If `$ARGUMENTS` is provided, treat it as the session title.
3. Otherwise, ask: "What are you working on this session?" (one line).
4. Run `octopus session start --title "<title>"`.
5. If the CLI reports other open sessions, follow its prompt (continue / new / end-previous / abort). Surface the options to the user verbatim.
6. Report the new session filename.

## Notes

- Multiple sessions can be open simultaneously — that's allowed.
- The active session is sticky across CLI invocations (cached in `~/.cache/octopus/active-sessions.json`).
- After this command, `/octopus:log "<note>"` writes timestamped entries to the active session.

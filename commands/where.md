---
description: Show what activity I'm in, what's pinned, what's active.
allowed-tools:
  - Bash(octopus *)
---

# /octopus:where

Surface the current Octopus context.

## Steps

1. Run `octopus where` and show its output verbatim.
2. If inside an activity, also run `octopus memory show` (default preview).
3. If there's an active session, run `octopus session show`.
4. Synthesize a one-paragraph "you are here" summary.

## Output shape

```
Activity:  <id> — <title>
Pinned:    <N> tasks
Active:    <session filename> (started <time>)
Memory:    summary + State + last 3 Decisions + N open questions
```

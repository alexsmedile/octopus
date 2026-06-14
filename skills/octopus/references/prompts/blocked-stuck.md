# Prompt: What's blocked / stuck

**Trigger:** "what's blocked", "what's stuck", "what can't move forward", "impediments"

**Call:**
```bash
octopus stuck
```

**Reply shape:**
```
[N] stuck task(s):

- **[slug]** ([activity_title]) · [issue: blocked/waiting]
  [blocked_by or waiting_for if set — the specific reason]
  → octopus unblock [slug] --activity [id]   # if the blocker is resolved
  → octopus drop [slug] --activity [id]      # if it's not going to happen

[If none:] Nothing stuck — no tasks with issue: blocked or waiting in open buckets.
```

**Conditional logic:**
- `blocked_by` is set → show the dependency slug; check if that task is done: `octopus status [blocked_by slug]`
- `waiting_for` is set → show what's being waited on (person/system)
- Many stuck items (> 5) → group by activity, suggest a project-level triage: `octopus status [activity] --json`
- User says "unblock everything" → confirm each one individually — bulk unblock is a write operation

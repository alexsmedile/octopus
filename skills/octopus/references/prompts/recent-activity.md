# Prompt: What did I work on

**Trigger:** "what did I work on today/this week", "what was I working on", "recent activity"

**Call:**
```bash
# today
octopus list activities --touched-within 1 --json

# this week
octopus list activities --touched-within 7 --json
```

**Reply shape:**
```
You touched [N] project(s) [today/this week]:

- **[title]** — last touched [relative time]
  [bucket summary if interesting, e.g. "1 now · 3 next"]

[repeat per activity, most recent first]
```

**Conditional logic:**
- Nothing touched → "Nothing recorded in that window. Sessions and task moves update `last_touched_at` — if you worked without the CLI, the index won't know."
- User says "yesterday" → use `--touched-within 2` and filter out today in the reply
- Follow-up "what did I actually do in [project]" → `octopus session list --activity [id]` for the session log

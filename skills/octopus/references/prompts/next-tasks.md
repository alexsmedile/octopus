# Prompt: Top tasks / what to work on

**Trigger:** "what should I work on", "top tasks for tomorrow", "what's next", "what's on my plate"

**Call:**
```bash
octopus next --json --limit 3
```

**Reply shape:**
```
Here are your top [N] tasks for [tomorrow/today]:

1. **[title]** · [activity_title]
   [one sentence from `why` breakdown — e.g. "Pinned and due tomorrow." / "Urgent, overdue by 2 days."]
   → octopus start [slug] --activity [activity_id]

2. ...

3. ...
```

**Conditional logic:**
- `issue: blocked` or `waiting` → prepend "⚠ [slug] is blocked — skip or unblock first."
- User mentioned time constraint (e.g. "30 mins") → drop `energy: high` tasks, note the filter
- User mentioned low energy → prefer `energy: low` tasks, reorder before presenting
- All top 3 blocked → run `octopus impact --json` and skip blocked items manually

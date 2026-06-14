# Prompt: Project status

**Trigger:** "how's [project]", "status of [project]", "what's happening with [project]"

**Call:**
```bash
octopus status [project] --json
```

**Reply shape:**
```
**[title]** · [status] · [priority if set]
[type][, area if set] · last touched [relative: "today", "3 days ago", "never"]

Tasks: [backlog] backlog · [next] next · [now] now[· [done] done if > 0]

[working on — only if now > 0:]
Working on: [slug] — [title]

[pinned — only if pinned > 0:]
Pinned: [slug] — [title]

[overdue — only if overdue > 0:]
⚠ Overdue: [slug] (due [date])

→ [one suggested next action]
```

**Suggested next action logic:**
- `now` is empty and `next` > 0 → `octopus focus [top next slug] --activity [id]`
- `now` has items → `octopus start [slug] --activity [id]` (if not already started)
- `overdue` > 0 → `octopus finish [slug]` or `octopus drop [slug] --activity [id]`
- everything in backlog, nothing in next/now → `octopus plan [slug] --activity [id]`

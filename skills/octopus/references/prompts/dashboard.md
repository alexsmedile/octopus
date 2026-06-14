# Prompt: Dashboard / big picture

**Trigger:** "what's going on", "dashboard", "overview", "give me the picture", "where am I"

**Call:**
```bash
octopus dashboard --json
```

**Reply shape:**
```
**[N] pinned** · **[N] overdue** · **[N] in progress**

[overdue section — only if overdue > 0:]
⚠ Overdue ([N]): [slug] ([activity_title], [N] days late) …

[now section — only if now > 0:]
In progress: [slug] ([activity_title]) …

[pinned section — only if pinned > 0:]
Pinned: [slug] ([activity_title]) …

[blocked section — only if blocked > 0:]
Blocked: [slug] — octopus unblock [slug] or octopus drop [slug]

Priority projects: [activity titles with priority urgent/high]
```

**Conditional logic:**
- Everything empty → "Nothing active. Run `octopus next` to see what's ranked highest."
- overdue > 3 → lead with overdue, suggest a triage pass: `octopus stuck`
- blocked > 0 → always show, never skip — blocked items are the primary friction signal

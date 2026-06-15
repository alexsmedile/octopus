# D100 — Blocked / waiting tasks can sit in any bucket when set by a human

- A human-set `issue: blocked` or `issue: waiting` is a **signal**, not a misfiling. The user is the source of truth about what's loaded into mental focus.
- NOW = "what I'm holding in working memory this session" (including stalled items I don't want to lose). NEXT = queue. BACKLOG = list.
- The TUI / renderers surface the block visibly (slot-1 glyph per D96) — the data structure stays sharp, the display does the work.
- **AI-driven flow (deferred):** when an agent (`actor != human`) sets `issue: blocked|waiting`, the agent must demote the task to NEXT or BACKLOG before saving. Enforcement spec is a separate request — not in scope for v1.x.
- `octopus lint` (request 42) emits **info**, not warn/error, on blocked/waiting in NOW or NEXT — visibility only, never auto-fix.

---

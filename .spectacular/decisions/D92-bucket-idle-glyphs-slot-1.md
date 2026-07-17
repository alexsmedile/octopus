# D92 — Bucket idle glyphs (slot 1)

- The slot-1 glyph is a **collapsed hybrid** of bucket × progress × exception. Priority: exception > session > progress > bucket-idle.
- **Bucket idle glyphs (when no progress, no session, no exception):**
  - `backlog` → `·` grey dot
  - `next`    → `□` outline square (was `○`)
  - `now`     → `▣` filled-inner square (was `◐`)
  - `done`    → `●` filled green (terminal — also top of progress ladder)
  - `dropped` → `✕` grey (terminal)
- Progress ladder (`○ ◐ ◑ ●`) is now used *only* when a task has explicit `progress` value. Inherits bucket color.
- Column headers (`board.py`, `focus.py`) updated to match: `□ NEXT`, `▣ NOW`, `● DONE`, `✕ DROPPED`.

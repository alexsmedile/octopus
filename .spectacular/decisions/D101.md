# D101 — View 0 "Activities" joins Focus (1) and Board (2)

- The TUI now has three top-level views, not two: **0 Activities**, **1 Focus**, **2 Board**. Digits `0/1/2` switch between them from anywhere.
- Boot rule: outside any activity → land on Activities (view 0). Inside an activity → land on Focus (view 1, unchanged from v1.0.0).
- Activities is a per-screen view, not a tab widget — implemented as `ActivitiesScreen` alongside `FocusScreen` / `BoardScreen`. Same chrome (HeaderBar, StatusBar, KeymapBar) so all three views feel like one app.
- Activities has its own `ActivitiesKeymapBar` (chips: `CR drill`, `TAB panel`, `␣ collapse`, `/ filter`, `r refresh`, `1 focus`, `2 board`, `? help`, `q quit`). Mutation chips from Focus/Board don't apply.
- Body: three vertically stacked, collapsible panels — `◇ INDEX` / `◆ CURRENT` / `◈ NESTED` (see D102).
- Drill: `Enter` on an activity → replaces screen with FocusScreen for that activity. `Esc` from Focus/Board → confirm modal "Back to Activities?" → `y` returns. `0` is the direct shortcut (no prompt) from anywhere.
- Cursor wraps both directions: `↑` from top → bottom; `↓` from bottom → top. Per-panel, not cross-panel.

---

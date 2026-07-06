---
bucket: done
created: '2026-05-25'
end_date: '2026-07-07'
priority: high
start_date: '2026-07-07'
title: test glyph rendering in low-color terminals
---

Tested manually: `TERM=xterm COLORTERM= octopus tui`, index view + focus view
(backlog/next/now panes). Checked `· □ ■ ● × ! ? ▸ ◇ ⌂ ⟳`.

Result: all glyphs render as real shapes, no `?` fallback boxes, no
collisions between neighbors. Semantic *colors* (amber `!`, pink `now`)
collapse toward plain white/grey without `COLORTERM`, but shape legibility
holds — no actionable gap found.

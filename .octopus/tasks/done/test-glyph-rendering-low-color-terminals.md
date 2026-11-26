---
created_at: '2026-05-25'
extensions:
  octopus.core:
    bucket: now
    start_date: '2026-07-07'
id: a2bf603a-604a-400c-a731-633cbf12cd98
otf_version: 0.1.0
priority: high
project: octopus
state: active
status: done
title: test glyph rendering in low-color terminals
type: task
---

Tested manually: `TERM=xterm COLORTERM= octopus tui`, index view + focus view
(backlog/next/now panes). Checked `· □ ■ ● × ! ? ▸ ◇ ⌂ ⟳`.

Result: all glyphs render as real shapes, no `?` fallback boxes, no
collisions between neighbors. Semantic *colors* (amber `!`, pink `now`)
collapse toward plain white/grey without `COLORTERM`, but shape legibility
holds — no actionable gap found.

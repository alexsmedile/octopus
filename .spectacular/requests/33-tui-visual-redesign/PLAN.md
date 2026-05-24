---
status: open
priority: medium
owner: alex
updated: 2026-05-24
summary: "Redesign the Textual TUI to take visual inspiration from the README hero mockup (docs/assets/tui-hero.svg). Borrow what translates to a terminal — the four-pane Focus layout with a dedicated Detail pane, the header bar with mascot + path + mode tabs + live counters, the colored selection/pin chrome, and the colored keymap chips in the status bar. This is a redesign request, not a rewrite: the existing widgets, write-layer, and keymap stay intact; their visual language updates."
related:
  - 05-tui (shipped)
  - 31-tui-mascot-ascii-animations (shipped)
gates: []
---

# TUI visual redesign — inspired by the README hero mockup

## Goal

The README hero mockup (`docs/assets/tui-hero.svg`) ended up better-designed than the live TUI. This request brings the live TUI's visual language up to match. Layout, chrome, color, and spacing — not behavior. The keymap, write layer (`octopus.actions`), and Focus/Board mode split stay exactly as they are.

This is **a design transfer, not a rebuild**. Alessandro will review the mockup and call out, pane by pane, which elements should land in the terminal and which were SVG-only conveniences.

## Inspiration source (locked)

- **File**: `docs/assets/tui-hero.svg`
- **Snapshot**: `docs/assets/_versions/v0.9.2-20260524-190209/tui-hero.svg` (in case the hero file evolves)
- **What it shows**: a mocked terminal window in Focus mode with mascot header, four panes (Backlog · Now · Next · Detail), pinned-task selection chrome, and a keymap status bar.

## Candidate elements to port (to be triaged)

These are the design choices visible in the mockup. Each one needs a yes/no/modify decision from Alessandro before implementation.

### Header bar
- [ ] **Mini mascot on the left** — already exists; keep the current animated 16×14.
- [ ] **Activity name + path stack** — `🐙 my-project` on top, full path muted underneath.
- [ ] **Mode tabs as styled chips** — `[1] Focus` filled lavender when active; `[2] Board` outlined when inactive. (Currently mode is text-only.)
- [ ] **Live counters on the right** — `● now N`, `○ next N`, `backlog N`, `done N` in a 2×2 grid with bucket-colored numbers. (Currently counters live in the status bar.)

### Pane chrome (Focus mode)
- [ ] **Four panes instead of three**: Backlog (left, tall) · Now (mid-top, highlighted) · Next (mid-bottom) · **Detail (right)**. The detail pane is new — currently the detail overlay is modal.
- [ ] **Pane-header bands**: rounded top bar in the pane's bucket color, holding the title `▾ BACKLOG · 7` style.
- [ ] **Focused pane gets a thicker colored border** (e.g. Now has a yellow 2px border vs. the rest at 1px).
- [ ] **Bucket-tinted pane bg** for the active pane (very faint, e.g. `#1A1620` for now).

### Row chrome
- [ ] **Pinned/selected row** — dashed amber border + 📌 prefix + brighter title color (visible in the mockup's `fix the webhook auth bug` row).
- [ ] **"Just finished" row** — faint green tint with `✓` prefix, fading out before the row leaves the pane.
- [ ] **Two-line rows**: title on top, muted meta line below (`code · started 2h ago`).

### Detail pane (if we adopt it)
- [ ] **Always-visible** vs. **toggle with `Enter`** (currently overlay).
- [ ] **Frontmatter as a key-value grid** with axis-colored values (bucket → yellow, pinned → yellow, issue → pink, etc.).
- [ ] **References + Notes** sections rendered as plain markdown below the grid.

### Status bar / keymap
- [ ] **Colored key chips** — each key in a colored rounded rectangle matching what it does (capture = lavender, finish = green, pin = teal, block = pink, generic = grey).
- [ ] **Right-aligned sync indicator** — `● synced · v0.9.2` and a muted `cwd:` line.
- [ ] **Drop the full keymap from the always-visible bar?** The mockup only shows 8 chips. The current bar is denser. Decision needed.

### Palette (already half-locked, confirm)
- bg: `#0F1014`
- panel bg: `#13141B` (slightly raised) / `#16171E` (sunken)
- border idle: `#2A2D38`
- text: `#E4E6F0` / muted `#8A8D9A` / dim `#6B6E7A`
- bucket accents: `#7AB8FF` backlog · `#5EEAD4` next · `#FACC15` now · `#86EFAC` done · `#F38BA8` dropped/blocked
- system accents: `#CBA6F7` lavender (octopus/identity), `#5EEAD4` mint (synced)

## Non-goals

- **No keymap changes.** Bindings stay 1:1 with `docs/TUI.md`.
- **No new verbs.** Mutations still route through `octopus.actions`.
- **No new modes.** Focus + Board only.
- **No window-chrome simulation** (traffic lights etc. are SVG-only conveniences; the real TUI lives inside the user's actual terminal window).
- **No emoji icons in panes** beyond what's already shipped (📌, ✓). Pixel-art / glyph minimalism preferred.

## Phases (proposed, to be confirmed)

1. **Triage pass** — Alessandro reviews the candidate list above and marks each item *port / modify / skip*.
2. **Theme file pass** — update `cli/src/octopus/tui/theme.tcss` with confirmed palette + chrome rules. No layout changes yet. Visual smoke test in current panes.
3. **Header bar pass** — restyle `header_bar.py` (mode tabs, counters, path stack) per the triage. Mascot widget unchanged.
4. **Pane chrome pass** — update pane headers and focused-pane border in `focus.py` + `board.py`.
5. **Row chrome pass** — pinned/selected/just-finished row styles in the relevant list widgets.
6. **Detail pane pass** — only if confirmed: promote the overlay to a fourth pane in Focus mode. Otherwise skip.
7. **Status bar pass** — colored key chips + right-side sync indicator in `status_bar.py`.
8. **Snapshot + regression** — terminal-screenshot the result in iTerm2 + Alacritty, compare to mockup, capture in `previews/`.

Each phase is small enough to land as one commit with passing tests.

## Files in scope

| File | Likely touch |
|---|---|
| `cli/src/octopus/tui/theme.tcss` | palette, border colors, pane bg, key-chip styles |
| `cli/src/octopus/tui/header_bar.py` | mode tabs, counters, path stack |
| `cli/src/octopus/tui/focus.py` | pane chrome, focused-pane border, possibly add Detail pane |
| `cli/src/octopus/tui/board.py` | pane chrome (columns) |
| `cli/src/octopus/tui/status_bar.py` | colored key chips, right-side sync |
| `cli/src/octopus/tui/overlay.py` | only if Detail becomes a pane — overlay may become unused |
| `cli/src/octopus/tui/icons.py` | bucket dots (●/○), bucket color helpers |
| `cli/src/octopus/tui/app.py` | wiring if a fourth pane lands |

## Open questions for Alessandro

1. **Which mockup elements are "SVG-only sugar"** vs. **must land in the terminal**? (The triage list above is the form for that answer.)
2. **Detail as a permanent pane** (4-pane Focus) or **stay as `Enter` overlay**? This is the biggest layout call.
3. **Always-visible keymap chips** or **collapse on idle / show on `?`**? Affects bottom-bar density.
4. **Counters in header or status bar**? The mockup moved them up; the live TUI has them down.
5. **One commit per phase**, or a single redesign branch with phased commits? (Matches your "local commit then continue" workflow either way.)

## Out of scope (defer to follow-ups)

- Board-mode redesign details beyond pane chrome (column reordering, drag-handles, etc.).
- Mascot animation additions — that's #18 / #32 territory.
- Search bar (`/`) restyle — keep current behavior, just inherit the new palette.
- Help overlay (`?`) restyle — same; inherits palette only.

## Done when

- All triaged "port" items are live in the TUI.
- `theme.tcss` is the single source of truth for the new palette.
- A side-by-side screenshot (live TUI vs. mockup SVG) shows the design language matches.
- Existing tests still pass (no behavior changes expected).
- A new `previews/` folder under this request holds the before/after terminal screenshots.

## Status notes

- 2026-05-24 — opened. Mockup approved by Alessandro as design north star. Triage pass pending: he wants to call out element-by-element what to port.

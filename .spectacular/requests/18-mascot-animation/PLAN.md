---
status: backlog
priority: low
owner: alex
updated: 2026-05-23
summary: "Animate the Octo mascot — pixel-art SVG tentacle wave + idle bob. Used in README hero and (optionally) TUI status bar."
related:
  - 05-tui
gates: []
---

# Octo mascot animation

## Goal

Bring the v1 Classic pixel-art mascot (`assets/mascot/octo-v1-classic.svg`) to life with subtle, looping motion that fits the modern-minimal TUI aesthetic.

## Why

The static mascot is already in the TUI (status bar) and will land in the README hero. A light animation:
- adds personality without distraction
- signals "alive" — useful in a daily-driver TUI
- pairs with the modern-pixel aesthetic of the rest of the design system

## Scope

### Pixel-art animations (SVG-native, no JS)
- **Tentacle wave** — 4 legs cycle height (3 → 2 → 3 px) on a staggered offset, ~600ms loop.
- **Idle bob** — entire body translates `y: 0 → -1 → 0` on a 1s loop.
- **Blink** — both eyes drop to `height: 0` for 100ms every ~4s.

All three should compose without fighting each other. Use SMIL `<animate>` or inline CSS keyframes — whichever survives best in GitHub README rendering.

### Deliverables
- `assets/mascot/octo-v1-animated.svg` — full animation, used in README hero.
- `assets/mascot/octo-v1-classic.svg` — keep the static version as the TUI mascot (terminals don't render SVG animation).
- Optional: `octo-v1-blink-only.svg` for use in places where motion is too much.

### Non-goals
- Animated mascot inside the TUI (terminals can't render SVG — would need a sprite cycler in unicode glyphs; defer).
- Walking, jumping, or scene-based animation.
- Multiple mascot poses for different states (sleeping, focused, etc) — possible follow-up.

## Approach

1. Author tentacle wave first as 3 keyframes per leg, staggered phase per leg.
2. Add idle bob to the parent group transform.
3. Add blink last (rare event, lowest priority).
4. Render-test on:
   - GitHub README (SMIL animation support is patchy in some renderers)
   - Safari, Chrome, Firefox
   - VS Code markdown preview
5. If SMIL fails on GitHub, fall back to CSS keyframes embedded in `<style>` inside the SVG.

## Open questions

- Should the TUI mascot pulse via Textual's own animation API (color flicker, not motion)? Out of scope here, but worth flagging.
- Pixel-perfect at any zoom — `shape-rendering: crispEdges` already handles it; verify after animation.

## Sign-off

- README hero shows the animated mascot.
- Animation is subtle (does not pull eye away from content).
- Static `octo-v1-classic.svg` remains untouched.

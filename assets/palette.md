# Octopus visual palette

Canonical color tokens for SVG diagrams. Extracted from `docs/assets/mental-model.svg`.

## Where things live

- `assets/` — **internal working files**: this palette spec, mascot source variants (`assets/mascot/`), other non-published design artifacts.
- `docs/assets/` — **public-facing media**: the SVGs the README and docs actually embed.

When you change a token here, propagate to the published SVGs in `docs/assets/`.

All diagrams should use these via `:root` CSS variables inside `<defs><style>`, with a `@media (prefers-color-scheme: dark)` override block. Single source of truth, GitHub + Obsidian + VS Code compatible.

The **mascot** (`octopus-mascot.svg`) is the exception: it uses the canonical TUI lavender `#CBA6F7` in both modes, no theming.

---

## Neutrals

| Token | Light | Dark | Use |
|---|---|---|---|
| `--fg` | `#1A1B22` | `#F5F5F7` | Primary text, headings |
| `--muted` | `#4A4D58` | `#C4C7D2` | Secondary text, descriptions |
| `--dim` | `#6B6E7A` | `#8A8D9A` | Tertiary text, file paths, captions |
| `--line` | `#9CA0AE` | `#5A5D6A` | Connectors, arrows |
| `--panel-bg` | `#FAFAFC` | `#16171E` | Card / panel background |
| `--panel-border` | `#D5D7E0` | `#3A3D48` | Card / panel border |

## Accent — fills (soft tinted backgrounds)

| Token | Light | Dark |
|---|---|---|
| `--fill-purple` | `#F3ECFC` | `#2A2540` |
| `--fill-blue` | `#E8F0FB` | `#1F2A3A` |
| `--fill-teal` | `#DCFAF3` | `#1F3530` |
| `--fill-yellow` | `#FBF2D4` | `#3A2F1A` |
| `--fill-pink` | `#FCE4EB` | `#3A1F25` |
| `--fill-green` | `#DEF5E2` | `#1F2A1F` |
| `--fill-grey` | `#ECEDF1` | `#2A2A2E` |

## Accent — strokes / chips (saturated, also for icon fills)

| Token | Light | Dark |
|---|---|---|
| `--stroke-purple` | `#7C4DD9` | `#CBA6F7` |
| `--stroke-blue` | `#3D7CC4` | `#7AB8FF` |
| `--stroke-teal` | `#1FA587` | `#5EEAD4` |
| `--stroke-yellow` | `#B58A0F` | `#FACC15` |
| `--stroke-pink` | `#C9466B` | `#F38BA8` |
| `--stroke-green` | `#2A8A3F` | `#86EFAC` |
| `--stroke-grey` | `#9CA0AE` | `#8A8D9A` |

## Bucket semantics

Pipeline buckets map 1:1 to accent families:

| Bucket | Family | Light stroke | Dark stroke |
|---|---|---|---|
| `backlog` | blue | `#3D7CC4` | `#7AB8FF` (or softer `#A8C9FF` in scaffold) |
| `next` | teal | `#1FA587` | `#5EEAD4` (or softer `#A0E9DA`) |
| `now` | yellow | `#B58A0F` | `#FACC15` (or softer `#F5D75F`) |
| `done` | green | `#2A8A3F` | `#86EFAC` (or softer `#A8E5B0`) |
| `dropped` | grey | `#9CA0AE` | `#8A8D9A` (or softer `#A0A3B0`) |

## Mascot lavender (no theming)

| Token | Value |
|---|---|
| Body | `#CBA6F7` |
| Eyes | `#1A1A1A` |

Canvas always transparent. Same lavender in light and dark — no `prefers-color-scheme` switch.

Source: `assets/mascot/octo-v2-lavender.svg` (canonical). Published copy: `docs/assets/octopus-mascot.svg`. Historical: `_archive/mascot/octo-v1-classic.svg`.

---

## Copy-paste boilerplate

Drop this into the `<defs><style>` block of any new diagram. Use `svg { ... }` as the selector — `:root` is unreliable inside SVG document context, especially in mobile WebKit (see "Known limitation" below).

```css
svg {
  --fg: #1A1B22;
  --muted: #4A4D58;
  --dim: #6B6E7A;
  --line: #9CA0AE;
  --panel-bg: #FAFAFC;
  --panel-border: #D5D7E0;

  --fill-purple: #F3ECFC;
  --fill-blue:   #E8F0FB;
  --fill-teal:   #DCFAF3;
  --fill-yellow: #FBF2D4;
  --fill-pink:   #FCE4EB;
  --fill-green:  #DEF5E2;
  --fill-grey:   #ECEDF1;

  --stroke-purple: #7C4DD9;
  --stroke-blue:   #3D7CC4;
  --stroke-teal:   #1FA587;
  --stroke-yellow: #B58A0F;
  --stroke-pink:   #C9466B;
  --stroke-green:  #2A8A3F;
  --stroke-grey:   #9CA0AE;
}
@media (prefers-color-scheme: dark) {
  svg {
    --fg: #F5F5F7;
    --muted: #C4C7D2;
    --dim: #8A8D9A;
    --line: #5A5D6A;
    --panel-bg: #16171E;
    --panel-border: #3A3D48;

    --fill-purple: #2A2540;
    --fill-blue:   #1F2A3A;
    --fill-teal:   #1F3530;
    --fill-yellow: #3A2F1A;
    --fill-pink:   #3A1F25;
    --fill-green:  #1F2A1F;
    --fill-grey:   #2A2A2E;

    --stroke-purple: #CBA6F7;
    --stroke-blue:   #7AB8FF;
    --stroke-teal:   #5EEAD4;
    --stroke-yellow: #FACC15;
    --stroke-pink:   #F38BA8;
    --stroke-green:  #86EFAC;
    --stroke-grey:   #8A8D9A;
  }
}
```

## Known limitation — mobile theme flipping

On desktop (GitHub.com, Obsidian, VS Code), the `prefers-color-scheme` media query inside each SVG resolves once and matches the surrounding page theme reliably.

On **mobile browsers** the same SVGs can appear to "flip" independently of the host page:

- **iOS Safari/Chrome** evaluate the media query in the SVG's own document context, sometimes caching the result and re-evaluating on repaint (scroll, tab-switch, reload).
- **Android "force-dark" / auto night-mode** inverts the host page but treats embedded SVGs as opaque images — so the SVG renders its own theme, which can disagree with the force-darkened page.
- **Browser-level theme overrides** (Safari's per-tab appearance, Chrome's auto-darken setting) can diverge from the system theme — `prefers-color-scheme` follows the system, while GitHub follows the browser.

This is a renderer-level inconsistency, not a bug in the SVGs. Accepted as a known limitation. Desktop remains the canonical viewing target.

## Reference implementations

- `mental-model.svg` — canonical palette use, all 5 accent families
- `pipeline.svg` — bucket semantics (blue/teal/yellow/green/grey)
- `lifecycle.svg` — bucket semantics + step rows
- `scaffold.svg` — bucket semantics on folder names (softer dark variants)
- `axes.svg` — full 5-color chip set + visibility (yellow) + derived (teal) callouts

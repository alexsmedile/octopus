---
status: queued
priority: medium
owner: alex
updated: 2026-05-24
summary: "Mascot design system: pixel grid spec (canvas, palette, anatomy) + animation language (motion principles, timing, easing). The 'how to draw and move an Octopus mascot' contract — usable for the v1 mascot, future variants, and seasonal skins."
related:
  - 18-mascot-animation
  - 31-tui-mascot-ascii-animations
gates:
  - 31-tui-mascot-ascii-animations
---

# Mascot design system

## Goal

Codify the rules behind Octopus's mascot — both the **shape** (pixel grid spec) and the **motion** (animation language) — so future mascots, variants, and skins stay coherent.

Two pillars, deliberately separated:

1. **Pixel grid spec.** Canvas dimensions, palette, anatomy zones, validation rules. The contract that every mascot grid must satisfy. Think "type metrics for a font".
2. **Animation principles.** A small set of motion rules: what reads as "Octopus," what doesn't. Pared down to ~5 principles, with concrete examples.

This is **documentation + reference assets**, not new code. The output is a design system doc + a specimen-style HTML page + a starter-grid template. Future authors can pick up this folder and produce a coherent new mascot without coaching.

## Why

After #31 ships, we'll have:
- A static mascot (octo-v1-classic).
- 3 TUI animation loops (base / capovolta / moonwalk).
- An HTML preview tool with 8 proposals.

That's a body of *implicit* design decisions. If we add a second mascot later (themed activity skins, seasonal sprite, holiday cameo, "loading" variant), there's nothing written down to anchor those decisions. We'd re-debate canvas size, palette extension rules, what's "in character," and what isn't — every time.

A small written spec prevents that. It also frees up future agents to draft new mascots autonomously, with guardrails: the spec rejects malformed grids before they ship.

## Locked decisions

| # | Locked |
|---|---|
| 1 | **Two-pillar structure** — pixel grid spec (anatomy + palette + canvas) and animation principles (motion language). No family rules / authoring workflow in v1 — defer until we have a second mascot to learn from. |
| 2 | **Output format**: a `MASCOT-DESIGN.md` reference doc + a self-contained HTML specimen page (extends the #31 preview). Both live under `assets/mascot/` or `docs/design/`. |
| 3 | **Gates on #31**: this request codifies what #31 produced. Won't start until #31 is done so we're documenting reality, not aspirations. |

## Scope

### Phase 1 — Pixel grid spec

A single canonical reference: `MASCOT-DESIGN.md` § "Pixel grid spec".

#### Canvas

- **Size**: 16 columns × 14 rows. Locked.
- **Reason**: 16 cells wide = comfortable terminal slot (TUI header has 18-col slot; 16 mascot + 2 padding). 14 rows = 7 cells when rendered as half-blocks — fits the 7-row TUI header exactly.
- **Aspect ratio**: ~1.14 (slightly taller than wide). Reads as a body, not a circle.

#### Palette

Locked symbol set:

| Char | Color | Meaning | Notes |
|---|---|---|---|
| `.` | `#0F1014` (terminal bg) | transparent / background | Renders as the terminal's own background |
| `L` | `#CBA6F7` lavender | body | Catppuccin lavender — matches PINNED chips |
| `E` | `#1A1A1A` near-black | eye | Open eye, 1 cell |
| `e` | half-lavender / half-black | half-blink | For mid-blink frames in animations |
| `c` | mostly-lavender / sliver-black | closed eye | For full-blink frames |

**Extension rule**: future mascots may add new palette chars **only** if they introduce a new visual concept (e.g. accessory color, secondary creature). Re-using `L` for "darker body" or adding `R` for red without a documented reason is forbidden. Palette additions land in this doc.

#### Anatomy zones

The 14 rows are partitioned into 5 functional bands:

| Rows | Band | Rules |
|---|---|---|
| 0-1 | **top margin** | reserved blank in static pose; animations may temporarily occupy for vertical bob |
| 2-4 | **head crown** | rounded body top; min 10 cells wide; centered |
| 5-6 | **eyes band** | exactly one eye pair on these two rows in any static or idle frame |
| 7-8 | **mid body** | full-width body; widest part of mascot |
| 9-11 | **legs** | tentacles/legs; gaps between groups are intentional (4 legs × 2 cells with 1-cell gaps) |
| 12-13 | **bottom margin** | blank in static; animations may extend legs here on certain frames |

**Static-pose constraints** (any non-animation frame):
- Eyes MUST be on rows 5-6 (one eye = 2 vertical cells).
- Legs MUST occupy rows 9-11 and reach the bottom of the body.
- The mascot is left-right symmetric (mirror across column 7.5).
- Body cells form a single connected region.

**Animation frames may break these constraints temporarily** — e.g. a capovolta inverted frame has eyes near the bottom — but only inside a loop, never as a resting state.

#### Validation rules

For an authoring tool / CI check:

1. Grid is exactly `16 * 14 = 224` characters.
2. Only documented palette chars appear.
3. (Static-pose only) eyes appear in rows 5-6.
4. (Static-pose only) mascot is mirror-symmetric across column 7-8 boundary.
5. (Static-pose only) body region is contiguous (single 4-connected component of non-`.` cells, excluding leg row 9-11 gaps).

A small Python validator script ships as part of this request: `cli/src/octopus/mascot/validate_grid.py`. Used by tests and (optionally) a future `octo mascot validate` verb.

### Phase 2 — Animation principles

A second section of `MASCOT-DESIGN.md`: § "Animation principles".

Six locked principles, each with a one-line rule + a concrete example from #31:

1. **Subtle idle, sharp accent** — the base loop is slow and small (1 px bob). Fun loops are fast and big (180° flip in 900 ms). The contrast is the point.
2. **Anticipation before motion** — every "fun" frame sequence starts with a small opposite movement (crouch before jump, squish before flip). One frame of anticipation, no more.
3. **Eyes are emotional state** — eye position and shape carry character. Closed eyes = sleeping / blinking. Eyes during a flip = empty (the head is rotating, the eyes "blur out"). Eyes don't move independently of the head in v1.
4. **Symmetry by default, asymmetry as signal** — static pose is mirror-symmetric. Asymmetric legs = motion (moonwalk slide). Asymmetric body = mid-action (capovolta tilt).
5. **Frame timing is the music** — base idle = 600 ms/frame (calm pulse). Fun loops = 150-200 ms/frame (a beat). Don't mix tempi within a single loop; the controller assumes one timing per loop.
6. **Return to base always** — every non-idle loop ends with a frame matching base idle frame 0. No abrupt cuts. The controller depends on this to hand off control back to the idle cycle.

Each principle gets:
- A short paragraph explaining the *why*.
- A concrete example from #31 (e.g. "Principle 2: see capovolta-B frames 0 (squish) → 1 (spring)").
- A *negative* example — what would break the principle (e.g. "a 4-second slow flip would violate principle 1; the contrast with idle disappears").

### Phase 3 — Specimen page

A standalone HTML reference: `assets/mascot/MASCOT-SPECIMEN.html`.

Extends the #31 preview format but reframed as a **catalog**, not a chooser:

- **Top**: the locked v1 mascot rendered at three scales (small / TUI / hero).
- **Anatomy diagram**: a single static frame with the 5 anatomy bands overlaid (color-coded zones, labels).
- **Palette swatch**: one row per palette character with its hex + role.
- **Animation gallery**: every shipped loop rendered side-by-side, with name + duration + trigger.
- **Validation report**: live JS validator runs the rules in Phase 1 against the displayed grids and reports pass/fail.
- **Authoring template**: an empty 16×14 grid the user can paint in-browser (click to cycle `.` → `L` → `E` → `.`). "Export Python grid" button at the bottom.

This page replaces the #31 preview as the *living reference*. The #31 preview was a chooser; this is the manual.

### Phase 4 — Validator script + test

`cli/src/octopus/mascot/validate_grid.py`:

```python
def validate_grid(grid: str, *, static: bool = True) -> list[str]:
    """Return a list of validation errors. Empty list = valid.

    static=True applies the static-pose constraints (eyes on rows 5-6,
    symmetric, contiguous body). Set False for animation frames.
    """
```

Tests in `cli/tests/test_mascot_grid_validation.py`:
- Reference grid passes.
- Adding a stray pixel outside the body fails the contiguity check.
- Asymmetric grid fails the symmetry check.
- Mid-flip animation frame (eyes at bottom) fails *static* validation but passes when `static=False`.
- Unknown palette char fails.

The TUI rendering doesn't *require* validation — but if a future author commits a malformed grid, the test suite catches it.

## Out of scope

- **Family rules / authoring workflow** — defer until we have a second mascot to learn from. Adding rules without real cases produces over-engineered abstractions.
- **A CLI subcommand** `octo mascot scaffold/validate` — nice to have, defer.
- **Programmatic SVG/GIF export** — could be useful, but distinct request. The HTML specimen + Python validator are enough for v1.
- **Color theme variants** — what if the TUI ever supports a light theme? Out of scope; address when we add theme switching.
- **Larger canvases** for a "hero" mascot — defer. If a bigger mascot is needed for the README, that's its own design exercise.

## Approach

1. **D-entry** locking canvas size, palette, anatomy zones, the six animation principles.
2. **Author `MASCOT-DESIGN.md`** at `assets/mascot/MASCOT-DESIGN.md`. Two sections: Pixel grid spec, Animation principles.
3. **Build `MASCOT-SPECIMEN.html`** — specimen page with anatomy diagram + palette swatch + animation gallery + validator + in-browser editor.
4. **Write `validate_grid.py`** + tests.
5. **Cross-link**: README references the spec; #31's preview.html links to the specimen as the canonical reference.

## Deliverables

- [ ] D-entry (D92) locking canvas, palette, anatomy zones, animation principles.
- [ ] `assets/mascot/MASCOT-DESIGN.md` — pixel grid spec + animation principles.
- [ ] `assets/mascot/MASCOT-SPECIMEN.html` — visual catalog + validator + authoring template.
- [ ] `cli/src/octopus/mascot/validate_grid.py` — runtime validator.
- [ ] `cli/tests/test_mascot_grid_validation.py` — validator tests.
- [ ] README cross-link to the design doc.
- [ ] CHANGELOG entry (probably 0.10.x patch since this is design docs + a small validator).

## Open for grilling

- **Anatomy band boundaries.** Currently: 0-1 top / 2-4 head / 5-6 eyes / 7-8 mid / 9-11 legs / 12-13 bottom. Is 5-6 too tight for eyes if a future variant wants larger eyes (3 cells tall)? The spec could allow eye band = "rows N to N+1 for some N in [4..7]" — looser but harder to validate. My pick: keep strict at 5-6 for v1; relax when a real need surfaces.
- **Palette extensibility cap.** Should we cap the palette at, say, 8 characters max? Prevents palette sprawl. My pick: yes, soft-cap at 8 with a written exception process.
- **Animation principles count.** Six feels right; could pare to four if any feel redundant. Want feedback after I draft them out.
- **Specimen as HTML vs. Markdown.** HTML lets us show the live animation gallery + run the validator client-side. Markdown is more portable. My pick: HTML for the gallery (with embedded Markdown via `<pre>` for the spec text), so a single file is the catalog.

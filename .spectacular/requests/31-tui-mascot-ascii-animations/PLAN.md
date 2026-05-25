---
status: done
priority: medium
owner: alex
updated: 2026-05-25
summary: "Animated TUI mascot — Calm-A idle (independent body + blink channels) plus two event-triggered loops (Capovolta-B on finish, Moonwalk-D6 on pin, with E as an optional second variant). Half-block pixel-art rendering on a 16×14 grid."
related:
  - 18-mascot-animation
gates: []
---

# TUI mascot ASCII animations

## Goal

Replace the static `octo-v1-classic` mascot in the TUI header with a frame-cycling animated version that:

1. Breathes continuously as the default state (Calm-A).
2. Reacts to user actions with quick celebratory animations (Capovolta on `finish`, Moonwalk on `pin`).
3. Always settles back to the centered base pose between animations.

All confirmed visuals were prototyped in `preview.html` and the design iteration is preserved in conversation history. This PLAN.md captures the **locked spec** for Python implementation.

## Canvas & palette (locked)

- **Canvas**: 16 columns × 14 pixel-rows. Rendered as 16 cells × 7 cells using `rich-pixels` half-blocks (`▀`).
- **Palette** (3 chars):
  - `.` → background (`#0F1014`, same as terminal bg)
  - `L` → body lavender (`#CBA6F7`, matches PINNED chips)
  - `E` → eye black (`#1A1A1A`)
- The blink overlay (see § Blink mechanics) does **not** add palette chars — it manipulates the existing `E` positions.

## Body anatomy (locked)

```
row  0-1   top margin (empty)
row  2-3   head crown (10 cols wide, margin 3)
row  4     shoulders (12 cols wide, margin 2)
row  5-6   eye band (12 cols wide, with EE pairs at cols 5-6 and 9-10)
row  7-8   mid body (12 cols wide)
row  9-11  legs (4 pairs at cols 2, 5, 8, 11)
row 12-13  bottom margin (empty)
```

Reference grid (`BASE_REF`):

```
................
................
...LLLLLLLLLL...
...LLLLLLLLLL...
..LLLLLLLLLLLL..
..LLLEELLLEELL..
..LLLEELLLEELL..
..LLLLLLLLLLLL..
..LLLLLLLLLLLL..
..LL.LL.LL.LL...
..LL.LL.LL.LL...
..LL.LL.LL.LL...
................
................
```

## Confirmed animations

### 1. Calm-A (base idle, always-on)

**Two independent channels** running on separate timers.

**Body channel** — deterministic sequence:

| Step | Frame | Hold |
|---|---|---|
| 0 | `POOL_P0` (rest = BASE_REF) | 1200ms |
| 1 | `POOL_P1` (up — body shifted -1 px) | 1200ms |
| 2 | `POOL_P0` (rest) | 1200ms |
| 3 | `POOL_P2` (down — body shifted +1 px) | 1200ms |

Loops. Full breathing cycle = 4.8s.

**Eye/blink channel** — random cooldown 2000-4000ms between blinks. ~20% are doubles.

Single blink phases:
| Phase | Level | Hold |
|---|---|---|
| half | 1 | 100ms |
| closed | 2 | 180ms |
| half | 1 | 100ms |
| (open resumes) | 0 | — |

Double blink: half(100) → closed(140) → open(100) → half(100) → closed(140) → half(100).

### 2. Capovolta-B (triggered on `octopus finish`)

6-frame one-shot. ~900ms total.

| Frame | Visual | Hold |
|---|---|---|
| 0 | Squish (head crown disappears, body squashed) | 150ms |
| 1 | Spring (body stretched up, legs reaching down) | 150ms |
| 2 | Flip-top (body inverted, legs at top) | 150ms |
| 3 | Fully inverted (vertical mirror of BASE_REF) | 200ms |
| 4 | Untwist (body returning) | 150ms |
| 5 | Land (BASE_REF) | 100ms |

Final frame is `BASE_REF` for clean handoff.

### 3. Moonwalk-D6 (triggered on `octopus pin`)

15-frame loop. ~2.7s total. Three layered mechanics:

1. **Body shift ±1 col** (subtle, doesn't touch walls)
2. **Legs ratchet ±2 cols independent of body** — on even frame indices legs at `body_dx-2`, odd at `body_dx+2`. The leg/body speed mismatch is the glide signature.
3. **Wave-of-legs**: one leg pair has its bottom cell removed per frame, cycling through the 4 pairs.
4. **At each apex (body=±1)**: blink shut + tilt head crown + eye shift in look direction. Blink replaces the discarded squash from earlier iterations.

Full sequence:

| # | body_dx | legs_dx | leg-up | eye-shift | opts | ms |
|---|---|---|---|---|---|---|
| 0 | 0 | -2 | 3 | 0 | — | 200 |
| 1 | +1 | +3 | 2 | 0 | — | 200 |
| 2 | +1 | +3 | 2 | +1 | tilt=+1, blink=1 | 150 |
| 3 | +1 | +3 | 2 | +1 | tilt=+1, blink=2 | 150 |
| 4 | +1 | +3 | 2 | +1 | tilt=+1, blink=1 | 150 |
| 5 | +1 | +3 | 2 | +1 | tilt=+1 | 200 |
| 6 | 0 | -2 | 0 | 0 | — | 200 |
| 7 | -1 | +1 | 1 | 0 | — | 200 |
| 8 | -1 | +1 | 1 | -1 | tilt=-1, blink=1 | 150 |
| 9 | -1 | +1 | 1 | -1 | tilt=-1, blink=2 | 150 |
| 10 | -1 | +1 | 1 | -1 | tilt=-1, blink=1 | 150 |
| 11 | -1 | +1 | 1 | -1 | tilt=-1 | 200 |
| 12 | 0 | -2 | 2 | 0 | — | 200 |
| 13 | 0 | +2 | 3 | 0 | — | 200 |
| 14 | 0 | 0 | — | 0 | settle=BASE_REF | 150 |

Final frame is `BASE_REF` for clean handoff.

### 4. Moonwalk-E (optional second variant, triggers TBD)

9-frame loop. ~1.75s total. Body completely still; each of 4 leg pairs takes a turn going up (bottom cell removed), cycling twice through the pairs, then settles.

| # | leg-up index | ms |
|---|---|---|
| 0 | 0 (leg 1) | 200 |
| 1 | 1 (leg 2) | 200 |
| 2 | 2 (leg 3) | 200 |
| 3 | 3 (leg 4) | 200 |
| 4 | 0 | 200 |
| 5 | 1 | 200 |
| 6 | 2 | 200 |
| 7 | 3 | 200 |
| 8 | settle=BASE_REF | 150 |

## Blink mechanics (locked, applies to all animations)

The blink overlay manipulates eye pixels regardless of body position. **Dynamically detects** which rows contain `E` chars (since body shifts move the eye band up or down by 1 row).

Algorithm:

```
def apply_blink(grid: str, level: int) -> str:
    if level == 0:
        return grid
    # Find rows containing eye chars
    rows = split into 14 rows of 16 chars
    eye_rows = [y for y in range(14) if 'E' in rows[y]]
    if not eye_rows:
        return grid
    top = eye_rows[0]
    bottom = eye_rows[-1]
    rows[top] = rows[top].replace('E', 'L')  # always blank top eye row at level 1+
    if level >= 2:
        rows[bottom] = rows[bottom].replace('E', 'L')  # also blank bottom at level 2
    return ''.join(rows)
```

Visual reading:
- **Level 0** (open): both eye rows have `E` → full eye block visible
- **Level 1** (half): top eye row blanked → thin dark line at the bottom of the eye cell (eyelid dropping from above)
- **Level 2** (closed): both rows blanked → eye fully gone

The dynamic detection was the key fix — early prototypes hardcoded rows 5-6 and broke when body shifted up/down (causing the blink to read as "upward" instead of "downward").

## State machine

```
state: "idle" | "capovolta" | "moonwalk-d6" | "moonwalk-e"
```

- **idle**: runs Calm-A controller (body channel + blink channel).
- **capovolta / moonwalk-d6 / moonwalk-e**: plays the fixed frame list once. On last frame, transitions back to idle.
- Public API: `trigger(loop_name)` — only honored when state is "idle". No queueing.

## Trigger model

Initial wiring (subject to revision once we see it in the TUI):
- `octopus finish` → capovolta-B
- `octopus pin` → moonwalk-D6
- (moonwalk-E reserved for a future hook — possibly `plan` or `focus`)
- Optional random ambient interrupt: every 30s, 15% chance to trigger one of D6/E. Decision deferred to visual QA.

## Implementation files

- `cli/src/octopus/tui/mascot_frames.py` — all grid constants + build helpers + apply_blink
- `cli/src/octopus/tui/mascot.py` — refactored: backwards-compat `render_mascot()` wrapper + `render_frame(name, idx, blink_level=0)`
- `cli/src/octopus/tui/header_bar.py` — `_Mascot` widget gets state machine + interval + `trigger()` API
- `cli/src/octopus/tui/focus.py` / `cli/src/octopus/tui/board.py` — call `mascot.trigger()` after finish/pin verbs succeed
- `cli/tests/test_mascot_animation.py` — frame parsing, state transitions, apply_blink with body shifts

## Out of scope

- More than two event-triggered animations (defer to v2)
- Reactive color shifts
- Configurability (`--no-animation`, mascot palette overrides) — add when requested
- SVG/README animation (that's #18, separate substrate)
- Audio cues

## Deliverables

- [x] Visual spec confirmed via preview.html (v1 through v9 iterations preserved in history)
- [x] Locked PLAN.md (this file)
- [x] `mascot_frames.py` with all confirmed grids
- [x] `mascot.py` refactored
- [x] `_Mascot` widget state machine
- [x] Event wiring (board.py + focus.py call `mascot.trigger()`)
- [x] Tests (27 mascot tests, 603 total)
- [x] Visual QA in real TUI (v0.9.6 session, ambient temp-boosted then reverted)
- [x] CHANGELOG entry (v0.9.6)
- [x] Version bump (0.9.5 → 0.9.6)
- [x] Ambient idle interrupt (30s / 15%, picks d6 or e)

## References

- `preview.html` — interactive prototype with all variants (confirmed + archived)
- `calm-debug.html` — frame scrubber used to diagnose the blink-direction bug
- Conversation history v1-v9 — design evolution and rejection rationale

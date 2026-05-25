"""Animated mascot frame library — see #31 PLAN.md for the locked spec.

Each frame is a 16×14 ASCII grid using palette `.` (bg) / `L` (body) / `E` (eye).
Build helpers (`shift_v`, `build_d6_frame`, `apply_blink`) generate frames
without manually retyping similar bodies.

Confirmed animations:
  - POOL_FRAMES: 3 body-bob frames for the Calm-A idle (rest, up, down)
  - CAPOVOLTA_B_FRAMES: 6-frame squish + flip on `octopus finish`
  - MOONWALK_D6_FRAMES: 15-frame glide on `octopus pin`
  - MOONWALK_E_FRAMES: 9-frame wave-of-legs (variant, trigger TBD)

All non-idle animations end on `BASE_REF` so the controller can hand control
back to Calm-A without a visual jump.
"""

from __future__ import annotations

from dataclasses import dataclass

W: int = 16
H: int = 14


# ─── Static reference (matches octo-v1-classic.svg) ───────────────────

BASE_REF: str = (
    "................"
    "................"
    "...LLLLLLLLLL..."
    "...LLLLLLLLLL..."
    "..LLLLLLLLLLLL.."
    "..LLLEELLLEELL.."
    "..LLLEELLLEELL.."
    "..LLLLLLLLLLLL.."
    "..LLLLLLLLLLLL.."
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "................"
    "................"
)


# ─── Geometry helpers ─────────────────────────────────────────────────


def shift_v(grid: str, dy: int) -> str:
    """Shift entire grid vertically by dy pixels. Positive = down, negative = up."""
    rows = [grid[y * W : (y + 1) * W] for y in range(H)]
    out = []
    for y in range(H):
        src = y - dy
        out.append(rows[src] if 0 <= src < H else "." * W)
    return "".join(out)


def mirror_v(grid: str) -> str:
    """Vertical mirror — used by the capovolta flip frame."""
    rows = [grid[y * W : (y + 1) * W] for y in range(H)]
    return "".join(reversed(rows))


# ─── Blink overlay (dynamic eye-row detection) ────────────────────────


def apply_blink(grid: str, level: int) -> str:
    """Apply a blink level to a grid.

    The eyelid drops from above regardless of body position. We find which
    rows currently contain eye chars (E) — they shift up/down with the body —
    and blank the top eye row at level 1, both eye rows at level 2.

    Levels:
      0 (open):   both eye rows have E → full eye block
      1 (half):   top eye row → body → thin dark line at the bottom of the cell
      2 (closed): both rows → body → eye fully gone
    """
    if level == 0:
        return grid
    rows = [grid[y * W : (y + 1) * W] for y in range(H)]
    eye_rows = [y for y in range(H) if "E" in rows[y]]
    if not eye_rows:
        return grid
    top, bottom = eye_rows[0], eye_rows[-1]
    rows[top] = rows[top].replace("E", "L")
    if level >= 2:
        rows[bottom] = rows[bottom].replace("E", "L")
    return "".join(rows)


# ─── Calm-A pool ──────────────────────────────────────────────────────

POOL_REST: str = BASE_REF
POOL_UP: str = shift_v(BASE_REF, -1)
POOL_DOWN: str = shift_v(BASE_REF, 1)

POOL_FRAMES: tuple[str, ...] = (POOL_REST, POOL_UP, POOL_DOWN)


@dataclass(frozen=True)
class CalmStep:
    """One step in the Calm-A body cycle."""

    pool_idx: int  # 0=rest, 1=up, 2=down
    ms: int


# Deterministic body cycle: rest → up → rest → down → repeat.
CALM_A_SEQUENCE: tuple[CalmStep, ...] = (
    CalmStep(pool_idx=0, ms=1200),
    CalmStep(pool_idx=1, ms=1200),
    CalmStep(pool_idx=0, ms=1200),
    CalmStep(pool_idx=2, ms=1200),
)


@dataclass(frozen=True)
class BlinkPhase:
    """One phase of a blink animation."""

    level: int  # 0=open, 1=half, 2=closed
    ms: int


# Single blink: half → closed → half → open (open is implicit, no entry needed).
SINGLE_BLINK_PHASES: tuple[BlinkPhase, ...] = (
    BlinkPhase(level=1, ms=100),
    BlinkPhase(level=2, ms=180),
    BlinkPhase(level=1, ms=100),
)

# Double blink: two singles glued together with an open frame between.
DOUBLE_BLINK_PHASES: tuple[BlinkPhase, ...] = (
    BlinkPhase(level=1, ms=100),
    BlinkPhase(level=2, ms=140),
    BlinkPhase(level=0, ms=100),
    BlinkPhase(level=1, ms=100),
    BlinkPhase(level=2, ms=140),
    BlinkPhase(level=1, ms=100),
)

# Cooldown range between blinks (ms).
BLINK_COOLDOWN_MIN_MS: int = 2000
BLINK_COOLDOWN_MAX_MS: int = 4000

# Probability of any given blink being a double.
DOUBLE_BLINK_PROB: float = 0.20

# Ambient idle interrupt: every AMBIENT_TICK_MS while idle, roll AMBIENT_PROB
# to spontaneously play moonwalk-d6 or moonwalk-e (50/50). Set AMBIENT_PROB=0
# to disable. See PLAN.md §"Trigger model".
AMBIENT_TICK_MS: int = 30_000
AMBIENT_PROB: float = 0.15
AMBIENT_ANIMATIONS: tuple[str, ...] = ("moonwalk-d6", "moonwalk-e")


# ─── Capovolta-B (squish + flip, triggered on `octopus finish`) ───────


_CAPO_B_SQUISH: str = (
    "................"
    "................"
    "................"
    "................"
    "................"
    "..LLLLLLLLLLLL.."
    "..LLEELLLEELLL.."
    "..LLEELLLEELLL.."
    "..LLLLLLLLLLLL.."
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "................"
    "................"
    "................"
)

_CAPO_B_SPRING: str = (
    "................"
    "...LLLLLLLLLL..."
    "..LLLLLLLLLLLL.."
    "..LLLEELLLEELL.."
    "..LLLEELLLEELL.."
    "..LLLLLLLLLLLL.."
    "..LLLLLLLLLLLL.."
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "................"
    "................"
    "................"
)

_CAPO_B_FLIP_TOP: str = (
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "..LLLLLLLLLLLL.."
    "..LLLLLLLLLLLL.."
    "..LLLLLLLLLLLL.."
    "..LLLLLLLLLLLL.."
    "...LLLLLLLLLL..."
    "................"
    "................"
    "................"
    "................"
    "................"
    "................"
    "................"
)

_CAPO_B_INVERTED: str = mirror_v(BASE_REF)

_CAPO_B_UNTWIST: str = (
    "................"
    "................"
    "................"
    "..LL.LL.LL.LL..."
    "..LL.LL.LL.LL..."
    "..LLLLLLLLLLLL.."
    "..LLLEELLLEELL.."
    "..LLLEELLLEELL.."
    "..LLLLLLLLLLLL.."
    "..LLLLLLLLLLLL.."
    "...LLLLLLLLLL..."
    "................"
    "................"
    "................"
)


@dataclass(frozen=True)
class AnimFrame:
    """A single frame in a non-idle animation."""

    grid: str
    ms: int


CAPOVOLTA_B_FRAMES: tuple[AnimFrame, ...] = (
    AnimFrame(grid=_CAPO_B_SQUISH, ms=150),
    AnimFrame(grid=_CAPO_B_SPRING, ms=150),
    AnimFrame(grid=_CAPO_B_FLIP_TOP, ms=150),
    AnimFrame(grid=_CAPO_B_INVERTED, ms=200),
    AnimFrame(grid=_CAPO_B_UNTWIST, ms=150),
    AnimFrame(grid=BASE_REF, ms=100),
)


# ─── Moonwalk-D6 (glide + ratcheting legs + blink at apex) ────────────


def _pad_row(content: str, left_margin: int) -> str:
    """Place content at left_margin within a 16-cell row, clipping at edges."""
    row = ["."] * W
    for i, ch in enumerate(content):
        col = left_margin + i
        if 0 <= col < W:
            row[col] = ch
    return "".join(row)


def build_d6_frame(
    body_dx: int,
    legs_dx: int,
    leg_up_idx: int,
    eye_shift: int,
    *,
    tilt: int = 0,
    blink_level: int = 0,
) -> str:
    """Assemble one D6 frame from its parameters.

    Args:
        body_dx: horizontal shift of body (whole body translates)
        legs_dx: horizontal shift of leg group (independent of body — the
            speed-difference ratchet that creates the glide effect)
        leg_up_idx: which of the 4 leg pairs has its bottom cell removed (the
            wave-of-legs pattern). 0..3.
        eye_shift: horizontal shift of eyes within the body (the "look"
            direction at the apex)
        tilt: head-crown tilt (rows 2-3 shifted independently)
        blink_level: 0/1/2 — applied AFTER eye placement, then dynamically
            blanked by apply_blink
    """
    body_template = [
        ("LLLLLLLLLL", 3),   # row 2 head crown
        ("LLLLLLLLLL", 3),   # row 3 head crown
        ("LLLLLLLLLLLL", 2), # row 4 shoulders
        ("LLLLLLLLLLLL", 2), # row 5 eye band (overlay below)
        ("LLLLLLLLLLLL", 2), # row 6 eye band (overlay below)
        ("LLLLLLLLLLLL", 2), # row 7 mid body
        ("LLLLLLLLLLLL", 2), # row 8 mid body
    ]
    # Tilt applies to head crown rows only.
    if tilt:
        body_template[0] = (body_template[0][0], body_template[0][1] + tilt)
        body_template[1] = (body_template[1][0], body_template[1][1] + tilt)

    out: list[str] = ["." * W, "." * W]
    for content, margin in body_template:
        out.append(_pad_row(content, margin + body_dx))

    # Overlay eyes on rows 5 and 6 (canvas rows). Skip on level-2 blink (eye gone).
    if blink_level < 2:
        left_eye_col = 4 + body_dx + eye_shift
        right_eye_col = 10 + body_dx + eye_shift
        for row_idx in (5, 6):
            chars = list(out[row_idx])
            for c in (left_eye_col, right_eye_col):
                if 0 <= c < W:
                    chars[c] = "E"
                if 0 <= c + 1 < W:
                    chars[c + 1] = "E"
            out[row_idx] = "".join(chars)
    # Level-1 blink: blank the top eye row only (apply_blink does this dynamically
    # later, but to make the function self-contained we replicate here).
    if blink_level == 1:
        chars = list(out[5])
        for i, ch in enumerate(chars):
            if ch == "E":
                chars[i] = "L"
        out[5] = "".join(chars)

    # Legs — 4 pairs at body-local cols 0, 3, 6, 9 (world cols 2, 5, 8, 11).
    leg_pair_cols = [2, 5, 8, 11]

    def leg_row() -> str:
        row = ["."] * W
        for c in leg_pair_cols:
            world_c = c + legs_dx
            if 0 <= world_c < W:
                row[world_c] = "L"
            if 0 <= world_c + 1 < W:
                row[world_c + 1] = "L"
        return "".join(row)

    def leg_bottom(skip: int) -> str:
        row = ["."] * W
        for p, c in enumerate(leg_pair_cols):
            if p == skip:
                continue
            world_c = c + legs_dx
            if 0 <= world_c < W:
                row[world_c] = "L"
            if 0 <= world_c + 1 < W:
                row[world_c + 1] = "L"
        return "".join(row)

    out.append(leg_row())                  # row 9 leg tops
    out.append(leg_row())                  # row 10 leg mids
    out.append(leg_bottom(leg_up_idx))     # row 11 leg bottoms (one pair missing)
    out.append("." * W)
    out.append("." * W)
    return "".join(out)


def _legs_for_d6(body_dx: int, frame_idx: int) -> int:
    """Legs ratchet ±2 cols around the body, alternating per frame index."""
    return body_dx - 2 if frame_idx % 2 == 0 else body_dx + 2


# 15-frame D6 cycle, ending at BASE_REF for clean handoff.
MOONWALK_D6_FRAMES: tuple[AnimFrame, ...] = (
    # Right glide: body 0 → +1
    AnimFrame(grid=build_d6_frame(0,  _legs_for_d6(0, 0), 3, 0), ms=200),    # 0
    AnimFrame(grid=build_d6_frame(1,  _legs_for_d6(1, 1), 2, 0), ms=200),    # 1
    # Right apex: drooping → closed → drooping → open with tilt+look
    AnimFrame(grid=build_d6_frame(1, _legs_for_d6(1, 1), 2, 1, tilt=1, blink_level=1), ms=150),  # 2
    AnimFrame(grid=build_d6_frame(1, _legs_for_d6(1, 1), 2, 1, tilt=1, blink_level=2), ms=150),  # 3
    AnimFrame(grid=build_d6_frame(1, _legs_for_d6(1, 1), 2, 1, tilt=1, blink_level=1), ms=150),  # 4
    AnimFrame(grid=build_d6_frame(1, _legs_for_d6(1, 1), 2, 1, tilt=1), ms=200),                  # 5
    # Left glide: body +1 → -1 (wave reverses)
    AnimFrame(grid=build_d6_frame(0,  _legs_for_d6(0, 6), 0, 0), ms=200),    # 6
    AnimFrame(grid=build_d6_frame(-1, _legs_for_d6(-1, 7), 1, 0), ms=200),   # 7
    # Left apex: same blink pattern with tilt=-1
    AnimFrame(grid=build_d6_frame(-1, _legs_for_d6(-1, 7), 1, -1, tilt=-1, blink_level=1), ms=150),  # 8
    AnimFrame(grid=build_d6_frame(-1, _legs_for_d6(-1, 7), 1, -1, tilt=-1, blink_level=2), ms=150),  # 9
    AnimFrame(grid=build_d6_frame(-1, _legs_for_d6(-1, 7), 1, -1, tilt=-1, blink_level=1), ms=150),  # 10
    AnimFrame(grid=build_d6_frame(-1, _legs_for_d6(-1, 7), 1, -1, tilt=-1), ms=200),                 # 11
    # Return to center
    AnimFrame(grid=build_d6_frame(0,  _legs_for_d6(0, 12), 2, 0), ms=200),   # 12
    AnimFrame(grid=build_d6_frame(0,  _legs_for_d6(0, 13), 3, 0), ms=200),   # 13
    # Settle to BASE_REF (clean handoff)
    AnimFrame(grid=BASE_REF, ms=150),                                         # 14
)


# ─── Moonwalk-E (wave of legs, variant) ───────────────────────────────


def _with_legs(leg_rows: tuple[str, str, str]) -> str:
    """Build a frame with custom leg rows on top of BASE_REF's body."""
    return (
        BASE_REF[: 9 * W]
        + leg_rows[0]
        + leg_rows[1]
        + leg_rows[2]
        + BASE_REF[12 * W :]
    )


_LEG1_UP = ("..LL.LL.LL.LL...", "..LL.LL.LL.LL...", ".....LL.LL.LL...")
_LEG2_UP = ("..LL.LL.LL.LL...", "..LL.LL.LL.LL...", "..LL....LL.LL...")
_LEG3_UP = ("..LL.LL.LL.LL...", "..LL.LL.LL.LL...", "..LL.LL....LL...")
_LEG4_UP = ("..LL.LL.LL.LL...", "..LL.LL.LL.LL...", "..LL.LL.LL......")


MOONWALK_E_FRAMES: tuple[AnimFrame, ...] = (
    AnimFrame(grid=_with_legs(_LEG1_UP), ms=200),
    AnimFrame(grid=_with_legs(_LEG2_UP), ms=200),
    AnimFrame(grid=_with_legs(_LEG3_UP), ms=200),
    AnimFrame(grid=_with_legs(_LEG4_UP), ms=200),
    AnimFrame(grid=_with_legs(_LEG1_UP), ms=200),
    AnimFrame(grid=_with_legs(_LEG2_UP), ms=200),
    AnimFrame(grid=_with_legs(_LEG3_UP), ms=200),
    AnimFrame(grid=_with_legs(_LEG4_UP), ms=200),
    # Settle to BASE_REF
    AnimFrame(grid=BASE_REF, ms=150),
)


# ─── Animation registry ───────────────────────────────────────────────


ANIMATIONS: dict[str, tuple[AnimFrame, ...]] = {
    "capovolta": CAPOVOLTA_B_FRAMES,
    "moonwalk-d6": MOONWALK_D6_FRAMES,
    "moonwalk-e": MOONWALK_E_FRAMES,
}

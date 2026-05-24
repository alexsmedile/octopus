"""Generate an animated SMIL SVG mascot for the README hero.

Source of truth: cli/src/octopus/tui/mascot_frames.py
Output: docs/assets/octopus-mascot.svg (overwrites the static version)

The animation mirrors the TUI's idle Calm-A loop (body bob + blink) plus a
leg-wiggle wave drawn from Moonwalk-E. Single loop, repeatCount=indefinite.

Run from the project root:
    python3 assets/mascot/build_animated_svg.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cli" / "src"))

from octopus.tui.mascot_frames import (  # noqa: E402
    BASE_REF,
    H,
    POOL_DOWN,
    POOL_REST,
    POOL_UP,
    W,
    _LEG1_UP,
    _LEG2_UP,
    _LEG3_UP,
    _LEG4_UP,
    _with_legs,
    apply_blink,
)

CELL = 14  # pixels per grid cell — matches existing static SVG (224×196)
BODY = "#CBA6F7"
EYE = "#1A1A1A"

# ── Build the frame timeline ───────────────────────────────────────────
# Each entry: (grid_string, duration_ms)
# Goal: a calm, looping idle that reads as "alive" on a README hero.

REST = POOL_REST
UP = POOL_UP
DOWN = POOL_DOWN
REST_HALF = apply_blink(REST, 1)
REST_CLOSED = apply_blink(REST, 2)
UP_HALF = apply_blink(UP, 1)
UP_CLOSED = apply_blink(UP, 2)

WIGGLE_1 = _with_legs(_LEG1_UP)
WIGGLE_2 = _with_legs(_LEG2_UP)
WIGGLE_3 = _with_legs(_LEG3_UP)
WIGGLE_4 = _with_legs(_LEG4_UP)

TIMELINE: list[tuple[str, int]] = [
    # One tight cycle: bob + blink + leg-wiggle, total ~4800ms.
    # Designed to read as "alive" without dominating the README hero.
    (REST, 600),
    # Blink (380ms) on rest
    (REST_HALF, 100),
    (REST_CLOSED, 180),
    (REST_HALF, 100),
    (REST, 400),
    # Body bob up
    (UP, 700),
    # Leg-wiggle wave during up-pose (4 legs × 150ms = 600ms)
    (WIGGLE_1, 150),
    (WIGGLE_2, 150),
    (WIGGLE_3, 150),
    (WIGGLE_4, 150),
    # Settle back to rest, then down, then close loop
    (REST, 500),
    (DOWN, 700),
    (REST, 600),
]

# Total loop duration
TOTAL_MS = sum(ms for _, ms in TIMELINE)

# ── Emit ───────────────────────────────────────────────────────────────

def grid_to_cells(grid: str) -> list[tuple[int, int, str]]:
    """Return (x_cell, y_cell, char) for every non-bg cell in the grid."""
    out = []
    for i, ch in enumerate(grid):
        if ch == ".":
            continue
        out.append((i % W, i // W, ch))
    return out


def emit_svg() -> str:
    width_px = W * CELL
    height_px = H * CELL

    # Strategy: every cell in the 16×14 grid gets one <rect>. Each rect has
    # an <animate> on its `fill` attribute, with values driven by the
    # timeline. This keeps the file flat and small (224 cells, ~5KB).

    # Build per-cell fill sequences.
    cell_fills: dict[tuple[int, int], list[str]] = {
        (x, y): [] for x in range(W) for y in range(H)
    }
    key_times: list[float] = []
    elapsed = 0
    for grid, ms in TIMELINE:
        for y in range(H):
            for x in range(W):
                ch = grid[y * W + x]
                color = BODY if ch == "L" else EYE if ch == "E" else "none"
                cell_fills[(x, y)].append(color)
        key_times.append(elapsed / TOTAL_MS)
        elapsed += ms
    # Close the loop back to the first frame for seamless wrap.
    for cell in cell_fills.values():
        cell.append(cell[0])
    key_times.append(1.0)

    dur_s = TOTAL_MS / 1000
    key_times_str = ";".join(f"{t:.6f}" for t in key_times)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width_px} {height_px}" '
        f'shape-rendering="crispEdges" '
        f'style="image-rendering: pixelated;" '
        f'role="img" aria-label="Octopus pixel mascot — lavender, animated">'
    )
    parts.append("  <title>Octopus mascot (animated)</title>")

    # Only emit rects for cells that are ever non-bg.
    for (x, y), fills in cell_fills.items():
        if all(f == "none" for f in fills):
            continue
        # Optimize: if the cell is always the same color, no animation.
        unique = set(fills)
        px, py = x * CELL, y * CELL
        if len(unique) == 1:
            color = fills[0]
            parts.append(
                f'  <rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" '
                f'fill="{color}" shape-rendering="crispEdges"/>'
            )
        else:
            values_str = ";".join(fills)
            parts.append(
                f'  <rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" '
                f'fill="{fills[0]}" shape-rendering="crispEdges">'
                f'<animate attributeName="fill" '
                f'values="{values_str}" '
                f'keyTimes="{key_times_str}" '
                f'calcMode="discrete" '
                f'dur="{dur_s:.3f}s" repeatCount="indefinite"/>'
                f"</rect>"
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    out_path = ROOT / "docs" / "assets" / "octopus-mascot.svg"
    src_path = ROOT / "assets" / "mascot" / "octo-v2-lavender-animated.svg"
    svg = emit_svg()
    out_path.write_text(svg)
    src_path.write_text(svg)
    print(f"wrote {out_path} ({len(svg)} bytes, loop = {TOTAL_MS}ms)")
    print(f"wrote {src_path} (source copy)")


if __name__ == "__main__":
    main()

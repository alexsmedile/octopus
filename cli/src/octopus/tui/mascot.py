"""Pixel-art octopus mascot — terminal rendering via rich-pixels + PIL.

Mirrors `assets/mascot/octo-v1-classic.svg` pixel-for-pixel. The SVG is on a
16×14 grid; we build a same-size in-memory RGB image and let rich-pixels
render it with unicode half-blocks (▀) so each terminal cell = 2 vertical
SVG pixels. Net result: a 16-cell-wide, 7-cell-tall pixel mascot.

Color: lavender (#CBA6F7) — matches PINNED chips and the brand accent.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image
from rich_pixels import Pixels

# Lavender (Catppuccin) — matches PINNED, brand accent.
MASCOT_COLOR = (203, 166, 247)   # #CBA6F7
EYE_COLOR = (26, 26, 26)         # #1A1A1A
BG_COLOR = (15, 16, 20)          # #0F1014 — same as TUI screen bg

# ASCII pixel map of octo-v1-classic.svg (16 cols × 14 rows).
#   .  = transparent / background
#   L  = lavender body
#   E  = black eye
_GRID = (
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
_W, _H = 16, 14
_PALETTE = {"L": MASCOT_COLOR, "E": EYE_COLOR, ".": BG_COLOR}


@lru_cache(maxsize=1)
def _build_image() -> Image.Image:
    img = Image.new("RGB", (_W, _H), BG_COLOR)
    pixels = img.load()
    for i, ch in enumerate(_GRID):
        x = i % _W
        y = i // _W
        pixels[x, y] = _PALETTE[ch]
    return img


@lru_cache(maxsize=1)
def render_mascot() -> Pixels:
    """Half-block-rendered mascot: 16 cells wide × 7 cells tall."""
    return Pixels.from_image(_build_image())

"""KeymapBar — custom footer with per-key colored chips.

Replaces Textual's built-in Footer (which doesn't expose per-binding CSS hooks).
Colors and label conventions are locked by `.spectacular/specs/TUI-KEYS.md`.

Layout (responsive — chips drop in/out by terminal width):

    [n] capture  [m] move  [f] finish  [p] pin  [d] drop  [b] block  …  [?] help  [q] quit

Each chip is `key` styled with its mnemonic color over a slightly darker
panel background. Description text follows in muted grey.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

# Color vocabulary — sourced from TUI-KEYS.md "Chip colors" table.
_GREY_FG = "#3A3D48"
_GREY_BG = "#16171E"
_TEXT_BG = "#0F1014"
_DESC_FG = "#8A8D9A"

# (key_label, description, fg_color)
# Width tiers: narrow (<100), medium (100-119), wide (≥120).
_CHIPS_WIDE: tuple[tuple[str, str, str], ...] = (
    ("n", "capture", "#CBA6F7"),
    ("m", "move",    "#FACC15"),
    ("f", "finish",  "#86EFAC"),
    ("p", "pin",     "#5EEAD4"),
    ("d", "drop",    "#F38BA8"),
    ("b", "block",   "#F38BA8"),
    ("CR", "open",   _GREY_FG),
    (",",  "detail", "#CBA6F7"),
    ("/",  "filter", _GREY_FG),
    ("?",  "help",   _GREY_FG),
    ("q",  "quit",   _GREY_FG),
)

_CHIPS_MEDIUM: tuple[tuple[str, str, str], ...] = (
    ("n", "capture", "#CBA6F7"),
    ("m", "move",    "#FACC15"),
    ("f", "finish",  "#86EFAC"),
    ("p", "pin",     "#5EEAD4"),
    ("d", "drop",    "#F38BA8"),
    ("b", "block",   "#F38BA8"),
    ("CR", "open",   _GREY_FG),
    ("?",  "help",   _GREY_FG),
    ("q",  "quit",   _GREY_FG),
)

_CHIPS_NARROW: tuple[tuple[str, str, str], ...] = (
    ("n", "capture", "#CBA6F7"),
    ("m", "move",    "#FACC15"),
    ("f", "finish",  "#86EFAC"),
    ("p", "pin",     "#5EEAD4"),
    ("d", "drop",    "#F38BA8"),
    ("?",  "help",   _GREY_FG),
    ("q",  "quit",   _GREY_FG),
)


def _select_chips(width: int) -> tuple[tuple[str, str, str], ...]:
    if width >= 120:
        return _CHIPS_WIDE
    if width >= 100:
        return _CHIPS_MEDIUM
    return _CHIPS_NARROW


class KeymapBar(Static):
    """Docked-bottom keymap chips. Re-renders on resize."""

    DEFAULT_CSS = ""  # styled by theme.tcss via #keymap-bar

    def __init__(self) -> None:
        super().__init__(id="keymap-bar")

    def on_resize(self, _event) -> None:
        self.refresh()

    def render(self) -> Text:
        try:
            width = self.size.width or 100
        except Exception:
            width = 100

        chips = _select_chips(width)
        out = Text()
        for i, (key, desc, color) in enumerate(chips):
            if i:
                out.append("  ", style=f"on {_TEXT_BG}")
            # key chip — bold key glyph on a dark pill
            out.append(f" {key} ", style=f"bold {color} on {_GREY_BG}")
            out.append(" ", style=f"on {_TEXT_BG}")
            out.append(desc, style=f"{_DESC_FG} on {_TEXT_BG}")
        return out

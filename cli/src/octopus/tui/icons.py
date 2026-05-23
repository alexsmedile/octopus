"""Glyph constants used across the TUI.

Plain unicode only — no emoji codepoints, no Nerd Font dependency.
Each glyph carries a single semantic meaning. See PLAN.md §Visual design language.
"""

NOW = "●"        # active bucket / in-flight task
NEXT = "○"       # on-deck
DONE = "✓"       # finished
DROPPED = "✗"    # dropped
PINNED = "⚐"     # pinned (lavender)
BLOCKED = "⏸"    # blocked / impediment
CURSOR = "▸"     # row cursor (primary color)
SESSION = "◆"    # active session marker (mint, slow pulse)
SPINNER = "⟳"    # reindex / loading
HOME = "⌂"       # activity marker in status bar

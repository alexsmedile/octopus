"""Glyph constants used across the TUI.

Plain unicode only — no emoji codepoints, no Nerd Font dependency.
Each glyph carries a single semantic meaning. See `.spectacular/specs/TUI-GLYPHS.md`
for the authoritative spec.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

# ── Status / progress glyphs ───────────────────────────────────────────

PARKED = "·"      # backlog, no work started
OPEN = "○"        # started / on-deck
HALF = "◐"        # ~50% done
MOSTLY = "◑"      # ~75% done
DONE_FULL = "●"   # done (full)
SESSION_RUN = "▶" # active session on this task
DROPPED = "✕"     # dropped
BLOCKED_BANG = "!"
WAITING = "?"
MIGRATED = "+"

# ── Legacy (kept for back-compat with existing chip code) ──────────────

NOW = "●"
NEXT = "○"
DONE = "✓"
PINNED = "*"      # was "⚐" — see spec D7 (flag glyphs)
BLOCKED = "!"     # was "⏸"
CURSOR = "▸"
SESSION = "◆"
SPINNER = "⟳"
HOME = "⌂"

# ── Flag glyphs (post-title meta) ──────────────────────────────────────

FLAG_PINNED = "*"
FLAG_PRIORITY = "!"
FLAG_REFS = ":"
FLAG_LOG = "^"
FLAG_SCHEDULED = "&"
FLAG_TAGGED = "#"


# ── Status glyph resolver ──────────────────────────────────────────────

# Precedence order (highest first), per TUI-GLYPHS.md:
#   blocked (!) > waiting (?) > session (▶) > migrated (+) >
#   done/dropped > progress ladder (by bucket + optional progress field)

def status_glyph(
    row: "sqlite3.Row | dict",
    *,
    active_session: bool = False,
    progress_stages: int = 4,
) -> str:
    """Resolve the single leading status glyph for a task row.

    Inputs:
    - row: sqlite3.Row or dict-like with keys: bucket, run_state, progress?
    - active_session: True if a session is currently running on this task
    - progress_stages: how many circle states to render in the ladder
                       (2 = · ●, 3 = · ◐ ●, 4 = · ◐ ◑ ●  [default])
    """
    def _get(key: str, default=None):
        try:
            keys = row.keys() if hasattr(row, "keys") else row
            if key in keys:
                return row[key]
        except (TypeError, KeyError, IndexError):
            pass
        return default

    bucket = (_get("bucket") or "").lower()
    run_state = (_get("run_state") or "").lower()

    # Overrides (highest precedence first)
    if run_state == "blocked":
        return BLOCKED_BANG
    if run_state == "waiting":
        return WAITING
    if active_session:
        return SESSION_RUN
    if run_state == "migrated" or _get("migrated"):
        return MIGRATED

    # Terminal states
    if bucket == "done":
        return DONE_FULL
    if bucket == "dropped":
        return DROPPED

    # Progress ladder
    progress: Optional[float] = _get("progress")
    if progress is None:
        # No explicit progress field — pick by bucket.
        if bucket == "backlog":
            return PARKED
        if bucket == "next":
            return OPEN
        if bucket == "now":
            return HALF
        return PARKED

    # Clamp + quantize progress to the requested ladder stages.
    p = max(0.0, min(1.0, float(progress)))
    if progress_stages <= 2:
        return DONE_FULL if p >= 0.5 else PARKED
    if progress_stages == 3:
        if p >= 0.75:
            return DONE_FULL
        if p >= 0.25:
            return HALF
        return PARKED
    # 4 stages (default): · ◐ ◑ ●
    if p >= 0.875:
        return DONE_FULL
    if p >= 0.625:
        return MOSTLY
    if p >= 0.25:
        return HALF
    if p > 0.0:
        return OPEN
    return PARKED


def status_glyph_color(glyph: str, bucket: str = "") -> str:
    """Color for a status glyph. Bucket carries the bucket axis;
    glyph carries the progress axis. Override glyphs ignore bucket.
    """
    if glyph == BLOCKED_BANG:
        return "#FAB387"
    if glyph == WAITING:
        return "#F5C76E"
    if glyph == SESSION_RUN:
        return "#89DCEB"
    if glyph == MIGRATED:
        return "#CBA6F7"
    if glyph == DROPPED:
        return "#8A8D9A"

    bucket = (bucket or "").lower()
    if bucket == "done":
        return "#A6E3A1"
    if bucket == "now":
        return "#F38BA8"
    if bucket == "next":
        return "#89DCEB"
    # backlog / unknown
    return "#8A8D9A"

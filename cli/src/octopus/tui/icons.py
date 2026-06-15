"""Glyph constants used across the TUI.

Plain unicode only — no emoji codepoints, no Nerd Font dependency.
Each glyph carries a single semantic meaning. See `.spectacular/specs/TUI-GLYPHS.md`
for the authoritative spec.

# Slot-1 model (the one cell at the start of every task row)

Slot 1 is a **collapsed hybrid** of bucket × progress × exception state.
Priority resolver (highest wins):

  1. Exception overrides:  !  blocked   →  ?  waiting   →  +  migrated   →  ✕  dropped
  2. Session live:         ▶  human session   (»  reserved for agent session)
  3. Progress active:      ○ → ◐ → ◑ → ●     (0% → 50% → 75% → 100%)
                            Inherits bucket color.
  4. Idle (no progress, no session) — bucket glyph:
        backlog → ·    grey dot
        next    → □    outline square
        now     → ▣    filled inner square
        done    → ●    filled green (terminal)
        dropped → ✕    grey (terminal — also covered as exception override)

Progress overrides bucket when active. Bucket glyph only appears when the
task is *idle* on that bucket (no progress field, no session, no exception).
"""

from __future__ import annotations

import sqlite3

# ── Slot 1 — Progress ladder ───────────────────────────────────────────
# Used when a task has an explicit `progress` value (0.0..1.0).
# Overrides bucket idle glyph; inherits bucket color.

OPEN = "○"        # progress ≈ 0   (started but no measurable progress)
HALF = "◐"        # progress ≈ 50%
MOSTLY = "◑"      # progress ≈ 75%
DONE_FULL = "●"   # progress = 100%  (also the idle glyph for bucket=done)

# ── Slot 1 — Bucket idle glyphs ────────────────────────────────────────
# Shown when a task has no progress and no exception state.
# `done` and `dropped` are terminal — their idle glyph IS their state.

BUCKET_BACKLOG = "·"     # grey dot — parked / no activity
BUCKET_NEXT    = "□"     # outline square — planned
BUCKET_NOW     = "▣"     # filled-inner square — current focus
BUCKET_DONE    = "●"     # filled green — done (also top of progress ladder)
BUCKET_DROPPED = "✕"     # grey — dropped

# Backwards-compat aliases (renamed but kept for callsites we haven't migrated).
PARKED = BUCKET_BACKLOG

# ── Slot 1 — Exception overrides ───────────────────────────────────────
# Highest precedence. Each has its own dedicated color.

BLOCKED_BANG = "!"        # run_state=blocked OR issue=blocked   — warn amber
WAITING      = "?"        # issue=waiting                         — mustard
MIGRATED     = "+"        # promoted_to is set                    — lavender
DROPPED      = BUCKET_DROPPED  # bucket=dropped                   — dim grey
SESSION_RUN  = "▶"        # active human session on this task     — cyan

# ── Subtask graph glyphs (D104 / D106) ────────────────────────────────
# ⎇ (U+2387) — branch/subtask indicator on parent task titles.
# Always visible on parent rows regardless of expand/collapse state.
# e.g. title renders as: "Fix auth ⎇3"

SUBTASK_BRANCH   = "⎇"   # inline parent decoration: title + ⎇N
SUBTASK_CHILD    = "├─"  # tree prefix for non-last child rows (expanded)
SUBTASK_CHILD_LAST = "└─" # tree prefix for last child row (expanded)

# ── Chrome glyphs (not status — UI affordances) ────────────────────────

CURSOR  = "▸"             # selected-row indicator on every list
SUCCESS = "✓"             # toast success prefix, terminal column header (DONE)
ERROR   = "✗"             # toast error prefix, save-failure banner
# Note: ERROR (✗ U+2717) and DROPPED (✕ U+2715) are visually similar but
# semantically distinct. ✗ = "operation failed", ✕ = "task dropped".

SPINNER = "⟳"             # TUI state row — ready / refreshing
HOME    = "⌂"             # path row prefix

# Backwards-compat: legacy NOW/NEXT/DONE constants used in chip code.
# Resolved to the canonical slot-1 glyphs above.
NOW  = BUCKET_NOW
NEXT = BUCKET_NEXT
DONE = SUCCESS            # column-header chrome, not slot-1 status

# Pin glyph — used in chip row AND preview row. Single source.
PINNED  = "*"             # was "★" in some callsites — see D7
BLOCKED = BLOCKED_BANG    # back-compat alias

# ── Header row glyphs (reserved allocations) ───────────────────────────
# Activity & repo prefixes in the header bar.
#   ◇ <activity-name>   ⬡ <repo-name>
# Filled variants reserved for future state encodings (D91).

ACTIVITY        = "◇"     # hollow diamond — activity prefix (reserved for activity)
REPO            = "⬡"     # hollow hexagon — repo prefix (reserved for git)
ACTIVITY_FILLED = "◆"     # reserved variant — DO NOT use for "session"
REPO_FILLED     = "⬢"     # reserved variant

# Agent run indicator — reserved for future autonomous-agent indicator.
# Pairs with SESSION_RUN (▶ = human). Chevron rather than ⏩ emoji.
AGENT_RUN = "»"           # reserved

# ── Slot 2 — Flag glyphs (reserved post-title meta) ────────────────────
# Defined for spec completeness. Currently only FLAG_PINNED is rendered.

FLAG_PINNED    = PINNED   # *  shipped
FLAG_PRIORITY  = "!"      # reserved (slot 2; distinct from slot 1 `!`)
FLAG_REFS      = ":"      # reserved
FLAG_LOG       = "^"      # reserved
FLAG_SCHEDULED = "&"      # reserved
FLAG_TAGGED    = "#"      # reserved


# ── Slot-1 resolver ────────────────────────────────────────────────────

def status_glyph(
    row: sqlite3.Row | dict,
    *,
    active_session: bool = False,
    progress_stages: int = 4,
) -> str:
    """Resolve the slot-1 glyph for a task row.

    Priority (highest wins):
        1. Exception overrides  (blocked / waiting / migrated / dropped)
        2. Session live          (active_session=True → ▶)
        3. Progress active       (row has non-null progress → ladder)
        4. Bucket idle           (no progress, no session, no exception)

    Inputs:
    - row: sqlite3.Row or dict-like with keys: bucket, run_state, issue?,
           progress?, promoted_to?
    - active_session: True if a session is currently running on this task
    - progress_stages: ladder granularity — 2 / 3 / 4 (default 4)
    """
    def _get(key: str, default=None):
        try:
            keys = row.keys() if hasattr(row, "keys") else row
            if key in keys:
                return row[key]
        except (TypeError, KeyError, IndexError):
            pass
        return default

    bucket    = (_get("bucket") or "").lower()
    run_state = (_get("run_state") or "").lower()
    issue     = (_get("issue") or "").lower()

    # ── 1. Exception overrides ────────────────────────────────────────
    # Blocked: `issue=blocked` (schema canonical) or legacy `run_state=blocked`.
    if issue == "blocked" or run_state == "blocked":
        return BLOCKED_BANG
    # Waiting: `issue=waiting` (schema canonical) or legacy `run_state=waiting`.
    if issue == "waiting" or run_state == "waiting":
        return WAITING
    # Migrated: `promoted_to` is set per SCHEMA-TASK.md.
    if _get("promoted_to"):
        return MIGRATED
    # Dropped is a terminal bucket — treat as override so progress doesn't
    # accidentally surface on a dropped task with a stale progress field.
    if bucket == "dropped":
        return BUCKET_DROPPED

    # ── 2. Session live ───────────────────────────────────────────────
    if active_session:
        return SESSION_RUN

    # ── 3. Progress active ────────────────────────────────────────────
    # Progress overrides bucket idle. Done bucket has its own glyph (●)
    # which happens to be the top of the ladder, so we handle that first.
    progress: float | None = _get("progress")
    if bucket == "done":
        return BUCKET_DONE

    if progress is not None:
        p = max(0.0, min(1.0, float(progress)))
        if progress_stages <= 2:
            return DONE_FULL if p >= 0.5 else OPEN
        if progress_stages == 3:
            if p >= 0.75:
                return DONE_FULL
            if p >= 0.25:
                return HALF
            return OPEN
        # 4 stages (default): ○ ◐ ◑ ●
        if p >= 0.875:
            return DONE_FULL
        if p >= 0.625:
            return MOSTLY
        if p >= 0.25:
            return HALF
        if p > 0.0:
            return OPEN
        # progress == 0 falls through to bucket-idle

    # ── 4. Bucket idle ────────────────────────────────────────────────
    if bucket == "backlog":
        return BUCKET_BACKLOG
    if bucket == "next":
        return BUCKET_NEXT
    if bucket == "now":
        return BUCKET_NOW
    # Unknown bucket — safe default
    return BUCKET_BACKLOG


def status_glyph_color(glyph: str, bucket: str = "") -> str:
    """Color for a slot-1 glyph. Bucket carries the bucket axis;
    glyph carries the progress / state axis.

    Exception override glyphs use dedicated colors; everything else
    inherits the bucket color.
    """
    # ── Exception override colors (glyph-specific, ignore bucket) ─────
    if glyph == BLOCKED_BANG:
        return "#FAB387"      # warn amber
    if glyph == WAITING:
        return "#F5C76E"      # mustard
    if glyph == SESSION_RUN:
        return "#89DCEB"      # cyan
    if glyph == MIGRATED:
        return "#CBA6F7"      # lavender
    if glyph == BUCKET_DROPPED:
        return "#8A8D9A"      # dim grey

    # ── Bucket colors (ladder + idle glyphs both use these) ───────────
    bucket = (bucket or "").lower()
    if bucket == "done":
        return "#A6E3A1"      # mint green
    if bucket == "now":
        return "#F38BA8"      # now-pink (shipped palette)
    if bucket == "next":
        return "#89DCEB"      # cyan
    # backlog / unknown
    return "#8A8D9A"          # grey

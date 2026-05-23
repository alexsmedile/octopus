"""Handoffs: deliberate context-transfer notes.

A handoff is a *deliberate package* of context for future-you or another
agent — distinct from a session (a recording of work) and from memory
(accumulated context). v1 is filesystem-only; no SQLite `handoffs` table
yet (tracked in TODO.md for v2).
"""

from octopus.handoffs.io import (
    HandoffNotFoundError,
    default_body,
    ensure_handoffs_dir,
    generate_filename,
    handoffs_dir,
    list_handoffs,
    new_handoff,
    read_handoff,
    show_handoff,
    write_handoff,
)

__all__ = [
    "HandoffNotFoundError",
    "default_body",
    "ensure_handoffs_dir",
    "generate_filename",
    "handoffs_dir",
    "list_handoffs",
    "new_handoff",
    "read_handoff",
    "show_handoff",
    "write_handoff",
]

"""Activity memory: append-only journal with 5 canonical sections.

Sections: Decisions / Open Questions / Context / Notes / State.
`## Notes` is the default `memory append` target. `## State` is append-only
but the latest entry is treated as "current state" by readers.
"""

from octopus.memory.io import (
    DEFAULT_SECTION,
    MARKER,
    MemoryNotFoundError,
    append_entry,
    memory_path,
    read_memory,
    scaffold_text,
    section_entries,
    set_summary,
    show_default,
    write_memory,
)
from octopus.memory.sections import (
    CANONICAL_SECTIONS,
    AmbiguousSectionError,
    UnknownSectionError,
    resolve_section,
)

__all__ = [
    "AmbiguousSectionError",
    "CANONICAL_SECTIONS",
    "DEFAULT_SECTION",
    "MARKER",
    "MemoryNotFoundError",
    "UnknownSectionError",
    "append_entry",
    "memory_path",
    "read_memory",
    "resolve_section",
    "scaffold_text",
    "section_entries",
    "set_summary",
    "show_default",
    "write_memory",
]

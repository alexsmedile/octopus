"""memory.md two-zone read/write.

Above the `<!-- octopus-managed-below -->` marker is user-curated and never
touched by the CLI (except `last_updated` and `summary` in the frontmatter,
via explicit verbs). Below the marker is machine-managed: canonical sections
each containing `### YYYY-MM-DD HH:MM\\n<text>` blocks, appended chronologically.

Critical invariants:
  - The marker is preserved on every write. If missing on append, it is
    re-inserted before the first canonical heading with a stderr warning.
  - Entries are never reformatted or reordered.
  - User-added sections (not in CANONICAL_SECTIONS) are preserved as-is.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import frontmatter

from octopus.core.models import Memory
from octopus.memory.sections import CANONICAL_SECTIONS, resolve_section

MARKER = "<!-- octopus-managed-below -->"
DEFAULT_SECTION = "Notes"
TIMESTAMP_FMT = "%Y-%m-%d %H:%M"  # Minute precision per SCHEMA-MEMORY.md.

MEMORY_FIELDS = {"activity", "last_updated", "summary", "tags"}

# Regex for an entry header line: `### YYYY-MM-DD HH:MM`.
_ENTRY_HEADER_RE = re.compile(r"^### \d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?\s*$")
_SECTION_HEADER_RE = re.compile(r"^## (?P<name>.+?)\s*$")


class MemoryNotFoundError(FileNotFoundError):
    """Raised when memory.md is absent and the caller didn't opt into scaffolding."""


# ── Path ─────────────────────────────────────────────────────────────


def memory_path(activity_root: Path) -> Path:
    return activity_root / ".octopus" / "memory.md"


# ── Frontmatter helpers ──────────────────────────────────────────────


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"cannot coerce {value!r} to date")


def read_memory(path: Path) -> tuple[Memory, str]:
    """Read memory.md. Returns (Memory, full body)."""
    if not path.is_file():
        raise MemoryNotFoundError(path)
    post = frontmatter.load(path)
    data = post.metadata
    extra = {k: v for k, v in data.items() if k not in MEMORY_FIELDS}
    memory = Memory(
        activity=str(data.get("activity", "")),
        last_updated=_coerce_date(data.get("last_updated")) or date.today(),
        summary=data.get("summary"),
        tags=list(data.get("tags") or []),
        path=path,
        extra=extra,
    )
    return memory, post.content


def write_memory(path: Path, memory: Memory, body: str) -> None:
    data: dict[str, Any] = {
        "activity": memory.activity,
        "last_updated": memory.last_updated.isoformat(),
    }
    if memory.summary is not None:
        data["summary"] = memory.summary
    if memory.tags:
        data["tags"] = memory.tags
    for k, v in memory.extra.items():
        if k not in data:
            data[k] = v
    post = frontmatter.Post(body, **data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


# ── Scaffold ─────────────────────────────────────────────────────────


def scaffold_text(activity_id: str, title: str | None = None) -> str:
    """Render the body of a fresh memory.md (no canonical headings yet — lazy)."""
    heading = f"# Memory: {title}" if title else "# Memory"
    return f"\n{heading}\n\n{MARKER}\n"


def _scaffold(path: Path, activity_id: str, title: str | None) -> tuple[Memory, str]:
    memory = Memory(activity=activity_id, last_updated=date.today())
    body = scaffold_text(activity_id, title)
    write_memory(path, memory, body)
    return memory, body


# ── Two-zone split ───────────────────────────────────────────────────


def _split_on_marker(body: str) -> tuple[str, str, bool]:
    """Split body at the marker. Returns (above, below, marker_present)."""
    idx = body.find(MARKER)
    if idx == -1:
        return body, "", False
    above = body[:idx]
    below = body[idx + len(MARKER):]
    # Leading newline on `below` is part of the marker line break; preserve.
    return above, below, True


def _reinsert_marker(body: str) -> str:
    """Re-insert marker before the first canonical heading (or at end)."""
    lines = body.splitlines(keepends=True)
    insert_at = len(lines)
    for i, line in enumerate(lines):
        m = _SECTION_HEADER_RE.match(line.rstrip("\n"))
        if m and m.group("name").strip() in CANONICAL_SECTIONS:
            insert_at = i
            break
    new_lines = lines[:insert_at] + [f"{MARKER}\n", "\n"] + lines[insert_at:]
    return "".join(new_lines)


# ── Section operations on `below` ────────────────────────────────────


def _parse_sections(below: str) -> list[tuple[str, str]]:
    """Return [(heading_name, raw_block_including_heading), ...] in file order."""
    if not below.strip():
        return []
    # Split on lines starting with `## `; first chunk may be pre-heading whitespace.
    sections: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for line in below.splitlines(keepends=True):
        m = _SECTION_HEADER_RE.match(line.rstrip("\n"))
        if m:
            if current_name is not None:
                sections.append((current_name, "".join(current_lines)))
            current_name = m.group("name").strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_name is not None:
        sections.append((current_name, "".join(current_lines)))
    return sections


def _section_body(block: str) -> str:
    """Strip the leading `## Heading\\n` from a section block."""
    lines = block.splitlines(keepends=True)
    return "".join(lines[1:]) if lines else ""


def section_entries(below: str, section: str) -> list[tuple[str, str]]:
    """Return [(header_line, body_text), ...] for entries in `## <section>`.

    `header_line` is the `### YYYY-MM-DD HH:MM[:SS]` text (no leading hashes).
    `body_text` is everything below the header until the next `### ` or end.
    """
    for name, block in _parse_sections(below):
        if name == section:
            return _parse_entries(_section_body(block))
    return []


def _parse_entries(section_body: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    current_header: str | None = None
    current_body: list[str] = []
    for line in section_body.splitlines(keepends=True):
        if _ENTRY_HEADER_RE.match(line.rstrip("\n")):
            if current_header is not None:
                entries.append((current_header, "".join(current_body).rstrip("\n")))
            current_header = line.rstrip("\n").lstrip("# ").strip()
            current_body = []
        else:
            if current_header is not None:
                current_body.append(line)
    if current_header is not None:
        entries.append((current_header, "".join(current_body).rstrip("\n")))
    return entries


def _render_sections(sections: list[tuple[str, str]]) -> str:
    """Reassemble parsed sections into a body string."""
    return "".join(block for _, block in sections)


# ── Append ───────────────────────────────────────────────────────────


def append_entry(
    activity_root: Path,
    activity_id: str,
    note: str,
    *,
    section: str = DEFAULT_SECTION,
    when: datetime | None = None,
    activity_title: str | None = None,
) -> tuple[Memory, str]:
    """Append `### <timestamp>\\n<note>` to the named section.

    - Creates `memory.md` from scaffold if absent.
    - Re-inserts the marker if a user has deleted it (with a stderr warning).
    - Creates the section heading lazily on first write.
    - Returns (Memory, canonical_section_name).
    """
    if not note or not note.strip():
        raise ValueError("note must be non-empty")
    canon = resolve_section(section)
    when = when or datetime.now()
    stamp = when.strftime(TIMESTAMP_FMT)

    path = memory_path(activity_root)
    if not path.is_file():
        _scaffold(path, activity_id, activity_title or activity_root.name)

    memory, body = read_memory(path)
    above, below, marker_ok = _split_on_marker(body)
    if not marker_ok:
        print(
            "warning: memory.md marker missing — re-inserting "
            f"`{MARKER}` before next append",
            file=sys.stderr,
        )
        body = _reinsert_marker(body)
        above, below, marker_ok = _split_on_marker(body)

    sections = _parse_sections(below)
    section_names = [n for n, _ in sections]

    entry_block = f"\n### {stamp}\n{note.rstrip()}\n"

    if canon in section_names:
        # Append to existing section.
        new_sections: list[tuple[str, str]] = []
        for name, block in sections:
            if name == canon:
                block = block.rstrip("\n") + "\n" + entry_block
            new_sections.append((name, block))
        new_below = _render_sections(new_sections)
    else:
        # Create section in canonical position (relative to existing canonical sections).
        new_block = f"\n## {canon}\n{entry_block}"
        new_sections = list(sections)
        new_sections = _insert_section_in_canonical_order(new_sections, canon, new_block)
        new_below = _render_sections(new_sections)

    new_body = above + MARKER + new_below
    # Normalize: ensure exactly one newline after marker if below isn't empty.
    if new_below and not new_below.startswith("\n"):
        new_body = above + MARKER + "\n" + new_below

    memory.last_updated = when.date()
    write_memory(path, memory, new_body)
    return memory, canon


def _insert_section_in_canonical_order(
    sections: list[tuple[str, str]],
    new_name: str,
    new_block: str,
) -> list[tuple[str, str]]:
    """Insert `new_block` into `sections` respecting CANONICAL_SECTIONS order.

    Non-canonical user sections keep their relative position.
    """
    new_canonical_pos = CANONICAL_SECTIONS.index(new_name)
    result: list[tuple[str, str]] = []
    inserted = False
    for name, block in sections:
        if not inserted and name in CANONICAL_SECTIONS:
            existing_pos = CANONICAL_SECTIONS.index(name)
            if new_canonical_pos < existing_pos:
                result.append((new_name, new_block))
                inserted = True
        result.append((name, block))
    if not inserted:
        result.append((new_name, new_block))
    return result


# ── Summary ──────────────────────────────────────────────────────────


def set_summary(
    activity_root: Path,
    activity_id: str,
    text: str,
    *,
    activity_title: str | None = None,
) -> Memory:
    """Set the frontmatter `summary:` field. Creates memory.md if absent."""
    path = memory_path(activity_root)
    if not path.is_file():
        _scaffold(path, activity_id, activity_title or activity_root.name)
    memory, body = read_memory(path)
    memory.summary = text
    memory.last_updated = date.today()
    write_memory(path, memory, body)
    return memory


# ── Show ─────────────────────────────────────────────────────────────


PREVIEW_LIMIT = 3
PREVIEW_SECTIONS: tuple[str, ...] = ("State", "Open Questions", "Decisions")


def show_default(activity_root: Path) -> str:
    """Render the default `memory show` output.

    Format:
      Memory: <title>
      summary: <text>     (if set)

      ## State (showing latest 3 of N)
      ### timestamp
      body
      ...
      [N-3 more — run `octopus memory show --section state` for all]

      ## Open Questions (showing latest 3 of N)
      ...

      ## Decisions (showing latest 3 of N)
      ...
    """
    path = memory_path(activity_root)
    if not path.is_file():
        return "no memory.md — run `octopus memory append \"<note>\"` to create one."
    memory, body = read_memory(path)
    above, below, _ = _split_on_marker(body)

    lines: list[str] = []
    # Header
    first_heading = _first_heading(above) or "Memory"
    lines.append(first_heading.lstrip("# ").strip())
    if memory.summary:
        lines.append("")
        lines.append(f"summary: {memory.summary}")

    for section in PREVIEW_SECTIONS:
        entries = section_entries(below, section)
        if not entries:
            continue
        n = len(entries)
        shown = min(PREVIEW_LIMIT, n)
        lines.append("")
        lines.append(f"## {section} (showing latest {shown} of {n})")
        for hdr, txt in entries[-PREVIEW_LIMIT:]:
            lines.append("")
            lines.append(f"### {hdr}")
            if txt.strip():
                lines.append(txt)
        if n > PREVIEW_LIMIT:
            section_arg = section.split()[0].lower()  # "Open Questions" → "open"
            lines.append("")
            lines.append(
                f"[{n - PREVIEW_LIMIT} more — "
                f"run `octopus memory show --section {section_arg}` for all]"
            )

    return "\n".join(lines) + "\n"


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line
    return None

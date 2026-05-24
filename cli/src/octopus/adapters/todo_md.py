"""TODO.md adapter — pull-only import of checkbox lines from a markdown file.

The simplest possible adapter:
- Single file source (no API, no auth, no network).
- No groups concept (one file = one source).
- Reads `- [ ]` checkbox lines at activity root.
- Stable external_ids via title slug (survives line-number drift).

Config (in `~/.config/octopus/bridges/todo-md.toml`):
    path = "TODO.md"           # relative to activity root, or absolute
    include_checked = false    # if true, [x] lines also import (as done)
    section_filter = []        # empty = all sections; slugs = filter to these

See SCHEMA-ADAPTER.md for the protocol contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from octopus.adapters.base import (
    AdapterStatus,
    Capability,
    ExternalTask,
    PullResult,
    PushResult,
)
from octopus.adapters.journal import read_journal
from octopus.config import load_adapter_config
from octopus.fs.discover import find_activity_root


# ── parsing primitives (pure functions, testable in isolation) ────────


@dataclass(frozen=True)
class CheckboxLine:
    """One parsed checkbox row from a TODO.md."""

    state: str        # one of: "unchecked", "checked", "in-progress"
    text: str         # the body of the line, after the checkbox
    section: str | None = None  # slug of the most recent heading, if any


# Match `- [ ] text`, `- [x] text`, `- [X] text`, `- [-] text`, `- [/] text`.
# Anything else inside the brackets is treated as unchecked (forgiving).
CHECKBOX_RE = re.compile(r"^\s*[-*+]\s*\[(.)\]\s+(.+?)\s*$")

# Recognized prefixes → (kind_or_None, skip_flag)
PREFIX_MAP: dict[str, tuple[str | None, bool]] = {
    "TODO": (None, False),
    "FIXME": (None, False),
    "BUG": ("bug", False),
    "HACK": ("chore", False),
    "NOTE": (None, True),     # notes are not tasks
}
PREFIX_RE = re.compile(r"^([A-Z]+)\s*:\s*(.+)$")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _slugify_heading(text: str) -> str:
    """Cheap heading slug: lowercase, alphanumerics + hyphens.

    `## Backlog` → `backlog`. `## To Do` → `to-do`. `## v0.4 Release` → `v0-4-release`.
    """
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _parse_checkbox(line: str) -> CheckboxLine | None:
    """Return a CheckboxLine or None if `line` isn't a checkbox row."""
    m = CHECKBOX_RE.match(line)
    if not m:
        return None
    marker, text = m.group(1), m.group(2)
    if marker == " ":
        state = "unchecked"
    elif marker in ("x", "X"):
        state = "checked"
    elif marker in ("-", "/"):
        state = "in-progress"
    else:
        # Unknown marker — treat as unchecked (forgiving v1 behavior).
        state = "unchecked"
    return CheckboxLine(state=state, text=text)


def _extract_title_meta(text: str) -> tuple[str, str | None, bool]:
    """Strip recognized leading prefixes and map them to kind metadata.

    Returns (cleaned_title, kind_or_None, skip_flag).
    Unknown prefixes (e.g. `XYZ:`) are kept verbatim — no false positives.
    """
    m = PREFIX_RE.match(text)
    if not m:
        return text, None, False
    prefix, rest = m.group(1), m.group(2)
    if prefix not in PREFIX_MAP:
        return text, None, False
    kind, skip = PREFIX_MAP[prefix]
    return rest, kind, skip


def _parse_todo_md(
    content: str,
    *,
    section_filter: list[str] | None = None,
    include_checked: bool = False,
    source_path: str = "TODO.md",
) -> list[ExternalTask]:
    """Walk the file line by line; return a list of ExternalTask.

    Sections are tracked via heading slug. Section-filter applies after parsing.
    Title prefix stripping + kind mapping happens here.
    """
    tasks: list[ExternalTask] = []
    seen_slugs: set[str] = set()
    current_section: str | None = None
    filter_set = set(section_filter) if section_filter else None

    for line in content.splitlines():
        # Heading update
        hm = HEADING_RE.match(line)
        if hm:
            current_section = _slugify_heading(hm.group(2))
            continue

        cb = _parse_checkbox(line)
        if cb is None:
            continue

        # Section filter
        if filter_set is not None and current_section not in filter_set:
            continue

        # State filter
        if cb.state == "checked" and not include_checked:
            continue

        # Title + kind extraction
        title, kind, skip = _extract_title_meta(cb.text)
        if skip:
            continue
        if not title:
            continue

        # external_id via slug (Q6) — collision counter if needed
        base = _slugify_heading(title) or "item"
        slug = base
        counter = 2
        while slug in seen_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        seen_slugs.add(slug)

        external_id = f"{source_path}#{slug}"

        # Map state to bucket
        if cb.state == "checked":
            bucket = "done"
        elif cb.state == "in-progress":
            bucket = "now"
        else:
            bucket = "backlog"

        tasks.append(
            ExternalTask(
                external_id=external_id,
                title=title,
                suggested_bucket=bucket,
                suggested_kind=kind,
                source_group=current_section,
            )
        )

    return tasks


# ── adapter class ─────────────────────────────────────────────────────


class TodoMdAdapter:
    """Pull-only adapter: imports checkbox lines from a TODO.md file.

    No groups concept — TODO.md is a single file. `list_groups()` returns [].
    """

    name = "todo-md"
    capabilities: set[Capability] = {Capability.PULL}

    def status(self) -> AdapterStatus:
        journal = read_journal(self.name)
        return AdapterStatus(
            name=self.name,
            healthy=True,
            last_pull=journal.last_pull,
            last_push=journal.last_push,
            capabilities=self.capabilities,
        )

    def validate_config(self, data: dict) -> list[str]:
        """Validate `path`, `include_checked`, `section_filter` shape."""
        errors: list[str] = []
        path = data.get("path", "TODO.md")
        if not isinstance(path, str) or not path.strip():
            errors.append("`path` must be a non-empty string")
        ic = data.get("include_checked", False)
        if not isinstance(ic, bool):
            errors.append("`include_checked` must be a boolean")
        sf = data.get("section_filter", [])
        if not isinstance(sf, list):
            errors.append("`section_filter` must be a list of heading slugs")
        elif not all(isinstance(s, str) for s in sf):
            errors.append("`section_filter` entries must be strings")
        return errors

    def list_groups(self) -> list[str]:
        # TODO.md is a single-file source. No groups concept.
        return []

    def peek(self, groups: list[str] | None = None) -> PullResult:
        """Read the configured TODO.md and parse it. No side effects."""
        return self._read_and_parse(groups)

    def pull(self, groups: list[str] | None = None) -> PullResult:
        """Same as peek — the framework's pipeline does the materialization."""
        return self._read_and_parse(groups)

    def search(self, query: str, groups: list[str] | None = None) -> PullResult:
        """No native search API — peek + Python filter on title substring."""
        result = self._read_and_parse(groups)
        if not query:
            return result
        q = query.lower()
        result.tasks = [t for t in result.tasks if q in t.title.lower()]
        return result

    def push(self, task) -> PushResult:
        return PushResult(error="todo-md is pull-only")

    # ── internals ─────────────────────────────────────────────────────

    def _read_and_parse(self, groups: list[str] | None) -> PullResult:
        cfg = load_adapter_config(self.name)
        cfg_path = cfg.get("path", "TODO.md")
        include_checked = bool(cfg.get("include_checked", False))

        # Section filter: caller-provided `groups` overrides config; both
        # may also be empty (= no filter).
        section_filter: list[str] | None = None
        if groups:
            section_filter = [_slugify_heading(g) for g in groups]
        elif cfg.get("section_filter"):
            section_filter = list(cfg["section_filter"])

        # Resolve TODO.md path: relative is interpreted from activity root,
        # absolute is taken verbatim.
        path = Path(cfg_path)
        if not path.is_absolute():
            root = find_activity_root(Path.cwd())
            if root is None:
                return PullResult(errors=["not inside an activity; cannot resolve TODO.md path"])
            path = root / cfg_path

        if not path.is_file():
            return PullResult(
                errors=[],
                tasks=[],
                skipped=[(str(path), "no TODO.md found")],
            )

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            return PullResult(errors=[f"failed to read {path}: {exc}"])

        # Use the relative form in external_id when possible (more portable).
        display_path = cfg_path

        tasks = _parse_todo_md(
            content,
            section_filter=section_filter,
            include_checked=include_checked,
            source_path=display_path,
        )

        return PullResult(tasks=tasks)

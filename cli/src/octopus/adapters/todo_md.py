"""TODO.md adapter — pull + source-annotation + limited mutation verbs.

Format (D72): GFM checklist + Obsidian Tasks emoji conventions + the
Octopus `→ <provider>:<slug>` arrow (D73). Zero invention beyond the arrow.

Behavior (D74): on successful pull, the adapter rewrites `- [ ]` lines to
`- [x] → octopus:<task-slug>` in the source file. Items with an arrow are
skipped on re-pull — they're someone else's responsibility now.

Mutation verbs (D75): `add`, `mark_complete`, `mark_open` for editing
TODO.md without ever importing into the task tree.

Config (`~/.config/octopus/bridges/todo-md.toml`):
    path = "TODO.md"           # relative to activity root, or absolute
    include_checked = false    # if true, [x] lines without arrow import as done
    section_filter = []        # empty = all sections; slugs = filter to these
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
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
class InlineMetadata:
    """Parsed Obsidian Tasks emoji + tags + Octopus arrow from a line body."""

    title: str                      # cleaned title with all metadata stripped
    priority: str | None = None     # urgent | low | None
    due: date | None = None
    scheduled: date | None = None
    start_date: date | None = None
    tags: tuple[str, ...] = ()
    arrow_target: str | None = None  # full "provider:slug" if an arrow is present
    has_arrow: bool = False          # convenience flag


@dataclass(frozen=True)
class CheckboxLine:
    """One parsed checkbox row from a TODO.md, after full metadata extraction."""

    state: str                      # "unchecked" | "checked" | "in-progress" | "cancelled"
    metadata: InlineMetadata
    raw_line: str                   # original line, useful for in-place rewrite


# Match `- [X] text` for any single char X. Anything else inside the brackets
# is recognized — the state map below decides what each means.
CHECKBOX_RE = re.compile(r"^(\s*)([-*+])\s+\[(.)\]\s+(.*?)\s*$")

# D72 state map. Each GFM/Obsidian Tasks marker maps to one of our four states.
STATE_MARKERS: dict[str, str] = {
    " ": "unchecked",
    "x": "checked",
    "X": "checked",
    "/": "in-progress",
    "-": "in-progress",
    "!": "cancelled",       # Obsidian Tasks "cancelled" — skipped on import
    # "?" intentionally falls through to "unchecked" — forgiving treatment
}


# Carry-over from #21 (D72 keeps these). Prefix → (kind, skip).
PREFIX_MAP: dict[str, tuple[str | None, bool]] = {
    "TODO": (None, False),
    "FIXME": (None, False),
    "BUG": ("bug", False),
    "HACK": ("chore", False),
    "NOTE": (None, True),
}
PREFIX_RE = re.compile(r"^([A-Z]+)\s*:\s*(.+)$")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# D72 emoji map. Each emoji captures one piece of inline metadata.
# Date emojis are followed by a YYYY-MM-DD; priority emojis are bare.
PRIORITY_EMOJI: dict[str, str | None] = {
    "🔺": "urgent",
    "⏫": "urgent",
    "🔼": None,        # Octopus has no medium — drop to default
    "🔽": "low",
    "⏬": "low",
}
DATE_EMOJI_FIELDS: dict[str, str] = {
    "📅": "due",
    "⏳": "scheduled",
    "🛫": "start_date",
}
# Emoji that we recognize and drop (informational; not surfaced as Octopus fields v1)
NOOP_EMOJI = {"➕", "✅", "❌", "🔁"}

# Combined regex of all known emoji — used to strip metadata cleanly.
ALL_EMOJI = (
    set(PRIORITY_EMOJI.keys())
    | set(DATE_EMOJI_FIELDS.keys())
    | NOOP_EMOJI
)
ANY_EMOJI_RE = re.compile("|".join(re.escape(e) for e in ALL_EMOJI))

# Date emojis with their date: e.g. `📅 2026-05-30` or `📅2026-05-30`
DATE_EMOJI_PAIR_RE = re.compile(
    r"(" + "|".join(re.escape(e) for e in DATE_EMOJI_FIELDS) + r")\s*(\d{4}-\d{2}-\d{2})"
)

# Date-only emojis we just strip (no field captured)
NOOP_DATE_PAIR_RE = re.compile(
    r"(" + "|".join(re.escape(e) for e in (NOOP_EMOJI - {"🔁"})) + r")\s*(\d{4}-\d{2}-\d{2})?"
)
# Recurrence is `🔁 every week` etc. — strip greedily up to next emoji/arrow/end.
RECURRENCE_RE = re.compile(r"🔁\s*[^🔺⏫🔼🔽⏬📅⏳🛫➕✅❌→#\n]*")

# `→ provider:slug` — slug allows alnum + hyphen + colon (for nested IDs like github:owner/repo#42)
ARROW_RE = re.compile(r"→\s*([a-z][a-z0-9_-]*)\s*:\s*(\S+)")

# Hashtag — alnum + hyphen + underscore. Stops at whitespace.
TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9][\w-]*)")


def _slugify_heading(text: str) -> str:
    """Cheap heading slug: lowercase, alphanumerics + hyphens."""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _parse_inline_metadata(text: str) -> InlineMetadata:
    """Extract priority, dates, tags, and `→ arrow` from a line body.

    Returns the cleaned title (with metadata removed) plus all captured fields.
    Order of operations matters — extract structured stuff first, then strip
    bare emoji, then trim.
    """
    priority: str | None = None
    due: date | None = None
    scheduled: date | None = None
    start_date: date | None = None
    arrow_target: str | None = None
    has_arrow = False

    # 1. Arrow first — it's at the end of the line by convention.
    am = ARROW_RE.search(text)
    if am:
        has_arrow = True
        provider, identifier = am.group(1), am.group(2)
        arrow_target = f"{provider}:{identifier}"
        text = text[: am.start()] + text[am.end() :]

    # 2. Date-emoji pairs: extract values, strip pair from text.
    def _date_repl(m: re.Match[str]) -> str:
        nonlocal due, scheduled, start_date
        emoji = m.group(1)
        date_str = m.group(2)
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            return ""
        field = DATE_EMOJI_FIELDS[emoji]
        if field == "due":
            due = d
        elif field == "scheduled":
            scheduled = d
        elif field == "start_date":
            start_date = d
        return ""

    text = DATE_EMOJI_PAIR_RE.sub(_date_repl, text)

    # 3. Drop no-op date emojis (created/completed/cancelled with their dates).
    text = NOOP_DATE_PAIR_RE.sub("", text)

    # 4. Recurrence rules — strip but don't capture (v1).
    text = RECURRENCE_RE.sub("", text)

    # 5. Tags — collect, but keep them in the title (markdown viewers render them).
    #    Actually no — strip them too, surface as `tags` on the ExternalTask. The
    #    user can re-add a tag if they want it in the title.
    tags = tuple(m.group(1) for m in TAG_RE.finditer(text))
    text = TAG_RE.sub("", text)

    # 6. Priority emoji — bare, no companion. Last one wins if multiple.
    for emoji in PRIORITY_EMOJI:
        if emoji in text:
            priority = PRIORITY_EMOJI[emoji]
            text = text.replace(emoji, "")

    # 7. Strip any leftover known emoji.
    text = ANY_EMOJI_RE.sub("", text)

    # 8. Collapse runs of whitespace into single spaces.
    title = re.sub(r"\s+", " ", text).strip()

    return InlineMetadata(
        title=title,
        priority=priority,
        due=due,
        scheduled=scheduled,
        start_date=start_date,
        tags=tags,
        arrow_target=arrow_target,
        has_arrow=has_arrow,
    )


def _parse_checkbox(line: str) -> CheckboxLine | None:
    """Return a CheckboxLine or None if `line` isn't a checkbox row."""
    m = CHECKBOX_RE.match(line)
    if not m:
        return None
    marker = m.group(3)
    body = m.group(4)
    state = STATE_MARKERS.get(marker, "unchecked")
    metadata = _parse_inline_metadata(body)
    return CheckboxLine(state=state, metadata=metadata, raw_line=line)


def _extract_title_meta(text: str) -> tuple[str, str | None, bool]:
    """Strip recognized BUG:/HACK:/etc. prefixes (carry-over from #21).

    Returns (cleaned_title, kind_or_None, skip_flag).
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
    """Walk the file line by line; return a list of importable ExternalTasks.

    D73: items with `→` arrows are skipped — they're already handed off.
    D72: state markers + emoji metadata flow into the ExternalTask fields.
    """
    tasks: list[ExternalTask] = []
    seen_slugs: set[str] = set()
    current_section: str | None = None
    filter_set = set(section_filter) if section_filter else None

    for line in content.splitlines():
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

        # D73: items with `→` arrows are excluded from import (already handed off).
        if cb.metadata.has_arrow:
            continue

        # D72: cancelled items are explicitly skipped.
        if cb.state == "cancelled":
            continue

        # State filter — checked items skipped unless include_checked.
        if cb.state == "checked" and not include_checked:
            continue

        # Carry-over: BUG:/HACK:/etc. prefixes.
        title, kind, skip = _extract_title_meta(cb.metadata.title)
        if skip:
            continue
        if not title:
            continue

        # external_id via slug — collision counter if needed
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
                suggested_tags=list(cb.metadata.tags),
                suggested_priority=cb.metadata.priority,
                suggested_due=cb.metadata.due,
                source_group=current_section,
            )
        )

    return tasks


# ── source rewrite (D74 — mark_pulled) ────────────────────────────────


def _annotate_pulled_line(line: str, task_slug: str) -> str:
    """Rewrite a `- [ ] ...` line to `- [x] ... → octopus:<slug>`.

    Preserves indentation, bullet char, original body + inline metadata.
    """
    m = CHECKBOX_RE.match(line)
    if not m:
        return line  # not a checkbox line, leave alone
    indent, bullet, marker, body = m.group(1), m.group(2), m.group(3), m.group(4)
    # Drop any pre-existing arrow (idempotent in case mark_pulled runs twice).
    body = ARROW_RE.sub("", body).rstrip()
    new_body = f"{body} → octopus:{task_slug}".strip()
    return f"{indent}{bullet} [x] {new_body}"


# ── adapter class ─────────────────────────────────────────────────────


class TodoMdAdapter:
    """Pull + source-annotation adapter for TODO.md files."""

    name = "todo-md"
    capabilities: set[Capability] = {Capability.PULL, Capability.MARK_PULLED}

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
        return []

    def peek(self, groups: list[str] | None = None) -> PullResult:
        return self._read_and_parse(groups)

    def pull(self, groups: list[str] | None = None) -> PullResult:
        return self._read_and_parse(groups)

    def search(self, query: str, groups: list[str] | None = None) -> PullResult:
        result = self._read_and_parse(groups)
        if not query:
            return result
        q = query.lower()
        result.tasks = [t for t in result.tasks if q in t.title.lower()]
        return result

    def push(self, task) -> PushResult:
        return PushResult(error="todo-md is pull-only")

    # ── D74: mark_pulled — rewrite source after successful pull ───────

    def mark_pulled(self, mapping: dict[str, str]) -> None:
        """Rewrite TODO.md in-place, annotating successfully-imported lines.

        Args:
            mapping: {external_id → octopus_task_slug}. The adapter looks up
                     each parsed checkbox by its computed external_id and
                     rewrites the line if there's a mapping for it.
        """
        if not mapping:
            return
        path = self._resolve_path()
        if path is None or not path.is_file():
            return

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return

        cfg = load_adapter_config(self.name)
        source_path = cfg.get("path", "TODO.md")

        # Rebuild line-by-line, applying the same external_id computation as
        # _parse_todo_md so we can match.
        new_lines: list[str] = []
        seen_slugs: set[str] = set()
        for line in content.splitlines(keepends=False):
            new_lines.append(self._maybe_annotate_line(
                line, mapping=mapping, seen_slugs=seen_slugs, source_path=source_path,
            ))

        # Preserve trailing newline if the source had one.
        trailing = "\n" if content.endswith("\n") else ""
        path.write_text("\n".join(new_lines) + trailing, encoding="utf-8")

    def _maybe_annotate_line(
        self,
        line: str,
        *,
        mapping: dict[str, str],
        seen_slugs: set[str],
        source_path: str,
    ) -> str:
        """Annotate one line if its external_id appears in the mapping."""
        cb = _parse_checkbox(line)
        if cb is None:
            return line
        if cb.metadata.has_arrow:
            return line  # already annotated
        if cb.state in ("cancelled",):
            return line

        # Apply the same title-cleaning logic as the parser (BUG: prefix etc.)
        title, _kind, skip = _extract_title_meta(cb.metadata.title)
        if skip or not title:
            return line

        # Compute the same external_id the parser would compute.
        base = _slugify_heading(title) or "item"
        slug = base
        counter = 2
        while slug in seen_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        seen_slugs.add(slug)
        external_id = f"{source_path}#{slug}"

        task_slug = mapping.get(external_id)
        if not task_slug:
            return line

        return _annotate_pulled_line(line, task_slug)

    # ── D75: limited mutation verbs ───────────────────────────────────

    def add_item(
        self,
        title: str,
        *,
        section: str | None = None,
        priority: str | None = None,
        due: str | None = None,
        tags: list[str] | None = None,
        state: str = "open",
    ) -> str:
        """Append a new checkbox to TODO.md under the chosen section.

        Returns a human-readable description of where it landed.

        Args:
            title: the task text.
            section: heading slug to append under. Defaults to the first
                section in `section_filter` config, or the file root.
            priority: "urgent" | "low" | None — encoded with Obsidian emoji.
            due: ISO date string — encoded as `📅 YYYY-MM-DD`.
            tags: list of bare tag names (no `#` prefix).
            state: "open" | "in-progress" → marker `[ ]` or `[/]`.
        """
        path = self._resolve_path()
        if path is None:
            raise FileNotFoundError("not inside an activity or no TODO.md path configured")

        # Build the new line with Obsidian Tasks emoji + tags.
        parts = [title.strip()]
        if priority == "urgent":
            parts.append("⏫")
        elif priority == "low":
            parts.append("🔽")
        if due:
            # Validate by parsing — raises ValueError on bad input, caller surfaces.
            date.fromisoformat(due)
            parts.append(f"📅 {due}")
        for t in tags or []:
            parts.append(f"#{t.lstrip('#')}")
        marker = "/" if state == "in-progress" else " "
        new_line = f"- [{marker}] {' '.join(parts)}"

        # Read existing content (create file if missing).
        content = path.read_text(encoding="utf-8") if path.is_file() else ""

        if section is None:
            # Pull from config: first section_filter entry.
            cfg = load_adapter_config(self.name)
            sf = cfg.get("section_filter") or []
            section = sf[0] if sf else None

        new_content, where = _insert_under_section(content, section, new_line)
        path.write_text(new_content + ("" if new_content.endswith("\n") else "\n"), encoding="utf-8")
        return f"added to {path} ({where})"

    def mark_complete(self, match: str, *, first: bool = False) -> str:
        """Toggle a `- [ ]` line to `- [x]` in place. Returns description."""
        return self._toggle_state(match, target_state="checked", first=first)

    def mark_open(self, match: str, *, first: bool = False) -> str:
        """Toggle a `- [x]` line back to `- [ ]`, stripping any arrow."""
        return self._toggle_state(match, target_state="unchecked", first=first)

    def _toggle_state(self, match: str, *, target_state: str, first: bool) -> str:
        path = self._resolve_path()
        if path is None or not path.is_file():
            raise FileNotFoundError("no TODO.md to edit")

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        q = match.lower().strip()
        matches: list[int] = []
        for i, line in enumerate(lines):
            cb = _parse_checkbox(line)
            if cb is None:
                continue
            # When marking complete we want OPEN items; when marking open we want CHECKED ones.
            if target_state == "checked" and cb.state == "checked":
                continue
            if target_state == "unchecked" and cb.state != "checked":
                continue
            if q in cb.metadata.title.lower():
                matches.append(i)

        if not matches:
            raise ValueError(f"no matching {('open' if target_state=='checked' else 'checked')} item for {match!r}")
        if len(matches) > 1 and not first:
            preview = "; ".join(lines[i].strip()[:60] for i in matches[:5])
            raise ValueError(
                f"{len(matches)} matches for {match!r}: {preview}. "
                "Pass --first to act on the top hit."
            )

        target_idx = matches[0]
        # Capture the pre-flip title for a cleaner confirmation message.
        cb_before = _parse_checkbox(lines[target_idx])
        title = cb_before.metadata.title if cb_before else lines[target_idx].strip()
        lines[target_idx] = _flip_marker(lines[target_idx], target_state)
        path.write_text("\n".join(lines) + ("\n" if content.endswith("\n") else ""), encoding="utf-8")
        verb = "completed" if target_state == "checked" else "reopened"
        return f"{verb}: {title}"

    # ── internals ─────────────────────────────────────────────────────

    def _resolve_path(self) -> Path | None:
        """Resolve the configured TODO.md path relative to the active activity."""
        cfg = load_adapter_config(self.name)
        cfg_path = cfg.get("path", "TODO.md")
        path = Path(cfg_path)
        if path.is_absolute():
            return path
        root = find_activity_root(Path.cwd())
        if root is None:
            return None
        return root / cfg_path

    def _read_and_parse(self, groups: list[str] | None) -> PullResult:
        cfg = load_adapter_config(self.name)
        cfg_path = cfg.get("path", "TODO.md")
        include_checked = bool(cfg.get("include_checked", False))

        section_filter: list[str] | None = None
        if groups:
            section_filter = [_slugify_heading(g) for g in groups]
        elif cfg.get("section_filter"):
            section_filter = list(cfg["section_filter"])

        path = self._resolve_path()
        if path is None:
            return PullResult(errors=["not inside an activity; cannot resolve TODO.md path"])

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

        display_path = cfg_path
        tasks = _parse_todo_md(
            content,
            section_filter=section_filter,
            include_checked=include_checked,
            source_path=display_path,
        )
        return PullResult(tasks=tasks)


# ── helpers ───────────────────────────────────────────────────────────


def _flip_marker(line: str, target_state: str) -> str:
    """Replace the marker character in a checkbox line. Strips arrow if reopening."""
    m = CHECKBOX_RE.match(line)
    if not m:
        return line
    indent, bullet, _marker, body = m.group(1), m.group(2), m.group(3), m.group(4)
    new_marker = "x" if target_state == "checked" else " "
    if target_state == "unchecked":
        # Strip the arrow (item is back as an open todo, no longer handed off).
        body = ARROW_RE.sub("", body).rstrip()
    return f"{indent}{bullet} [{new_marker}] {body}".rstrip()


def _insert_under_section(content: str, section: str | None, new_line: str) -> tuple[str, str]:
    """Insert `new_line` after the matching heading. Returns (new_content, where).

    If `section` is None, appends to the end of the file.
    If `section` is set but no matching heading exists, appends to the end with a
    "no matching section" hint in the `where` description.
    """
    if section is None:
        # Plain append.
        if content and not content.endswith("\n"):
            content += "\n"
        return (content + new_line, "end of file (no section configured)")

    target_slug = _slugify_heading(section)
    lines = content.splitlines()
    target_idx: int | None = None
    next_heading_idx: int | None = None
    for i, line in enumerate(lines):
        hm = HEADING_RE.match(line)
        if hm and _slugify_heading(hm.group(2)) == target_slug:
            target_idx = i
            continue
        if target_idx is not None and HEADING_RE.match(line):
            next_heading_idx = i
            break

    if target_idx is None:
        # Section not found — append at end with the section heading.
        if content and not content.endswith("\n"):
            content += "\n"
        return (
            content + f"\n## {section}\n\n{new_line}\n",
            f"new section '{section}' (heading not found, appended)",
        )

    # Insert just before the next heading, or at end of file.
    insert_at = next_heading_idx if next_heading_idx is not None else len(lines)
    # Walk back past trailing blanks so the insert sits neatly at the bottom of
    # the section content rather than on a blank line.
    while insert_at > target_idx + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, new_line)
    return ("\n".join(lines), f"under section '{section}'")

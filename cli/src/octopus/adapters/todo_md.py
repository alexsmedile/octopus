"""TODO.md adapter — pull + source-annotation + limited mutation verbs.

Format (D72, D103):
  Layer 1 — GFM checklist + Obsidian Tasks emoji + `→` arrow (D73).
  Layer 2 — shorthand sigils (@owner ~bucket !priority 🗓️ date),
            body block (> text lines), YAML expansion block (```yaml```),
            per-activity section_map config defaults.

Behavior (D74): on successful pull, the adapter rewrites `- [ ]` lines to
`- [x] → octopus:<task-slug>` in the source file. Items with an arrow are
skipped on re-pull — they're someone else's responsibility now.

Mutation verbs (D75): `add`, `mark_complete`, `mark_open` for editing
TODO.md without ever importing into the task tree.

Config (`~/.config/octopus/bridges/todo-md.toml`):
    path = "TODO.md"           # relative to activity root, or absolute
    include_checked = false    # if true, [x] lines without arrow import as done
    section_filter = []        # empty = all sections; slugs = filter to these

Per-activity `.octopus/config.toml`:
    [bridges.todo-md.section_map.skills]
    kind = "feat"
    [bridges.todo-md.section_map.infrastructure]
    kind = "chore"
    priority = "low"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

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
    """Parsed sigils + Obsidian Tasks emoji + tags + Octopus arrow from a line body."""

    title: str                      # cleaned title with all metadata stripped
    priority: str | None = None     # urgent | low | high | None
    due: date | None = None
    scheduled: date | None = None
    start_date: date | None = None
    tags: tuple[str, ...] = ()
    owner: str | None = None        # @sigil
    bucket: str | None = None       # ~sigil
    kind: str | None = None         # %sigil
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
# D103: calendar emoji aliases for `due` (same field, different glyphs).
CALENDAR_ALIAS_EMOJI = {"🗓️", "📆"}

# Emoji that we recognize and drop (informational; not surfaced as Octopus fields v1)
NOOP_EMOJI = {"➕", "✅", "❌", "🔁"}

# Combined regex of all known emoji — used to strip metadata cleanly.
ALL_EMOJI = (
    set(PRIORITY_EMOJI.keys())
    | set(DATE_EMOJI_FIELDS.keys())
    | CALENDAR_ALIAS_EMOJI
    | NOOP_EMOJI
)
ANY_EMOJI_RE = re.compile("|".join(re.escape(e) for e in ALL_EMOJI))

# Date emojis with their date. Accepts ISO (YYYY-MM-DD), DD-MM-YYYY, DD/MM/YYYY.
_DATE_PAT = r"(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})"
_DUE_EMOJI_PAT = "|".join(re.escape(e) for e in {**DATE_EMOJI_FIELDS, **{k: "due" for k in CALENDAR_ALIAS_EMOJI}})
DATE_EMOJI_PAIR_RE = re.compile(
    r"(" + "|".join(re.escape(e) for e in DATE_EMOJI_FIELDS) + r")\s*" + _DATE_PAT
)
# Calendar aliases always map to `due`.
CALENDAR_ALIAS_PAIR_RE = re.compile(
    r"(" + "|".join(re.escape(e) for e in CALENDAR_ALIAS_EMOJI) + r")\s*" + _DATE_PAT
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

# D103 shorthand sigils.
# @word — owner. Word = alphanumerics + hyphen + underscore + dot.
OWNER_RE = re.compile(r"(?:^|\s)@([\w.\-]+)")
# ~word — bucket. Accepts full names and single-char shorthand (~b ~n ~!).
BUCKET_RE = re.compile(r"(?:^|\s)~(\S+)")
# !word — priority. Accepts full names and single-char shorthand (!l !h !!).
# Uses a word-boundary-style check: stops at whitespace. Does NOT match [!] state markers
# because those are extracted by CHECKBOX_RE before body parsing ever runs.
PRIORITY_SIGIL_RE = re.compile(r"(?:^|\s)!([\S]+)")
# %word — kind. Accepts full names and single-char shorthand (%f %b %s %c %r).
KIND_SIGIL_RE = re.compile(r"(?:^|\s)%([\w]+)")

# YAML fenced block: ```yaml ... ``` (handles optional leading whitespace on fences).
YAML_FENCE_OPEN_RE = re.compile(r"^\s*```yaml\s*$")
YAML_FENCE_CLOSE_RE = re.compile(r"^\s*```\s*$")

# Body block: GFM blockquote lines, with optional leading whitespace (0-3 spaces per GFM spec).
BODY_LINE_RE = re.compile(r"^ {0,3}> ?(.*)")

# Bucket shorthand map.
_BUCKET_SHORTHANDS: dict[str, str] = {
    "b": "backlog", "backlog": "backlog",
    "n": "next",    "next": "next",
    "!": "now",     "now": "now",
    "d": "done",    "done": "done",
    "x": "dropped", "dropped": "dropped",
}

# Priority shorthand map.
_PRIORITY_SHORTHANDS: dict[str, str] = {
    "l": "low",    "low": "low",
    "h": "high",   "high": "high",
    "!": "urgent", "urgent": "urgent",
    "u": "urgent",
}

# Kind shorthand map — full names only (single-letter shorthands intentionally omitted).
_KIND_SHORTHANDS: dict[str, str] = {
    "feat": "feat",
    "bug": "bug",
    "spec": "spec",
    "chore": "chore",
    "refactor": "refactor",
    "polish": "polish",
    "test": "test",
    "docs": "docs",
    "idea": "idea",
}


def _slugify_heading(text: str) -> str:
    """Cheap heading slug: lowercase, alphanumerics + hyphens."""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _parse_date_str(s: str) -> date | None:
    """Parse ISO (YYYY-MM-DD), DD-MM-YYYY, or DD/MM/YYYY. Returns None on failure."""
    s = s.strip()
    # ISO
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    # DD-MM-YYYY or DD/MM/YYYY
    m = re.match(r"^(\d{2})[-/](\d{2})[-/](\d{4})$", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def _parse_inline_metadata(text: str) -> InlineMetadata:
    """Extract sigils, emoji, tags, and `→ arrow` from a line body (D72, D103).

    Order: arrow → date emoji → noop emoji → recurrence → tags →
           owner sigil → bucket sigil → priority sigil → priority emoji →
           leftover emoji → whitespace collapse.
    """
    priority: str | None = None
    due: date | None = None
    scheduled: date | None = None
    start_date: date | None = None
    owner: str | None = None
    bucket: str | None = None
    kind: str | None = None
    arrow_target: str | None = None
    has_arrow = False

    # 1. Arrow — at the end of the line by convention.
    am = ARROW_RE.search(text)
    if am:
        has_arrow = True
        provider, identifier = am.group(1), am.group(2)
        arrow_target = f"{provider}:{identifier}"
        text = text[: am.start()] + text[am.end():]

    # 2. Date-emoji pairs (original DATE_EMOJI_FIELDS).
    def _date_repl(m: re.Match[str]) -> str:
        nonlocal due, scheduled, start_date
        d = _parse_date_str(m.group(2))
        if d is None:
            return ""
        field = DATE_EMOJI_FIELDS[m.group(1)]
        if field == "due":
            due = d
        elif field == "scheduled":
            scheduled = d
        elif field == "start_date":
            start_date = d
        return ""

    text = DATE_EMOJI_PAIR_RE.sub(_date_repl, text)

    # 3. Calendar alias emoji (🗓️ 📆) — always map to `due`.
    def _cal_repl(m: re.Match[str]) -> str:
        nonlocal due
        d = _parse_date_str(m.group(2))
        if d is not None:
            due = d
        return ""

    text = CALENDAR_ALIAS_PAIR_RE.sub(_cal_repl, text)

    # 4. Drop no-op date emojis.
    text = NOOP_DATE_PAIR_RE.sub("", text)

    # 5. Recurrence rules — strip but don't capture (v1).
    text = RECURRENCE_RE.sub("", text)

    # 6. Tags — strip and collect.
    tags = tuple(m.group(1) for m in TAG_RE.finditer(text))
    text = TAG_RE.sub("", text)

    # 7. D103 sigils — @owner.
    om = OWNER_RE.search(text)
    if om:
        owner = om.group(1)
        text = text[: om.start()] + text[om.end():]

    # 8. D103 sigils — ~bucket.
    bm = BUCKET_RE.search(text)
    if bm:
        raw = bm.group(1).lower()
        bucket = _BUCKET_SHORTHANDS.get(raw)
        text = text[: bm.start()] + text[bm.end():]

    # 8.5. %kind sigil.
    km = KIND_SIGIL_RE.search(text)
    if km:
        raw = km.group(1).lower()
        resolved_kind = _KIND_SHORTHANDS.get(raw)
        if resolved_kind is not None:
            kind = resolved_kind
            text = text[: km.start()] + text[km.end():]

    # 9. D103 sigils — !priority (before emoji so both don't fire on same item).
    pm = PRIORITY_SIGIL_RE.search(text)
    if pm:
        raw = pm.group(1).lower()
        resolved = _PRIORITY_SHORTHANDS.get(raw)
        if resolved is not None:
            priority = resolved
            text = text[: pm.start()] + text[pm.end():]

    # 10. Priority emoji — only if sigil didn't already set priority.
    if priority is None:
        for emoji in PRIORITY_EMOJI:
            if emoji in text:
                priority = PRIORITY_EMOJI[emoji]
                text = text.replace(emoji, "")

    # 11. Strip any leftover known emoji.
    text = ANY_EMOJI_RE.sub("", text)

    # 12. Collapse runs of whitespace.
    title = re.sub(r"\s+", " ", text).strip()

    return InlineMetadata(
        title=title,
        priority=priority,
        due=due,
        scheduled=scheduled,
        start_date=start_date,
        tags=tags,
        owner=owner,
        bucket=bucket,
        kind=kind,
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


def _apply_yaml_overrides(block: str, et: ExternalTask) -> ExternalTask:
    """Parse a YAML block string and return a new ExternalTask with overrides applied.

    Unknown keys are silently ignored. Invalid values are silently ignored.
    Precedence: existing ExternalTask values (from sigils/emoji) win over YAML.
    """
    try:
        import yaml as _yaml  # optional dep — stdlib tomllib not suitable for inline YAML
        data: dict[str, Any] = _yaml.safe_load(block) or {}
    except Exception:
        return et

    if not isinstance(data, dict):
        return et

    def _get(key: str) -> Any:
        return data.get(key)

    # Only apply if not already set by a higher-precedence source (sigil/emoji).
    bucket = et.suggested_bucket
    if bucket is None:
        raw = _get("bucket")
        if isinstance(raw, str) and raw in {"backlog", "next", "now", "done", "dropped"}:
            bucket = raw

    stage = et.suggested_stage or (_get("stage") if isinstance(_get("stage"), str) else None)

    pinned = et.suggested_pinned
    if pinned is None and _get("pinned") is True:
        pinned = True

    issue = et.suggested_issue
    if issue is None:
        raw = _get("issue")
        if isinstance(raw, str) and raw in {"blocked", "waiting"}:
            issue = raw

    blocked_by = et.suggested_blocked_by or (
        _get("blocked_by") if isinstance(_get("blocked_by"), str) else None
    )
    waiting_for = et.suggested_waiting_for or (
        _get("waiting_for") if isinstance(_get("waiting_for"), str) else None
    )

    due = et.suggested_due
    if due is None:
        raw = _get("due")
        if isinstance(raw, str):
            due = _parse_date_str(raw)
        elif isinstance(raw, date):
            due = raw

    scheduled = et.suggested_scheduled
    if scheduled is None:
        raw = _get("scheduled")
        if isinstance(raw, str):
            scheduled = _parse_date_str(raw)
        elif isinstance(raw, date):
            scheduled = raw

    priority = et.suggested_priority
    if priority is None:
        raw = _get("priority")
        if isinstance(raw, str) and raw in {"low", "high", "urgent"}:
            priority = raw

    energy = et.suggested_energy or (
        _get("energy") if isinstance(_get("energy"), str) and _get("energy") in {"low", "mid", "high"} else None
    )

    actor = et.suggested_actor
    if actor is None:
        raw = _get("actor")
        if isinstance(raw, str) and raw in {"human", "ai", "automation"}:
            actor = raw

    owner = et.suggested_owner or (
        _get("owner") if isinstance(_get("owner"), str) else None
    )

    kind = et.suggested_kind
    if kind is None:
        raw = _get("kind")
        if isinstance(raw, str):
            kind = raw  # soft validation — unknown values warn at write time

    # Merge tags: existing + yaml, deduped, order preserved.
    extra_tags: list[str] = []
    raw_tags = _get("tags")
    if isinstance(raw_tags, list):
        extra_tags = [str(t) for t in raw_tags]
    elif isinstance(raw_tags, str):
        extra_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    merged_tags = list(et.suggested_tags)
    seen = set(merged_tags)
    for t in extra_tags:
        if t not in seen:
            merged_tags.append(t)
            seen.add(t)

    return ExternalTask(
        external_id=et.external_id,
        title=et.title,
        body=et.body,
        suggested_bucket=bucket,
        suggested_stage=stage,
        suggested_pinned=pinned,
        suggested_issue=issue,
        suggested_blocked_by=blocked_by,
        suggested_waiting_for=waiting_for,
        suggested_due=due,
        suggested_scheduled=scheduled,
        suggested_priority=priority,
        suggested_energy=energy,
        suggested_actor=actor,
        suggested_owner=owner,
        suggested_kind=kind,
        suggested_tags=merged_tags,
        created_external=et.created_external,
        source_group=et.source_group,
    )


def _apply_section_map(et: ExternalTask, section_map: dict[str, dict]) -> ExternalTask:
    """Apply per-section config defaults (lowest precedence — only fills absent fields)."""
    if not et.source_group:
        return et
    defaults = section_map.get(et.source_group, {})
    if not defaults:
        return et

    def _default(current: Any, key: str) -> Any:
        return current if current is not None else defaults.get(key)

    return ExternalTask(
        external_id=et.external_id,
        title=et.title,
        body=et.body,
        suggested_bucket=_default(et.suggested_bucket, "bucket"),
        suggested_stage=_default(et.suggested_stage, "stage"),
        suggested_pinned=et.suggested_pinned,   # per-item only
        suggested_issue=et.suggested_issue,     # per-item only
        suggested_blocked_by=et.suggested_blocked_by,
        suggested_waiting_for=et.suggested_waiting_for,
        suggested_due=et.suggested_due,
        suggested_scheduled=et.suggested_scheduled,
        suggested_priority=_default(et.suggested_priority, "priority"),
        suggested_energy=_default(et.suggested_energy, "energy"),
        suggested_actor=_default(et.suggested_actor, "actor"),
        suggested_owner=et.suggested_owner,     # per-item only
        suggested_kind=_default(et.suggested_kind, "kind"),
        suggested_tags=et.suggested_tags,
        created_external=et.created_external,
        source_group=et.source_group,
    )


def _parse_todo_md(
    content: str,
    *,
    section_filter: list[str] | None = None,
    include_checked: bool = False,
    source_path: str = "TODO.md",
    section_map: dict[str, dict] | None = None,
) -> list[ExternalTask]:
    """Walk the file line by line; return a list of importable ExternalTasks.

    D73: items with `→` arrows are skipped — already handed off.
    D72: state markers + emoji metadata.
    D103: sigils (@owner ~bucket !priority 🗓️ date), body block (> text),
          YAML expansion block (```yaml ... ```), section_map defaults.
    """
    tasks: list[ExternalTask] = []
    seen_slugs: set[str] = set()
    current_section: str | None = None
    filter_set = set(section_filter) if section_filter else None
    _section_map = section_map or {}

    # D105: track the most-recently-seen top-level item per indent level so
    # indented children can reference their parent slug.
    # Maps indent_len → (slug, indent_len) of the last top-level item at that depth.
    # Only 1-level nesting is supported; deeper items are treated as top-level.
    last_top_level_slug: str | None = None  # slug of the last depth-0 item

    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # Heading → update current section; reset depth tracking.
        hm = HEADING_RE.match(line)
        if hm:
            current_section = _slugify_heading(hm.group(2))
            last_top_level_slug = None
            i += 1
            continue

        cb = _parse_checkbox(line)
        if cb is None:
            i += 1
            continue

        # Measure indent of this item.
        m_indent = CHECKBOX_RE.match(line)
        indent_len = len(m_indent.group(1)) if m_indent else 0
        is_child = indent_len > 0

        # Section filter.
        if filter_set is not None and current_section not in filter_set:
            if not is_child:
                last_top_level_slug = None
            i += 1
            continue

        # D73: skip items already handed off.
        if cb.metadata.has_arrow:
            if not is_child:
                last_top_level_slug = None
            i += 1
            continue

        # D72: skip cancelled.
        if cb.state == "cancelled":
            i += 1
            continue

        # Skip checked unless include_checked.
        if cb.state == "checked" and not include_checked:
            if not is_child:
                last_top_level_slug = None
            i += 1
            continue

        # BUG:/HACK:/etc. prefix stripping.
        title, kind_from_prefix, skip = _extract_title_meta(cb.metadata.title)
        if skip or not title:
            i += 1
            continue

        # Consume body block (> text) and YAML block (```yaml ... ```) on following lines.
        i += 1
        body_lines: list[str] = []
        yaml_lines: list[str] = []

        # Body block: consecutive `> ...` lines immediately after checkbox.
        while i < len(lines):
            bm = BODY_LINE_RE.match(lines[i])
            if bm:
                body_lines.append(bm.group(1))
                i += 1
            else:
                break

        # YAML block: ```yaml ... ``` immediately after checkbox (or body block).
        # Skip over any blank lines between body and yaml fence.
        j = i
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j < len(lines) and YAML_FENCE_OPEN_RE.match(lines[j]):
            i = j + 1  # step past the opening fence
            while i < len(lines) and not YAML_FENCE_CLOSE_RE.match(lines[i]):
                yaml_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # step past the closing fence

        # Build external_id from slug (collision-safe).
        base = _slugify_heading(title) or "item"
        slug = base
        counter = 2
        while slug in seen_slugs:
            slug = f"{base}-{counter}"
            counter += 1
        seen_slugs.add(slug)
        external_id = f"{source_path}#{slug}"

        # Bucket: sigil > state marker.
        if cb.metadata.bucket:
            bucket = cb.metadata.bucket
        elif cb.state == "checked":
            bucket = "done"
        elif cb.state == "in-progress":
            bucket = "now"
        else:
            bucket = "backlog"

        # D105: resolve suggested_parent for indented children.
        suggested_parent: str | None = None
        if is_child and last_top_level_slug is not None:
            suggested_parent = last_top_level_slug
        elif not is_child:
            last_top_level_slug = slug

        et = ExternalTask(
            external_id=external_id,
            title=title,
            body="\n".join(body_lines) if body_lines else None,
            suggested_bucket=bucket,
            suggested_kind=cb.metadata.kind or kind_from_prefix,
            suggested_tags=list(cb.metadata.tags),
            suggested_priority=cb.metadata.priority,
            suggested_due=cb.metadata.due,
            suggested_scheduled=cb.metadata.scheduled,
            suggested_owner=cb.metadata.owner,
            suggested_parent=suggested_parent,
            source_group=current_section,
        )

        # Apply YAML overrides (higher precedence than section_map, lower than sigils).
        if yaml_lines:
            et = _apply_yaml_overrides("\n".join(yaml_lines), et)

        # Apply section_map defaults (lowest precedence).
        et = _apply_section_map(et, _section_map)

        tasks.append(et)

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

        # Load per-activity section_map from .octopus/config.toml.
        # _merge() in config.py drops unknown keys, so read the raw TOML directly.
        section_map: dict[str, dict] = {}
        activity_root = find_activity_root(Path.cwd())
        if activity_root is not None:
            import tomllib as _tomllib
            toml_path = activity_root / ".octopus" / "config.toml"
            if toml_path.is_file():
                try:
                    raw_toml = _tomllib.loads(toml_path.read_text(encoding="utf-8"))
                except Exception:
                    raw_toml = {}
                raw_map = (
                    raw_toml.get("bridges", {})
                    .get("todo-md", {})
                    .get("section_map", {})
                )
                if isinstance(raw_map, dict):
                    section_map = {
                        _slugify_heading(k): v
                        for k, v in raw_map.items()
                        if isinstance(v, dict)
                    }

        tasks = _parse_todo_md(
            content,
            section_filter=section_filter,
            include_checked=include_checked,
            source_path=cfg_path,
            section_map=section_map,
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

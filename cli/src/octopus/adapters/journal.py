"""Sync journal — one JSON file per adapter at ~/.local/share/octopus/sync/<name>.json.

v1 schema (D65): minimal counters + timestamps + cursor. No event-level
history. #10 (sync modes addendum) may grow this into a directory of
per-event files in v2.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class JournalEntry:
    """Per-adapter state. Fields default to safe values so a missing
    journal file is indistinguishable from an unused adapter.
    """

    adapter: str
    last_pull: datetime | None = None
    last_push: datetime | None = None
    pull_count: int = 0
    push_count: int = 0
    cursor: str | None = None


def journal_dir() -> Path:
    """`$XDG_DATA_HOME/octopus/sync/` (~/.local/share/octopus/sync/)."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "octopus" / "sync"


def journal_path(adapter_name: str) -> Path:
    return journal_dir() / f"{adapter_name}.json"


def read_journal(adapter_name: str) -> JournalEntry:
    """Read the journal for an adapter. Missing file → sane defaults."""
    path = journal_path(adapter_name)
    if not path.is_file():
        return JournalEntry(adapter=adapter_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupted journal — start fresh rather than crash the CLI.
        return JournalEntry(adapter=adapter_name)
    return JournalEntry(
        adapter=adapter_name,
        last_pull=_parse_dt(data.get("last_pull")),
        last_push=_parse_dt(data.get("last_push")),
        pull_count=int(data.get("pull_count") or 0),
        push_count=int(data.get("push_count") or 0),
        cursor=data.get("cursor"),
    )


def write_journal(entry: JournalEntry) -> None:
    """Persist the journal. Creates parent dirs and the file as needed."""
    path = journal_path(entry.adapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "adapter": entry.adapter,
        "last_pull": entry.last_pull.isoformat(timespec="seconds") if entry.last_pull else None,
        "last_push": entry.last_push.isoformat(timespec="seconds") if entry.last_push else None,
        "pull_count": entry.pull_count,
        "push_count": entry.push_count,
        "cursor": entry.cursor,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def update_journal(
    adapter_name: str,
    *,
    pulled: bool = False,
    pushed: bool = False,
    cursor: str | None = ...,  # type: ignore[assignment]
) -> JournalEntry:
    """Read-modify-write the journal after a pull/push operation.

    - `pulled=True` updates `last_pull` to now and increments `pull_count`.
    - `pushed=True` updates `last_push` to now and increments `push_count`.
    - `cursor` is updated if explicitly passed (default sentinel keeps existing).
    """
    entry = read_journal(adapter_name)
    now = datetime.now()
    if pulled:
        entry.last_pull = now
        entry.pull_count += 1
    if pushed:
        entry.last_push = now
        entry.push_count += 1
    # Sentinel: only update cursor when caller explicitly passed it.
    if cursor is not ...:
        entry.cursor = cursor  # type: ignore[assignment]
    write_journal(entry)
    return entry


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None

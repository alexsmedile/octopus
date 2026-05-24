"""Wrapper for the `remindctl` CLI (steipete/remindctl, MIT).

Encapsulates every subprocess call and JSON parse, so the adapter logic
in `reminders.py` stays declarative and the tests can mock a single layer.

Why this exists as a separate module: `reminders.py` is the protocol-shaped
adapter; this is the implementation detail. Splitting keeps the adapter
file readable and lets tests stub `_reminders_io` wholesale.

Verified against `remindctl 0.1.1`. See `.spectacular/requests/09-adapter-reminders-pull/PLAN.md`
for the JSON contract.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# Subprocess timeout — Apple Reminders is local-only, so anything beyond a few
# seconds means trouble (auth prompt blocked, system stuck).
SUBPROCESS_TIMEOUT_SECS = 5.0


# ── data classes (typed mirrors of remindctl JSON) ─────────────────────


@dataclass(frozen=True)
class RemindersList:
    id: str
    title: str
    reminder_count: int = 0
    overdue_count: int = 0


@dataclass(frozen=True)
class RemindersItem:
    id: str                               # EventKit UUID (stable)
    title: str
    list_name: str
    list_id: str
    is_completed: bool = False
    priority: str = "none"                # none | low | medium | high
    due_date: date | None = None          # date portion of dueDate (UTC stripped)
    notes: str | None = None
    completion_date: date | None = None


# ── errors ─────────────────────────────────────────────────────────────


class RemindctlError(Exception):
    """Wraps any subprocess / parse failure with a user-facing message."""


class RemindctlNotInstalled(RemindctlError):
    """The `remindctl` binary is not on PATH."""


# ── primitives ─────────────────────────────────────────────────────────


def which_remindctl() -> str | None:
    """Return the path to `remindctl` or None if not installed."""
    return shutil.which("remindctl")


def _run(args: list[str]) -> str:
    """Run remindctl with stdout captured. Raises RemindctlError on failure."""
    bin_path = which_remindctl()
    if not bin_path:
        raise RemindctlNotInstalled(
            "remindctl not found on PATH — install via `brew install steipete/tap/remindctl`"
        )
    try:
        result = subprocess.run(
            [bin_path, *args],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RemindctlError(f"remindctl timed out after {SUBPROCESS_TIMEOUT_SECS}s") from exc
    except FileNotFoundError as exc:
        raise RemindctlNotInstalled(str(exc)) from exc
    if result.returncode != 0:
        # `remindctl status` returns non-zero when access denied — caller may
        # want to handle that path-specifically. We always raise here; the
        # auth_status() helper catches and translates.
        raise RemindctlError(
            f"remindctl exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


# ── auth ───────────────────────────────────────────────────────────────


def auth_status() -> str:
    """Return one of: "Full access" | "Denied" | "Not Determined" | "missing-binary".

    Does not raise on auth-denied (returns the string) — only on subprocess
    plumbing failures.
    """
    if not which_remindctl():
        return "missing-binary"
    try:
        out = _run(["status"])
    except RemindctlError:
        # Non-zero exit on `remindctl status` typically means denied.
        # Re-shell explicitly to grab the human-readable phrase.
        try:
            proc = subprocess.run(
                [which_remindctl(), "status"],
                capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECS, check=False,
            )
            text = (proc.stdout + proc.stderr).lower()
            if "denied" in text:
                return "Denied"
            if "not determined" in text or "notdetermined" in text:
                return "Not Determined"
            return "Denied"  # fallback — non-zero with no recognizable phrase
        except Exception:
            return "Denied"
    # Parse the human line: "Reminders access: Full access"
    line = out.strip().lower()
    if "full" in line:
        return "Full access"
    if "denied" in line:
        return "Denied"
    if "not determined" in line:
        return "Not Determined"
    # Unknown phrasing — return raw output trimmed, useful for debug
    return out.strip() or "Unknown"


# ── lists ──────────────────────────────────────────────────────────────


def list_lists() -> list[RemindersList]:
    """Return every Reminders list visible to remindctl."""
    raw = _run(["list", "--json"])
    return [_parse_list_row(row) for row in _safe_json(raw)]


def _parse_list_row(row: dict[str, Any]) -> RemindersList:
    return RemindersList(
        id=str(row.get("id") or ""),
        title=str(row.get("title") or ""),
        reminder_count=int(row.get("reminderCount") or 0),
        overdue_count=int(row.get("overdueCount") or 0),
    )


# ── reminders ─────────────────────────────────────────────────────────


def show_list(list_name: str, *, include_completed: bool = False) -> list[RemindersItem]:
    """Return reminders in the given list, optionally including completed ones."""
    filter_arg = "all" if include_completed else "all"
    # We always ask for `all` and filter Python-side. Reason: there's no
    # `incomplete` filter; `today` etc. filter by date, not completion.
    raw = _run(["show", filter_arg, "--list", list_name, "--json"])
    items = [_parse_item_row(row) for row in _safe_json(raw)]
    if not include_completed:
        items = [i for i in items if not i.is_completed]
    return items


def _parse_item_row(row: dict[str, Any]) -> RemindersItem:
    return RemindersItem(
        id=str(row.get("id") or ""),
        title=str(row.get("title") or ""),
        list_name=str(row.get("listName") or ""),
        list_id=str(row.get("listID") or ""),
        is_completed=bool(row.get("isCompleted") or False),
        priority=str(row.get("priority") or "none"),
        due_date=_iso_to_date(row.get("dueDate")),
        notes=row.get("notes") or None,
        completion_date=_iso_to_date(row.get("completionDate")),
    )


# ── helpers ────────────────────────────────────────────────────────────


def _safe_json(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RemindctlError(f"failed to parse remindctl JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RemindctlError(f"expected JSON array, got {type(data).__name__}")
    return [row for row in data if isinstance(row, dict)]


def _iso_to_date(value: Any) -> date | None:
    """Convert remindctl's ISO 8601 UTC timestamp string to a date.

    Time portion is intentionally dropped — Octopus is date-granularity by
    design (per existing schema).
    """
    if not value or not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        # Try date-only ISO
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

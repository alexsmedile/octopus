"""Apple Reminders adapter — pull-only import via `remindctl`.

Hard-requires `remindctl` (MIT, EventKit-based) on PATH. See PLAN.md for
the verified JSON contract and `DECISIONS.md D67–D71` for the locked
mapping rules.

Architecture: this module is protocol-shaped (status/peek/pull/search/etc.);
all subprocess + JSON parsing lives in `_reminders_io.py` so the adapter
is trivially mockable.
"""

from __future__ import annotations

from octopus.adapters._reminders_io import (
    RemindctlError,
    RemindctlNotInstalled,
    RemindersItem,
    auth_status,
    list_lists,
    show_list,
    which_remindctl,
)
from octopus.adapters.base import (
    AdapterStatus,
    Capability,
    ExternalTask,
    PullResult,
    PushResult,
)
from octopus.adapters.journal import read_journal
from octopus.config import load_adapter_config

_BREW_HINT = "install via `brew install steipete/tap/remindctl`"


class RemindersAdapter:
    """Pull-only adapter for Apple Reminders. Multi-list. macOS-only."""

    name = "reminders"
    capabilities: set[Capability] = {Capability.PULL}

    # ── status / config ──────────────────────────────────────────────

    def status(self) -> AdapterStatus:
        journal = read_journal(self.name)
        # Fast-path: cached auth state, no subprocess on every call.
        # `auth_state` is stored in the journal's extra fields if we wrote it.
        cached_auth = getattr(journal, "auth_state", None) or self._read_cached_auth()

        if not which_remindctl():
            return AdapterStatus(
                name=self.name,
                healthy=False,
                error=f"remindctl not installed — {_BREW_HINT}",
                last_pull=journal.last_pull,
                capabilities=self.capabilities,
            )

        # Cache miss or "Not Determined" → re-probe.
        if cached_auth in (None, "Not Determined"):
            cached_auth = auth_status()
            self._write_cached_auth(cached_auth)

        if cached_auth == "Full access":
            return AdapterStatus(
                name=self.name,
                healthy=True,
                last_pull=journal.last_pull,
                last_push=journal.last_push,
                capabilities=self.capabilities,
            )
        return AdapterStatus(
            name=self.name,
            healthy=False,
            error=f"Reminders access: {cached_auth} — run `remindctl authorize` or grant in System Settings",
            last_pull=journal.last_pull,
            capabilities=self.capabilities,
        )

    def validate_config(self, data: dict) -> list[str]:
        errors: list[str] = []

        lists = data.get("lists", [])
        if not isinstance(lists, list):
            errors.append("`lists` must be a list of strings")
        elif not all(isinstance(s, str) for s in lists):
            errors.append("`lists` entries must be strings")

        ic = data.get("include_completed", False)
        if not isinstance(ic, bool):
            errors.append("`include_completed` must be a boolean")

        da = data.get("default_activity", "")
        if not isinstance(da, str):
            errors.append("`default_activity` must be a string")

        # remindctl + auth probe — informational, not fatal here. Caller
        # (`octopus bridge enable`) surfaces the errors. We do NOT block
        # enabling — the user may be enabling on a CI box or before
        # installing the binary. status() will keep reporting unhealthy.
        if not which_remindctl():
            errors.append(f"remindctl is not installed yet — {_BREW_HINT}")
        else:
            # Probe auth once at enable-time, cache in journal.
            current = auth_status()
            self._write_cached_auth(current)
            if current == "Denied":
                errors.append(
                    "Reminders access denied — run `remindctl authorize` "
                    "or grant in System Settings → Privacy & Security → Reminders"
                )
            # "Full access" + "Not Determined" don't block enable; the
            # first peek/pull will surface anything that's wrong.

        return errors

    # ── discovery ────────────────────────────────────────────────────

    def list_groups(self) -> list[str]:
        try:
            return [L.title for L in list_lists()]
        except RemindctlError:
            return []

    # ── pull-side verbs ──────────────────────────────────────────────

    def peek(self, groups: list[str] | None = None) -> PullResult:
        return self._read(groups, include_completed_override=None)

    def pull(self, groups: list[str] | None = None) -> PullResult:
        return self._read(groups, include_completed_override=None)

    def search(self, query: str, groups: list[str] | None = None) -> PullResult:
        result = self._read(groups, include_completed_override=None)
        if not query:
            return result
        q = query.lower()
        result.tasks = [
            t for t in result.tasks
            if q in t.title.lower() or (t.body and q in t.body.lower())
        ]
        return result

    def push(self, task) -> PushResult:
        return PushResult(error="reminders adapter is pull-only in v1 (see #14 for two-way)")

    # ── internals ────────────────────────────────────────────────────

    def _read(
        self,
        groups: list[str] | None,
        *,
        include_completed_override: bool | None,
    ) -> PullResult:
        # Hard guard — remindctl missing means we can't do anything.
        if not which_remindctl():
            return PullResult(errors=[f"remindctl not installed — {_BREW_HINT}"])

        cfg = load_adapter_config(self.name)
        include_completed = bool(cfg.get("include_completed", False))
        if include_completed_override is not None:
            include_completed = include_completed_override

        # Resolve which lists to read from
        target_lists: list[str]
        if groups is not None:
            target_lists = list(groups)
        elif cfg.get("lists"):
            target_lists = list(cfg["lists"])
        else:
            # Fallback — no config, no caller — return discovery hint.
            return PullResult(
                errors=[
                    "no lists configured — set `lists = [...]` in "
                    "bridges/reminders.toml or pass --list <name>"
                ],
            )

        all_tasks: list[ExternalTask] = []
        errors: list[str] = []
        for list_name in target_lists:
            try:
                items = show_list(list_name, include_completed=include_completed)
            except RemindctlNotInstalled as exc:
                errors.append(str(exc))
                continue
            except RemindctlError as exc:
                errors.append(f"list {list_name!r}: {exc}")
                continue

            for it in items:
                all_tasks.append(_reminder_to_external_task(it))

        return PullResult(tasks=all_tasks, errors=errors)

    def _read_cached_auth(self) -> str | None:
        """Auth cache lives in the journal under a non-standard key.

        The `JournalEntry` dataclass doesn't have `auth_state`, but we can
        stash it in a sidecar file alongside the JSON. Simpler approach:
        re-shell `remindctl status` on cache miss; it's <100ms.
        """
        # MVP: no cache. status() always probes when missing. The journal
        # entry's last_pull is enough lifecycle signal. If repeated probes
        # become a perf issue, add a real `auth_state` field to JournalEntry.
        return None

    def _write_cached_auth(self, value: str) -> None:
        # See note above. No-op for MVP — the probe is cheap.
        return None


# ── mapping (D70) ─────────────────────────────────────────────────────


_PRIORITY_MAP: dict[str, str | None] = {
    "none": None,        # default omission
    "low": "low",
    "medium": None,      # Octopus has no medium; map to default
    "high": "high",
}


def _reminder_to_external_task(item: RemindersItem) -> ExternalTask:
    """Apply the D70 field mapping table."""
    body = item.notes or None

    return ExternalTask(
        external_id=item.id,                          # bare EventKit UUID (D69)
        title=item.title,
        body=body,
        suggested_bucket="backlog",                   # no auto-`now` (D70)
        suggested_kind=None,                          # Reminders has no kind
        suggested_tags=[],
        suggested_priority=_PRIORITY_MAP.get(item.priority),  # D70 mapping
        suggested_due=item.due_date,                  # date (UTC time stripped) per D70
        created_external=None,
        source_group=item.list_name,
    )


# Expose for tests
__all__ = [
    "RemindersAdapter",
    "_reminder_to_external_task",
    "_PRIORITY_MAP",
]

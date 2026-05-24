"""Apple Reminders adapter — STUB until request #09 lands.

Final implementation: pull-only via osascript, configured `lists` field
selects which Reminders lists to import from. See PRD §7.5.
"""

from __future__ import annotations

from octopus.adapters.base import (
    AdapterStatus,
    Capability,
    PullResult,
    PushResult,
)

_NOT_IMPL = "Apple Reminders adapter not implemented — see request #09"


class RemindersAdapter:
    """STUB. #09 will implement osascript-driven pull."""

    name = "reminders"
    capabilities: set[Capability] = {Capability.PULL}

    def status(self) -> AdapterStatus:
        return AdapterStatus(
            name=self.name,
            healthy=False,
            error=_NOT_IMPL,
            capabilities=self.capabilities,
        )

    def validate_config(self, data: dict) -> list[str]:
        return [_NOT_IMPL]

    def list_groups(self) -> list[str]:
        return []

    def peek(self, groups: list[str] | None = None) -> PullResult:
        return PullResult(errors=[_NOT_IMPL])

    def pull(self, groups: list[str] | None = None) -> PullResult:
        return PullResult(errors=[_NOT_IMPL])

    def push(self, task) -> PushResult:
        return PushResult(error=_NOT_IMPL)

    def search(self, query: str, groups: list[str] | None = None) -> PullResult:
        return PullResult(errors=[_NOT_IMPL])

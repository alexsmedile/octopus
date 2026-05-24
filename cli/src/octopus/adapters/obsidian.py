"""Obsidian adapter — STUB until request #07 lands.

Final implementation: vault symlink bridge (viewer pattern), not a pull
source. See PRD §7.4. The protocol is satisfied here so the framework
is testable end-to-end on #06 ship.
"""

from __future__ import annotations

from octopus.adapters.base import (
    AdapterStatus,
    Capability,
    PullResult,
    PushResult,
)

_NOT_IMPL = "Obsidian adapter not implemented — see request #07"


class ObsidianAdapter:
    """STUB. #07 will implement the symlink/viewer behavior."""

    name = "obsidian"
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

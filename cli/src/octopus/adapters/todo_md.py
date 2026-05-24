"""TODO.md adapter — STUB until request #21 lands.

Final implementation: reads `- [ ]` checkbox lines from a `TODO.md` file
at the activity root (or configured path). Single-file source — no
groups, no `--list` flag.
"""

from __future__ import annotations

from octopus.adapters.base import (
    AdapterStatus,
    Capability,
    PullResult,
    PushResult,
)

_NOT_IMPL = "TODO.md adapter not implemented — see request #21"


class TodoMdAdapter:
    """STUB. #21 will implement the file parser."""

    name = "todo-md"
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
        # TODO.md is a single file — no concept of groups by design.
        return []

    def peek(self, groups: list[str] | None = None) -> PullResult:
        return PullResult(errors=[_NOT_IMPL])

    def pull(self, groups: list[str] | None = None) -> PullResult:
        return PullResult(errors=[_NOT_IMPL])

    def push(self, task) -> PushResult:
        return PushResult(error=_NOT_IMPL)

    def search(self, query: str, groups: list[str] | None = None) -> PullResult:
        return PullResult(errors=[_NOT_IMPL])

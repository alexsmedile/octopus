"""Adapter framework public surface.

Importing from this module is the supported way to write a new adapter.
See SCHEMA-ADAPTER.md for the protocol contract.
"""

from octopus.adapters.base import (
    Adapter,
    AdapterStatus,
    Capability,
    ExternalRef,
    ExternalTask,
    PullResult,
    PushResult,
)

__all__ = [
    "Adapter",
    "AdapterStatus",
    "Capability",
    "ExternalRef",
    "ExternalTask",
    "PullResult",
    "PushResult",
]

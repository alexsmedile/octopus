"""Finding + Severity for `octopus lint`."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    """Lint finding severity. Ordered: info < warn < error."""

    INFO = "info"
    WARN = "warn"
    ERROR = "error"

    def rank(self) -> int:
        return {"info": 0, "warn": 1, "error": 2}[self.value]


@dataclass
class Finding:
    """A single lint result for a single file."""

    code: str
    severity: Severity
    path: Path
    message: str
    auto_fixable: bool = False
    # Free-form preview of what `--fix` would change (e.g. {"slug": "foo-bar"}).
    fix_preview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "path": str(self.path),
            "message": self.message,
            "auto_fixable": self.auto_fixable,
            "fix_preview": self.fix_preview,
        }

"""ViewState + TabState dataclasses.

Per the PLAN: cursor and scroll are per-panel so the model fits both the
Activities view (3 panels: index/current/nested) and Focus/Board (per-bucket
cursors) without special-casing.

Focus and Board states are namespaced by activity id in `ViewState.per_tab`
(keys like `focus:octopus-aaaa`) so the cursor in project A doesn't pollute
project B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class TabState:
    tab_id: str
    cursors: dict[str, str] = field(default_factory=dict)
    active_panel: str | None = None
    scroll_offsets: dict[str, int] = field(default_factory=dict)
    filter: str | None = None
    collapsed_panels: list[str] = field(default_factory=list)
    activity_id: str | None = None
    # Catch-all for unknown fields read from disk — preserved on round-trip
    # so forward-compatibility doesn't lose data.
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "tab_id": self.tab_id,
            "cursors": dict(self.cursors),
            "active_panel": self.active_panel,
            "scroll_offsets": dict(self.scroll_offsets),
            "filter": self.filter,
            "collapsed_panels": list(self.collapsed_panels),
            "activity_id": self.activity_id,
        }
        # Preserve unknown fields.
        for k, v in self.extra.items():
            if k not in out:
                out[k] = v
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TabState:
        known = {
            "tab_id", "cursors", "active_panel", "scroll_offsets",
            "filter", "collapsed_panels", "activity_id",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            tab_id=str(data.get("tab_id", "")),
            cursors=dict(data.get("cursors") or {}),
            active_panel=data.get("active_panel"),
            scroll_offsets=dict(data.get("scroll_offsets") or {}),
            filter=data.get("filter"),
            collapsed_panels=list(data.get("collapsed_panels") or []),
            activity_id=data.get("activity_id"),
            extra=extra,
        )


@dataclass
class ViewState:
    active_tab: str = "activities"
    per_tab: dict[str, TabState] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    # Catch-all for top-level unknown fields.
    extra: dict[str, Any] = field(default_factory=dict)

    def get_tab(self, key: str) -> TabState | None:
        return self.per_tab.get(key)

    def set_tab(self, key: str, state: TabState) -> None:
        self.per_tab[key] = state

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "active_tab": self.active_tab,
            "per_tab": {k: v.to_dict() for k, v in self.per_tab.items()},
        }
        for k, v in self.extra.items():
            if k not in out:
                out[k] = v
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ViewState:
        known = {"schema_version", "active_tab", "per_tab"}
        extra = {k: v for k, v in data.items() if k not in known}
        per_tab_raw = data.get("per_tab") or {}
        per_tab = {
            k: TabState.from_dict(v) for k, v in per_tab_raw.items()
            if isinstance(v, dict)
        }
        return cls(
            active_tab=str(data.get("active_tab", "activities")),
            per_tab=per_tab,
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            extra=extra,
        )

---
status: done
priority: high
owner: alex
updated: 2026-05-26
summary: "Persist cursor and view position across tab switches (always-on) and optionally across octopus sessions (opt-in via config flag). Universal across every tab — Focus, Board, Activities (Tab 0), future tabs."
related:
  - 43-activities-tab
gates: []
---

# Cursor & view state persistence

## Goal

Make the TUI remember where the user was last looking. Three layers:

| Layer | What it remembers | Lifetime |
|---|---|---|
| **L1 — Cursor memory** | Per-tab cursor position (which task/activity was hovered) | Always-on, in-memory while octopus runs |
| **L2 — Last-active page** | Which tab (0, 1, 2…) was last focused, including which panel within Tab 0 | Always-on, in-memory while octopus runs |
| **L3 — Cross-session** | L1 + L2 state survives quitting and relaunching octopus | Opt-in via config flag `restore_last_view = true`, persisted to `~/.cache/octopus/ui-state.json` |

Universal scope: applies to every existing and future tab. Not a per-feature opt-in.

## Why

Today: every tab switch resets to top-of-bucket. Every relaunch is cold. The user pays attention tax every time they bounce between Focus and Board, or quit and come back.

After this request: tab-switch is free (cursor where you left it). Relaunch is optionally free (`restore_last_view = true`). The TUI starts to feel like a workspace the user *returns to* instead of a viewer they *re-orient* each time.

This is the foundation feature that makes Tab 0 (request #43) genuinely usable as a navigation hub — without it, every drill-and-return loses your place in the Index panel.

## Locked decisions

| # | Locked |
|---|---|
| 1 | Three layers (L1, L2, L3) as defined above. |
| 2 | L1 + L2 are always-on. No user toggle. The cost of in-memory state is trivial. |
| 3 | L3 is opt-in via `[ui] restore_last_view = true` in `~/.config/octopus/config.toml`. Default = false (cold-start behavior). |
| 4 | L3 storage: `~/.cache/octopus/ui-state.json`. **Cache-class** — disposable, follows XDG cache spec. Losing it is annoying for one session, never harmful. |
| 5 | Storage format: JSON (human-inspectable, no schema migration framework needed). |
| 6 | If the previously-hovered task/activity no longer exists on relaunch (deleted, archived, moved), cursor falls back to **the nearest sibling** in the same panel/bucket. Silent — no warning toast. |
| 7 | If the previously-active tab no longer exists (e.g. tab structure changed), fall back to Tab 0. Silent. |
| 8 | "Position" includes: active tab, active panel (Tab 0), cursor target (task slug for Focus/Board, activity id for Tab 0), scroll offset within the panel, filter string if any, collapse state of panels (Tab 0). |
| 9 | State is per-activity-context for Focus/Board (the cursor in Focus is the cursor in *this* activity's Focus) and global for Tab 0 (Index/Current/Nested are global views). |
| 10 | Writes to disk happen on quit + on tab switch (so a `kill -9` doesn't lose more than one transition). No write-on-every-keystroke. |
| 11 | **Per-activity shared cursor (bucket, slug)** — Focus and Board share a single cursor per activity. Switch Focus → Board → Focus for the same activity and the cursor follows by slug. Each view keeps its own scroll/active-pane state, but the *selected task* is shared. Encoded as `ViewState.activity_cursors[<activity_id>] = ActivityCursor(bucket, slug)`. |

## Scope

### In

- In-memory `ViewState` model — single source of truth for cursor + view position across the TUI.
- Per-tab cursor restore on tab entry.
- Per-panel cursor restore on panel entry (Tab 0).
- Active-tab restore on app launch when L3 is enabled.
- Stale-target fallback: nearest-sibling in panel order.
- Config flag `[ui] restore_last_view = bool` with `false` default.
- JSON serializer + loader for `ui-state.json`.
- Cache-dir creation if missing.
- `octopus tui --no-restore` flag to bypass L3 for one run (forces cold start; doesn't change config).
- `octopus tui --reset-view` flag to delete the cache file before launching.
- Tests: simulate tab switches, simulate restart with stale slug, simulate restart with missing config flag.

### Out

- Multi-window / multi-session state. Single-process model only.
- Sync across machines (would require non-cache storage and conflict resolution).
- Per-day or per-project history (only "last position," not a stack of recent positions).
- Cursor restoration *during* a tab session if the underlying data changes (e.g. another process modifies a task — the cursor doesn't chase). State is captured on transitions, not live.
- Search query history (out — search is its own thing if it ships).
- Visual scroll position pixel-precision — line-precision only.

## Model

```python
@dataclass
class TabState:
    tab_id: str                                # "activities" | "focus" | "board" | ...
    # Per-panel cursor map. For Focus this is bucket→slug ({"now": "do-thing"}).
    # For Activities this is panel→activity_id ({"index": "octopus-aaaa"}).
    # For Board same as Focus.
    cursors: dict[str, str] = field(default_factory=dict)
    active_panel: str | None = None            # which panel is currently focused
    scroll_offsets: dict[str, int] = field(default_factory=dict)  # per-panel scroll
    filter: str | None = None
    collapsed_panels: list[str] = field(default_factory=list)
    activity_id: str | None = None             # Focus/Board: which activity this is for

@dataclass
class ViewState:
    active_tab: str = "activities"
    per_tab: dict[str, TabState] = field(default_factory=dict)
    schema_version: int = 1
```

Cursor and scroll are **per-panel** to handle the Activities view (3 panels) and Focus's quadrants (3 buckets) uniformly. `active_panel` tells the restorer which pane to focus when re-entering the tab.

`per_tab` keys for Focus/Board are namespaced by activity id (`focus:octopus-aaaa`, `board:octopus-aaaa`) so the cursor in project A's Focus doesn't pollute project B's.

## Storage format

```json
{
  "schema_version": 1,
  "saved_at": "2026-05-26T14:30:00Z",
  "active_tab": "focus:octopus-aaaa",
  "per_tab": {
    "activities": {
      "tab_id": "activities",
      "cursors": {"index": "octopus-aaaa"},
      "active_panel": "index",
      "scroll_offsets": {"index": 0},
      "collapsed_panels": ["nested"]
    },
    "focus:octopus-aaaa": {
      "tab_id": "focus",
      "activity_id": "octopus-aaaa",
      "cursors": {"now": "implement-h-header-mode-cycle"},
      "active_panel": "now",
      "scroll_offsets": {"now": 2}
    }
  }
}
```

`saved_at` is informational only — not used for validation. Schema version is the only field the loader gates on. Unknown future fields are preserved on round-trip.

## Module layout

```
cli/src/octopus/tui/
├── state/
│   ├── __init__.py
│   ├── model.py          # ViewState, TabState dataclasses
│   ├── persistence.py    # load(), save(), cache_path()
│   └── resolve.py        # stale-target fallback (nearest-sibling)
```

`OctopusApp` holds a single `ViewState` instance. Every tab widget reads its `TabState` on entry, writes on exit. The app writes to disk on tab transitions and on quit (if L3 enabled).

## Config

`~/.config/octopus/config.toml`:

```toml
[ui]
restore_last_view = true   # default false
```

When false: app boots with empty `ViewState`, never reads cache file. L1 + L2 still work in-memory for the session.

When true: app reads cache file on boot, populates `ViewState`. Writes back on quit + tab switches.

CLI overrides:
- `octopus tui --no-restore` — force false for this run
- `octopus tui --reset-view` — delete cache file, then run as if false (next save will write fresh)

## Fallback rules (stale targets)

| Stale element | Fallback |
|---|---|
| Cursor target task doesn't exist | Nearest sibling in bucket order (down first, then up) |
| Cursor target activity doesn't exist | Nearest sibling in panel order (down first) |
| Active tab no longer exists | Tab 0 (Activities) |
| Active panel no longer exists | First panel of the active tab |
| Active activity_id doesn't exist (for Focus/Board namespaced state) | Drop that TabState entry; fall back to active_tab = "activities" |
| Cache file unreadable / wrong schema | Discard; cold-start; do not crash |

All fallbacks are silent. No toast, no log to stderr, no banner. The user sees a sensible position; they don't need to know why.

## Method

1. Write this PLAN.md (✓).
2. Generate `TASKS.md`.
3. Define `ViewState` + `TabState` model. Unit tests for round-trip serialize/deserialize.
4. Implement `persistence.py` — cache path resolution, JSON IO, error swallowing for unreadable cache.
5. Implement `resolve.py` — nearest-sibling fallback. Unit tests with deleted slugs.
6. Wire `ViewState` into `OctopusApp` as a singleton. Inject into existing tab widgets (Focus, Board); they currently track their own cursor in widget-local state. Replace.
7. Add tab-switch hook: on switch, write current tab's state into `ViewState`, then read next tab's state from `ViewState`, restore cursor + scroll.
8. Add quit hook: if `restore_last_view = true`, write to disk.
9. Add boot hook: if `restore_last_view = true` and cache exists, load. Else empty.
10. Add CLI flags `--no-restore` and `--reset-view` to `octopus tui`.
11. Sync `CLI-VERBS.md` (the new flags) + skill mirror.
12. Add `[ui]` config schema docs.
13. Test matrix: 4 scenarios × 3 cursor states (present / missing / archived).
14. CHANGELOG entry.
15. Close request.

## Risks

- **State corruption survives across sessions.** If a buggy write produces an unparseable cache file, the user might restart octopus repeatedly into a broken state. Mitigation: every loader call wraps in try/except and silently falls back to empty state. The `--reset-view` flag is the user's recovery button.
- **Race condition on quit.** If octopus is killed during a tab-switch write, the cache file could be half-written. Mitigation: atomic write (write to `ui-state.json.tmp`, then `os.replace()`).
- **Activity-namespaced keys grow unbounded.** Every visited activity creates a `focus:<id>` and `board:<id>` entry. Over years, the cache file could bloat. Mitigation: prune entries whose `activity_id` no longer exists in the index, at load time.
- **Out-of-order tab transitions.** If the user rapid-fire taps `1 2 1 2`, the in-memory state must be consistent. Mitigation: synchronous read-and-write on transition; no async deferral.
- **Coupling with request #43.** Tab 0 introduces new panel concepts. If #43 lands first, Tab 0 has naive default-to-top behavior; this request retrofits memory on top without #43 needing changes. If they land in opposite order, this request gates Tab 0's full UX. Order doesn't block correctness — both ship-as-coded.

## Deliverables

- `cli/src/octopus/tui/state/` module (3 files)
- `OctopusApp` integration — `ViewState` singleton + tab-switch/quit hooks
- `octopus tui --no-restore` + `--reset-view` flags
- `[ui] restore_last_view` config field documented
- `cli/tests/tui/test_view_state.py` — round-trip, fallback, namespacing tests
- Updated `CLI-VERBS.md` + skill mirror
- CHANGELOG entry under `[Unreleased]`

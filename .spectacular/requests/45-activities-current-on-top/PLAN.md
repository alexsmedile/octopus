---
status: done
priority: medium
owner: alex
updated: 2026-05-26
summary: "Reorder Activities (Tab 0) panels: CURRENT on top with a property-rich overview; INDEX below; NESTED last. When no current activity (e.g. opened from $HOME), the CURRENT panel still renders an empty hint and INDEX is the focused fallback panel."
related:
  - 43-activities-tab
  - 44-cursor-view-state-persistence
gates: []
---

# Activities — CURRENT on top with property overview

## Goal

Two changes to the Activities view (Tab 0):

1. **Reorder panels** vertically: `CURRENT → INDEX → NESTED` (was `INDEX → CURRENT → NESTED`).
2. **Property-rich CURRENT block**: when an activity is detected at cwd, the CURRENT panel renders an expanded overview — more properties than the standard 3-row `ActivityBlock`, because the CURRENT panel has more vertical space and only ever shows one item.
3. **Fallback focus**: when CURRENT is empty (no activity at cwd, e.g. `octopus tui` from `~`), the active panel on mount falls back to INDEX (not CURRENT).

## Why

- CURRENT is the "you are here" anchor. Putting it on top matches the diamond-glyph hierarchy where ◆ (filled) is the prominent active state.
- The standard 3-row block compresses properties into one dim line (`type · status   NOW n  NEXT n  BACKLOG n`). When the panel only ever holds *one* item — the current activity — there's room to surface more: priority, area, tags, last_reviewed, locations count, full path.
- Opening octopus from `~` currently focuses an empty CURRENT panel. The user wants INDEX as the sensible fallback so `Enter` does something useful immediately.

## Locked decisions

| # | Locked |
|---|---|
| 1 | Panel order: CURRENT (top) → INDEX (middle) → NESTED (bottom). |
| 2 | CURRENT renders an `ActivityOverview` block (new) instead of `ActivityBlock` when populated. Empty hint unchanged. |
| 3 | Overview properties shown (when present): title + short id, type · status · priority · area, bucket counts (NOW / NEXT / BACKLOG / DONE), tags, last_reviewed, full path. Omit any line whose values are all empty. |
| 4 | Initial focus rule: if CURRENT has an item → focus CURRENT; else focus INDEX. View-state restore (req #44) still wins if a saved `active_panel` exists. |
| 5 | Tab cycle order follows panel order: CURRENT → INDEX → NESTED → CURRENT (wraps). |
| 6 | View-state TabState `active_panel` values unchanged (`"index" | "current" | "nested"`) — only display order changes. |

## Scope

### In
- `ActivitiesScreen.compose()` reorders the `Vertical(...)` children.
- `self._panels` list reordered to `[current, index, nested]` so Tab cycling and indexing follow visual order.
- New `ActivityOverview(ListItem)` class — multi-row Static with optional rows.
- `_load_current()` returns `[ActivityOverview(...)]` instead of `[ActivityBlock(...)]`.
- `on_mount` fallback rule: if CURRENT has no `ActivityOverview` (only `_EmptyHint`), set `self._active_panel_idx = 1` (INDEX).
- View-state `_restore_from_view_state` order-agnostic — it already keys by panel id, not index.
- Tests: panel order, fallback when no current activity, overview rendering with all-fields and minimal-fields cases.

### Out
- Editing activity properties from the overview (read-only render).
- Sparkline / mini-charts of bucket counts.
- Changing the standard `ActivityBlock` rendering (INDEX/NESTED keep the 3-row form).

## Layout sketch

```
┌─ ▼ ◆ CURRENT (1) ──────────────────────────────────────────────┐
│ ▸ octopus  Octopus — folder-native task system                 │
│     project · active · high · personal                         │
│     NOW 3   NEXT 7   BACKLOG 12   DONE 41                      │
│     tags: tui, cli, infra                                      │
│     last reviewed: 2026-05-20                                  │
│     ~/vault/data/skills_db/octopus                             │
└────────────────────────────────────────────────────────────────┘
┌─ ▼ ◇ INDEX (24) ───────────────────────────────────────────────┐
│ ▸ act-one   Some activity                                      │
│     project · active   NOW 1  NEXT 0  BACKLOG 3                │
│     ~/path/to/act-one                                          │
│   act-two   Another                                            │
│     ...                                                        │
└────────────────────────────────────────────────────────────────┘
┌─ ▼ ◈ NESTED (0) ───────────────────────────────────────────────┐
│     (no sub-activities)                                        │
└────────────────────────────────────────────────────────────────┘
```

## Method

1. Add `ActivityOverview(ListItem)` to `activities_screen.py`, mirroring `ActivityBlock` API (`set_selected`, `activity_id`, `activity_path`) so cursor-restore and drill actions don't branch.
2. Build content as a single Static with `\n` (same workaround as ActivityBlock for Textual visual-cache).
3. Conditionally include rows: omit empty `tags`, omit empty `last_reviewed`, omit `area`/`priority` from the second line if both unset.
4. Reorder `compose()` Vertical children: `self._current, self._index, self._nested`.
5. Reorder `self._panels` list to `[self._current, self._index, self._nested]`.
6. In `on_mount` after `_refresh_all()`: if `view_state` did not provide an `active_panel`, use the fallback rule. Implementation: track whether restore set the panel; if not, inspect CURRENT panel for an `ActivityOverview` child and default to CURRENT (idx 0) or INDEX (idx 1) accordingly.
7. Tests under `cli/tests/tui/` — pure rendering tests that don't need a running Textual app where possible; for panel-order, assert `screen._panels[0].panel_id == "current"`.
8. Sync CHANGELOG `[Unreleased]`.
9. Close request → status: done.

## Deliverables

- `cli/src/octopus/tui/activities_screen.py` — `ActivityOverview` class, panel reorder, fallback focus rule
- Tests
- CHANGELOG entry under `[Unreleased]`

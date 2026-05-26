---
request: 43-activities-tab
updated: 2026-05-26
---

# Tasks — 43-activities-tab

## Spine
- [x] T1 — `switch_to_activities()` on OctopusApp + launch from outside any activity
- [x] T2 — `ActivitiesScreen` skeleton + bindings
- [x] T3 — `ActivityBlock` 3-row renderer (single Static, sidesteps Textual visual-cache edge case)
- [x] T4 — `0` binding on FocusScreen + BoardScreen

## Panels
- [x] T5 — `IndexPanel` (`list_activities()`, archived hidden by default)
- [x] T6 — `CurrentPanel` (resolves cwd, empty-state placeholder)
- [x] T7 — `NestedPanel` (walk-down, excludes self, bails on $HOME)

## Navigation
- [x] T8 — `Tab` / `Shift+Tab` cycles panel focus
- [x] T9 — `↑↓` moves cursor — wraps top↔bottom (per user request)
- [x] T10 — `Space` collapses / expands
- [x] T11 — `Enter` drills into FocusScreen
- [x] T12 — `Esc` from Focus/Board root prompts "Back to Activities?" via ConfirmModal
- [x] T13 — `r` refresh
- [x] T14 — `/` filter (basic wiring; full UX deferred)
- [x] T15 — `A` toggle include-archived

## Visuals
- [x] T16 — `◇ INDEX` / `◆ CURRENT` / `◈ NESTED` panel headers
- [x] T17 — Cursor `▸`
- [x] T18 — `▼` / `▶` panel-collapse indicators
- [x] T19 — Path shortening (`$HOME` → `~`, middle-truncate >60 chars)
- [x] T19b — Full chrome match with Focus/Board (HeaderBar + StatusBar + ActivitiesKeymapBar)
- [x] T19c — Activities-specific keymap chips (replaces task-mutation chips that don't apply)

## Smoke + tests
- [x] T20 — Smoke: launch from `~` → ActivitiesScreen renders
- [x] T21 — Smoke: launch from inside `octopus/` → ActivitiesScreen with Current populated
- [x] T22 — Smoke: full drill + esc + confirm + back round-trip
- [ ] T23 — Snapshot/unit tests for `ActivityBlock` rendering — deferred (smoke verified; pytest snapshot tests need fixture work for the index)

## Spec sync
- [x] T24 — `TUI-KEYS.md` (Activities view section + `0` binding + Esc back-confirm) + skill mirror
- [x] T25 — `TUI-GLYPHS.md` (◆ activated, ◈ added) + skill mirror
- [x] T26 — `DECISIONS.md` D101 (three-view shell) + D102 (diamond family)

## Close
- [x] T27 — CHANGELOG entry
- [x] T28 — `status: done` in PLAN.md

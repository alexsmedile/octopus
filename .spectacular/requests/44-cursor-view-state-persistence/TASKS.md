---
request: 44-cursor-view-state-persistence
updated: 2026-05-26
---

# Tasks — 44-cursor-view-state-persistence

## L1 + L2 — in-memory state (always-on)

- [x] T1 — `tui/state/model.py`: `TabState` + `ViewState` dataclasses with per-panel cursors + scroll
- [x] T2 — `tui/state/persistence.py`: cache path (`~/.cache/octopus/ui-state.json`, env override `OCTOPUS_CACHE_DIR`), atomic write, swallow-errors load
- [x] T3 — `tui/state/__init__.py`: public API exports
- [x] T4 — `OctopusApp.view_state` singleton (legacy `shared_cursor` kept for back-compat with Board's existing logic)
- [x] T5 — `OctopusApp._swap_top` captures outgoing screen's state via `capture_view_state()`
- [x] T6 — ActivitiesScreen reads its TabState on mount; restores active panel + cursor per panel + collapse state
- [x] T7 — ActivitiesScreen `capture_view_state()` writes cursors + active_panel + scroll_offsets + collapsed_panels
- [x] T8 — FocusScreen reads its TabState (keyed by `focus:<activity_id>`) on mount; restores active bucket + cursor in each bucket
- [x] T9 — FocusScreen `capture_view_state()` writes per-bucket cursors + active quadrant
- [x] T10 — BoardScreen reads/writes its TabState; ViewState wins over legacy shared_cursor

## L3 — disk persistence (opt-in)

- [x] T11 — Config: `[ui] restore_last_view` (default `false`)
- [x] T12 — App boot: if `restore_last_view` true → `load()` from cache, restore boot screen from `active_tab`
- [x] T13 — App quit: `OctopusApp.exit()` override captures + persists ViewState if L3 enabled
- [x] T14 — Atomic write (`.tmp` then `os.replace()`)
- [x] T15 — Unknown-field round-trip preservation

## Stale-target fallback

- [x] T16 — `resolve_cursor(target, candidates)` → first-fallback when missing
- [x] T17 — `resolve_cursor_with_index(target, candidates, previous_index)` → nearest-sibling, clamped
- [ ] T18 — Wire resolver into restore paths — *not needed yet*: current restore just scans for the slug/id; if absent the cursor stays where Textual put it (top). Resolver lives ready for the moment we want clamped-by-previous-index UX (deferred to follow-up).
- [ ] T19 — Skip orphan `focus:<id>` entries on load — *deferred*: doesn't crash today (cursors silently don't match anything), but worth a cache-pruning pass later.

## CLI flags

- [x] T20 — `octopus tui --no-restore` (force L3 off for this run)
- [x] T21 — `octopus tui --reset-view` (delete cache before launching)

## Tests

- [x] T22 — `tests/tui/state/test_state.py`: round-trip, unknown-field preservation
- [x] T23 — `tests/tui/state/test_state.py`: missing/corrupt/wrong-schema → empty state
- [x] T24 — `tests/tui/state/test_state.py`: resolve_cursor + resolve_cursor_with_index variants
- [x] T25 — Smoke: drill + Esc + confirm + back → cursor restored
- [x] T26 — Smoke: quit + relaunch with `restore_last_view=True` → cursor restored

## Spec sync

- [x] T27 — CLI-VERBS.md `octopus tui` entry with `--no-restore` / `--reset-view` + skill mirror
- [x] T28 — `[ui] restore_last_view` documented in CLI-VERBS.md

## Close

- [x] T29 — CHANGELOG entry
- [x] T30 — `status: done` in PLAN.md

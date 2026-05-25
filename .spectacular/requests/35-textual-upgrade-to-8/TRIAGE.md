---
request: 35-textual-upgrade-to-8
phase: 1
updated: 2026-05-25
---

# Phase 1 — Triage results

## Environment after `pip install -e .`

| Package | Version |
|---|---|
| textual | 8.2.7 |
| rich | 15.0.0 |
| rich-pixels | 3.0.1 |
| pillow | 11.3.0 |

## Import audit

All 12 TUI modules import cleanly — zero breakage:

```
from octopus.tui import (
    app, focus, board, header_bar, keymap_bar, status_bar,
    mascot, prompts, overlay, help, filter_bar, toast,
)
```

## Test suite

Initial run on Textual 8.2.7: **601 passed, 2 failed**. Both failures were pre-existing stale tests from the v0.9.7-rc1 visual redesign, not Textual API breakage:

| Test | Was | Now | Fix |
|---|---|---|---|
| `test_icons_are_plain_unicode_no_emoji` | `icons.SESSION` | retired for `icons.SESSION_RUN` | rename in test |
| `test_status_bar_setters` | `sb.activity_name` | renamed `sb.activity_id` | rename in test |
| `test_focus_row_rendering` | pin glyph `⚐` | pin glyph `*` (Slot 2) | swap in test |

After three one-line test fixes: **603/603 green**.

## API surface — concrete check

| Symbol used in our code | Status on 8.2.7 |
|---|---|
| `App.suspend()` | ✅ present (the whole point) |
| `App.compose()` | ✅ unchanged |
| `App.push_screen()` | ✅ unchanged |
| `Screen` | ✅ unchanged |
| `ModalScreen` | ✅ unchanged signature |
| `Binding(...)` | ✅ unchanged constructor |
| `reactive[T]` | ✅ unchanged |
| `Horizontal/Vertical/VerticalScroll/Container` | ✅ unchanged |
| `Static/Input/Label/ListView/ListItem` | ✅ unchanged imports |
| `Widget.render()` returning Rich Group | ✅ still works |
| `rich_pixels.Pixels.from_image()` | ✅ rich-pixels 3.0.1 on Rich 15.0 |

## CSS

`theme.tcss` (444 lines) parses without errors. No `$variable` syntax issues because we hex-inline everything.

## Verdict

The upgrade is **non-breaking for our codebase**. The portion of Textual we use (composition, modal screens, reactive widgets, static rendering, half-block pixels) stayed stable across the 0.46 → 8.x climb.

Phase 2 (port) is **not required**. Skip to Phase 3 (validation gate).

## Next step

- Commit the dep bump + three test fixes.
- Restore `e`/`E` edit handler (the `if hasattr(self.app, "suspend")` branch now always hits the success path; the fallback toast can be removed).
- Run the smoke test from `TASKS.md` Phase 3.

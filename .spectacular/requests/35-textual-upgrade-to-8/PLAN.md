---
status: done
priority: medium
owner: alex
updated: 2026-05-25
summary: "Upgrade Textual from 0.46 to latest 8.2.7. Unlocks App.suspend() (fixes `e`/`E` edit binding) and brings three years of bugfixes, but spans 1.0 + 8.x major breaks. Work on a branch (feat/textual-8x), validate every screen, then merge."
related:
  - 33-tui-visual-redesign (shipped — current TUI under test)
  - 34-tui-key-schema (shipped — keymap surface)
gates: []
---

# Upgrade Textual: 0.46 → 8.2.7

## Goal

Replace our pinned Textual `>=0.46` (resolved to 0.46.0) with `>=8.2.7`. The immediate driver is `App.suspend()`, missing in 0.46, which blocks the `e`/`E` edit-in-`$EDITOR` binding. The broader payoff is three years of bugfixes, modern CSS support (CSS variables, `$` syntax), the stable post-1.0 API, and unblocking later async-handler work.

This is **a framework upgrade, not a redesign**. The visual language, keybindings, and widget composition stay as they are. We chase API renames, event signature changes, and any CSS that the new parser rejects — nothing else.

## Why now

- `e`/`E` is the second-most-requested mutation in the TUI and silently no-ops on 0.46 (toast says "needs newer Textual").
- The v0.9.7-rc1 RC is the right window: the visual redesign just shipped, so the diff between "what worked" and "what regressed" is small.
- Skipping intermediate minors makes the climb harder later. The 0.x→8.x climb is one porting pass either way.

## Why a branch and not a fork

Git branches are snapshots. A fork doesn't add safety here — it just adds an extra remote. We work on `feat/textual-8x`, validate against `main`, merge when green.

Branch: `feat/textual-8x`, cut from `main` at v0.9.7-rc1.

## Non-goals

- No new features, no visual changes, no keybinding changes. Pure upgrade.
- No bump of `rich-pixels`, `pillow`, or other deps unless the new Textual demands it.
- No 1.0 release. Ships as `v0.9.8` after the RC is signed off.

## Known breakage surface (from a scan of `cli/src/octopus/tui/`)

Touchpoints: 76 across 11 files. 444-line TCSS. The Textual changes most likely to bite us, scored by likelihood:

| Area | Risk | Where it lives |
|---|---|---|
| `App.dark` → `App.theme` (1.0) | LOW | we don't reference it |
| `ListView` selection event renames (≥2.0) | MED | `focus.py`, `board.py` |
| `Binding.action` stricter validation (≥3.0) | LOW | all our actions are method names |
| `ModalScreen` lifecycle (≥4.0) | MED | `prompts.py`, `overlay.py`, `help.py`, `filter_bar.py` |
| `reactive[T]` typing (≥5.0) | LOW | `header_bar.py`, `status_bar.py` |
| `Widget.render()` return narrowing (≥6.0) | MED | `header_bar.py` returns rich `Group` |
| Async-preferred event handlers (≥7.0) | LOW | sync handlers still work, mostly |
| Rich version bump cascade (8.x) | **HIGH** | `rich-pixels` (mascot) is the wildcard |
| CSS `$var` parser tightening (≥0.74) | LOW | we hex-inline everything |

The two real unknowns are **rich-pixels compatibility** and **ModalScreen lifecycle**. Everything else is grep-and-rename work.

## Approach

Three phases. Each is small enough to revert.

### Phase 1 — Dependency upgrade and import audit (≤30 min)

1. Cut `feat/textual-8x` from `main`.
2. Bump `cli/pyproject.toml` constraint: `textual>=8.2,<9`.
3. `pip install -e .` in the venv, capture the new dep tree (especially Rich version).
4. Run `pytest -x` and capture the first failure.
5. Run `python -m octopus.tui.app` and capture the first crash (likely an import or attribute error).

Deliverable: a triage list of failing imports / events / attributes, ordered by where they live.

### Phase 2 — Port (1–2 hours)

Work the triage list top to bottom. For each entry:
- Identify the Textual changelog entry that explains the rename.
- Update the call site.
- Re-run the failing test or screen.

Focus zones, in order of expected friction:

1. **`focus.py` + `board.py`** — ListView event signatures, key bindings, screen lifecycle.
2. **`prompts.py` + `filter_bar.py` + `overlay.py` + `help.py`** — ModalScreen lifecycle, `dismiss()` signatures.
3. **`header_bar.py`** — `render() -> RenderResult` typing, reactive watch decorators.
4. **`mascot.py` (rich-pixels)** — if the new Rich breaks `Pixels.from_image()`, vendor a thin wrapper or pin `rich-pixels`.
5. **`theme.tcss`** — only touch what the new CSS parser rejects. Don't refactor speculatively.

Deliverable: every screen renders, full test suite green.

### Phase 3 — Validation gate (30 min)

Smoke test, in order:
1. `octopus tui` opens in Focus mode at default terminal size.
2. `H` cycles header modes (Full/Mid/Compact/Slim).
3. Arrow keys + Tab move focus across panes; bucket colors flip correctly on focus.
4. `n` captures, `m` moves, `f` finishes, `p` pins, `d` drops, `b`/`B` blocks/unblocks, `y` yanks, `g` goes to slug.
5. **`e` opens `$EDITOR`** — the whole point of the upgrade.
6. `,` toggles detail pane, scrolling works inside it.
7. `?` opens help overlay, Esc closes.
8. `/` filter modal opens, Enter applies, Esc closes.
9. `2` switches to Board mode; columns render; `1` returns.
10. Mascot animation still ticks (ambient interrupt fires within 90s of idle).
11. `q` quits cleanly with session-confirm prompt.

Deliverable: a 1-pager smoke-test report in this folder (`SMOKE.md`).

## Rollback plan

If Phase 2 stalls beyond two hours or Phase 3 reveals a regression we can't track in 30 minutes:
- Abandon `feat/textual-8x`.
- Reopen `04-edit-feature` (or new request) to fix `e`/`E` via the **manual-suspend** path (option 2 in the earlier triage): use `App._driver.stop_application_mode()` / `start_application_mode()` directly. Ugly but stays on 0.46.

Either way, no half-merged state on `main`.

## Definition of done

- `feat/textual-8x` merges to `main` cleanly.
- `pip show textual` reports 8.2.7+ in the install.
- All 603 existing tests pass.
- `SMOKE.md` checklist all-green.
- `e`/`E` opens `$EDITOR`, the user saves, returns, task body is updated, list refreshes.
- v0.9.8 cut after RC sign-off (separate `/wrap-up`).

## Out of scope

- Refactoring CSS to use Textual's `$variable` syntax (cleanup, not upgrade).
- Migrating sync handlers to async (lift it later if needed).
- Adopting any 8.x-only new widgets (DataTable improvements, etc.).
- Replacing `rich-pixels` with a different renderer.

## Open questions

- **Does rich-pixels work with the Rich version bundled by Textual 8.2?** Resolved in Phase 1 by inspecting `pip install` output.
- **Do we still need `Static.render() -> Group`?** If 8.x narrowed the return type, header_bar needs to switch to `RenderResult` (a union including Group). Resolved in Phase 2.
- **Does `Binding(... show=True)` still drive a built-in Footer?** We replaced Footer with our own `KeymapBar` in v0.9.7-rc1, so this should be a non-issue — but verify the `Binding` constructor signature didn't change.

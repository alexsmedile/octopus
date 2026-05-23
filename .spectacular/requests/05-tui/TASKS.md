---
status: active
updated: 2026-05-23
plan: PLAN.md
---

# Tasks — Textual TUI v1

Work top-to-bottom. Check off as you go. Each top-level group is one focused session.

## 1. Skeleton & CWD detection

- [ ] Add `textual` to `cli/pyproject.toml` runtime deps (latest stable; pin minor).
- [ ] Create `cli/src/octopus/tui/__init__.py` (empty) and `cli/src/octopus/tui/app.py` (Textual `App` subclass stub).
- [ ] Add `octopus tui` Typer command in `cli/src/octopus/cli.py`. Defer `from octopus.tui.app import OctopusApp` import inside the command body (startup cost: never pay Textual import if not running TUI).
- [ ] Reuse the existing CWD-detection helper used by `octopus where`. If no `.octopus/` is found, exit with the same error message + exit code (2) as `where`.
- [ ] App boots into a stub Focus screen with the activity name in the header and `q` to quit. Smoke test: launch + quit returns 0.

## 2. Theme & design system

- [ ] Create `cli/src/octopus/tui/theme.css` (Textual CSS). Define all palette variables from PLAN ($primary, $accent, $warning, $error, $secondary, $surface, $panel, $text, $text-muted).
- [ ] Wire light/dark auto-switch via `App.dark` + `$TEXTUAL_THEME` env honor.
- [ ] Define reusable classes: `.panel` (rounded border, padding 1 2), `.panel--focused` (border $primary), `.row--selected` ($primary 15% bg), `.chip--tab` (rounded pill), `.chip--tab--active` ($primary bg).
- [ ] Define icon constants in `tui/icons.py`: `NOW=●`, `NEXT=○`, `DONE=✓`, `DROPPED=✗`, `PINNED=⚐`, `BLOCKED=⏸`, `CURSOR=▸`, `SESSION=◆`, `SPINNER=⟳`. Plain unicode only — no emoji, no Nerd Font dependency.
- [ ] Status bar widget: three-zone layout (activity left, state center, hints right). Wire bucket counts from index.

## 3. Focus mode — read-only

- [ ] `tui/focus.py` — `FocusScreen` with two stacked panels: `NowList` (top), `OnDeckRow` (bottom, compact).
- [ ] Load tasks from SQLite index, scoped to current activity.
- [ ] Sort: pinned-first within `now`, then by `updated` desc.
- [ ] Render rows with cursor glyph + title + axis chips (right-aligned, dim).
- [ ] Arrow-key nav (`↑`/`↓`) on now-stack. Selection visual per theme spec.
- [ ] `OnDeckRow`: read-only horizontal row, one-line task titles separated by `·`, truncated with ellipsis.
- [ ] Empty-state hints for both panels (per PLAN tone).
- [ ] `Enter` / `→` open overlay; `Esc` / `←` close.

## 4. Detail overlay

- [ ] `tui/overlay.py` — `TaskDetailOverlay` modal. Centered, ~70% width, rounded border, scrollable body.
- [ ] Renders: title, axis chips, body markdown, session log (last 5), memory entries (last 5).
- [ ] Open/close fade + slide animation (150ms / 100ms per PLAN).
- [ ] `Esc` closes; preserves now-stack cursor position.

## 5. Mutation keymap

- [ ] Define a thin `octopus.actions` module — single entry per verb (`start`, `finish`, `drop`, `move`, `edit`, `capture`, `pin`, `unpin`). Both CLI Typer commands and TUI call this layer. Refactor existing CLI commands to call it.
- [ ] Wire `s` / `S` (session start: quick / picker+note).
- [ ] Wire `f` / `F` (finish: quick / with closing note). Pulse animation on row before relocation.
- [ ] Wire `n` (inline capture: blank row at top of current section, cursor inside, Enter commits, Esc cancels).
- [ ] Wire `N` (full overlay capture: title + bucket + axes + body).
- [ ] Wire `m` / `M` (move bucket: quick → next in pipeline / picker).
- [ ] Wire `e` (open in `$EDITOR`, suspend TUI, restore + reindex on exit).
- [ ] Wire `d` (drop with y/n confirm modal; coral pulse before removal).
- [ ] Wire `p` (toggle pin; `⚐` glyph fade in/out 100ms; no row jump until next sort pass).

## 6. Board mode

- [ ] `tui/board.py` — `BoardScreen`, four-column kanban (`backlog`, `next`, `now`, `done`). Equal column widths v1.
- [ ] Arrow-key nav within and across columns. Tab/Shift-Tab as alternate column jump.
- [ ] Same overlay reuse for detail.
- [ ] Same keymap operates on the focused column. `n` capture inserts at top of focused column.
- [ ] Mode switcher tab chips in header. `1` = Focus, `2` = Board. Active tab styled per theme.

## 7. Filter, help, refresh

- [ ] `/` opens filter input bar (slides up from bottom, 120ms). Live title-substring match, case-insensitive. Esc cancels + restores; Enter commits.
- [ ] Filter scope: visible tasks only (Focus = now+next; Board = all 4 columns).
- [ ] `r` triggers reindex + refresh. Status bar shows `⟳ reindexing…` rotating spinner, fades to `ready` on completion.
- [ ] `?` opens help overlay (centered modal, two-column grouped keybindings).

## 8. Polish & ship

- [ ] Quit confirmation (`q`): if an active session is open, prompt y/n.
- [ ] Error states: broken task file (unparseable YAML) → render row with `⏸` glyph + dim title + error tooltip on Enter.
- [ ] Snapshot tests (Textual snapshot harness): Focus empty, Focus with tasks, Focus with overlay, Board, filter active, help modal. Pin terminal size 120×40.
- [ ] Smoke tests: each mutation keybinding calls the right `octopus.actions` function with the right args.
- [ ] README section: "Daily driver — the TUI" with keymap table + one screenshot.
- [ ] Update `skills/octopus/references/cli-verbs.md` if any verb signatures shifted during the `octopus.actions` refactor.

## Sign-off

- [ ] Manual run-through on a real activity: capture 3 tasks, start a session, finish one, move one, drop one, pin one, switch modes, filter, reindex, quit.
- [ ] Set PLAN.md `status: done`. Append D-entry to `.spectacular/DECISIONS.md` summarizing locked decisions (Focus+Board, mode-switching, theme palette, `octopus.actions` shared layer).

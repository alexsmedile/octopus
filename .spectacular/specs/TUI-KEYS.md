# TUI-KEYS — Keybinding schema

Authoritative spec for the Octopus TUI keybindings (Focus + Board modes). Locked by request [34-tui-key-schema](../requests/34-tui-key-schema/PLAN.md). Companion to [TUI-GLYPHS.md](TUI-GLYPHS.md).

## Principles

1. **Single keystroke per verb.** No chord bindings, no macros. Octopus is a one-key TUI by design.
2. **Verbs only.** Mnemonic from the action, not the object. `n` = capture, not `t` = task.
3. **Capital pair = inverse.** `s`/`S`, `m`/`M`, `b`/`B`, `f`/`F` — capital is the more specific or inverse variant.
4. **ASCII-only chip labels.** Non-letter keys render as 2-3 char text: `CR` `TAB` `ESC`. Arrows use Unicode geometric (`←` `→` `↑` `↓`) — same family as the locked glyph set.
5. **Same map in both modes.** Focus and Board share the keymap; pane semantics differ but verbs don't.
6. **Mutations route through `octopus.actions`.** No second write path. The TUI is a renderer.

## Navigation

| Key | Action |
|---|---|
| `1` | Switch to Focus mode |
| `2` | Switch to Board mode |
| `←` `→` | Move between panes (Focus) / columns (Board) |
| `↑` `↓` | Move within list; edge presses spill into the adjacent pane |
| `Tab` `S-Tab` | Cycle panes forward / backward |
| `Enter` | If Detail pane is visible: focus it. If collapsed: open it (= `,`). |
| `Esc` | Close overlay / clear filter |
| `,` | Toggle Detail pane (open ↔ collapsed) |
| `g` | Go-to slug (prompts) |

### Pane spill rules (Focus)

- `↑` at the top of NEXT jumps into NOW (last row).
- `↓` at the bottom of NOW jumps into NEXT (first row).
- `←` from any pane walks toward BACKLOG.
- `→` from any pane walks toward DETAIL (if visible).

### Detail pane visibility (Focus)

- Default open at ≥120 cols (terminal width).
- Default collapsed below 120 cols.
- `,` toggles regardless of width. Preference does not persist — re-evaluates per session.

## Mutations

All mutations route through `octopus.actions`. The TUI optimistically refreshes the index after each mutation; failures surface as toast errors and revert.

| Key | Action |
|---|---|
| `n` | Capture new task into the focused pane |
| `m` | Advance pipeline step (`backlog → next → now → done`) |
| `M` | Move to a chosen bucket (prompts) |
| `f` | Finish task (moves to `done/`, stamps `end_date`, clears `pinned`) |
| `d` | Drop (with `y/n` confirm) |
| `p` | Toggle pin |
| `b` | Block (prompts for reason) |
| `B` | Unblock |
| `e` | Edit in `$EDITOR` |
| `s` | Session start (quick) |
| `S` | Session start (titled, prompts) |
| `u` | Undo last mutation |
| `y` | Yank slug to clipboard |

## Search & system

| Key | Action |
|---|---|
| `/` | Filter by title substring |
| `r` | Refresh from index + clear filter |
| `?` | Help overlay (full keymap) |
| `q` | Quit (confirms if a session is open) |

## Status-bar chip set (responsive)

The status bar at the bottom of the TUI shows colored key chips. The visible subset is responsive to terminal width. `?` always reveals the complete keymap.

| Width | Chips shown |
|---|---|
| narrow (<100 cols) | `n` `m` `f` `p` `d` `?` `q` (7 chips) |
| medium (100-119) | `n` `m` `f` `p` `d` `b` `CR` `?` `q` (9 chips) |
| wide (≥120 cols) | `n` `m` `f` `p` `d` `b` `CR` `,` `/` `?` `q` (11 chips) |

### Chip colors

| Key | Glyph | Chip color | Mnemonic |
|---|---|---|---|
| `n` | `n` | lavender `#CBA6F7` | capture |
| `m` | `m` | now-yellow `#FACC15` | move → |
| `f` | `f` | done-green `#86EFAC` | finish |
| `p` | `p` | next-teal `#5EEAD4` | pin |
| `d` | `d` | drop-pink `#F38BA8` | drop |
| `b` | `b` | drop-pink `#F38BA8` | block |
| `,` | `,` | lavender `#CBA6F7` | detail (aside) |
| `CR` | `CR` | grey `#3A3D48` | open |
| `TAB` | `TAB` | grey `#3A3D48` | pane |
| `ESC` | `ESC` | grey `#3A3D48` | close |
| `/` | `/` | grey `#3A3D48` | filter |
| `?` | `?` | grey `#3A3D48` | help |
| `q` | `q` | grey `#3A3D48` | quit |
| `←→↑↓` | `←→↑↓` | grey `#3A3D48` | navigate |

## Help overlay (`?`)

Pressing `?` opens a full-screen overlay listing every binding grouped by Navigation / Mutations / Search & System. Dismiss with `Esc` or `?` again.

## Behavior contracts

### `,` (detail toggle)

- If Detail pane is collapsed: open it (animates in from the right).
- If Detail pane is open: collapse it (animates out).
- Focus stays on the previously-focused list pane.

### `Enter` (focus or open detail)

- If Detail pane is **visible**: shift focus to the Detail pane (allow scrolling, Esc to return).
- If Detail pane is **collapsed**: same as `,` — open it. Focus moves to the Detail pane on first open.

### `u` (undo)

- Reverses the most recent mutation in the session (e.g. last drop, last move, last finish).
- Bounded by the actions-layer audit log; stack depth is `octopus.actions.UNDO_DEPTH` (default 32).
- Shows toast: `↩ undone: <verb> on <slug>`.
- `u` while the stack is empty: toast `nothing to undo`.

### `y` (yank slug)

- Copies the currently-selected task's slug to the system clipboard.
- Uses `pbcopy` on macOS, `xclip`/`wl-copy` on Linux, `clip.exe` on Windows.
- Falls back to printing the slug to a toast if no clipboard tool is available.

### `q` (quit)

- If an active session is open on the current activity: prompt `Quit while session <id> is open? (y/N)`.
- Otherwise: exit immediately.

## Conflicts with terminal multiplexers

- `Tab` and `S-Tab` are intercepted by Octopus. tmux's default `C-b` prefix is unaffected.
- No `Ctrl+*` bindings — those are flaky across multiplexers and avoided by design.
- `Esc` is not used for chorded sequences; it's a single-press close.

## Migration from pre-locked behavior

| Was | Becomes |
|---|---|
| `d` = drop | `d` = drop (unchanged) |
| (no key) = detail toggle | `,` = detail toggle |
| `b` = block (doc only, not wired) | `b` = block (wired) |
| `u` = unblock (doc only, not wired) | `B` = unblock |
| (no key) = undo | `u` = undo |
| (no key) = yank slug | `y` = yank |
| `Enter` = overlay only | `Enter` = focus / open Detail pane |

## Implementation contract

Bindings live in `cli/src/octopus/tui/focus.py` and `cli/src/octopus/tui/board.py` as Textual `Binding(...)` declarations. Both files must declare an identical set (this is enforced by a unit test that compares the two binding tables).

The help overlay text is generated from a single in-code table (`cli/src/octopus/tui/help.py::KEY_TABLE`) — never hand-maintained markdown. This spec is its source of truth for the labels and groupings.

## See also

- [TUI-GLYPHS.md](TUI-GLYPHS.md) — companion spec for the read-side glyph vocabulary
- [CLI-VERBS.md](CLI-VERBS.md) — the CLI verbs the TUI delegates to
- [DECISIONS.md](../DECISIONS.md) — locked decisions D1-D7
- [docs/KEYS.md](../../docs/KEYS.md) — public-facing mirror (lighter prose)

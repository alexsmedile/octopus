# TUI keys — v1

Keybinding map for the Octopus TUI. Same map in Focus and Board modes.

Mirror of `.spectacular/specs/TUI-KEYS.md` — operational subset. Keep in sync.

## Principles

1. **One keystroke per verb.** No chords, no macros.
2. **Verbs not objects.** `n` = capture, not `t` = task.
3. **Capital = inverse / specific.** `s`/`S`, `m`/`M`, `b`/`B`, `f`/`F`.
4. **ASCII chip labels.** Non-letters render as `CR` `TAB` `ESC`. Arrows use Unicode (`← → ↑ ↓`).
5. **Same map both modes.** Focus + Board share the table.
6. **Mutations route through `octopus.actions`.** TUI is a renderer only.

## Navigation

| Key | Action |
|---|---|
| `0` | Activities view (cross-activity) |
| `1` | Focus mode |
| `2` | Board mode |
| `←` `→` | Move between panes (Focus) / columns (Board) |
| `↑` `↓` | Move within list; edge presses spill across panes |
| `Tab` `S-Tab` | Cycle panes forward / back |
| `Enter` | If Detail visible: focus it. If collapsed: open it (= `,`). |
| `Esc` | Close overlay / clear filter. From Focus/Board root: confirm "Back to Activities?" |
| `,` | Toggle Detail pane |
| `g` | Go-to slug (prompts) |

### Activities view (`0`)

| Key | Action |
|---|---|
| `Tab` `S-Tab` | Cycle panel focus: INDEX → CURRENT → NESTED (wraps) |
| `↑` `↓` | Move cursor; wraps top↔bottom within panel |
| `Enter` | Drill into highlighted activity → Focus mode for it |
| `Space` | Collapse / expand active panel |
| `r` | Refresh |
| `/` | Filter INDEX |
| `A` | Toggle include-archived in INDEX |
| `1` `2` | Drill into highlighted activity → Focus or Board |

### Pane spill rules (Focus)

- Right column: **NEXT (top) → NOW (bottom)** — pipeline funnels downward
- `↑` at top of NOW jumps to NEXT (last row)
- `↓` at bottom of NEXT jumps to NOW (first row)
- `←` walks toward BACKLOG
- `→` walks toward DETAIL (if visible)

### Detail pane visibility

- Default open at ≥120 cols; collapsed below 120.
- `,` toggles regardless of width.
- Preference does not persist across sessions.

## Mutations

All route through `octopus.actions`. Optimistic refresh; failures toast + revert.

| Key | Action |
|---|---|
| `n` | Capture new task into focused pane |
| `m` | Advance pipeline (`backlog → next → now → done`) |
| `M` | Move to chosen bucket (prompts) |
| `f` | Finish (→ `done/`, stamps `end_date`, clears `pinned`) |
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
| `r` | Refresh + clear filter |
| `?` | Help overlay |
| `q` | Quit (confirms if session is open) |

## Keymap bar (responsive)

The bottom bar shows colored key chips. Visible subset varies by terminal width. `?` always reveals full keymap.

| Width | Chips |
|---|---|
| narrow (<100) | `n` `m` `f` `p` `d` `?` `q` (7) |
| medium (100-119) | `n` `m` `f` `p` `d` `b` `CR` `?` `q` (9) |
| wide (≥120) | `n` `m` `f` `p` `d` `b` `CR` `,` `/` `?` `q` (11) |

### Chip colors

| Key | Color | Mnemonic |
|---|---|---|
| `n` | lavender `#CBA6F7` | capture |
| `m` | now-yellow `#FACC15` | move → |
| `f` | done-green `#86EFAC` | finish |
| `p` | next-teal `#5EEAD4` | pin |
| `d` | drop-pink `#F38BA8` | drop |
| `b` | drop-pink `#F38BA8` | block |
| `,` | lavender `#CBA6F7` | detail |
| `CR` | grey `#3A3D48` | open |
| `TAB` | grey `#3A3D48` | pane |
| `ESC` | grey `#3A3D48` | close |
| `/` | grey `#3A3D48` | filter |
| `?` | grey `#3A3D48` | help |
| `q` | grey `#3A3D48` | quit |
| `←→↑↓` | grey `#3A3D48` | navigate |

## Behavior contracts

### `,` (detail toggle)

- Collapsed → open (animates from right).
- Open → collapse (animates out).
- Focus stays on previously-focused list pane.

### `Enter`

- Detail **visible** → shift focus to Detail (scrollable, Esc returns).
- Detail **collapsed** → open it (same as `,`), focus moves to Detail.

### `u` (undo)

- Reverses most recent mutation in session.
- Stack depth: `octopus.actions.UNDO_DEPTH` (default 32).
- Toast on success: `↩ undone: <verb> on <slug>`.
- Empty stack: toast `nothing to undo`.

### `y` (yank slug)

- Copies selected slug to clipboard.
- `pbcopy` (macOS) / `xclip` or `wl-copy` (Linux) / `clip.exe` (Windows).
- Fallback: print to toast.

### `q` (quit)

- If session open on current activity: confirm `Quit while session <id> is open? (y/N)`.
- Otherwise: exit immediately.

## Multiplexer compatibility

- `Tab` / `S-Tab` intercepted by Octopus. tmux `C-b` prefix unaffected.
- No `Ctrl+*` bindings (flaky across multiplexers).
- `Esc` is single-press only; no chord sequences.

## Implementation contract

Bindings: `cli/src/octopus/tui/focus.py` + `cli/src/octopus/tui/board.py` as Textual `Binding(...)`. Both must declare identical sets (enforced by unit test).

Help overlay text generated from `cli/src/octopus/tui/help.py::KEY_TABLE` — never hand-maintained markdown.

Keymap bar widget: `cli/src/octopus/tui/keymap_bar.py` — owns per-chip colors.

## See also

- `tui-glyphs.md` — read-side glyph vocabulary
- `cli-verbs.md` — verbs the TUI delegates to

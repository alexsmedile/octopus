# Keys & Glyphs

The Octopus TUI uses a small, consistent vocabulary for **what tasks look like** (glyphs) and **what you press to change them** (keys). Two layers, one mental model.

This page is the public-facing companion to the authoritative specs:
- [`.spectacular/specs/TUI-GLYPHS.md`](../.spectacular/specs/TUI-GLYPHS.md) — glyph dictionary
- [`.spectacular/specs/TUI-KEYS.md`](../.spectacular/specs/TUI-KEYS.md) — keybinding schema

## Glyphs (the read layer)

Each row in the TUI looks like:

```
  ◐  fix the webhook auth bug                *!   code · 2h
  └─ status glyph                            └─ flags    └─ kind · age
```

### Status (one per row)

A single glyph encodes how far along the task is. The **color** tells you the bucket (backlog, next, now, done).

| Glyph | Meaning |
|---|---|
| `·` | parked / idle (in backlog, no work started) |
| `○` | open |
| `◐` | halfway |
| `◑` | most-done |
| `●` | done |
| `▶` | session is actively running on this task |
| `✕` | dropped |
| `!` | blocked |
| `?` | waiting |
| `+` | migrated (moved into another system) |

Higher-priority states (`!`, `?`, `▶`) override the progress ladder.

### Flags (after the title, up to 3)

| Glyph | Meaning |
|---|---|
| `*` | pinned |
| `!` | high priority |
| `:` | has references |
| `^` | has linked session log |
| `&` | scheduled (has a date) |
| `#` | tagged |

### Customize

Glyphs are tunable per-activity or per-user via `.octopus/config.yaml`:

```yaml
ui:
  glyphs:
    style: collapsed         # collapsed (default) | combined | minimal
    progress_stages: 4       # 2 | 3 | 4 — how many circle states
    use_color: true
```

`minimal` drops to pure ASCII (`· o O X`) for monochrome terminals or scripts.

## Keys (the write layer)

All mutations route through the same code path as the CLI — there's no second source of truth.

### Navigate

| Key | What |
|---|---|
| `1` | Focus mode |
| `2` | Board mode |
| `←` `→` | move between panes / columns |
| `↑` `↓` | move within a list (edges spill to adjacent pane) |
| `Tab` `S-Tab` | cycle panes |
| `Enter` | focus or open the Detail pane |
| `Esc` | close overlay / clear filter |
| `,` | toggle Detail pane (open ↔ collapsed) |
| `g` | go to slug (prompts) |

### Mutate

| Key | What |
|---|---|
| `n` | capture new task |
| `m` | advance the pipeline (`backlog → next → now → done`) |
| `M` | move to a chosen bucket |
| `f` | finish |
| `d` | drop (with `y/n` confirm) |
| `p` | toggle pin |
| `b` | block (prompts reason) |
| `B` | unblock |
| `e` | edit in `$EDITOR` |
| `s` / `S` | session start (quick / titled) |
| `u` | undo last mutation |
| `y` | yank slug to clipboard |

### Search & system

| Key | What |
|---|---|
| `/` | filter by title |
| `r` | refresh + clear filter |
| `?` | help overlay (full keymap) |
| `q` | quit (confirms if a session is open) |

## Status-bar chips

The bar at the bottom shows colored chips for the most common keys. The chip set is **responsive** to your terminal width:

| Width | Chips |
|---|---|
| narrow (<100 cols) | `n m f p d ? q` |
| medium (100-119) | `n m f p d b CR ? q` |
| wide (≥120 cols) | `n m f p d b CR , / ? q` |

Press `?` any time for the full keymap.

## See also

- [TUI.md](TUI.md) — TUI modes, scope rules, and the write layer
- [`.spectacular/specs/TUI-GLYPHS.md`](../.spectacular/specs/TUI-GLYPHS.md) — authoritative glyph spec
- [`.spectacular/specs/TUI-KEYS.md`](../.spectacular/specs/TUI-KEYS.md) — authoritative key spec

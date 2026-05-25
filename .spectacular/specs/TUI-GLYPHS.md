# TUI-GLYPHS — Status & flag glyph dictionary

Authoritative spec for the visual vocabulary used by the Octopus TUI and (opt-in) the CLI. Locked by request [34-tui-key-schema](../requests/34-tui-key-schema/PLAN.md). Companion to [TUI-KEYS.md](TUI-KEYS.md).

## Model

Each task row exposes **three positional slots**:

```
  ◐  fix the webhook auth bug                *!:   code  ~2h
  └─ status glyph                            └─ flag glyphs (≤3)   └─ kind · age
  (slot 1, single cell)                      (slot 2, ≤3 cells)    (slot 3, dim)
```

- **Slot 1 — status glyph.** Exactly one. Carries progress along a 4-stage circle ladder; bucket axis comes from row color and (in the TUI) the pane the row lives in. Exception states (`▶` `!` `?` `✕` `+`) break the ladder.
- **Slot 2 — flag glyphs.** Zero to three. Independent boolean flags (pinned, priority, references, etc.). Cap at 3; overflow collapses to `…` and surfaces in the Detail pane.
- **Slot 3 — meta suffix.** Dim grey, right-aligned: `kind` chip + `age` (e.g. `code · 2h ago`). Already shipped; documented here for completeness.

## Slot 1 — Status glyphs

| Glyph | State | When | Color |
|---|---|---|---|
| `·` | parked / idle | `bucket=backlog` AND `progress` is null | dim grey |
| `○` | open | `progress` rounds to 0 (and not parked) | bucket color |
| `◐` | half | `progress` rounds to 0.5 | bucket color |
| `◑` | most-done | `progress` rounds to 0.75+ (only when `progress_stages: 4`) | bucket color |
| `●` | done | `bucket=done` (terminal state) | done-green |
| `▶` | session live | `session_id` is set on the task | now-yellow, bold |
| `✕` | dropped | `bucket=dropped` | drop-pink, dim |
| `!` | blocked | `run_state=blocked` | drop-pink |
| `?` | waiting | `issue=waiting` | drop-pink |
| `+` | migrated | `promoted_to` is set | lavender |

### Precedence (highest wins)

When multiple states apply, the higher-precedence glyph wins. A task that is `blocked` AND has progress=0.5 shows `!`, not `◐`.

1. `!` blocked
2. `?` waiting
3. `▶` session live
4. `+` migrated
5. `●` done (terminal bucket)
6. `✕` dropped (terminal bucket)
7. Progress ladder: `·` parked → `○` open → `◐` half → `◑` most → (`●` is the top of the ladder, already at level 5)

### Bucket axis

Color carries the bucket in the collapsed (default) variant. Pane context reinforces it in the TUI: rows in the Backlog pane look uniformly muted; rows in the Now pane share the yellow accent.

| Bucket | Color |
|---|---|
| backlog | `#7AB8FF` (or muted grey for fully-idle rows) |
| next | `#5EEAD4` |
| now | `#FACC15` |
| done | `#86EFAC` |
| dropped | `#F38BA8` (dim) |

## Slot 2 — Flag glyphs

Independent boolean flags. Rendered after the title, before the meta suffix. Cap at 3.

| Glyph | Flag | Color | Source field |
|---|---|---|---|
| `*` | pinned | next-teal | `pinned: true` |
| `!` | priority high | drop-pink | `priority: high` |
| `:` | has references | lavender | `refs:` non-empty |
| `^` | has linked session | next-teal | any session log exists |
| `&` | scheduled | now-yellow | `scheduled_for` is set |
| `#` | tagged | dim grey | `tags:` non-empty |

### Slot-collision note

`!` appears in both slot 1 (blocked) and slot 2 (priority high). This is intentional and unambiguous because the slots sit in different columns. Renderers must never collapse the slots into one cell.

## Detail pane — KV value glyphs

In the Detail pane's frontmatter key/value grid, the value is prefixed with the slot-1 glyph for the relevant field:

| Field | Value rendering |
|---|---|
| `bucket` | `· backlog` / `○ next` / `◐ now` / `● done` / `✕ dropped` |
| `pinned` | `* true` / `false` |
| `issue` | `? waiting` / `! failed` / `· none` |
| `progress` | `○ 0%` / `◐ 50%` / `● 100%` (rounded to nearest stop) |
| `stage` | (free text, no glyph) |

## Progress field

The `progress` field on a task is `0.0 .. 1.0`, nullable. Defaults to null. The renderer rounds to the nearest visible stop:

| `progress_stages` config | Stops | Visible glyphs |
|---|---|---|
| 2 | 0, 1 | `○ ●` |
| 3 | 0, 0.5, 1 | `○ ◐ ●` |
| 4 (default) | 0, 0.33, 0.66, 1 | `○ ◐ ◑ ●` |

A null `progress` shows `·` in backlog rows, `○` everywhere else.

## Config knobs

Override the rendering via config. Resolution order (highest wins):

1. `--glyphs <style>` CLI flag
2. `.octopus/config.yaml` `ui.glyphs.*` (per-activity)
3. `~/.config/octopus/config.yaml` `ui.glyphs.*` (user-global)
4. Built-in defaults

```yaml
ui:
  glyphs:
    style: collapsed         # collapsed | combined | minimal
    progress_stages: 4       # 2 | 3 | 4
    use_color: true          # false → ASCII-only fallback
    session_marker: arrow    # arrow | none
```

### Style presets

| `style` | Slot 1 dictionary |
|---|---|
| `collapsed` (default) | `· ○ ◐ ◑ ● ▶ ✕ ! ? +` — locked v1 set |
| `combined` | Two-cell `bucket-arrow + progress-circle` (e.g. `▷○`, `▶◐`) for flat list views |
| `minimal` | Pure-ASCII fallback `· o O X` — for monochrome terminals or scripts |

### `use_color: false`

Drops color and switches to the `minimal` glyph set automatically. The `style` setting is ignored. Bucket axis is then carried entirely by the glyph itself (the `minimal` dictionary is bucket-distinct).

## Implementation contract

The glyph renderer is a single pure function:

```python
def render_status(task: Task, style: GlyphStyle) -> RenderedGlyph:
    """Return (glyph_char, color_class) for slot 1."""
```

No call-site branching. Themes are pure data. New presets are added by extending the `GlyphStyle` table — no changes to row code.

## Terminal compatibility

The locked dictionary has been smoke-tested in:

- Alacritty (macOS, Linux)
- iTerm2 (macOS)
- kitty (macOS, Linux)
- GNOME Terminal (Linux)
- Windows Terminal
- tmux 3.4
- screen 5.0

If a glyph fails to render in any of those, the user can drop to `minimal` style via config. The `minimal` set uses only ASCII characters guaranteed by ANSI X3.4.

## CLI adoption

`octopus list` and `octopus show` accept a `--glyphs <style>` flag. Default: off (text-only output, backward-compatible with scripts). Flipping the default to `on` is deferred until v1 ships.

## See also

- [TUI-KEYS.md](TUI-KEYS.md) — companion spec for the keybinding layer
- [SCHEMA-TASK.md](SCHEMA-TASK.md) — task fields the renderer reads (`progress`, `bucket`, `run_state`, `issue`, etc.)
- [DECISIONS.md](../DECISIONS.md) — locked decisions G1-G4

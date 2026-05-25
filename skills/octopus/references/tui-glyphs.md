# TUI glyphs — v1

Visual vocabulary used by the Octopus TUI (and opt-in by the CLI). Three positional slots per task row, plus a header-bar slot.

Mirror of `.spectacular/specs/TUI-GLYPHS.md` — operational subset. Keep in sync.

## Row slots

```
  ◐  fix the webhook auth bug                *!:   code · 2h
  └─ slot 1: status (1 cell)                 └─ slot 2: flags (≤3)   └─ slot 3: meta (dim)
```

- **Slot 1** — exactly one glyph. Progress ladder + exception states.
- **Slot 2** — 0–3 flags. Overflow collapses to `…`; surface rest in Detail pane.
- **Slot 3** — dim meta suffix (`kind · age`). Already shipped.

## Slot 1 — Status glyphs

| Glyph | State | Trigger |
|---|---|---|
| `·` | parked | `bucket=backlog` AND `progress` is null |
| `○` | open | `progress ≈ 0` (not parked) |
| `◐` | half | `progress ≈ 0.5` |
| `◑` | most-done | `progress ≥ 0.75` (only when `progress_stages: 4`) |
| `●` | done | `bucket=done` |
| `▶` | session live | `session_id` set |
| `✕` | dropped | `bucket=dropped` |
| `!` | blocked | `run_state=blocked` |
| `?` | waiting | `issue=waiting` |
| `+` | migrated | `promoted_to` set |

### Precedence (highest wins)

`!` blocked → `?` waiting → `▶` session → `+` migrated → `●` done → `✕` dropped → progress ladder (`· ○ ◐ ◑`).

Blocked+50% renders `!`, not `◐`.

### Bucket colors

| Bucket | Hex |
|---|---|
| backlog | `#7AB8FF` (or grey when fully idle) |
| next | `#5EEAD4` |
| now | `#FACC15` |
| done | `#86EFAC` |
| dropped | `#F38BA8` (dim) |

## Slot 2 — Flag glyphs

| Glyph | Flag | Color | Source |
|---|---|---|---|
| `*` | pinned | next-teal | `pinned: true` |
| `!` | priority high | drop-pink | `priority: high` |
| `:` | has refs | lavender | `refs:` non-empty |
| `^` | has session log | next-teal | any session log file |
| `&` | scheduled | now-yellow | `scheduled_for` set |
| `#` | tagged | dim grey | `tags:` non-empty |

`!` appears in both slot 1 and slot 2 — different columns, never collapse.

## Slot 3 — Header glyphs

Static labels in the top header bar (never per-task).

| Glyph | Codepoint | Color | Where | Status |
|---|---|---|---|---|
| `⌂` | U+2302 | dim `#8A8D9A` | Path row | active |
| `◇` | U+25C7 | lavender `#CBA6F7` | Activity row prefix | **active** |
| `⬡` | U+2B21 | lavender `#CBA6F7` | Repo row prefix (in git) | **active** |
| `◆` | U+25C6 | — | Activity row variant | **reserved** |
| `⬢` | U+2B22 | — | Repo row variant | **reserved** |
| `▶` | U+25B6 | cyan `#89DCEB` | State row | active — human session |
| `»` | U+00BB | cyan `#89DCEB` | State row | **reserved** — agent run |
| `⟳` | U+27F3 | dim / `#F5C76E` busy | State row | active — ready/refresh |

### Activity row layout

```
◇ <activity-name>   ⬡ <repo-name>
```

Both glyphs lavender. Activity name white. Repo name dim grey. Repo segment omitted when not in a git repo.

**Detection.** Walk up from activity root looking for `.git/`. Stop at filesystem root or `$HOME`. Repo name = basename of git toplevel. Detected once on mount (not reactive).

**Why walk up.** Activities frequently sit as subfolders of a parent repo. `$HOME` ceiling prevents surfacing unrelated parent repos.

### Session vs agent

Same color family, distinct silhouettes:

- `▶` — human session running (active, used in header + row override).
- `»` — agent run indicator (reserved). Will share cyan with `▶`.

Emoji `⏩` rejected: inconsistent rendering, breaks plain-glyph vocabulary.

### Reserved filled variants

`◆` and `⬢` reserved for future state encodings on activity/repo rows (e.g. unread alerts, uncommitted changes). Color stays lavender; only fill changes.

## Detail pane — KV glyphs

| Field | Render |
|---|---|
| `bucket` | `· backlog` / `○ next` / `◐ now` / `● done` / `✕ dropped` |
| `pinned` | `* true` / `false` |
| `issue` | `? waiting` / `! failed` / `· none` |
| `progress` | `○ 0%` / `◐ 50%` / `● 100%` (rounded) |
| `stage` | free text, no glyph |

## Progress field

`progress`: `0.0..1.0`, nullable, defaults null. Rounded to nearest stop:

| `progress_stages` | Stops | Glyphs |
|---|---|---|
| 2 | 0, 1 | `○ ●` |
| 3 | 0, 0.5, 1 | `○ ◐ ●` |
| 4 (default) | 0, 0.33, 0.66, 1 | `○ ◐ ◑ ●` |

Null `progress`: `·` in backlog, `○` elsewhere.

## Config

Resolution order (highest wins):

1. `--glyphs <style>` CLI flag
2. `.octopus/config.yaml` → `ui.glyphs.*`
3. `~/.config/octopus/config.yaml` → `ui.glyphs.*`
4. Defaults

```yaml
ui:
  glyphs:
    style: collapsed         # collapsed | combined | minimal
    progress_stages: 4       # 2 | 3 | 4
    use_color: true          # false → ASCII-only
    session_marker: arrow    # arrow | none
```

| `style` | Slot-1 set |
|---|---|
| `collapsed` (default) | `· ○ ◐ ◑ ● ▶ ✕ ! ? +` |
| `combined` | Two-cell `bucket-arrow + progress` (e.g. `▷○`, `▶◐`) |
| `minimal` | Pure ASCII `· o O X` |

`use_color: false` → forces `minimal` regardless of `style`.

## Implementation contract

Single pure function:

```python
def render_status(task: Task, style: GlyphStyle) -> RenderedGlyph:
    """Return (glyph_char, color_class) for slot 1."""
```

No call-site branching. Themes are pure data.

## Terminal compatibility

Smoke-tested in Alacritty, iTerm2, kitty, GNOME Terminal, Windows Terminal, tmux 3.4, screen 5.0. Fallback: `style: minimal` for monochrome / ASCII-only.

## See also

- `tui-keys.md` — keybinding companion
- `schemas/task.md` — fields the renderer reads

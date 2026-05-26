# TUI-GLYPHS — Status & flag glyph dictionary

Authoritative spec for the visual vocabulary used by the Octopus TUI and (opt-in) the CLI. Locked by request [34-tui-key-schema](../requests/34-tui-key-schema/PLAN.md) and revised by [41-tui-glyph-audit](../requests/41-tui-glyph-audit/PLAN.md). Companion to [TUI-KEYS.md](TUI-KEYS.md).

## Model

Each task row exposes **three positional slots**, plus a chrome layer:

```
  ▸  ▣  fix the webhook auth bug                *!:   code · 2h
  │  │                                          │     │
  │  └─ slot 1: status (single cell)            │     └─ slot 3: meta (dim)
  └─ chrome: cursor (when row is selected)      └─ slot 2: flags (≤3)
```

- **Chrome** — `▸ cursor`, `✓ success`, `✗ error`. Affordances, never task state.
- **Slot 1 — status glyph.** Exactly one cell. **Collapsed hybrid** of bucket × progress × exception state, resolved by precedence. See "Slot 1" below.
- **Slot 2 — flag glyphs.** Zero to three. Independent boolean flags. Cap at 3; overflow collapses to `…` and surfaces in the Detail pane. **Currently only `*` (pinned) is shipped; the rest are reserved.**
- **Slot 3 — meta suffix.** Dim grey, right-aligned: `kind` chip + `age` (e.g. `code · 2h ago`). Already shipped; documented here for completeness.

## Slot 1 — Status glyph (collapsed hybrid)

Slot 1 is a single cell that collapses three axes — **bucket × progress × exception state** — into one glyph. The resolver runs top-down; first match wins.

### Priority resolver

1. **Exception overrides** — `!` blocked → `?` waiting → `+` migrated → `✕` dropped (terminal bucket).
2. **Session live** — `▶` (active human session). `»` is reserved for agent sessions.
3. **Progress active** — when the task has a non-null `progress` value, show the **progress ladder**: `○ ◐ ◑ ●`. Inherits **bucket color**.
4. **Bucket idle** — no progress, no session, no exception. Shows the **bucket idle glyph**.

A task with `progress=0.5` AND `bucket=now` AND `issue=blocked` renders `!`, not `◐` or `▣`. Exceptions always win.

### Why a hybrid

Bucket and progress are independent axes — the user needs to see *both*. But slot 1 is one cell. Trade-off: when a task is **idle**, the bucket axis is the only signal worth showing; when a task is **active** (has progress), progress is the more informative axis and the bucket axis is carried by **color** (the glyph inherits the bucket's color, even though the glyph shape comes from the progress ladder).

### Glyphs

#### Exception overrides (highest precedence)

| Glyph | State | Trigger | Color |
|---|---|---|---|
| `!` | blocked | `issue=blocked` (canonical) or `run_state=blocked` (legacy) | warn amber `#FAB387` |
| `?` | waiting | `issue=waiting` (canonical) or `run_state=waiting` (legacy) | mustard `#F5C76E` |
| `+` | migrated | `promoted_to` is set | lavender `#CBA6F7` |
| `✕` | dropped | `bucket=dropped` (terminal) | dim grey `#8A8D9A` |

#### Session

| Glyph | State | Trigger | Color |
|---|---|---|---|
| `▶` | session live | active human session on this task | cyan `#89DCEB` |
| `»` | reserved — agent session | (future) | cyan `#89DCEB` |

#### Progress ladder (active tasks with `progress` field)

| Glyph | Stop | Color |
|---|---|---|
| `○` | open / progress ≈ 0 | bucket color |
| `◐` | half / progress ≈ 50% | bucket color |
| `◑` | most / progress ≈ 75% (only when `progress_stages: 4`) | bucket color |
| `●` | done / progress = 100% | bucket color (done → mint green) |

#### Bucket idle (no progress, no session, no exception)

| Bucket | Glyph | Why | Color |
|---|---|---|---|
| backlog | `·` | grey dot — parked, no activity | dim grey `#8A8D9A` |
| next | `□` | outline square — planned but inert | cyan `#89DCEB` |
| now | `▣` | filled-inner square — current focus | now-pink `#F38BA8` |
| done | `●` | filled green — terminal (also top of progress ladder) | mint `#A6E3A1` |
| dropped | `✕` | terminal (also covered as exception override) | dim grey `#8A8D9A` |

### Bucket axis (color reinforcement)

Color carries the bucket axis when the glyph shape comes from the progress ladder. Pane context (in the TUI) reinforces it: rows in the BACKLOG pane are uniformly muted; rows in the NOW pane share the now-pink accent.

| Bucket | Color |
|---|---|
| backlog | `#8A8D9A` dim grey |
| next | `#89DCEB` cyan |
| now | `#F38BA8` pink |
| done | `#A6E3A1` mint |
| dropped | `#8A8D9A` dim grey |

The `now` color is pink (`#F38BA8`), not yellow. Yellow (`#F5C76E`) is reserved for `?` waiting and `⟳` busy spinner.

## Slot 2 — Flag glyphs

Independent boolean flags. Rendered after the title, before the meta suffix. Cap at 3.

| Glyph | Flag | Color | Source field | Status |
|---|---|---|---|---|
| `*` | pinned | lavender `#CBA6F7` | `pinned: true` | **active** |
| `!` | priority high | drop-pink | `priority: high` | **reserved** |
| `:` | has refs | lavender | `refs:` non-empty | **reserved** |
| `^` | has session log | next-teal | any session log exists | **reserved** |
| `&` | scheduled | now-yellow | `scheduled` is set | **reserved** |
| `#` | tagged | dim grey | `tags:` non-empty | **reserved** |

### Slot-collision note

`!` appears in both slot 1 (blocked) and slot 2 (priority high). This is intentional and unambiguous because the slots sit in different columns. Renderers must never collapse the slots into one cell.

### Pinned glyph

Pinned uses `*` (asterisk) in **both** the chip row and the inline preview row. The previous `★` (filled star) literal in `_row_preview` was retired in v1.0 — same glyph everywhere.

## Header glyphs

Glyphs in the top header bar. Static labels for the kind of line you're looking at — never per-task state.

| Glyph | Code point | Color | Where | Status |
|---|---|---|---|---|
| `⌂` | U+2302 | dim `#8A8D9A` | Path row | active |
| `◇` | U+25C7 | lavender `#CBA6F7` | Activity row prefix | **active — reserved for activity** |
| `⬡` | U+2B21 | lavender `#CBA6F7` | Repo row prefix (when activity root is inside a git repo) | **active — reserved for git** |
| `◆` | U+25C6 | lavender `#CBA6F7` | Activities view — CURRENT panel header | **active** (D102) — "the activity I'm in" |
| `◈` | U+25C8 | lavender `#CBA6F7` | Activities view — NESTED panel header | **active** (D102) — "sub-activities live inside this one" |
| `⬢` | U+2B22 | lavender (future) | Repo row variant | **reserved** — filled variant for future repo-state encoding |
| `▶` | U+25B6 | cyan `#89DCEB` | State row + slot-1 override | active — human session running |
| `»` | U+00BB | cyan `#89DCEB` | State row + slot-1 override | **reserved** — agent session running |
| `⟳` | U+27F3 | dim or `#F5C76E` busy | State row | active — TUI ready / refreshing |

### Activity row layout

Single-line form: `◇ <activity-name>   ⬡ <repo-name>` — both glyphs lavender, activity name in default-foreground white, repo name in dim grey. The repo segment is omitted when the activity root is not inside a git repo.

**Detection.** Walk up from the activity root looking for a directory containing `.git/`. Stop at filesystem root or `$HOME`, whichever comes first. The repo name is the basename of the git toplevel. Detected once on TUI mount; not reactive.

**Why walk up.** Activity folders are commonly subfolders of a larger repo (e.g. `~/repo/projects/foo/`) — walking up catches this without the user having to flag it. The `$HOME` ceiling prevents accidentally surfacing a parent repo when the activity actually lives in a non-git location.

**Diamond family — fully activated for activity scope (D102).** The diamond family now has three meanings, all activity-scoped:
- `◇` outline — **label**: activity-name prefix (existing, D95).
- `◆` filled — **active state**: "the activity I'm in." Used as the CURRENT panel header in the Activities view (D101).
- `◈` outline-with-interior — **containment**: "sub-activities live inside this one." Used as the NESTED panel header.

`◆` outside Activities (e.g. inline on a task row) remains reserved for future "activity has unread alerts" / per-task activity-state encoding — D102 activates one specific use, not all of them.

**Hexagon family stays git-only.** `⬡` outline = repo row prefix (active); `⬢` filled = future repo-state encoding (reserved). Diamond and hexagon stay strictly in their lanes — never cross-assign.

### Session vs agent

Two complementary "something is running" indicators, in the same color family but distinct silhouettes:

- `▶` — **active**. Human session running. Used in both header state row and task-row slot-1 override.
- `»` — **reserved**. Agent run indicator. Reserved for when an autonomous agent is acting on the activity or a specific task. Will use the same color as `▶` (cyan) so both read as "live activity," but the silhouette distinguishes "human at the wheel" from "agent at the wheel."

Emoji fast-forward (`⏩`) was rejected: renders inconsistently across terminals, breaks the plain-glyph vocabulary, and color-emoji rendering clashes with the rest of the palette.

### Retired allocations

- `◆ session` (filled diamond as session indicator) — **retired** in v1.0. The filled-diamond slot is reserved for future activity-state encoding. Session live is `▶`. See D91.

## Chrome glyphs

Not status, not flags — UI affordances. Listed here so they never get reassigned.

| Glyph | Meaning | Where |
|---|---|---|
| `▸` | cursor — selected row indicator | every list view |
| `✓` | success affordance | toast success prefix, DONE column header would alias here historically (now uses `●` to match slot-1 done) |
| `✗` | error affordance | toast error prefix, save-failure banner in edit modal |
| `⟳` | refresh / busy | state row, refresh toasts |
| `⌂` | path / home | path row prefix |

### `✕` vs `✗`

Visually similar (U+2715 vs U+2717), semantically distinct:
- `✕` = task state (slot 1, terminal bucket "dropped")
- `✗` = operation failure (chrome, toast/banner)

Never substitute one for the other.

## Board / Focus column headers

The bucket name in each column's `border_title` uses the **bucket idle glyph** (consistent with slot 1):

| Column | Header text |
|---|---|
| BACKLOG | `BACKLOG` (no glyph — uniform-mute treatment) |
| NEXT | `□ NEXT` |
| NOW | `▣ NOW` |
| DONE | `● DONE` |
| DROPPED | `✕ DROPPED` |

`DONE` header uses `●` (the slot-1 done glyph), not `✓` (chrome). Consistency across the row glyph and the column header is more valuable than chrome flair.

## Detail pane — KV value glyphs

In the Detail pane's frontmatter key/value grid, the value is prefixed with the slot-1 glyph for the relevant field:

| Field | Value rendering |
|---|---|
| `bucket` | `· backlog` / `□ next` / `▣ now` / `● done` / `✕ dropped` |
| `pinned` | `* true` / `false` |
| `issue` | `! blocked` / `? waiting` / `· none` |
| `progress` | `○ 0%` / `◐ 50%` / `◑ 75%` / `● 100%` (rounded to nearest stop) |
| `stage` | (free text, no glyph) |

## Progress field

The `progress` field on a task is `0.0 .. 1.0`, nullable. Defaults to null. **Not yet in `SCHEMA-TASK.md`** — forward-spec for v1.x. The renderer is shipped; the schema field is reserved.

When set, the renderer rounds to the nearest visible stop:

| `progress_stages` config | Stops | Visible glyphs |
|---|---|---|
| 2 | 0, 1 | `○ ●` |
| 3 | 0, 0.5, 1 | `○ ◐ ●` |
| 4 (default) | 0, 0.33, 0.66, 1 | `○ ◐ ◑ ●` |

A null `progress` falls through to the bucket idle glyph (see Slot 1 resolver step 4).

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
| `collapsed` (default) | `· □ ▣ ● ○ ◐ ◑ ▶ ✕ ! ? +` — locked v1 set |
| `combined` | Two-cell `bucket-arrow + progress-circle` (e.g. `▷○`, `▶◐`) for flat list views |
| `minimal` | Pure-ASCII fallback `· [ ] # o O X` — for monochrome terminals or scripts |

### `use_color: false`

Drops color and switches to the `minimal` glyph set automatically. The `style` setting is ignored. Bucket axis is then carried entirely by the glyph itself (the `minimal` dictionary is bucket-distinct).

## Implementation contract

The slot-1 resolver lives at `cli/src/octopus/tui/icons.py:status_glyph(row, *, active_session, progress_stages) -> str` and follows the priority order above exactly. No call-site branching. New presets are added by extending the resolver and palette — no changes to row rendering code.

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

Known quirk: `▣` (U+25A3, filled inner square) renders correctly in all of the above. `□` (U+25A1) is universally supported. Both are 1-cell wide.

## CLI adoption

`octopus list` and `octopus show` accept a `--glyphs <style>` flag. Default: off (text-only output, backward-compatible with scripts). Flipping the default to `on` is deferred until v1 ships.

## See also

- [TUI-KEYS.md](TUI-KEYS.md) — companion spec for the keybinding layer
- [SCHEMA-TASK.md](SCHEMA-TASK.md) — task fields the renderer reads (`bucket`, `run_state`, `issue`, `promoted_to`; `progress` is forward-spec)
- [DECISIONS.md](../DECISIONS.md) — locked decisions G1–G4, D91, and v1 glyph allocations

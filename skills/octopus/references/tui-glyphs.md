# TUI glyphs — v1

Visual vocabulary used by the Octopus TUI (and opt-in by the CLI). Operational mirror of `.spectacular/specs/TUI-GLYPHS.md`. Keep in sync.

## Row anatomy

```
  ▸  ▣  fix the webhook auth bug                *    code · 2h
  │  │                                          │    │
  │  └─ slot 1: status (1 cell, hybrid)         │    └─ slot 3: meta (dim)
  └─ chrome: cursor                              └─ slot 2: flags (≤3)
```

## Slot 1 — Status glyph (collapsed hybrid)

Single cell. Resolved by priority — first match wins:

1. **Exception override:** `! blocked` → `? waiting` → `+ migrated` → `✕ dropped`
2. **Session live:** `▶` (human). `»` reserved for agent.
3. **Progress active:** task has `progress` field → ladder `○ ◐ ◑ ●`. Inherits bucket color.
4. **Bucket idle:** no progress, no session, no exception → bucket glyph below.

Progress overrides bucket. Bucket idle glyph only appears when nothing else is true on that row.

### Exception override glyphs

| Glyph | State | Trigger | Color |
|---|---|---|---|
| `!` | blocked | `issue=blocked` (or legacy `run_state=blocked`) | `#FAB387` amber |
| `?` | waiting | `issue=waiting` (or legacy `run_state=waiting`) | `#F5C76E` mustard |
| `+` | migrated | `promoted_to` is set | `#CBA6F7` lavender |
| `✕` | dropped | `bucket=dropped` | `#8A8D9A` grey |

### Session

| Glyph | State | Status | Color |
|---|---|---|---|
| `▶` | human session live | active | `#89DCEB` cyan |
| `»` | agent session live | **reserved** | `#89DCEB` cyan |

### Progress ladder

| Glyph | Stop | Color |
|---|---|---|
| `○` | 0% (open) | bucket color |
| `◐` | 50% (half) | bucket color |
| `◑` | 75% (most) | bucket color |
| `●` | 100% (done) | bucket color |

### Bucket idle glyphs

| Bucket | Glyph | Color | Reading |
|---|---|---|---|
| backlog | `·` | `#8A8D9A` grey | parked |
| next | `□` | `#89DCEB` cyan | planned, inert |
| now | `▣` | `#F38BA8` pink | current focus |
| done | `●` | `#A6E3A1` mint | terminal |
| dropped | `✕` | `#8A8D9A` grey | terminal |

`now` is **pink**, not yellow. Yellow is reserved for `?` waiting + `⟳` busy spinner.

## Slot 2 — Flag glyphs

Independent boolean flags after the title, cap 3.

| Glyph | Flag | Color | Status |
|---|---|---|---|
| `*` | pinned | `#CBA6F7` lavender | **active** |
| `!` | priority high | drop-pink | reserved |
| `:` | has refs | lavender | reserved |
| `^` | has session log | next-teal | reserved |
| `&` | scheduled | now-yellow | reserved |
| `#` | tagged | dim grey | reserved |

`!` lives in both slot 1 (blocked) and slot 2 (priority). Different columns; never collapse.

Pinned uses `*` everywhere — chip row and preview row. The old `★` literal was retired in v1.0.

## Header glyphs

Top header bar. Static — never per-task state.

| Glyph | Color | Where | Status |
|---|---|---|---|
| `⌂` | `#8A8D9A` | path row prefix | active |
| `◇` | `#CBA6F7` lavender | activity row prefix · Activities view INDEX header | **active** — activity label |
| `◆` | `#CBA6F7` lavender | Activities view CURRENT header | **active** (D102) — "the activity I'm in" |
| `◈` | `#CBA6F7` lavender | Activities view NESTED header | **active** (D102) — "sub-activities live inside this one" |
| `⬡` | `#CBA6F7` lavender | repo row prefix (in git) | **active — reserved for git** |
| `⬢` | lavender | repo variant | reserved (D91) |
| `▶` | `#89DCEB` cyan | state row + slot-1 override | active — human session |
| `»` | `#89DCEB` cyan | state row + slot-1 override | reserved — agent session |
| `⟳` | dim / `#F5C76E` busy | state row | active — ready / refreshing |

### Activity row

```
◇ <activity-name>   ⬡ <repo-name>
```

Both glyphs lavender. Activity name white. Repo name dim grey. Repo segment omitted when not in a git repo.

**Detection.** Walk up from activity root looking for `.git/`. Stop at filesystem root or `$HOME`. Repo name = basename of git toplevel. Detected once on mount.

### Reserved permanently

- `◇` `◆` `◈` — diamond family, **activity scope only** (D95, D102). `◇` label, `◆` active state, `◈` containment.
- `⬡` `⬢` — hexagon family, **git/repo scope only** (D95). Never cross-assign with diamond.
- `▶` `»` — session indicators (human active, agent reserved).

Never reassign.

### Retired

- `◆ session` (filled diamond as session indicator) — retired v1.0. Session live is `▶`. The filled diamond stays reserved for activity state.

## Chrome glyphs

UI affordances, never task state.

| Glyph | Meaning | Where |
|---|---|---|
| `▸` | cursor — selected row | every list view |
| `✓` | success affordance | toast success prefix |
| `✗` | error affordance | toast errors, save-failure banner |
| `⟳` | refresh / busy | state row, refresh toasts |
| `⌂` | path / home | path row prefix |

### `✕` vs `✗`

Look alike, mean different things:
- `✕` (U+2715) = task state (dropped bucket, slot 1)
- `✗` (U+2717) = operation failure (chrome)

Never substitute.

## Column headers (Board + Focus)

Bucket name uses the **bucket idle glyph** — same as slot 1:

| Column | Title |
|---|---|
| BACKLOG | `BACKLOG` (no glyph) |
| NEXT | `□ NEXT` |
| NOW | `▣ NOW` |
| DONE | `● DONE` |
| DROPPED | `✕ DROPPED` |

DONE header uses `●` (slot-1 glyph), not `✓` (chrome). Row-and-header consistency wins.

## Detail pane — KV glyphs

| Field | Render |
|---|---|
| `bucket` | `· backlog` / `□ next` / `▣ now` / `● done` / `✕ dropped` |
| `pinned` | `* true` / `false` |
| `issue` | `! blocked` / `? waiting` / `· none` |
| `progress` | `○ 0%` / `◐ 50%` / `◑ 75%` / `● 100%` |
| `stage` | free text, no glyph |

## Config

```yaml
ui:
  glyphs:
    style: collapsed         # collapsed | combined | minimal
    progress_stages: 4       # 2 | 3 | 4
    use_color: true          # false → ASCII-only
    session_marker: arrow    # arrow | none
```

Resolution: `--glyphs` flag > `.octopus/config.yaml` > `~/.config/octopus/config.yaml` > defaults.

| `style` | Slot-1 set |
|---|---|
| `collapsed` (default) | `· □ ▣ ● ○ ◐ ◑ ▶ ✕ ! ? +` |
| `combined` | two-cell bucket+progress (e.g. `▷○`, `▶◐`) |
| `minimal` | ASCII `· [ ] # o O X` |

`use_color: false` → forces `minimal`.

## Implementation contract

Single resolver at `tui/icons.py:status_glyph(row, *, active_session, progress_stages)`. No call-site branching.

## Terminal compatibility

Smoke-tested: Alacritty, iTerm2, kitty, GNOME Terminal, Windows Terminal, tmux 3.4, screen 5.0. Fallback: `style: minimal`.

`▣` (U+25A3) and `□` (U+25A1) are both 1-cell wide and universally supported.

## See also

- `tui-keys.md` — keybinding companion
- `schemas/task.md` — fields the renderer reads (`progress` is forward-spec)

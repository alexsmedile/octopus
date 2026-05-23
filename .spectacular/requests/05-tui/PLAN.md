---
status: done
priority: medium
owner: alex
updated: 2026-05-23
activated: 2026-05-23
closed: 2026-05-23
summary: "Textual TUI v1 — Focus + Board modes, CWD-scoped, manual refresh, 13-key v1 keymap, modern minimal aesthetic."
related:
  - 03-index-sqlite
  - 04-sessions-memory
  - 12-watcher-daemon
gates:
  - 04-sessions-memory
---

# Textual TUI v1

## Goal

`octopus tui` — a Textual app over the SQLite index, scoped to the current activity (CWD). Daily driver for the *act* loop (start → work → finish), not a browser of the whole vault. v1 ships two modes (Focus, Board), a 13-key keymap, manual refresh, and zero new write paths beyond what the CLI already exposes.

## Why

The CLI verbs are stable, but day-to-day work is a tight loop: see what's `now`, start a session, finish, move to the next thing. Each verb is one shell invocation today. A TUI collapses that loop into single keystrokes against a live view of `now` + `on-deck`, with detail one keystroke away. Octopus's design principle is "act, don't triage" — the TUI must reflect that.

## Scope summary

One app, one binary, two modes. CWD-scoped: launching outside an `.octopus/` folder errors immediately. Reads from SQLite (same access layer as CLI). Writes go through the same CLI verb implementations — no new mutation logic.

## Locked decisions (from interview 2026-05-23)

### Architecture

| # | Topic | Decision |
|---|---|---|
| 1 | Scope | Single app: `octopus tui` |
| 2 | Default view | Focus mode |
| 3 | Layout strategy | Mode switching (not persistent panes, not summoned panes) |
| 4 | v1 modes | **Focus** + **Board** only |
| 5 | Activity scope | CWD only — error with "not inside an octopus activity" if no `.octopus/` is found |
| 12 | Refresh | Manual `r` only in v1; autoupdate deferred to v2 with on/off toggle |

### Focus mode layout (revised after first visual review)

```
┌──── BACKLOG ────────┬──── ● NOW ────────────┐
│  ▸ task A           │  ▸ task X   <chips>   │
│    task B           │    task Y             │
│    task C           ├──── ○ NEXT ───────────┤
│    task D           │  ▸ task M             │
│    …                │    task N             │
└─────────────────────┴───────────────────────┘
       ↓ Enter on highlighted task
   ┌──── task X ─────────────────────┐
   │ body, axis chips, session log,  │
   │ memory entries — scrollable     │
   │           [Esc to close]        │
   └─────────────────────────────────┘
```

- **Three quadrants**: BACKLOG (left, full height, ~40% width) + NOW (top-right, ~50% of right) + NEXT (bottom-right, ~50% of right).
- **Arrow keys traverse panels** at boundaries: `→` from BACKLOG jumps to NOW (or NEXT if NOW empty); `←` from NOW/NEXT returns to BACKLOG; `↓` past last NOW row jumps into NEXT; `↑` past first NEXT row jumps back to NOW. `Tab`/`Shift-Tab` cycle quadrants explicitly.
- **Focused panel** gets the pink accent border; others stay muted.
- **`n` captures into the focused quadrant's bucket.** No auto-pin (pin is a separate axis — press `p` to toggle).
- **`m`** advances the highlighted task one step along the pipeline.
- Pinned tasks sort to the top within each list (per AXIS-MODEL spec).
- Detail is a **summoned overlay**. `Enter` (or `→` from a list) opens; `Esc` closes.

Why backlog visible in Focus: the default bucket for new tasks is `backlog`. The original "NOW + NEXT only" layout assumed a populated activity; in practice the daily-driver flow is *capture into backlog → promote forward*, so backlog needs first-class presence.

### Board mode layout (sketch — to refine during build)

Kanban columns for the active activity: `backlog`, `next`, `now`, `done`. Arrow keys navigate within and across columns. Same overlay for detail. Capture (`n`/`N`) creates into the currently focused column.

### Naming convention

- **Command keys** = verbs in imperative form: `start`, `finish`, `drop`, `move`, `edit`, `capture`, `pin`.
- **UI labels / properties** = nouns: `done`, `now`, `next`, `pinned`, `blocked`.
- A key like `f` triggers the **command `finish`**, which under the hood sets the **property `done: true`** + `end_date: <today>` + bucket move. User-facing language is verb; on-disk language is noun.

### Mutation policy

- Instant for all writes except `drop`.
- `drop` (key `d`) prompts y/n.
- No undo stack in v1 (deferred).

### v1 keymap (13 keys, case-sensitive)

```
Enter / →    open detail overlay
Esc   / ←    close overlay / back
↑ ↓          navigate now-stack
1 / 2        Focus / Board mode
s            session start (quick — on highlighted task, no note)
S            session start (picker — pick task + add opening note)
f            finish (quick)
F            finish (with closing note)
n            capture (inline at top of current section)
N            capture (full overlay — title + bucket + axes + body)
m            move bucket (quick — to next bucket in pipeline)
M            move bucket (picker — choose target bucket)
e            edit in $EDITOR
d            drop (with y/n confirm)
p            toggle pin (calls `pin`/`unpin`)
/            filter visible tasks (title substring, case-insensitive, live)
r            reindex + refresh from DB
?            help (modal listing all bindings)
q            quit
```

Convention: **lowercase = quick path; uppercase = with options**. `p` has no picker-form (binary toggle); `P` left unbound to avoid shadowing a useless key.

### Filter behavior

- Key `/` opens a one-line input.
- Match: case-insensitive substring on **task title only**.
- Live (filters as you type).
- Scope: **currently visible tasks only**. In Focus that's `now` + `next`. In Board that's all four columns.
- Esc cancels and restores; Enter commits the filter (visible until cleared with `Esc` or `/` + empty + Enter).

### Capture behavior

- `n` — blank row appears at the top of the **current section** (in Focus: top of `now`; in Board: top of focused column). Cursor lands in it. `Enter` commits with all other fields defaulted; `Esc` cancels.
- `N` — full overlay: title input + bucket select + axis chips (DOMAIN/RUNTIME/IMPEDIMENT/pin toggle) + body textarea. `Enter` to commit, `Esc` to cancel.
- Both call `capture` under the hood.

## Visual design language

**Direction: fresh, sleek, modern, minimal.** Treat the TUI like a 2026-era productivity app that happens to run in a terminal — not a vintage hacker screen. No green-on-black matrix. No ASCII-art borders that look like 1995. No phosphor glow.

### Aesthetic principles

- **Generous whitespace.** Padding between sections > density. Padding 1 cell minimum, 2 around panels.
- **Soft borders.** Use rounded box-drawing (`╭ ╮ ╰ ╯ ─ │`) for panels. Single-line, never double. Heavy/double borders only for the focused panel (subtle weight change, not a color scream).
- **Color as signal, not decoration.** Most text is neutral grey/white. Color is reserved for state: focus, selection, active session, blocked, pinned, done.
- **Typography hierarchy through weight + dim, not size.** Section headers = bold + uppercase + 1 letter-spaced. Metadata = `dim`. Body = default. No size simulation tricks.
- **No emoji-as-decoration.** Icons only where they carry meaning (see icon set below). One icon per task row max.

### Color palette (Textual CSS variables)

Inspired by Posting / Catppuccin Mocha — pure dark backdrop, one vivid warm accent (pink), cyan & lavender for differentiation. No blue-washed panels (those read as Windows Aero / XP-era).

```
bg          #0F1014   # near-black, screen background
surface     #16171E   # panel/card background (barely lighter than bg)
surface-2   #1C1E26   # focused panel / status bar
border      #2A2C36   # resting border (muted, low contrast)
border-hi   #3A3D4A   # subtle structural separator
text        #F5F5F7   # default text — high contrast
muted       #8A8D9A   # metadata, hints, dim labels
primary     #F38BA8   # warm pink — focus, selection, active tab
accent      #89DCEB   # cyan — active session, "go" actions
success     #A6E3A1   # green — done bucket
warning     #FAB387   # peach — blocked / impediment
pinned      #CBA6F7   # lavender — pinned indicator
```

Light-theme variant deferred to v1.1 — dark-first ships v1. Posting's reference works on Catppuccin Latte equivalents if needed later.

### Icons

ASCII / unicode box-drawing & symbol glyphs only. No emoji anywhere in the UI. Each glyph carries one meaning:

| Glyph | Meaning |
|---|---|
| `●` | now (active) |
| `○` | next / on-deck |
| `✓` | done |
| `✗` | dropped |
| `⚐` | pinned (lavender) |
| `⏸` | blocked / impediment |
| `▸` | row cursor (primary color) |
| `◆` | active session marker (mint, blinks slow) |
| `⟳` | reindex spinner |

All glyphs above are plain unicode (Geometric Shapes, Dingbats, Miscellaneous Symbols) and render in any monospace font without Nerd Font requirement. No emoji codepoints. No fallback layer needed.

### Selection & focus visuals

- **Selected row (cursor):** subtle background tint (`$primary 15%`) + `▸` glyph in `$primary` at left margin. No full-row inverse video — that's the vintage look we're avoiding.
- **Focused panel:** border color shifts from `$text-muted` to `$primary`. No border thickness change.
- **Active tab (mode switcher):** background `$primary`, foreground white, rounded pill shape (`╭─ Focus ─╮` style chip). Inactive tabs are dim grey, no background.
- **Hover** *(mouse, if Textual mouse-events on):* row gets `$primary 8%` tint. Lighter than selection.

### Animations & motion

Keep motion **subtle and short** (under 200ms). No bouncing, no full-screen transitions.

- **Loading / reindex (`r`):** small spinner `⟳` in the status bar, rotating at ~10fps. Disappears when done. Status bar text fades from "reindexing…" to "ready" over 300ms.
- **Mutation feedback:** when a task is finished/dropped/moved, its row briefly pulses the relevant color (mint for finish, coral for drop) for ~250ms before relocating. Use Textual's `animate()` on background-color.
- **Overlay open:** fade-in on opacity (0 → 1 over 150ms) + slight slide-down (translate-y -2 → 0). On close: reverse, shorter (100ms).
- **Filter input (`/`):** input bar slides up from the bottom into view (120ms). On Esc, slides down.
- **Pin toggle:** the `⚐` glyph fades in/out (100ms) when toggled. No row jump until the next sort pass.

### Status bar

Bottom row, full width, single line. Three zones:

```
 ⌂ projectname/activity   ◆ session 12m   │   ⟳ ready  ·  3 now · 7 next · 2 blocked   │   ? help  q quit
```

- Left: activity name (preceded by `⌂` home glyph)
- Center: session state + index status + bucket counts (dim)
- Right: minimal key hints (always visible: `?` and `q`)

### Empty states

Empty buckets aren't blank — show a one-line muted hint:

```
NOW
   (nothing active. Press `s` to start a session, or `n` to capture.)
```

Tone: friendly, terse, action-oriented. Never apologetic ("Sorry, no tasks!"). Never cute.

### Help overlay (`?`)

Centered modal, ~60% width, rounded border, two columns of keybindings grouped by category (Navigate / Act / Capture / View / System). Each binding is `<key>  <verb>  <one-line description>`. Closes on `?` again or `Esc`.

### What we explicitly **don't** want

- Box-drawing art used as decoration (banners, ASCII logos in headers).
- Green-on-black or amber-on-black "terminal nostalgia" palettes.
- Heavy double-lined borders everywhere.
- Full-row inverse-video selection (looks like ncurses 1998).
- All-caps SHOUTING outside of small section labels.
- Emoji of any kind — ASCII/unicode symbol glyphs only.
- Progress bars wider than 20 cells.
- Blinking text (except the single `◆` session indicator, slow pulse).

## Approach

Six deliverables, smallest-to-largest.

1. **Skeleton & CWD detection** — `octopus tui` entry point. Detect `.octopus/` in CWD; error out with the same message as `octopus where` if missing. Launch into a stub Focus screen.
2. **Focus mode (read-only)** — render now-stack + on-deck. Arrow-key nav. Pinned sort. Overlay open/close on `Enter`/`Esc`. No mutations yet.
3. **Mutation keymap** — wire `s`/`f`/`n`/`m`/`e`/`d`/`p` and their uppercase forms to the CLI verb layer. Confirm prompt for `d`. Inline capture (`n`). Full-overlay capture (`N`).
4. **Board mode** — second screen, four-column kanban. Mode switch via `1`/`2`. Same overlay reuse. Same keymap operates on the focused column.
5. **Filter, help, refresh** — `/` filter, `?` help modal, `r` reindex.
6. **Polish & ship** — error states (empty buckets, broken task files), keyboard discoverability, README section, tests.

## Deliverables

- `cli/src/octopus/tui/__init__.py` + `app.py` + `focus.py` + `board.py` + `overlay.py` (rough structure — to refine during build).
- `octopus tui` CLI entry point (Typer command in `cli.py`).
- Textual added to `cli/pyproject.toml` as a runtime dep.
- Tests: snapshot tests for Focus / Board / overlay layouts (Textual provides a snapshot harness); smoke test for each keybinding's CLI verb call.
- README section: "Daily driver — the TUI."

## Out of scope (deferred to later requests)

- **Navigator mode** (three-pane cross-activity browser) — deferred to v1.1+.
- **Session mode** (current session + handoff/memory readout) — deferred.
- **Inbox mode** (unrouted tasks) — deferred (currently expressible as a filter on Board).
- **Log mode** (recent activity stream) — deferred.
- **Undo stack** — deferred to v1.1.
- **Auto-refresh** (file-watcher or DB poll) — deferred to v2; user-configurable on/off toggle. See request #12-watcher-daemon for the file-watching foundation.
- **Structured filter query** (`@blocked`, `#tag`, `runtime:agent`) — deferred to v1.1; title-substring is v1.
- **Cross-activity navigation** — deferred. v1 is CWD-only.
- **Multi-activity dashboard** — out of scope; that's request #13-viewer-web's job.

## Open questions

- Board mode column widths: equal split, or weighted by bucket size? *Recommend equal for v1; revisit when buckets get lopsided in real use.*
- Capture `n` from on-deck (next) section in Focus: which section's bucket wins? Locked: **inline `n` always targets the top section** (`now` in Focus). `N` overlay lets you pick bucket explicitly.
- Color/theme: follow `$TEXTUAL_THEME` env or hardcode a dark theme? *Recommend honor env, ship dark default.*
- Should `q` confirm on active session (don't accidentally quit mid-session)? *Recommend: yes, single y/n if a session is open.*

## Risks

- **Textual maturity for keyboard apps** — Textual is solid but has rough edges around modal overlays + focus handling. Mitigate by keeping overlays simple (no nested modals) and testing snapshot per state.
- **Mutation layer coupling** — TUI must call the same code path as CLI verbs, not duplicate logic. Risk: as CLI verbs grow flags, TUI calls fall behind. Mitigate by routing every TUI mutation through the `octopus.cli` Typer commands programmatically, or through a thin shared `octopus.actions` layer.
- **Startup cost** — Textual import is ~150ms cold. `octopus tui` must not become the slow command. Defer Textual import until the `tui` subcommand body runs (not at module top).
- **Test ergonomics** — Textual snapshot tests are flaky on terminal-size differences. Pin terminal size in tests.

## Estimate

3–5 focused sessions. Skeleton + Focus read-only is one session; mutations are one; Board is one; polish is one or two.

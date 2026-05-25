---
status: locked
priority: medium
owner: alex
updated: 2026-05-25
summary: "Define two intertwined vocabularies for the Octopus TUI: (1) a status-glyph system inspired by bullet-journal notation, using progress-fill circles (○ ◐ ◑ ●) with color carrying the bucket axis; (2) the keybinding schema that drives mutations. All G1-G3 + D1-D7 decisions locked. Specs land at .spectacular/specs/TUI-GLYPHS.md and TUI-KEYS.md mirrored into docs/KEYS.md."
related:
  - 33-tui-visual-redesign
  - 05-tui (shipped)
gates: []
---

# TUI key schema + glyph vocabulary — single source of truth

> Two layers, one request:
> - **Glyphs** (what tasks *look like*) — bullet-journal–style prefixes that signal state at a glance.
> - **Keys** (what users *press*) — single-keystroke bindings that route through `octopus.actions`.
>
> They share a vocabulary (capture, advance, finish, drop, block, pin) but operate at different layers. A glyph is a visual rendering of state; a key is the verb that transitions state. Same words, different jobs.

## Part A — Glyph vocabulary (bullet-journal–inspired)

### Why this layer exists

Today the TUI uses a thin, inconsistent glyph set: `▸` for selection, `📌` for pinned (emoji), `✓` for finished, `⊘` somewhere in icons.py. The archived `_archive/docs/KEYS.md` is a half-finished draft of a much richer dictionary: open/half/closed circles, hourglasses, milestones, drops. Bullet journal users will recognise the family — `·`, `○`, `●`, `X`, `>`, `<`, `*` form a complete state language in two strokes per task.

Adopt this layer for two reasons:
1. **Density** — one column of glyphs replaces three columns of chips (`[pinned] [blocked] [done]`).
2. **Terminal-friendly** — pure single-cell Unicode geometric chars. No emoji, render in any terminal, copy-pasteable, screen-reader sane.

### Glyph slots on a task row

Each row reserves three positional slots:

```
  X  task title here                    +>  code  ~2h
  │  └─ title (left-aligned, marquee)   │   └─ kind / age suffix
  └─ status glyph (bucket × state)      └─ flag glyphs (priority, blocked, etc.)
```

Slot 1 = **status glyph** (which bucket + run state). One per row.
Slot 2 = **flag glyphs** (pinned, blocked, has-references, has-issue). Up to ~3.
Slot 3 (suffix, dim) = **meta** (kind chip + age). Already exists.

### Status glyphs (slot 1) — one per row  *(locked: collapsed variant)*

The status glyph encodes **progress** along a 4-stage circle ladder. **Bucket** is carried by *color* and *pane context* (rows live inside the Backlog/Now/Next/Done pane that owns them). This is the "collapsed" variant from the design exploration — one cell per row, maximum density.

| Glyph | Progress | When shown | Color (= bucket) |
|---|---|---|---|
| `·` | parked / idle | bucket=backlog, no work started | dim grey |
| `○` | open | started but not progressed | bucket color |
| `◐` | half | progress >= 0.25 | bucket color |
| `◑` | most-done | progress >= 0.75 | bucket color |
| `●` | done | bucket=done, end_date set | done-green |
| `▶` | session live | session_id set (overrides progress glyph) | now-yellow, bold |
| `✕` | dropped | bucket=dropped | drop-pink, dim |
| `!` | blocked | run_state=blocked (overrides progress glyph) | drop-pink |
| `?` | waiting | issue=waiting (overrides progress glyph) | drop-pink |
| `+` | migrated | promoted_to set | lavender |

**Precedence** (top wins): `!` blocked → `?` waiting → `▶` session → `+` migrated → progress ladder (`·`/`○`/`◐`/`◑`/`●`) → `✕` dropped.

These are mutually exclusive: a task gets exactly one slot-1 glyph at any time. The four-stage ladder is the carrier in the common case; exception states (`▶`/`!`/`?`/`✕`/`+`) break the ladder to pop visually.

### Progress field

The `progress` field on a task is `0.0 .. 1.0` (nullable; defaults to null). The renderer rounds to the nearest visible stop based on `progress_stages` config:

| `progress_stages` | Stops | Glyphs |
|---|---|---|
| 2 | 0, 1 | `○ ●` |
| 3 | 0, 0.5, 1 | `○ ◐ ●` |
| 4 (default) | 0, 0.33, 0.66, 1 | `○ ◐ ◑ ●` |

When `progress` is null, slot 1 shows `·` (parked) in backlog rows and `○` (open) elsewhere.

### Flag glyphs (slot 2) — up to ~3

Renders right after the title, before the kind/age suffix. Each flag is independent.

| Glyph | Flag | Color |
|---|---|---|
| `*` | pinned | next-teal (mockup uses `[*]`) |
| `!` | priority high (frontmatter `priority: high`) | drop-pink |
| `:` | has references (`refs:` non-empty) | lavender |
| `^` | has linked session | next-teal |
| `&` | scheduled (has `scheduled_for` date) | now-yellow |
| `#` | tagged (`tags:` non-empty) | dim grey |

Cap at 3 flags per row to avoid line-noise; the rest collapse into `…` and surface in the Detail pane.

### Detail-pane KV value glyphs (already partly defined)

In the right-pane key/value grid, axis values are colored *and* glyph-prefixed:

| Field | Value | Glyph |
|---|---|---|
| bucket | now / next / backlog / done / dropped | `O` / `o` / `·` / `X` / `~` |
| pinned | true | `*` |
| issue | waiting / failed / none | `?` / `!` / `·` |
| stage | (free text, no glyph) | — |

This keeps the read-side vocabulary identical in the row and the detail view.

### Glyph constraints (locked)

- **ASCII-only**, single cell. No combining chars, no emoji, no double-width glyphs.
- **Terminal smoke-tested**: Alacritty, iTerm2, kitty, GNOME Terminal, plus screen + tmux. Anything that breaks in any of those, drop.
- **Color carries meaning**, but the glyph alone is sufficient (color is reinforcement, not the carrier). Important for screen readers and color-blind users.
- **No glyph collisions across slots.** `!` is both "blocked" (status) and "priority" (flag) — fine because they sit in different columns, but the doc must call this out.

### Glyph decisions (all locked)

#### G1 — Variant for slot 1  *(locked: B — collapsed)*

| Option | Slot 1 shape | Cells | Notes |
|---|---|---|---|
| A | Bucket arrow + progress circle (`▷○`, `▶◐`) | 2 | Self-describing in flat list views; wider |
| **B (locked)** | Progress circle only (`○ ◐ ◑ ●`); color = bucket; pane context = bucket | 1 | Tightest, BuJo-faithful, requires panes for monochrome readers |
| C | Progress circle alone with `▶` for sessions only | 1 | Variant 3 from the exploration — collapses to B for non-session rows |

**Locked: B.** Variant 2 from the exploration. One cell, color carries bucket axis.

#### G2 — Session marker  *(locked: A)*

When a session is actively running on a task:

| Option | Behavior |
|---|---|
| **A (locked)** | `▶` replaces the progress glyph whenever `session_id` is set | session is the louder signal |
| B | `▶` rides slot 2 (a flag glyph alongside progress) | keeps progress visible but spends a flag slot |

**Locked: A.** `▶` overrides slot 1 when a session is live. The progress information is still surfaced in the Detail pane.

#### G3 — CLI adoption  *(locked: A)*

`octopus list` currently prints text. Glyph dictionary should be a single source across CLI + TUI.

| Option | CLI uses glyphs? |
|---|---|
| **A (locked)** | Yes, behind `--glyphs` flag (default off for v1 to avoid breaking scripts) |
| B | TUI only |

**Locked: A.** `--glyphs` flag on `octopus list` and `octopus show`. Default off until v1 ships, then re-evaluate flipping the default.

#### G4 — Config knobs  *(locked: full surface)*

Users can override the glyph rendering via config. Resolution order:
1. `--glyphs <style>` CLI flag (highest)
2. `.octopus/config.yaml` `ui.glyphs.*` (per-activity)
3. `~/.config/octopus/config.yaml` `ui.glyphs.*` (user-global)
4. Built-in defaults (lowest)

```yaml
ui:
  glyphs:
    style: collapsed         # collapsed | combined | minimal
    progress_stages: 4       # 2 | 3 | 4
    use_color: true          # false → ASCII-only fallback (no Unicode circles)
    session_marker: arrow    # arrow | none
```

**Style presets:**

| `style` | Slot 1 |
|---|---|
| `collapsed` (default) | `○ ◐ ◑ ●` — variant B, the lock |
| `combined` | `▷○`, `▶◐` — variant A, two cells |
| `minimal` | `· o O X` — pure ASCII fallback for monochrome / failing terminals |

The implementation collapses to a single `render_status(task, style) -> str` function. Themes are pure data — no branching at call sites.

---

## Part B — Keybinding schema

### Why this layer exists

Three things are out of sync:

1. **Code** — `focus.py` / `board.py` define 17 bindings. `b` (block) and `u` (unblock) are in `docs/TUI.md` but **not wired in code**.
2. **Docs** — `docs/TUI.md` lists `b`/`u` as if they exist, lists `d` as drop. No mention of help-pane focus, undo, copy-id, multi-select.
3. **Design (#33)** — the visual redesign adds a collapsible Detail pane and reserves `d` for it. That collides with `d = drop`.

Plus: the user wants **ASCII-only key chips** in the status bar (no `↵`, `⇥`, `→`). That means non-letter keys get a 2-3 char text label (`CR`, `TAB`, `>`).

### Goal

Ship **one** key schema doc, in two places that stay in sync via the existing "spec ↔ skill reference" rule in `CLAUDE.md`:

- `.spectacular/specs/TUI-KEYS.md` — authoritative spec, listed in `CLAUDE.md` "Where the specs live"
- `docs/KEYS.md` — public mirror, linked from `docs/TUI.md` and `README.md`

The skill reference under `skills/octopus/references/tui-keys.md` is the operational rewrite for installed skills.

### Inventory (today)

#### Live in code

| Key | Action | Live in |
|---|---|---|
| `q` | quit (confirm if session open) | focus, board |
| `?` | help overlay | focus, board |
| `/` | filter | focus, board |
| `r` | refresh + clear filter | focus, board |
| `1` | switch to Focus mode | focus, board |
| `2` | switch to Board mode | focus, board |
| `←` `→` | move between panes/columns | focus, board |
| `↑` `↓` | move within list (edge jumps) | focus, board |
| `Tab` `S-Tab` | cycle panes | focus, board |
| `Enter` | open task detail overlay | focus, board |
| `Esc` | close overlay (noop in main view) | focus, board |
| `n` | capture into focused pane | focus, board |
| `N` | capture (alias) | focus only |
| `m` | advance pipeline step | focus, board |
| `M` | move to picked bucket | focus, board |
| `f` `F` | finish task | focus, board |
| `d` | drop (with confirm) | focus, board |
| `p` | toggle pin | focus, board |
| `e` | edit in `$EDITOR` | focus, board |
| `s` | session start (quick) | focus, board |
| `S` | session start (titled) | focus only |

#### Documented but not coded

| Key | Doc claim | Reality |
|---|---|---|
| `b` | block (prompts reason) | not bound anywhere |
| `u` | unblock | not bound anywhere |

These either need to be wired or removed from docs. The schema below assumes **wire them** — they fit the verb taxonomy and the chips look incomplete without a block key.

### Constraints

- **ASCII-only chip glyphs.** `Enter` → `CR`, `Tab` → `TAB`, `Esc` → `ESC`, arrows → `<`/`>`/`^`/`v` or unicode `←→↑↓` (decision below).
- **No emoji** anywhere — `📌` and `🐙` are already swapped to `[*]` / `*` in the v3 mockup.
- **Don't break muscle memory.** Renames carry a real cost; the bar is high.
- **Cap the always-visible chips at 6** on narrow terminals, 10 on wide. `?` shows the full map.
- **Single mnemonic vocabulary.** Capture, move, finish, drop, pin, block, edit, detail, session, help, quit. Verbs only — no nouns.

### Open decisions (mark for Alessandro)

#### D1 — Resolve the `d` collision  *(locked: E)*

Pick one:

| Option | Detail toggle | Drop | Notes |
|---|---|---|---|
| A | `d` | `x` | `x` = "delete-ish", common in vim/kakoune for cut/drop. Clearest verb separation. |
| B | `Shift+d` | `d` | Keeps drop on `d`, detail on capital. Shift-keys read poorly in chips. |
| C | `T` | `d` | T for "task pane". Loses verb-ness of detail. |
| D | `d` (drop), no key | n/a | Detail pane toggle uses `→` from last column (no dedicated key). Mockup loses the chip. |
| **E (locked)** | `,` | `d` | Keep `d` = drop (muscle memory). `,` is unused, single-press, ASCII, no Shift. Reads as "pause / aside" — fits a pane that's an *aside* to the main panes. Chip label is just `,`. |

**Locked: E.** No breaking change to `d`; new key `,` for detail toggle.

#### D2 — Block / unblock keys  *(locked: A)*

| Option | Block | Unblock |
|---|---|---|
| **A (locked)** | `b` | `B` (capital) |
| B | `b` | `u` |
| C | `b` (toggle) | same key |

**Locked: A.** Capital pairs are the existing idiom (`s`/`S`, `m`/`M`, `f`/`F`). `u` reserved for undo (D6).

#### D3 — Arrow chip glyphs  *(locked: A)*

| Option | Arrows shown as |
|---|---|
| **A (locked)** | `←` `→` `↑` `↓` — unicode geometric, same family as `●`/`○` |
| B | `<` `>` `^` `v` — pure ASCII fallback |
| C | `H J K L` — vim-style hint |

**Locked: A.** Same Unicode block as the locked glyph set. Falls back to B if any terminal smoke-test fails.

#### D4 — Enter / Tab / Esc chip labels  *(locked: A)*

| Option | Enter | Tab | Esc |
|---|---|---|---|
| **A (locked)** | `CR` | `TAB` | `ESC` |
| B | `RET` | `TAB` | `ESC` |
| C | `↵` | `⇥` | `⎋` |

**Locked: A.** `CR` is 2 chars (matches the chip width). `↵`/`⇥` rejected as emoji-adjacent.

#### D5 — Enter semantics under 4-pane Focus  *(locked: A)*

Under #33 the detail pane is collapsible:

| Option | Enter behavior |
|---|---|
| **A (locked)** | If detail pane is **visible**: focus it. If **collapsed**: open it (same as `,`). |
| B | Always open the legacy overlay regardless of pane state. |
| C | Remove `Enter` binding; rely on `,` only. |

**Locked: A.** Preserves muscle memory while making the detail pane discoverable.

#### D6 — Undo  *(locked: A)*

| Option | Key |
|---|---|
| **A (locked)** | `u` for the last mutation |
| B | `Ctrl+z` |
| C | Defer to v2 |

**Locked: A.** `Ctrl+*` keys are flaky across terminal multiplexers.

#### D7 — Yank task slug  *(locked: A)*

| Option | Key |
|---|---|
| **A (locked)** | `y` (yank, vim idiom) |
| B | `c` (copy) |
| C | Defer |

**Locked: A.**

## Final schema (v1, all locked)

All decisions locked: G1-G4 (glyphs) + D1-D7 (keys).

### Navigation

| Key | Action | Always visible? |
|---|---|---|
| `1` | Focus mode | yes |
| `2` | Board mode | yes |
| `←` `→` | prev/next pane (or column in Board) | yes |
| `↑` `↓` | within-list move (edges spill into adjacent pane) | yes |
| `Tab` `S-Tab` | cycle panes | no (`?`) |
| `Enter` | focus Detail pane (or open it if collapsed) | wide only |
| `Esc` | close overlay / clear filter | no |
| `,` | toggle Detail pane (open ↔ collapsed) | wide only |
| `g` | go-to slug (prompt) | no (`?`) |

### Mutations

| Key | Action | Always visible? |
|---|---|---|
| `n` | capture into focused pane | yes |
| `m` | advance pipeline step (`backlog → next → now → done`) | yes |
| `M` | move to picked bucket (prompt) | no (`?`) |
| `f` | finish task | yes |
| `d` | drop task (with `y/n` confirm) | yes |
| `p` | toggle pin | yes |
| `b` | block (prompt reason) | narrow: no, wide: yes |
| `B` | unblock | no (`?`) |
| `e` | edit in `$EDITOR` | no (`?`) |
| `s` | session start (quick) | no (`?`) |
| `S` | session start (titled) | no (`?`) |
| `u` | undo last mutation | no (`?`) |
| `y` | yank slug to clipboard | no (`?`) |

### Search & system

| Key | Action | Always visible? |
|---|---|---|
| `/` | filter by title substring | wide only |
| `r` | refresh + clear filter | no (`?`) |
| `?` | help overlay (full keymap) | yes |
| `q` | quit | yes |

### Responsive chip set

The status bar shows different chip subsets at different widths. `?` always reveals everything.

```
Narrow  (<100 cols)   n  m  f  p  d  ?  q                                (7 chips)
Medium  (100-119)     n  m  f  p  d  b  CR  ?  q                         (9 chips)
Wide    (≥120 cols)   n  m  f  p  d  b  CR  ,  /  ?  q                  (11 chips)
```

### Chip glyphs (final)

| Key | Glyph | Color (chip bg) | Mnemonic |
|---|---|---|---|
| `n` | `n` | lavender | capture |
| `m` | `m` | now-yellow | move → |
| `f` | `f` | done-green | finish |
| `p` | `p` | next-teal | pin |
| `d` | `d` | drop-pink | drop |
| `b` | `b` | drop-pink | block |
| `,` | `,` | lavender | detail (aside) |
| `CR` | `CR` | grey | open |
| `TAB` | `TAB` | grey | pane |
| `ESC`| `ESC`| grey | close |
| `/` | `/` | grey | filter |
| `?` | `?` | grey | help |
| `q` | `q` | grey | quit |
| `←→↑↓` | `←→↑↓` | grey | nav |

## Migration impact

Changes from today (after D1=E locked):

| Was | Becomes | Migration |
|---|---|---|
| `d` = drop | `d` = drop (unchanged) | none |
| _no key_ = detail toggle | `,` = detail toggle | new |
| `b` = block (doc only) | `b` = block (wired) | implement |
| `u` = unblock (doc only) | `B` = unblock | re-key + implement |
| _no key_ = undo | `u` = undo | implement |
| _no key_ = yank | `y` = yank | implement |
| `Enter` = overlay only | `Enter` = focus/open detail pane | rewire under #33 |

D1=E kept `d` on drop — zero muscle-memory cost. Only new keys to teach: `,` (detail), `b`/`B` (block), `u` (undo), `y` (yank). Changelog line: **"new keys: `,` detail · `b`/`B` block · `u` undo · `y` yank"**.

## Deliverables

### Schema-locking (this request)
- [ ] Lock G1-G3 decisions (glyph layer)
- [ ] Lock D1-D7 decisions (key layer)
- [ ] Write `.spectacular/specs/TUI-GLYPHS.md` with the final glyph dictionary + slot rules
- [ ] Write `.spectacular/specs/TUI-KEYS.md` with the final keybinding schema
- [ ] Mirror both to `docs/KEYS.md` (public-facing, lighter prose; combines glyphs + keys in one page)
- [ ] Mirror to `skills/octopus/references/tui-keys.md` + `skills/octopus/references/tui-glyphs.md` (terse, operational)
- [ ] Update `docs/TUI.md` keymap section to link `KEYS.md` (single source of truth)
- [ ] Update `CLAUDE.md` "Where the specs live" + skill-reference-sync table to include TUI-KEYS and TUI-GLYPHS
- [ ] Update `.spectacular/DECISIONS.md` with the locked picks (G1-G3 + D1-D7)
- [ ] Terminal smoke test of the glyph set across Alacritty, iTerm2, kitty, GNOME Terminal, tmux

### Implementation (separate request, gated on this one)
- [ ] **Glyph layer** — rewrite `cli/src/octopus/tui/icons.py` to expose the locked dictionary; update `_row_chips` + `_row_text` in `focus.py` to render status glyph (slot 1) and flag glyphs (slot 2); update overlay/detail KV rendering.
- [ ] **Key layer**:
  - Wire `b` + `B` (block / unblock)
  - Move `drop` from `d` → `x`
  - Wire `d` as detail toggle (under #33 work)
  - Wire `u` (undo) — needs actions-layer support
  - Wire `y` (yank slug)
  - Wire `g` (goto)
  - Update help overlay + `docs/TUI.md` keymap table
- [ ] **CLI glyph adoption** (G3-A) — opt-in `--glyphs` flag on `octopus list` and `octopus show`.

## Out of scope

- Multi-select rows (defer; needs a real visual selection model).
- Macros / chord bindings (`gd`, `gg`, etc.) — Octopus is a single-keystroke TUI by design.
- Custom keymaps in config — defer until enough users ask. Today the keymap is the contract.
- Mouse bindings — Textual handles these automatically; out of scope for this schema.

## Notes

- `_archive/docs/KEYS.md` is the **glyph dictionary draft** that seeded Part A above. The exotic glyphs (`⨀`, `◐`, `⧖`, `⧑`, `⋈`) didn't make the cut: they're hard to type, not in the BuJo idiom, and not single-cell in every terminal. The locked ASCII set (`·` `o` `O` `>` `X` `~` `!` `?` `=` `+`) covers every state with characters present on any keyboard. Archive stays archived; this spec replaces it.
- Once G1-G3 + D1-D7 are locked, the implementation request opens as `35-tui-key-schema-impl` with both deliverable lists above as its task list.
- The glyph dictionary is the **read** vocabulary; the key schema is the **write** vocabulary. Both must stay in sync — if `b` triggers block, the row must immediately re-render with the `!` status glyph. The implementation request will enforce this round-trip with a test.

## Status notes

- 2026-05-25 — opened. Two-layer schema drafted (glyphs + keys) with recommendations.
- 2026-05-25 — locked: D1=E (`d`=drop, `,`=detail).
- 2026-05-25 — locked: G1=B (collapsed variant, 1-cell progress glyph, color = bucket).
- 2026-05-25 — locked: G2=A, G3=A, G4 (config knobs added).
- 2026-05-25 — locked: D2-D7 = all "A" (block=`b`/`B`, arrows=`←→↑↓`, labels=`CR`/`TAB`/`ESC`, Enter focuses detail, undo=`u`, yank=`y`).
- 2026-05-25 — status flipped to **locked**. Writing specs at `.spectacular/specs/TUI-GLYPHS.md` + `.spectacular/specs/TUI-KEYS.md`.

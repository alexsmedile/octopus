# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased]

### Added

- **`octopus lint` — corpus hygiene audit** (request #42). Read-only verb that walks task files in the cwd activity (or `--all` indexed activities, or a named activity) and reports drift between filename, slug, bucket, schema, and dates. Eight starter rules covering slug ↔ filename match, slug shape, bucket ↔ folder match, frontmatter parse + legacy-field detection, `start_date` without `bucket=now`, dangling `blocked_by` references, stale `done` items (>30d), and `issue=blocked|waiting` in NOW/NEXT (info-only per D100). Optional `--fix` applies safe auto-repairs with per-file confirmation (`--yes` to skip prompts). `--json` for machine output. `--rule CODE` / `--severity LEVEL` filters. Exit codes: `0` clean, `1` info/warn only, `2` ≥1 error. Rules are independently registered under `cli/src/octopus/lint/rules/` — adding a rule is one file + one registry entry.
- **D100 — bucket × blocked/waiting policy.** Human-set `issue: blocked|waiting` is allowed in any bucket (NOW / NEXT / BACKLOG); the TUI's slot-1 resolver already makes the block visibly distinct. `bucket-blocked` lint rule surfaces these as info-only, never auto-fixes. AI-actor enforcement (force-demote to NEXT) is a separate future request.

### Fixed

- **Corrupted `slug:` fields** in two backlog tasks (`clarify-n-sessions-output-in-reindex`, `fix-duplicate-timestamps-in-rapid-session-log-entries`). Both were created during the 2026-05-23 F1-naming housekeeping pass with hand-pasted notes that bled into the YAML `slug:` field. Fixed by hand; `octopus lint --rule=slug-match --fix` would have caught both in seconds.

### Housekeeping

- Archived 9 stale task records to `_archive/tasks-pre-v1/` (7 pre-v1 done entries + 2 dropped smoke-tests). `.octopus/tasks/done/` is now empty; `dropped/` retains only the real decision artifact (`link-tasks-to-requests-via-tags`).

---

## [1.0.0] — 2026-05-25

**v1 — the symbolic milestone.** A year-plus of folder-first task design finally crosses the line. Visual vocabulary is locked, slot-1 has a real resolver, and every glyph in the TUI traces back to a single source of truth.

### Added

- **Inline property preview row on Enter** (Focus + Board) — pressing `Enter` on a task expands a one-row preview beneath it with per-bucket properties (created/priority for backlog, scheduled/priority for next, started/due for now, ended/kind for done/dropped). Second `Enter` collapses it. `e` still opens the edit modal — Enter is preview-only. Moving the cursor auto-collapses.
- **Blocked/waiting reason always surfaced** — when a task has `issue: blocked` or `issue: waiting`, the preview row replaces slot 2 with the `blocked_by` / `waiting_for` reason, in the slot-1 glyph color (amber for blocked, mustard for waiting). Load-bearing context never gets hidden by view-specific property slots.
- **Slot-1 hybrid resolver** (`cli/src/octopus/tui/icons.py`) — single pure function that collapses bucket × progress × exception into one glyph by priority: exception override (`! ? + ✕`) → session live (`▶`) → progress ladder (`○ ◐ ◑ ●`) → bucket idle. Replaces the ad-hoc precedence logic.

### Changed

- **Bucket idle glyphs** — `next` now renders `□` (was `○`), `now` renders `▣` (was `◐`). The old `○ ◐` are reserved for the progress ladder only; bucket and progress are now two distinct axes that share slot 1 by priority. `backlog=·`, `done=●`, `dropped=✕` unchanged.
- **Header chip ordering** — backlog → next → now → done (was: backlog → now → next → done). Pipeline order, matches the Board left-to-right flow.
- **Pin glyph + color** — pin is `*` everywhere (chip row AND preview row; the literal `★` in the preview row was retired). Pin color is `#CBA6F7` lavender — the octopus brand color family — same as `+ migrated` and `◇` activity prefix. Pink is now reserved for `now` bucket and urgent affordances only.
- **Column titles aligned with slot-1** — Board + Focus borders: `□ NEXT`, `▣ NOW`, `● DONE`, `✕ DROPPED`. Row glyphs and column headers now share the same vocabulary.
- **Exception triggers follow schema** — `! blocked` reads `issue=blocked` (canonical, per `SCHEMA-TASK.md`), `? waiting` reads `issue=waiting`, `+ migrated` reads `promoted_to` is set. Legacy `run_state` values still honored for backwards compat.

### Fixed

- **`◆ session` docstring drift** (`cli/src/octopus/tui/header_bar.py`) — the ASCII header art referenced a retired allocation (`◆` for "session live"). Updated to `▶ session`. Filled diamond stays permanently reserved for future activity-state encoding.
- **`✗ DROPPED` column title** — board header used the chrome "error" glyph (`✗ U+2717`) instead of the slot-1 dropped glyph (`✕ U+2715`). Now `✕ DROPPED` for consistency with task rows.

### Docs

- Spec rewritten: `.spectacular/specs/TUI-GLYPHS.md` now leads with the priority resolver, documents chrome glyphs as a separate layer (`▸ ✓ ✗ ⟳ ⌂`), marks unshipped slot-2 flags as reserved (`! : ^ & #`), permanently reserves the diamond family for activity and hexagon family for git.
- `DECISIONS.md` appends D91–D99 — v1 glyph locks, retired `◆ session`, bucket idle glyph allocations, `now` color, pin color, schema field alignment.
- Skill reference `skills/octopus/references/tui-glyphs.md` mirrored from spec.
- New `.spectacular/requests/41-tui-glyph-audit/` shipped with full `AUDIT.md` drift table for future reference.

---

## [0.9.9] — 2026-05-25

**Board view, refined.** The Board (`2`) now spans all five buckets via a sliding 3-column window, the inline detail pane drops down from the bottom on `,` (no more centered overlay), and the cursor follows you across Focus↔Board swaps. The Edit modal grows a third pane: a properties cheat-sheet that inserts the right YAML stub on Enter, so you stop guessing the schema.

### Added

- **Board sliding window** — `2` now pages across `backlog → next → now → done → dropped` in a 3-column window. Pages: `backlog|next|now`, `next|now|done`, `now|done|dropped`. Navigation: `→`/`Tab` past the rightmost slot slides; past the last page **jumps back to page 0** (no wrap-around loop). `←`/`Shift+Tab` hard-stops at page 0. `]` / `[` slide without moving the cursor slot.
- **Inline detail pane on Board** (`cli/src/octopus/tui/board.py`) — `,` toggles a detail pane docked at the bottom (40% of board height); board columns stay visible above. `↓`/`↑` scroll the detail body. Re-renders as the highlight moves across columns. Matches the Focus screen's `,` behavior.
- **Cross-view cursor restore** (`cli/src/octopus/tui/app.py`) — `App.shared_cursor: (bucket, slug)` is stashed before each mode swap. The incoming screen aligns its page to contain the bucket and restores the highlight to the same task.
- **Edit modal: properties pane** (`cli/src/octopus/tui/edit_modal.py`) — read-only cheat-sheet of all 24 canonical task properties (from `SCHEMA-TASK.md`) with one-line descriptions. `F2` focuses the list; `Enter` inserts the YAML stub (`due: YYYY-MM-DD`, `priority: high`, etc.) into the frontmatter pane at the cursor row, then returns focus to the frontmatter.

### Changed

- **Edit modal redesigned** — matches the main-view design vocabulary: heavy lavender frame, bucket-color resting borders, flexible 90% × 90% sizing with floors, footer chip strip, and `_OctopusTextArea` subclass with macOS-native `Alt+←/→` word jump and `Alt+Backspace` word delete.
- **Confirm/Input/Picker modals redesigned** (`cli/src/octopus/tui/prompts.py`) — title in the heavy lavender border, footer chip strip in the same color vocabulary as `KeymapBar`, flexible sizing with min/max floors, alt+arrow word nav in `_OctopusInput`. `BucketPickerModal` shows each row in its bucket color and lands the cursor on the current bucket.
- **`Enter` no longer opens detail on Board** — `,` does (matches Focus). `Enter` is reserved for list-row selection inside ListView widgets.

### Fixed

- **Mode-switch crash on Textual 8.x** (`cli/src/octopus/tui/app.py`) — `switch_screen()` failed with `IndexError: pop from empty list` because root screens are pushed without a result callback. Pressing `1`/`2` crashed the TUI instantly. Replaced with a pop-then-push helper.
- **`1`/`2`/`Enter`/`Esc` swallowed by ListView focus** — Textual 8.x propagation order changed; ListView consumed digit keys before the screen binding fired. Marked the screen-level bindings as `priority=True` on both Focus and Board.
- **Edit modal `e`/`E` split** — `e` opens the in-app modal editor, `E` keeps the `$EDITOR` (vim) flow.

### Notes

- Test suite: 604/604 green.
- `Ctrl+P` for properties pane was the natural binding but Textual 8.x reserves it for the command palette; we use `F2`.
- Focus mode pagination across all 5 buckets is still pending — the current Focus layout is structurally different from the Board's column row and needs a separate design pass.

---

## [0.9.8] — 2026-05-25

**Textual upgrade 0.46 → 8.2.7.** The pinned Textual was three years behind. Crossing 1.0 + 8.x landed without code damage — every API we touch (composition, modal screens, reactive widgets, Static rendering, half-block pixels) stayed stable. Unlocks `App.suspend()`, which fixes the `e`/`E` edit binding that was silently no-oping on 0.46. Promotes v0.9.7-rc1 to a regular release in the same commit since the redesign was visually signed off.

### Changed

- **Textual constraint** in `cli/pyproject.toml`: `>=0.46` → `>=8.2,<9`.
- **`action_edit_external`** in `cli/src/octopus/tui/focus.py` and `board.py` — dropped the `if hasattr(self.app, "suspend"):` guard. `App.suspend()` is always present on 8.x, so `e`/`E` now opens `$EDITOR` directly, the user saves, control returns to the TUI, and the task list refreshes.

### Fixed

- **`e`/`E` edit-in-`$EDITOR`** — previously silent on 0.46 (toast `open: <path>  (e needs newer Textual)`); now functional.
- **Three stale tests** from the v0.9.7-rc1 visual redesign that the previous release missed:
  - `icons.SESSION` → `icons.SESSION_RUN`
  - `status_bar.activity_name` → `status_bar.activity_id`
  - pin glyph `⚐` → `*` (Slot 2 flag glyph per `TUI-GLYPHS.md`)

### Notes

- Test suite: 603/603 green on Textual 8.2.7.
- Rich version bumped 13.x → 15.0.0 as a transitive of Textual. `rich-pixels` 3.0.1 (mascot renderer) is compatible — the suspected wildcard turned out fine.
- CSS parser tightened in late 0.x — `theme.tcss` (444 lines) parses without changes because all colors are hex-inlined.
- Plugin manifests still on `0.1.0` (independent track).
- Documented in `.spectacular/requests/35-textual-upgrade-to-8/`.

---

## [0.9.7-rc1] — 2026-05-25

**TUI visual redesign — release candidate.** Header restructured into a real 3-column layout (mascot · left meta · right counts+tabs) with four height modes (Slim 1 · Compact 3 · Mid 5 · Full 7), an ASCII OCTOPUS wordmark in Full mode, and a smaller content-cropped mascot for Mid. Activity rows now carry `◇ <activity>   ⬡ <repo>` glyphs (lavender) with walk-up git detection bounded at `$HOME`. Panel borders + titles flip to the pane's bucket color on focus instead of universal pink. Replaced Textual's built-in Footer with a custom `KeymapBar` widget so each key chip renders in its mnemonic color per `TUI-KEYS.md`. Detail pane is scrollable, toggleable with `,`, and expands the backlog column when hidden.

### Added

- **Header Mid mode** (height 5) — smaller static mascot + plain OCTOPUS row + activity/path/state rows. Sits between Full and Compact. Auto-selected at 110-139 cols.
- **ASCII wordmark** (Option B) — 3-row block-letter OCTOPUS for Full mode.
- **Activity & repo glyphs** — `◇` (U+25C7) for activity name, `⬡` (U+2B21) for git repo name. Filled variants `◆` `⬢` reserved for future state encodings. Agent-run indicator `»` reserved.
- **`KeymapBar` widget** (`cli/src/octopus/tui/keymap_bar.py`) — replaces Textual's Footer. Per-key colors sourced from `TUI-KEYS.md`: `n` lavender, `m` yellow, `f` green, `p` teal, `d`/`b` pink, `,` lavender, system keys grey. Responsive: 7/9/11 chips by terminal width.
- **Detail pane** — scrollable, lavender border on focus, toggle with `,`, backlog widens when hidden.
- **Bindings**: `b` block (prompts reason), `B` unblock, `u` undo (stub toast), `y` yank slug to clipboard, `g` go-to slug, `H` cycle header mode.
- **Block / unblock actions** in `cli/src/octopus/actions.py`.
- **Skill mirror refs**: `skills/octopus/references/tui-glyphs.md` and `tui-keys.md` — operational subset of the spec, per the CLAUDE.md sync rule.

### Changed

- **Panel border colors are now bucket-coherent on focus only** — BACKLOG grey, NOW pink, NEXT cyan, DETAIL lavender, board DONE green. Resting panels keep the neutral grey border (`#2A2C36`).
- **Header restructured** into Textual `Horizontal` columns (mascot | left meta | right counts) instead of one widget with internal row padding.
- **Counts moved to right corner**; Full/Mid show 2-row counts with labels, Compact uses single-row no-labels.
- **Small mascot** now content-bbox cropped (cols 2-13, rows 2-11) instead of resized — pixel-exact 12×10 figure preserves aspect.
- **Session glyph hygiene**: `▶` is now the single canonical session glyph in both header state row and task-row override. `◆` was retired from "session" allocation (D91).

### Fixed

- **Duplicate OCTOPUS** in the header (purple title + white activity name on separate rows). Activity name now sits on its own glyph-prefixed row.
- **Crooked small mascot** caused by asymmetric source padding (3 left, 2 right) being dragged into the resize. Replaced resize with content-bbox crop.
- **Emoji fast-forward `⏩`** swapped to plain glyph `»` for the reserved agent-run slot.

### Notes

- Plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.agents/`) stay on the independent `0.1.0` track — only the CLI version moves.
- The custom `KeymapBar` replaces Textual's `Footer` entirely; the cyan footer overrides in `theme.tcss` were removed.
- This is RC1 — visual QA pass requested before promoting to `v0.9.7` final.

---

## [0.9.6] — 2026-05-25

**Mascot ambient idle interrupt.** The TUI mascot now occasionally moonwalks on its own while idle — every 30s there's a 15% chance to spontaneously play `moonwalk-d6` or `moonwalk-e` (50/50). Verb-triggered animations (`finish` → capovolta, `pin` → moonwalk-d6) still take priority and reset the ambient clock on completion.

### Added

- **Ambient idle animation roller** in `cli/src/octopus/tui/mascot.py` — tunable via `AMBIENT_TICK_MS` (30_000), `AMBIENT_PROB` (0.15), and `AMBIENT_ANIMATIONS` (`moonwalk-d6`, `moonwalk-e`) in `mascot_frames.py`. Set `AMBIENT_PROB=0` to disable.
- 2 new tests covering the no-fire window and the forced-fire path. Full suite: 603/603 green.

### Notes

- Closes the last open deliverable on `.spectacular/requests/31-tui-mascot-ascii-animations`: ambient interrupt was deferred from initial implementation pending visual QA. QA confirmed; rate locked to the values listed in PLAN.md §"Trigger model".

---

## [0.9.5] — 2026-05-25

**CI hotfix.** Clears 68 ruff violations that were blocking the test workflow on every push to main. No runtime or behavioral changes; 601/601 tests pass.

### Fixed

- **CI test workflow** — `ruff check src tests` (which runs before pytest) was failing with 68 lint violations introduced over recent commits, blocking all CI runs on `main`. Now clean.

### Changed

- **Lint cleanup** in `cli/`:
  - 49 auto-fixes: unused imports, import sort, f-string flags missing placeholders, `zip(..., strict=False)`.
  - Manual fixes: 11× drop `.keys()` from `in` checks (SIM118), 4× collapse nested `if` blocks (SIM102), 2× replace loop-with-return with `any(...)` (SIM110), 2× rename unused loop vars `c`/`q` → `_c`/`_q` (B007), 2× rename ambiguous `l` → `entry` (E741).
- **`cli/pyproject.toml`** — added `SIM401` to `tool.ruff.lint.ignore` with rationale (false positive on `sqlite3.Row`, which supports `in` but not `.get()`).

---

## [0.9.4] — 2026-05-25

**Visual + copy polish pass.** No CLI code changes — refinement of the README hero, diagrams, and positioning copy. Animated mascot, terminal-style lifecycle, vertical axes infographic, and a tighter pitch throughout.

### Added

- **Animated mascot SVG** — `docs/assets/octopus-mascot.svg` is now an animated SMIL loop (~4.5s) mirroring the TUI's idle Calm-A: body bob + blink + leg-wiggle wave. Generator at `assets/mascot/build_animated_svg.py` (re-run any time `cli/src/octopus/tui/mascot_frames.py` changes).
- **`assets/` folder** — internal working files separated from public-facing media:
  - `assets/mascot/octo-v2-lavender.svg` (canonical source)
  - `assets/mascot/octo-v2-lavender-animated.svg` (animated variant)
  - `assets/mascot/build_animated_svg.py` (generator script)
  - `assets/palette.md` — canonical color tokens + copy-paste boilerplate + mobile-renderer limitations.
- **`docs/assets/_versions/`** — pre-edit snapshots from every visual revision in this release (mental-model, scaffold, pipeline, lifecycle, axes, pre-svg-selector batch).

### Changed

- **Lifecycle diagram** redesigned as a single dark terminal window with six numbered command blocks (`# 1. capture an idea` / `$ octopus capture …` / `→ output`). Matches `tui-hero.svg` aesthetic. Dark-only by design. Now `lifecycle.v4.svg`.
- **Axes diagram** rebuilt as a vertical 2-column infographic with larger text (titles 13→18px, values 10.5→13px). Layout: Pipeline | Domain · Attention | Runtime · Impediment | Visibility · Derived (full width). Now `axes.v7.svg`.
- **All theme-adaptive SVGs** (mental-model, scaffold, pipeline, lifecycle, axes) now:
  - Use `svg { ... }` as the CSS selector (replacing `:root`, which doesn't bind reliably in mobile WebKit when SVGs are loaded via `<img>`).
  - Carry a `canvas-bg` rect so light/dark flips are visually unambiguous.
  - Use the canonical palette from `assets/palette.md`.
- **Mascot in tui-hero** rebuilt from the canonical `BASE_REF` grid (was hand-traced and visually off — head started at the wrong row, eye band wrong height, leg pattern compressed).
- **Pipeline diagram** centered horizontally (was left-biased: content x=20→640 inside a 760-wide viewBox).
- **Axes grid gaps** equalized — 20px between cards in all directions (was 10px horizontal / 20px vertical).
- **Animated mascot rendering**:
  - `calcMode="discrete"` on every `<animate>` so pixel cells snap between frames instead of cross-fading (was producing a blurred / smudged look).
  - Tightened loop from 10.76s → 4.48s.
  - Dropped explicit `width`/`height` from the SVG root so the README `<img width="160">` sizes cleanly; added `shape-rendering="crispEdges"` and `image-rendering: pixelated`.
- **Mascot color** locked to lavender `#CBA6F7` in both light and dark modes (no `prefers-color-scheme` switch — matches the TUI's canonical mascot).
- **Derived-row visual weight** in axes muted to a neutral grey wash so it reads as a system note, not another axis card.
- **README copy** tightened in several places:
  - Hero tagline: `A folder-first task system.` → `A folder-first task system. CLI + skill.`
  - Mental-model bullet 1: now leads with "Octopus is the omnipresent entity. Invoke it from the terminal, or hand it to any agent."
  - Mental-model intro: replaced the three-noun framing with `**Octopus → activity → task.** That's the whole shape.`
  - "Why this exists" comparison table: added fifth column **Lives in git**, reordered so **Hands off to agents** lands last (the dramatic differentiator). Honest pass on every cell — competitors with markdown/API access downgraded from ❌ to ⚠️ on the agent column.
  - "Why this exists" closer: `The fracture is the problem. Octopus is the seam.` → `One source of truth: the folder you're already in.`
  - "List is context-aware" sentence moved into a `[!TIP]` callout.
  - Footer note ("A note for the curious") rewritten: `Implementations come and go. The folder primitive stays. For Octopus, every folder is a potential activity — and that idea is the product. If it speaks `.octopus/`, it's Octopus.`
  - Final tagline: `*No app to open. No app to forget.*`
- **Scaffold tag column** moved left and font shrunk (11px → 10px) so long descriptions stop overflowing the left panel.
- **Mental-model "octopus" card** widened (180→220px) and subtitle updated to `CLI + skill — one brain, everywhere`.
- **Octopus-mascot v1** archived to `_archive/mascot/octo-v1-classic.svg`.

### Fixed

- **Mobile WebKit theme-flip inconsistencies** mitigated via the `svg { ... }` selector + explicit canvas-bg rects. (The underlying `prefers-color-scheme` evaluation is still renderer-dependent on mobile; documented as a known limitation in `assets/palette.md`.)
- **Animated mascot blur** — see `calcMode="discrete"` above.
- **Pipeline left-bias** — content shifted right 50px to balance 70/70 margins.
- **Derived row overflow** in axes — `→ bucket NOT IN (done, dropped)` (33px past the panel edge) replaced with `→ bucket ∉ done, dropped`.
- **Scaffold tag overflow** — tags moved from x=280 to x=250 and font-size dropped to 10px so the longest description (`optional · notes for future-you / agents`) fits inside the left panel.

---

## [0.9.3] — 2026-05-24

**Docs split-out + README visual upgrade.** No CLI code changes — pure documentation pass that pulled three heavy sections out of the README into dedicated docs and replaced ASCII mockups with proper SVG assets (matching the lavender TUI palette).

### Added

- **`docs/REPO-LAYOUT.md`** — full repo tree + "where to look for what" table + conventions.
- **`docs/TUI.md`** — full TUI keymap (movement / mutations / search), mode table, mascot behavior, scope rules, log path. The README now keeps only the mockup and a one-paragraph summary.
- **`docs/ROADMAP.md`** — release history + phase table (with phases 30, 31 added) + per-version notes from v0.4.0 → v0.9.2.
- **`docs/assets/`** — 7 SVG diagrams used across the README:
  - `octopus-mascot.svg` — 16×14 pixel-art mascot generated from `BASE_REF` (transparent bg).
  - `mental-model.svg` — hierarchical view of octopus → activity → tasks / sessions / memory / handoffs.
  - `scaffold.svg` — `.octopus/` folder tree with bucket subfolders.
  - `pipeline.svg` — five-bucket flow with `dropped/` as side exit.
  - `lifecycle.svg` — six-step task lifecycle (capture → finish).
  - `axes.svg` — five-axes 3+2 grid with custom icons (track-dots, branching, play, pin, padlock) and a bottom "derived, not stored" strip.
  - `tui-hero.svg` — terminal mockup used as both repo hero and the TUI section preview.
- **`docs/assets/_versions/`** — timestamped SVG snapshots so design history survives later edits.
- **Request #33 — TUI visual redesign** (`.spectacular/requests/33-tui-visual-redesign/PLAN.md`). Opens the design-transfer work from `tui-hero.svg` into the live Textual UI. Status: open, awaiting Alessandro's triage of 28 candidate elements.

### Changed

- **README.md** slimmed **819 → 418 lines** (-49%). Same information density at the top; long reference content moved to `docs/`.
  - Replaced 5 inline SVGs in the wrong coral/peach palette with `<img>` refs to the new lavender assets.
  - Mental-model ASCII tree → `mental-model.svg`.
  - Folder-scaffold inline SVG → `scaffold.svg` (now tree-shaped with proper guide lines).
  - Pipeline / lifecycle / axes inline SVGs → matching files in `docs/assets/`.
  - Tiny ASCII TUI mock in **Daily driver — the TUI** → full `tui-hero.svg` mockup (which now also doubles as the repo hero, placed above the pitch).
  - **"Where things live in this repo"** — long 27-line tree + paragraph → one sentence + link to `docs/REPO-LAYOUT.md`.
  - **"Daily driver — the TUI"** — kept the mockup + one-paragraph summary; full keymap moved to `docs/TUI.md`.
  - **"Status & what's next"** — long release log + phase table → one paragraph (latest version + current phase + v1 gate) + link to `docs/ROADMAP.md`.
  - **`~/code/shift`** placeholder replaced with **`~/code/my-project`** throughout (init output, `octopus where` example, prose).
  - Removed the early `> [!NOTE]` "the protocol is the product" block from the top (too dev-heavy for the intro); re-added as "A note for the curious" at the bottom.
- **Badge colors** updated to match the new palette (lavender / mint).
- **`cli/pyproject.toml`** version `0.9.2 → 0.9.3` to keep CLI and docs releases aligned.

### Fixed

- `axes.svg` and `lifecycle.svg` had clipped bottom margins (last line cut off) — viewBox heights extended.
- `octopus-mascot.svg` no longer paints a `#0F1014` background — transparent, lets the GitHub theme show through.

---

## [0.9.2] — 2026-05-24

**Animated TUI mascot** (#31 done). The static octo in the TUI header is now alive: a continuously-breathing idle state with decoupled blink channel, plus two event-triggered animations that play on top of user actions.

The design was iterated through ~9 rounds in a self-contained HTML preview before any Python landed — preview.html and calm-debug.html in `.spectacular/requests/31-tui-mascot-ascii-animations/` document the journey.

### Added

- **`cli/src/octopus/tui/mascot_frames.py`** — frame library with all confirmed grids:
  - `BASE_REF` + `POOL_FRAMES` for Calm-A (rest / up / down body bob)
  - `CAPOVOLTA_B_FRAMES` (6-frame squish + flip, ~900ms)
  - `MOONWALK_D6_FRAMES` (15-frame glide with ratcheting legs + blink at apex, ~2.7s)
  - `MOONWALK_E_FRAMES` (9-frame wave-of-legs variant, ~1.75s)
- **`apply_blink(grid, level)`** — dynamic eye-row detection so the blink direction stays consistent regardless of body shift. The lid always drops from above, leaving a thin dark line at the bottom of the eye cell.
- **`MascotController`** — pure-Python state machine. Default state runs Calm-A (independent body + blink channels with random timing). `trigger(name)` plays a one-shot animation, then returns to idle. Triggers during animations are ignored (no queueing).
- **Event wiring** — `octopus finish` (from focus or board) triggers capovolta; `octopus pin` triggers moonwalk-D6. Silent on lookup miss; verbs never fail because of the mascot.
- **25 new tests** in `test_mascot_animation.py`: frame integrity, apply_blink across body shifts (the v9 bug), state machine transitions, animation completion (601 total, was 576).

### Changed

- **`cli/src/octopus/tui/mascot.py`** refactored to a generic frame renderer + state machine wrapper. The old single-frame `render_mascot()` still works (backwards compat). New `render_grid(grid)` accepts any 16×14 grid string.
- **`_Mascot` widget** (in `header_bar.py`) is now stateful. Owns a `MascotController`, drives it via a 50ms Textual interval, re-renders only when the grid changes (cheap diff).

### Locked design

| Component | Choice | Why |
|---|---|---|
| Canvas | 16×14 pixels (existing) | Fits the TUI header slot. |
| Body bob | rest → up → rest → down, 1200ms each | Deterministic (random caused visible "jumps"). |
| Blink | half 100ms → closed 180ms → half 100ms; cooldown 2-4s; ~20% doubles | Decoupled from body so blinks happen mid-cycle naturally. |
| Capovolta | 6-frame squish + flip | Smaller motion than the rejected somersault. |
| Moonwalk D6 | Body ±1, legs ratchet ±2, blink at apex | Legs visibly glide faster than body. Blink replaces head-squash (kept eyes visible). |
| Moonwalk E | Wave-of-legs, body still | Variant for a different verb hook (TBD). |

### Notes

- Triggering during a running animation is a no-op. We deliberately don't queue — keeping the mascot reactive but not overloaded.
- The 50ms tick granularity is the GCD-ish of all our animation timings (100/150/180/200ms). Cheap enough that visual lag is imperceptible.
- `apply_blink` dynamically detects eye-row positions instead of hardcoding rows 5-6 — fixes a class of bugs where blinks looked inverted when the body was bobbed up or down.

---

## [0.9.1] — 2026-05-24

**Skill upgrade — proactive agent behaviors** (#29 done). `skills/octopus/SKILL.md` now teaches agents *when* to use the verbs that shipped in 0.8.0/0.9.0. Pure documentation; no CLI changes. The skill version bumps to 0.9.1 to track.

### Added (SKILL.md)

- **"Proactive behaviors — user intent → verb routing"** section: a table mapping common user phrasings ("what should I do", "what's going on", "add to <project>", "what's overdue", "give me JSON of <project>") to the verb the agent should run, plus the natural follow-up.
- **"Triage rituals"** section: morning review, end of day, inbox triage, weekly stale check, cross-project sweep. Each is a sequence of CLI invocations the agent can suggest or run autonomously.
- **"Choosing the right verb"** decision trees for: adding a task, editing a task, moving between buckets, reading a project. Forces the agent to confront the question "which axis am I on?" before composing a command.
- **"Reading vs writing — never blow up the user's data"** section: confirmation checklist for the destructive corners (`forget`, `--slug` rename, bulk `set --task`/`set --activity`).
- **Hard rules 10/11/12**:
  - **Rule 10** — never `forget` or cascading slug rename without explicit confirmation.
  - **Rule 11** — cross-activity writes use `--activity <id>` whenever the user names a target; never silently default to cwd.
  - **Rule 12** — when intent is ambiguous, ASK; never pick arbitrarily.

### Changed (SKILL.md)

- **Description** in frontmatter expanded to include dashboards, ranking, and the cross-activity routing intent — so the skill is invoked by Claude on questions like "what should I do" without the user naming Octopus.
- **Verb index** refreshed with the new `add task/activity`, `dashboard`, `next`, `impact`, `get activity`, `list tasks/activities`, `forget activity`, and the `--activity` flag.
- **Cross-activity flag callout** (`--activity <id>`) added inline after the verb index so the pattern is impossible to miss.

### Notes

- The skill is now self-contained for the proactive use case: an agent loaded with it can answer "what should I do" or "what's the status of X" without further coaching, and won't try to grep `list --all` when `dashboard` / `next` / `impact` exist.
- The decision-tree section is intentionally exhaustive — agents pattern-match better with explicit branches than with prose advice.

---

## [0.9.0] — 2026-05-24

**Cross-activity reads + dashboards** (#27 done). Octopus now answers "what's going on across all my projects" without `cd` — and ranks tasks by impact so agents can pick the right next thing automatically. New verbs: `dashboard`, `next`, `impact`, `get activity`, plus noun-explicit `list tasks/activities` with rich filter flags. The activity-level `priority` field that #26 stubbed out is now live.

This is the read-half of the cross-activity story. Combined with #26 (write verbs), an agent in a global terminal can now ask "what should I work on?", get a ranked answer, write to any project, and never need to `cd`.

### Added

- **`octopus dashboard`** (D90) — composite cross-activity view: pinned tasks, overdue tasks, in-progress (`now`) tasks, blocked items, and activity priority breakdown. Rich text by default; `--json` writes JSON to stdout; `--json-out <path>` writes JSON to file.
- **`octopus next [--limit N]`** (D90) — top N tasks ranked by impact (R1 heuristic). Default N=3.
- **`octopus impact [--limit N] [--show-score]`** (D90) — full ranked task list. Default top 20; `--limit 0` = unlimited; `--show-score` reveals the numeric score per row.
- **`octopus get activity <path-or-id>`** (D90) — JSON dump of activity metadata + bucket counts + now/pinned/overdue task previews. Noun-explicit (future-stable for `get task <slug>`). TTY → pretty JSON; pipe → compact; `--format pretty|compact` override.
- **`octopus list tasks <path-or-id>`** and **`octopus list activities`** (D90) — noun-explicit subcommands of `list`. Bare `octopus list` stays context-aware (tasks inside an activity, activities outside).
- **Activity-level filter flags on `list`**:
  - `--priority low|high|urgent` (uses D87 field)
  - `--type` / `--area` (multi-value via comma)
  - `--has-pinned` / `--has-overdue` / `--has-now`
  - `--touched-within <N>` (last N days)
- **`octopus status <path-or-id>`** now extended (D90) — accepts a path or id, shows priority chip, last-reviewed/last-touched dates, and first N now/pinned/overdue task titles. `--limit N` controls how many.
- **Activity `priority` field** (D87) — optional enum (`low|high|urgent`) on `activity.md`. Set via `octopus set --activity <id> --priority X` or `octopus add activity --priority X` (the #26 stub-reject is gone).
- **`core/ranking.py`** — R1 heuristic implementation with 21 unit tests covering every weight contribution and exclusion case.
- **23 new integration tests** in `test_cross_activity_reads.py` covering list filters, status rich view, get JSON, dashboard, next, impact, and ranking order.

### Changed

- **`octopus list` signature**: now accepts an optional noun (`tasks` or `activities`) and an optional path-or-id target. Single-positional invocation behaves as before; the new shapes are additive.
- **Activity table sort order**: priority desc (urgent → high → normal → low), then `last_touched_at` desc, then title. The dashboard list reflects this naturally.
- **`upsert_activity`** gained a `touch=True` keyword (D88) that bumps `last_touched_at` to now. Called from `sync_*_after_write` paths so every write refreshes the activity's heat signature.

### Locked in DECISIONS.md

- **D87** — Activity `priority` field; strict enum; same convention as task priority.
- **D88** — Schema v3 → v4 migration: `activities.priority` + `activities.last_touched_at` columns + supporting indexes. Idempotent.
- **D89** — R1 ranking heuristic; algorithm fixed for v1, configurable weights deferred. Algorithm goes in `core/ranking.py` so call sites stay stable when weights become tunable.
- **D90** — Dashboard / read-verb output conventions: rich text default, `--json` flag for stdout, `--json-out <path>` for file. Noun-explicit forms for `list` and `get`.

### Notes

- The `--json` + `--json-out` split (rather than a single `--json [path]`) is a deliberate compromise: Typer's optional-value flags don't compose cleanly with the rest of our flag matrix. Two flags, one mental model: `--json` means stdout, `--json-out` means file.
- Schema migration v3 → v4 is idempotent. Existing databases auto-migrate on next `get_db()`; existing rows get `priority = NULL` and `last_touched_at = NULL` until next write.
- `last_touched_at` is currently bumped on task writes only. Session/memory write touches are deferred — add later if dashboards need finer signal.

---

## [0.8.0] — 2026-05-24

**Cross-activity write verbs** (#26 done). Every task-mutation verb now accepts `--activity <id>` to redirect the operation to a specific activity without `cd`. New `octopus add task` and `octopus add activity` verbs are the canonical "from anywhere" entry points. `octopus set` gets multi-target shapes — `--task t1 t2 ...` for in-cwd tasks and `--activity a1 a2 ...` for activity-level edits anywhere, with strict one-target-axis-per-invocation enforcement.

This release closes the agent-friendliness gap: an agent (or a global terminal) can now add tasks, set priorities, finish work, or update activity metadata against any project on disk without changing directories.

### Added

- **`octopus add task "<title>" [--activity <id>] [...]`** (D85) — the "from anywhere" sibling of `capture`. Identical flag matrix; targets the named activity by id, unambiguous prefix, or filesystem path. Without `--activity`, behaves like `capture` (cwd-walk-up).
- **`octopus add activity "<name>" [--type --area --path --id --storage]`** (D85) — sibling of `octopus init`. Without `--path`, creates `<slug-of-name>/` under cwd; with `--path`, initializes that directory. `--priority` rejected with "not implemented" until #27 ships the activity priority field.
- **`octopus set --task t1 --task t2 ...`** (D84) — multi-target tasks within the current activity. Slugs resolve against the cwd activity only; cross-activity task mutation deliberately out of scope for v1.
- **`octopus set --activity a1 --activity a2 ...`** (D84) — multi-target activities from anywhere. Operates on activity-level frontmatter (title, status, type, area, last-reviewed, tags). Task-only flags rejected with the offending flag named.
- **Comma-shorthand** on `set --task` / `set --activity` — `--task t1,t2,t3` is equivalent to `--task t1 --task t2 --task t3`.
- **`--activity <id>` flag on every task-mutation verb** (D86): `capture`, `pin`/`unpin`, `plan`/`focus`/`park`/`defer`, `start`/`finish`/`drop`/`end`, `archive`/`restore`, `mv`/`move`, `block`/`wait`/`unblock`, `promote`. Path-or-id resolution via the shared `core/identify.py` resolver.
- 23 new tests in `test_cross_activity_writes.py` (531 total, was 508).

### Changed

- **`octopus set` positional signature**: was `set <slug>` (required, one), now `set [SLUGS]...` (variadic). Single-positional invocation behavior is unchanged. Multiple positional slugs now error with "use --task for multi-target" — keeping the foot-gun off.
- **`_load_task()` and `_move_bucket()`** internals: now accept an optional `activity_token` parameter, threaded through every verb that uses them. cwd-walk-up remains the default.

### Locked in DECISIONS.md

- **D84** — One-target-axis-per-invocation rule for `set`. Mixing positional + `--task`, positional + `--activity`, or `--task` + `--activity` is rejected. Activity-level fields only allowed with `--activity`; task-only fields rejected.
- **D85** — `add task` / `add activity` verb semantics. `capture` and `init` remain as aliases.
- **D86** — `--activity <id>` flag on all write verbs. Single-target on tasks; multi-target only via `set` per D84.

### Notes

- `--priority` on `add activity` and `set --activity` is intentionally stub-rejected with a pointer to #27, which will add the activity priority field (low/high/urgent enum, empty=normal).
- Cross-activity task mutation (e.g. "update task X in project A from inside project B") is **not v1 scope**. Activity-level edits go cross-activity; task-level edits stay within the cwd activity. This avoids the "wrong project's task" foot-gun.

---

## [0.7.0] — 2026-05-24

**Index hygiene** (#30 done). New `octopus forget activity` verb to remove an activity from the index without touching files (or with `--archive` to also move files to `_archive/`). Archived activities now hidden by default from `list --all`. One-time cleanup of accumulated test/smoke entries pruned 577 stale rows.

This release also introduces the **`forget` Typer sub-app** as the canonical home for index-removal verbs. Today: `forget activity`. Future-stable: `forget task` if real demand surfaces.

### Added

- **`octopus forget activity <path-or-id> [--archive] [-y]`** (D83) — remove an activity from the SQLite index.
  - Files on disk are NOT touched by default.
  - `--archive` (or `--also-archive`) moves the activity folder to `<parent>/_archive/<name>/`.
  - `-y` skips the interactive prompt. **`-y` alone does NOT imply archive** — it's the "yes, just forget" affirmation. Combine with `--archive` to do both.
  - Interactive prompt when neither flag is given; suggests both flag-form equivalents for next time.
  - Path-or-id auto-detection: tokens starting with `/`, `~`, or containing `/` → resolved as filesystem path; otherwise → resolved as activity ID (exact match or unambiguous prefix).
- **`octopus core.identify`** — shared path-or-id resolver. Will be reused by #26 (`add task --activity`) and #27 (`status / list tasks / get activity` with `<path-or-id>`).
- **`--include-archived` flag on `octopus list`** — surface archived activities (hidden by default).
- **19 new tests** in `tests/test_index_hygiene.py`. Total suite **508 passing** (was 489).

### Changed

- **Archived activities hidden by default** in `list_activities()` query (D83). The default cross-activity `list` and `list --all` now exclude any activity with `status: archived`. Use `--include-archived` to show them, or `--status archived` for archived-only.
- **`SchemA_VERSION` unchanged** at 3 — no schema migration needed; the change is purely query-level.

### Migration

- Existing databases: no schema migration. Archived activities (if any) silently disappear from default `list --all` output on first use of 0.7.0. To check what got hidden: `octopus list --all --include-archived`.

### Smoke / one-time cleanup

If your global index accumulated test/smoke noise:

```bash
# Remove any stale roots
octopus config root remove /tmp/some-stale-root

# Drop rows whose source files are gone
octopus reindex --prune

# Forget specific activities you no longer want indexed
octopus forget activity <id-or-path> [-y] [--archive]
```

This release was tested by cleaning 577 stale rows from the dev box's index in one pass.

---

## [0.6.1] — 2026-05-24

**Skill documentation patch.** Brings `skills/octopus/SKILL.md` and its references up to date with the v0.3.0 → v0.6.0 surface (kind enum, task promotion, adapter framework, three adapters, capture/edit polish). No code changes; agents using this skill now see the full v0.6.0 verb set, the tag flag matrix, the slug-rename cascade, the `set` vs `mv` boundary, and the corrected legacy-field rules.

### Changed

- **`skills/octopus/SKILL.md` → v0.6.1** (was v0.4.0).
  - Hard rules updated: `kind` is no longer legacy (rule 4); slug rename uses `set --slug` not `octopus rename` (rule 5); two new rules covering D80 explicit-default semantics, D76 tag storage, and D77 `set` vs `mv` separation.
  - Verb index updated: editing row now reads `set` (frontmatter-only), `set --slug` (cascading rename), `move`/`mv` (file move). New "References" row for `refs find`. `list` views row includes `--tag`. Capture row notes "rich flags".
  - New "Capture and edit at a glance (v0.6.0)" cheat-sheet below the verb index showing the full flag surface in copy-pasteable form.
  - New section "Tags (D76)" with the full flag matrix, input forms, mutex rule, and filter semantics.
  - New section "Slug renames and references (D78, D79)" documenting the cascade contract and `refs find` companion.
  - New section "`set` vs `mv` vs lifecycle verbs (D77)" explaining the three-way boundary.
  - New section "Capture flag surface (v0.6.0)" listing every accepted flag.
- **`skills/octopus/references/cli-verbs.md`** updated:
  - `capture` documentation shows the full v0.6.0 flag set with explicit-default behavior.
  - `archive`/`unarchive` corrected to `archive`/`restore` (the actual verbs).
  - `Set / rename / move` section rewritten with the full set/mv/slug-rename contract.
  - New "Tag input forms" + "Tag filter" + "References" sections.
- **`skills/octopus/references/critical-dependencies.md`** updated:
  - Rule T6 corrected: `kind` is no longer in the forbidden list.
  - Rule X1 clarified: default-omission applies to frontmatter; CLI flags follow D80 (explicit-default values clear).
  - Rule X3 corrected: filename stability uses `set --slug`, not the non-existent `octopus rename`.
  - Five new rules X8–X12 covering D76 (tag matrix), D77 (`set` frontmatter-only + `mv`), D78 (slug rename cascade), D80 (explicit-default clear), D81/D82 (capture defaults).

### Fixed

- Outdated references in skill docs that pointed at verbs which never shipped (`octopus rename`) or were superseded (the `kind` forbidden-field rule).

---

## [0.6.0] — 2026-05-24

**Capture and edit polish.** Months of paper-cuts cleaned in one pass: richer `capture` flags, atomic tag mutations with full Obsidian compatibility, a proper slug rename with cascading auto-fix, a `move`/`mv` verb that separates file-move from frontmatter-edit, and a `refs find` helper that locates every Octopus-managed reference to a slug.

### Added

- **Tag flag matrix** on `capture` and `set` (D76):
  - `--tag` / `--tags` — replace the tag list.
  - `--add-tag` / `--add-tags` — append, dedup.
  - `--remove-tag` / `--remove-tags` — subtract.
  - `--clear-tags` — empty.
  - All accept **comma-separated**, **space-separated** (within a quoted arg), and **repeated invocation**: `--tag X,Y` ≡ `--tag "X Y"` ≡ `--tag X --tag Y`.
  - Singular and plural are aliases.
  - Replace and incremental are **mutually exclusive** — mixing them errors with a clear message. Forces clarity over guessing.
- **Tag storage** with leading `#` to match Obsidian (`tags: ["#bug", "#tui/marquee"]`). Nested via `/`. Reader accepts both `#bug` and `bug` (silent normalization on write). Flag values accept with or without `#`.
- **Tag prefix-match filter** (`list --tag parent` matches `#parent` AND `#parent/*`) — Obsidian-compatible.
- **`capture` gains** `--due`, `--scheduled`, `--start-date`, `--end-date`, `--actor`, `--energy`, `--owner`, `--stage` flags.
- **`octopus move <slug> <bucket>` + `mv` alias** (D77) — pure file-move + frontmatter update. No date stamps, no lifecycle side effects. Validates against schema rules (e.g. `mv x done` without `end_date` is rejected and points at `finish`).
- **`octopus set <slug> --slug <new>` with cascading rename** (D78). Auto-fixes filesystem, SQLite index, `waiting_for` in other tasks, `related_tasks` and `promoted_from` in spectacular PLAN.md, and `→ octopus:<slug>` arrows in TODO.md. Soft warning (named files, not touched) for session bodies, memory body, handoff bodies. `-y` skips the confirmation prompt; default is interactive.
- **`octopus refs find <slug>`** (D79) — read-only verb. Greps every Octopus-managed text file for a slug and prints `category | file:line | line`. Splits managed vs user-prose categories. `--all` for cross-activity. Companion to `set --slug` for tracking down residual references.
- **7 decisions locked** (D76–D82).
- **85 new tests** (46 in `test_tag_parser.py` + 39 in `test_capture_edit_polish.py`). Total suite **489 passing** (was 404).

### Changed

- **`set --bucket` is frontmatter-only** (D77). Previously moved the file in folder mode; now edits the field only. Emits a soft warning in folder mode when the file's parent directory no longer matches the new bucket value, pointing at `octopus mv`. The lifecycle verbs (`start`/`finish`/`drop`) still move files because that's their job.
- **Explicit-default values clear instead of reject** (D80). `--priority normal`, `--actor human`, `--energy normal`, `--run-state idle`, empty strings on any optional field, etc. — all accepted and clear the field.
- **`capture --now` no longer auto-pins** (D81). Pin stays orthogonal to bucket per the AXIS-MODEL (D43). If you want a pinned-now task: `octopus capture X --now && octopus pin X`.
- **`capture` body is empty by default** (D82). Previously wrote `\n## References\n`; now writes nothing. `## References` reappears as a manual user choice. (Inline `--body` is deferred to a future request.)
- **Backwards-compatible tag migration:** tasks with `tags: ["bug"]` (no `#`) are still read correctly. On any write, the tag values are normalized to include `#`. Quiet migration — no schema change.

### Behavioral compatibility risks

- **Anyone scripting `set --bucket` and expecting the file to move** will be surprised. Use `octopus mv` instead. The soft warning makes this discoverable.
- **Anyone relying on the implicit pin from `capture --now`** will get an unpinned task. Add `&& octopus pin` if needed.
- **`capture` no longer writes `## References`**. New tasks have empty bodies. Add the heading manually or via a future `--body` flag.

### Smoke

```bash
# Capture with everything
octopus capture "ship it" --priority high --due 2026-07-01 --tag work,urgent --energy mid

# Tag mutations are now atomic + Obsidian-compatible
octopus set ship-it --add-tag p0 --remove-tag urgent
octopus set ship-it --clear-tags --add-tags release,launch

# Frontmatter ≠ file move
octopus set ship-it --bucket next        # → warning: run `octopus mv` to match
octopus mv ship-it next                  # → physical move + frontmatter

# Rename a slug, refs auto-fixed everywhere
octopus set old-name --slug new-name -y

# Find every reference
octopus refs find old-name --all
```

### Deferred

- `capture --kind` and full kind clarification — request #25.
- `capture --body` / inline body input — future.
- Tag exact-match (`--tag X --exact`) — future.
- Auto-fix of session/memory/handoff prose during slug rename — too risky; remains user task.
- `octopus refs rewrite` (would auto-fix the soft-warned files too) — too risky for v1; read-only `find` for now.

### Migration

- **No schema migration.** Tag format change is reader-tolerant; the next write normalizes.
- **SQLite untouched.** Schema stays at v3.

---

## [0.5.0] — 2026-05-24

**TODO.md becomes a real protocol surface** (#22). Adopts GFM checklist + [Obsidian Tasks emoji format](https://publish.obsidian.md/tasks/Reference/Task+Formats/Tasks+Emoji+Format) as the parsing standard, adds the `→ provider:slug` arrow convention (Octopus's only new syntax), and makes the adapter **two-way for source annotation**: on successful pull, `TODO.md` is rewritten in place so each imported `- [ ] thing` line becomes `- [x] thing → octopus:<task-slug>`. The file is now a living at-a-glance index of "what's in Octopus."

Plus three new mutation verbs (`add`/`complete`/`uncomplete`) for editing `TODO.md` without ever importing into the task tree.

### Added

- **`Capability.MARK_PULLED`** — new flag on the adapter protocol (D74). Declared by `todo-md`. Adapters declaring it implement `mark_pulled(mapping)` which is called by the pipeline after a successful materialize.
- **`→ <provider>:<slug>` arrow** in TODO.md is now the canonical "this item is now elsewhere's responsibility" marker. Parsed items with arrows are skipped on import. v1 providers: `octopus`, `spectacular`. Future-stable for `linear:`, `github:`, etc.
- **Obsidian Tasks emoji parsing** in `todo-md`:
  - Priorities: `🔺`/`⏫` → `priority: urgent`; `🔽`/`⏬` → `priority: low`; `🔼` dropped (Octopus has no medium).
  - Dates: `📅 YYYY-MM-DD` → `due`; `⏳` → `scheduled`; `🛫` → `start_date`.
  - Tags: `#tag` collected and appended to `tags`.
  - No-op emoji (`➕`/`✅`/`❌`/`🔁`) preserved on rewrite but not surfaced as Octopus fields v1.
- **Extended GFM marker set** in `todo-md`:
  - `- [/]` and `- [-]` → `bucket: now` (in-progress).
  - `- [!]` → cancelled (skipped on import).
  - `- [?]` → treated as unchecked (forgiving).
- **`octopus bridge add <adapter> <title>`** — new verb. Appends a new checkbox to the adapter's source with optional `--priority urgent|low`, `--due YYYY-MM-DD`, `--tag X` (repeatable), `--section <slug>`, `--state open|in-progress`. No Octopus task is created — the source is the truth.
- **`octopus bridge complete <adapter> <match>`** — substring-match an open checkbox, toggle to `[x]` in place. `--first` flag for ambiguous matches.
- **`octopus bridge uncomplete <adapter> <match>`** — reverse. Strips any `→ ...` arrow from the line (item is no longer handed off).
- **4 decisions locked** (D72–D75) in `.spectacular/DECISIONS.md`.
- **40 new tests** in `tests/test_adapter_todo_md.py` covering: inline metadata parsing for every emoji + tag + arrow case, arrow-exclusion on pull, cancelled/in-progress markers, prefix-plus-emoji combined parsing, the annotation primitive (basic + with metadata + idempotent), section insertion helpers, end-to-end mark_pulled rewrite, mutation verbs (add + complete + uncomplete) happy + edge paths, capability declaration assertions. **Total suite: 404 passing** (was 364).

### Changed

- **`todo-md` adapter** declares `{PULL, MARK_PULLED}`. The new behavior is opt-in by capability — `reminders` and the still-stub `obsidian` do NOT declare it and are unchanged.
- **`ExternalTask.source_group`** is now consistently populated by `todo-md` (set to the parsed heading slug). Was already in the schema; just used more reliably now.
- **`adapters/pipeline.py`** calls `adapter.mark_pulled(mapping)` after a successful materialize if the adapter declares the capability. Errors from `mark_pulled` are surfaced but do NOT undo the materialization.
- **Bridge mutation verbs are gated on `MARK_PULLED`** — calling `add`/`complete`/`uncomplete` on an adapter that doesn't declare it exits 1 with a clear message. Future-proofs the surface: if a `linear` adapter eventually declares `MARK_PULLED`, the same verbs work against it for free.

### Migration

- **No schema migration.** `Capability.MARK_PULLED` is a new enum value; existing adapter classes that don't declare it keep working unchanged.
- **No CHANGELOG-worthy breaking changes.** Users with an existing `TODO.md` see their first pull annotate every imported line — visible by design, recoverable via git.

### Deferred (request #23)

Full TODO.md CRUD (`edit`, `move`, `reorder`, `remove`, `--all` / `--matching`) is captured as a separate request, to be activated only if 4–6 weeks of real use surface concrete friction beyond what `add` / `complete` cover.

### Smoke

In any activity with a `TODO.md`:

```bash
# Add an item from the CLI, no editor needed
octopus bridge add todo-md "fix that thing" --priority urgent --due 2026-07-01 --tag work --section friction

# Pull — items get materialized AND the source gets annotated
octopus bridge pull todo-md

# Look at TODO.md — every imported line now shows → octopus:<slug>

# Complete in place without re-opening the editor
octopus bridge complete todo-md "thing"
```

---

## [0.4.2] — 2026-05-24

**Apple Reminders adapter ships** (#09). Second real adapter, hard-requires the [`remindctl`](https://github.com/steipete/remindctl) CLI for EventKit access. Pull-only — Reminders → Octopus backlog. Stable EventKit UUIDs make dedup trivial; native priority/due/notes mapping into Octopus fields.

### Added

- **`reminders` adapter** replaces its stub. Pulls from one or more configured Apple Reminders lists via `remindctl show all --list <name> --json`.
- **Multi-list aggregation:** `lists = ["Inbox", "Errands"]` in `bridges/reminders.toml` pulls from both into one PullResult.
- **`ExternalTask.suggested_priority` and `suggested_due`** added to the framework — adapters can hint priority and due dates, the pipeline propagates them to task frontmatter.
- **Field mapping** (D70):
  - EventKit UUID → `external_refs.reminders` (bare; D69)
  - `title` → task title (verbatim)
  - `notes` → task body (multi-line preserved)
  - `priority: high|low` → `priority` (Octopus); `none`/`medium` omitted
  - `dueDate` (ISO 8601 UTC) → `due` (date only; time stripped)
  - `listName` → `source_group` (surfaces in summary line)
  - `isCompleted: true` → skipped unless `include_completed = true`
- **Authorization probe** runs on `bridge enable reminders` via `remindctl status`. Denied access reported in `validate_config()`; user fix is one System Settings click.
- **Healthy `status()` reporting** requires both `remindctl` on PATH AND `Full access`. Missing binary → "install via `brew install steipete/tap/remindctl`" hint.
- **Wrapper isolation:** `adapters/_reminders_io.py` (private) contains every subprocess and JSON parse. The adapter module is declarative and trivially mockable. **35 new tests** in `tests/test_adapter_reminders.py` cover priority/due/notes mapping, validate_config rejection paths, multi-list aggregation, search filter, and graceful degradation when `remindctl` is missing.
- **5 decisions locked** (D67–D71) in `.spectacular/DECISIONS.md`.
- **Test suite total: 364 passing** (was 329).

### Changed

- **`ExternalTask`** gains two optional fields (`suggested_priority`, `suggested_due`). Backward-compatible with TODO.md adapter — both fields default to `None`.
- **Pipeline (`adapters/pipeline.py`)** honors the new suggestion fields during materialization.
- **Stub-protocol test** patched to acknowledge Reminders is now real (Obsidian alone remains a stub).

### Manual smoke (macOS only)

```bash
brew install steipete/tap/remindctl       # one-time
remindctl status                          # expect "Full access"

# In an activity:
octopus bridge enable reminders --set lists=Default,Inbox
octopus bridge peek reminders             # JSON rows displayed, no files
octopus bridge pull reminders             # materializes as backlog tasks
octopus bridge pull reminders             # "N already-known" — dedup via UUID
octopus task list                         # see imported items
```

### Migration

- Existing v0.4.x databases: no schema change. `ExternalTask` field additions are runtime-only.

---

## [0.4.1] — 2026-05-24

**First real adapter ships.** TODO.md (#21) replaces its stub with a working
pull-only adapter. The simplest possible adapter — single file source, no API,
no auth — and the reference implementation for #07 (Obsidian) and #09
(Reminders).

### Added

- **`todo-md` adapter** reads `- [ ] task` checkbox lines from a `TODO.md` file at the activity root (or any configured path).
- **Checkbox markers:** `[ ]` → backlog, `[x]`/`[X]` → done (skipped unless `include_checked = true`), `[-]`/`[/]` → in-progress (`bucket: now`). Unknown markers fall back to unchecked.
- **Title cleanup:** strips and maps leading prefixes. `BUG:` → `kind: bug`, `HACK:` → `kind: chore`, `TODO:`/`FIXME:` stripped without kind. `NOTE:` items are skipped (notes ≠ tasks). Unknown ALLCAPS prefixes are kept verbatim — no false positives.
- **Section filtering** via `bridges/todo-md.toml`: `section_filter = ["backlog", "ideas"]` matches heading slugs (`## Backlog` → `backlog`). Empty list = import every section.
- **Stable `external_id`s** via slug-of-title (`TODO.md#fix-crash-on-save`) — survives line-number drift, idempotent across re-pulls. Duplicate titles get a `-N` counter suffix.
- **Missing-file soft no-op:** `peek` returns empty, `pull` exits 0 with a "no TODO.md found at <path>" entry. Running after the file appears just works.
- **`search()`** falls back to `peek + filter` on title substring — no native API needed.
- **Single-source semantics:** `list_groups()` returns `[]`. `peek` no longer goes into discovery mode for single-source adapters; it just runs.

### Changed

- **`resolve_groups`** now takes `adapter_has_groups: bool` to distinguish multi-group adapters (Reminders, GitHub, …) from single-source ones (TODO.md). Single-source skips the `--list` / `--capture-all` matrix entirely.
- **CLI flow** updated: peek-discovery only fires when the adapter actually has groups.
- **Stub-protocol test** updated to reflect that TODO.md is now a real implementation (Obsidian + Reminders remain stubs).

### Tests

- **30 new tests** in `tests/test_adapter_todo_md.py`: checkbox parsing (all marker variants), title prefix mapping, slug heading normalization, full-content parsing under every config combination, dedup-by-slug across duplicate titles, missing-file no-op, search filter, validate_config rejection cases. Total suite **329 passing** (was 299).

---

## [0.4.0] — 2026-05-24

The **adapter framework**: a shared protocol every external integration implements (Obsidian, Apple Reminders, TODO.md, future GitHub/Linear/Notion), plus the `octopus bridge` CLI surface to operate them generically. Ships framework-only — no working adapter; the three known integrations land as stubs that satisfy the protocol but point at requests #07/#09/#21 for real implementations.

### Added

- **`octopus bridge` subcommand group** with seven verbs: `list / enable / disable / status / peek / pull / search`. Hidden alias `octopus adapter` works the same.
- **`peek` vs. `pull` split.** `peek` is read-only display (no files created, no index writes). `pull` materializes external items as Octopus tasks deduped via the new index. With no configured group and no flag, `peek` lists available groups (discovery mode); `pull` exits 3 to refuse unbounded materialization.
- **`bridge search <name> <query>`** — adapter-side search. Adapters with native APIs use them; others fall back to `peek + filter` internally.
- **`Capability` enum** with four atomic values: `PULL / PUSH / NOTIFY / RECONCILE`. v1 adapters declare only `PULL`; the others are forward-stable flags whose methods ship with #12 / #10.
- **`Adapter` Protocol** (`runtime_checkable`) with seven methods: `status / validate_config / list_groups / peek / pull / push / search`. `link()` from the PRD sketch dropped — pipeline glue, not adapter behavior.
- **Per-adapter Typer flags** via the generic `--set key=value` (repeatable). `lists`-named keys are always coerced to TOML arrays. `--force` skips `validate_config` (useful for stubs and temporarily-unhealthy adapters).
- **`list_groups()`** method on the protocol — drives both `peek` discovery and `--capture-all` resolution.
- **Group selection matrix:** `lists = []` config + `--list NAME[,NAME...]` flag + `--capture-all` override; `--list` and `--capture-all` mutually exclusive (exit 1). Per-adapter native flag names planned for #07/#09/#21 (Reminders `--list`, GitHub `--repo`, etc.).
- **Hybrid config layout** (D58): `[adapters.<name>] enabled` lives in main `~/.config/octopus/config.toml`; per-adapter content lives in `~/.config/octopus/bridges/<name>.toml`. Disable preserves the bridge file — re-enable is one command.
- **Sync journal**: one JSON file per adapter at `~/.local/share/octopus/sync/<name>.json` carrying `last_pull`, `last_push`, counters, and opaque `cursor`. Fixed-size in v1; no rotation needed.
- **Pull pipeline** (`adapters/pipeline.py`): materializes `ExternalTask` items into Octopus tasks with full provenance (`actor=human`, `imported_from=<adapter>`, `import_date=<today>`, `external_refs.<adapter>=<external_id>`). Honors `suggested_bucket`, `suggested_kind`, `suggested_tags` hints. Returns `MaterializeResult` (new / skipped / errors / source_groups).
- **Dedup index** (`task_external_refs` join table, schema v3): fast indexed lookup of `(adapter, external_id) → task_id`. `upsert_task` keeps it in sync with frontmatter on every write. v2→v3 migration backfills from existing tasks' `raw_frontmatter`.
- **Adapter registry** (`adapters/registry.py`): hardcoded built-ins + `importlib.metadata` entry-point overlay for v2's adapter SDK (#15). Built-in wins on name conflict; broken third-party loader is logged + skipped, never aborts.
- **Three stub adapters** registered as built-ins: `obsidian`, `reminders`, `todo-md`. Each satisfies the protocol and returns clear "not implemented — see request #NN" errors. The framework is testable end-to-end on this release; #07/#09/#21 each replace the stub body.
- **11 decisions locked** (D56–D66) in `.spectacular/DECISIONS.md`.
- **28 new tests** in `tests/test_adapters.py`. Total suite **299 passing** (was 271).

### Changed

- **`SCHEMA_VERSION` → 3.** Forward-chained migrator (`db/connection.py`) handles v1→v2→v3 in-place on first open.
- **`sync_task_after_write` now upserts the activity first** before the task — was failing FK constraint on fresh DBs.
- **`skills/octopus/SKILL.md` → v0.4.0.** New verb-index "Bridges" group; new load-on-demand entry for `adapter-framework.md`; "Bridges (v1 scope)" section rewritten to explain peek vs. pull and list the three v1 adapters.
- **`SCHEMA-ADAPTER.md`** (new spec doc, 10 sections): protocol, data types, config layout, registry, sync journal, pull pipeline, stub shape, repo layout.
- **`CLI-VERBS.md`** gains a "Bridge verbs" section with the full command reference, flag matrix, and exit codes.
- **`CRITICAL-DEPENDENCIES.md`** gains section U: config rules, capability gating, flag-matrix mutual exclusion, pipeline materialization invariants, dedup-index sync, sync-journal semantics, registry conflict resolution.
- **`SCHEMA-CONFIG.md`** documents the hybrid layout in §2b — main config holds only `enabled` per adapter; content moves to `bridges/<name>.toml`. Validation rules updated.
- **`SCHEMA-INDEX.md`** documents `task_external_refs` and the new `idx_tasks_kind` / `idx_tasks_promoted_to` (carry-over from D46/D48). `PRAGMA user_version = 3`.
- **Skill references mirrored** (`adapter-framework.md` new; `cli-verbs.md` + `critical-dependencies.md` extended).

### Migration

- Existing databases auto-migrate v2→v3 on first open: `task_external_refs` table created, then backfilled from each task's `raw_frontmatter.external_refs`.

---

## [0.3.0] — 2026-05-24

The **task → request promotion seam**: a single CLI verb makes Octopus and Spectacular work as one system, with one-way migration and derived back-references. Folds in the F1 naming + `kind` enum work that was tracked separately under request #19 (now superseded).

### Added

- **`octopus promote <slug>... --to <target>` verb.** Promotes one or more tasks into a Spectacular request (or any future external target). Rewrites the task body to a 3-line stub pointing at the PLAN.md; scaffolds the request if absent; sets `end_date` and `bucket: done`. Input forms: `provider:id`, `chip:id`, bare `id` (uses `[providers.default]`), provider-only shorthand (single-task only), and `provider:new --slug <id>`. Multi-task atomic pre-flight — all-or-nothing.
- **`--force` repoint** for already-promoted tasks (no re-body-rewrite). **`--revert`** soft-clears `promoted_to` + `end_date` and moves the task back to `bucket: backlog`. `promoted_from` on the request side is historical and survives repoint.
- **`kind` field on tasks** (D46). Optional enum: `feat | bug | spec | polish | test | chore`. Soft validation v1 — unknown values warn but don't reject. Indexed in SQLite. Renders as `[kind]` chip in both CLI list output and the TUI.
- **`octopus set --kind <value>`** to assign/clear.
- **`octopus list --kind <enum>` / `--promoted` / `--spec <slug>`** filter flags on both `list` and `task list`. `--promoted` and `--spec` override the default `done/`-excluded scope so promoted tasks (which live in `done/`) actually surface.
- **`[providers]` config section** in `~/.config/octopus/config.toml`: `default`, `[providers.chips]` aliases (ASCII ≤6 chars), `[providers.spectacular] auto_number` (default `true`).
- **Reindex propagation of `related_tasks`** to request PLAN.md (D54). Task-side `promoted_to` is the canonical link; the request side is a derived mirror. Sorted, deduped, default-omitted when empty. Malformed values surface as warnings, never abort. `_archive/` requests are skipped.
- **Schema migration v1 → v2**: in-place `ALTER TABLE tasks ADD COLUMN kind/promoted_to` + new indexes. Existing databases are upgraded transparently on first connection.
- **11 decisions locked** (D45–D55) in `.spectacular/DECISIONS.md`.
- **46 new tests** (`test_promote.py`, plus filter tests in `test_db_queries.py`, plus reindex tests in `test_db_reindex.py`). Total suite now **271 passing** (was 225).

### Changed

- **`skills/octopus/SKILL.md` → v0.3.0.** New sections "Task `kind`" and "Task promotion" with full input-form table, idempotency rules, multi-task semantics, and reverse-flow guidance. Chat-presentation layouts updated with `[kind]` chips and `→ chip:id` promotion arrows. Verb index gains a "Promotion" group.
- **`SCHEMA-TASK.md`**: `kind` added to the taxonomy group, `promoted_to` added to integrations & provenance. Field reference sections + validation rules for both.
- **`CLI-VERBS.md`**: documents `promote`, `--kind/--promoted/--spec` flags, exit codes 0/2/3/4, all input forms.
- **`CRITICAL-DEPENDENCIES.md`**: new sections S (kind) and T (promotion + reindex of `related_tasks`).
- **`SCHEMA-CONFIG.md`**: `[providers]` section + chip alias validation (reject non-ASCII / >6 chars, warn on collision).
- **`SCHEMA-TASK.md`** no longer rejects `kind` as a legacy field — it's a v1 work-classification.
- **Skill references mirrored** (`schemas/task.md`, `cli-verbs.md`, `critical-dependencies.md`).
- **TUI rows** render the `[kind]` chip and `→ chip:id` arrow when applicable, in both Focus and Board screens. Provider chips loaded once per session from `[providers.chips]`.
- **11 live tasks classified** with `kind` (3 feat · 2 bug · 1 spec · 2 polish · 1 test · 1 chore-finished).

### Removed

- **Request #19** archived as **superseded by #20**. Its naming-formula + kind-enum scope folded into this release.
- **`link-tasks-to-requests-via-tags`** task dropped — superseded by the canonical `promoted_to` field shipped here.
- **`drop-request-nn-suffix-from-task-titles`** task finished — the cleanup was already done in v0.2.7's rename pass.

---

## [0.2.7] — 2026-05-23

Housekeeping release — no code changes. Lifecycle hygiene + task-naming convention + chat-rendering rules for the agent skill.

### Changed

- **5 done requests archived** to `.spectacular/requests/_archive/`: `03-index-sqlite`, `04-sessions-memory`, `05-tui`, `08-plugin-claude-code` (scaffold-shipped; install-assistant polish deferred), `11-distribution-pipx`. Brings the active request list from 17 down to 12.
- **4 stale task files moved to `done/`** with `bucket: done` + `end_date` stamped: SQLite indexer (#03), sessions/memory verbs (#04), Textual TUI (#05), Claude Code plugin (#08). Frontmatter and slugs corrected.
- **11 live tasks renamed** to the F1 imperative naming formula (`verb result`, lowercase, no `(request NN)` suffix, no `Friction:` / `Bug:` prefix). Eight different verbs across the set so the verb actually carries signal. Files git-mv'd, slugs regenerated. Reindex clean — 16 tasks, no zombies.
- **`skills/octopus/SKILL.md`** gains two new sections (130 → 203 lines):
  - *Task naming — F1 imperative*: rule, verb list, examples (good + avoid), "don't over-use `add`" guidance with a concrete test for when `add` is correct.
  - *Presenting tasks in chat*: three ASCII layouts (Focus quadrants, Board kanban, compact list) matching the `octopus tui` glyphs, with a routing table that picks layout from user phrasing.
- **README phase table** cleaned up — request #08 promoted to explicit done row.

### Added

- **Request #19 — task naming + kinds** parked in backlog. F1 naming is locked now; `kind` enum + `area`-as-tags exploration deferred to a real spec pass.

---

## [0.2.6] — 2026-05-23

Patch — fixes zombie task rows in the TUI. If the SQLite index referenced a task whose `.md` file had been moved or archived, the TUI showed it but mutations (drop, finish, advance) failed with `task not found`.

### Fixed

- **TUI zombie rows** — Focus and Board now call `_drop_zombies()` in `_refresh_data()` to verify each indexed row has a backing file on disk before display. Index drift no longer leaks ghost tasks. The mutation layer (`octopus.actions`) already walks the filesystem, so this aligns what's shown with what's actionable.

### Added

- **3 new tests** (`test_tui_zombies.py`): live-file passthrough, missing-file removal, mixed live/missing case. **224 total passing**.

---

## [0.2.5] — 2026-05-23

Closes request #05 (Textual TUI v1). Adds the last two polish groups — live filter, help overlay, quit-confirm when a session is open — and locks D44 alongside the previously-promised D43.

### Added

- **`/` filter bar** — bottom modal slide-up input. Live title-substring filter (case-insensitive) narrows the visible task lists across all quadrants/columns. Esc clears + restores; Enter commits but keeps the filter applied. `r` (reindex) also clears the filter as a one-key reset.
- **`?` help overlay** — modal with the full 17-key keymap, grouped by Navigation / Modes / Mutations / View. Esc or `?` closes.
- **`q` quit-confirm** — if the activity has an open session (`sessions.cache.get_active`), quitting prompts y/n. No active session → exits immediately. Avoids stranding a session pointer when `q` is hit out of habit.
- **README "Daily driver — the TUI"** section: 3-quadrant Focus diagram + full keymap table.
- **9 new tests** (`test_tui_filter_help.py`, `test_tui_polish.py`): filter substring helper, key bindings present on both screens, quit-action override, broken-task resilience. **221 total passing**.
- **D43 + D44 logged** in `DECISIONS.md` — TUI v1 shape and the polish-group close-out.

### Changed

- Request #05 marked `status: done` in PLAN.md and TASKS.md (with a note in TASKS.md that the shipped TUI diverged from some bullets during dogfooding — see DECISIONS.md §D43–D44 for the canonical shape).

---

## [0.2.0] — 2026-05-23

Textual TUI ships. `octopus tui` opens a Focus or Board view of the current activity, with a 13-key mutation keymap, a pixel-art mascot in the header, and a shared `octopus.actions` write layer used by both CLI and TUI.

### Added

- **`octopus tui`** — Textual TUI for the current activity (CWD-scoped). Two modes: **Focus** (three quadrants: BACKLOG / NOW / NEXT) and **Board** (four-column kanban: backlog → next → now → done). Switch via `1` / `2`. Daily-driver view for the act loop.
- **13-key mutation keymap** shared across modes: `n` capture (into focused quadrant/column), `m` advance one pipeline step, `M` move-to-bucket picker, `f` finish, `d` drop (with y/n confirm), `p` toggle pin, `e` open in `$EDITOR`, `s` session start, `S` session start + title, `Enter` open detail overlay, `r` refresh.
- **`octopus.actions`** shared mutation layer — single entry per verb (`start_task`, `finish_task`, `drop_task`, `move_task`, `move_next`, `pin_task`, `unpin_task`, `toggle_pin`, `capture_task`, `start_session_for`). TUI calls it directly; CLI port deferred.
- **Catppuccin Mocha theme** (`tui/theme.tcss`): lavender (`#CBA6F7`) accent, teal footer keys, no Windows-blue washes. Plain unicode glyphs throughout (no emoji, no Nerd Fonts required).
- **Tall 7-row header** with pixel-accurate octopus mascot rendered via `rich-pixels` + PIL from a 16×14 ASCII pixel grid. Right side stacks: title, activity name, CWD path (collapsed to `~/`), session label + bucket counts, index state, mode tabs (`1 focus` / `2 board`).
- **Single-line task rows** with marquee scrolling for clipped titles. Cursor glyph (`▸`) scoped to the active quadrant's selected row only.
- **Detail overlay** (`Enter`) — modal with task chips, body, last 5 sessions, last 5 memory entries.
- **Mascot assets** at `assets/mascot/octo-v1-classic.svg`. Animation deferred to request #18 (backlog).
- **27 new tests**: `test_actions.py` (15), `test_tui_skeleton.py` (10), `test_tui_board.py` (4). **212 total passing**.

### Changed

- `cli/pyproject.toml` adds runtime deps: `textual>=0.46`, `rich-pixels>=3.0`, `pillow>=10.0`.
- `.gitignore` ignores `Screenshot*.png` / `Screenshot*.jpg` (local feedback artifacts).
- Request #05 closed (`status: done`); D43 logged in `DECISIONS.md`.

### Locked decisions

- **D43** — Textual TUI v1 shipped. Focus + Board modes, mode-switching via `1`/`2`, Catppuccin Mocha palette, shared `octopus.actions` mutation layer between CLI and TUI, `rich-pixels` + PIL for pixel-art mascot in the header. Request #18 (mascot animation) parked in backlog.

---

## [0.1.0] — 2026-05-23

Inaugural pre-release. Walking skeleton + SQLite index + continuity layer + plugin scaffold + self-contained agent skill + **pipx-installable distribution**. No git tag yet — bundling #11 into 0.1.0 so the first published wheel is feature-complete.

### Added

- **Sessions**: multi-open per activity, sticky-active cache (`~/.cache/octopus/active-sessions.json`, XDG-respectful), full lifecycle verbs (`session start/log/end/switch/list/show/prune`). Symmetric `session end --handoff` paired-handoff flow (writes `related_handoff` ↔ `from_session`).
- **Memory**: append-only `memory.md` with two-zone marker (`<!-- octopus-managed-below -->`) + 5 canonical sections (Decisions / Open Questions / Context / Notes / State). Default `memory show` preview with `(showing latest N of M)` headers + `[K more — run …]` footers. Section prefix-matching (`open` → `Open Questions`).
- **Handoffs (v1, filesystem-only)**: `handoff new/list/show`. Router-style default body template with `## Suggested next actions` block containing executable `octopus ...` commands. Persistent in-activity (not ephemeral $TMPDIR).
- **SQLite index**: `~/.local/share/octopus/index.db`, `reindex` verb, stale-check-on-read, cross-activity views, `config root add/list/remove`.
- **Claude Code + Codex plugin scaffold** at repo root: `.claude-plugin/plugin.json` + `marketplace.json`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`. 6 slash commands (`/octopus:start`, `/end`, `/handoff`, `/where`, `/memory`, `/log`), 3 agents (`session-keeper`, `handoff-writer`, `context-loader`), 2 hook files (Claude + Codex).
- **Self-contained agent skill** at `skills/octopus/`: `SKILL.md` (130 lines, router + hard rules + trigger table) + `references/` with progressive-disclosure (5 schema refs under `schemas/`, `cli-verbs.md`, `critical-dependencies.md`). Total skill size 1,025 lines.
- **`.gitignore`** pre-init covering Python build/test artifacts, macOS, backups (`_archive/`, `_backups/`), local configs (`.claude/settings.local.json`, `.spectacular.local/`, `CLAUDE.local.md`), octopus trash (`.octopus/.trash/`), tool-hidden dirs (`.scrapekit/`, `.playwright-mcp/`, `.smart-env/`).
- **CLAUDE.md skill-reference sync rule**: editing any spec under `.spectacular/specs/SCHEMA-*.md`, `CLI-VERBS.md`, or `CRITICAL-DEPENDENCIES.md` must update the matching file under `skills/octopus/references/` in the same commit.
- **`octopus diagnose`**: collects version, python/platform, config dump, index stats, log tail (last 500 lines) into a redacted (`$HOME` → `~/`) zip — `octopus-diagnose-YYYY-MM-DD-HHMMSS.zip` by default, or `--no-zip` for stdout. Drop the zip into a GitHub issue.
- **File logging**: rotating handler at `$XDG_DATA_HOME/octopus/logs/octopus.log` (1 MB × 5 backups). Stdout stays clean — file-only. Wired to `reindex`, `session start/end`, `handoff new` at INFO level.
- **`octopus --version`**: reads version from package metadata (`importlib.metadata`) — single source of truth in `pyproject.toml`.
- **pipx-installable**: `python -m build` produces a clean wheel + sdist bundling `schema.sql`. `pipx install ./dist/octopus_cli-0.1.0-py3-none-any.whl` works end-to-end on Python 3.11–3.14.
- **GitHub Actions CI**: `.github/workflows/test.yml` runs ruff + pytest on push/PR against `main` across Python 3.11/3.12/3.13. `.github/workflows/release.yml` builds wheel + sdist on `v*.*.*` tags and uploads to GH releases (no PyPI publish — manual gate).
- **README install section**: pipx (recommended) + from-source (editable) + upgrade/uninstall + sanity check pointing at `octopus diagnose`.

### Changed

- **`.spectacular/current/specs/` flattened to `.spectacular/specs/`** (aligns with spectacular 0.5.0 convention). All references updated across `README.md`, `CLAUDE.md`, `.spectacular/SPEC.md`, `.spectacular/PRD.md`, `.spectacular/DECISIONS.md`, request `PLAN.md`/`TASKS.md` files, `cli/README.md`, `cli/src/octopus/db/__init__.py`, `cli/src/octopus/handoffs/io.py`, `.claude/settings.local.json`.
- **Memory schema locked**: `## Log` dropped in favor of `## State` (append-only but latest entry is treated as "current"); default `memory append` target moved from Log to Notes (per D41).
- **Session log entries** use second precision (`### YYYY-MM-DD HH:MM:SS`); **memory entries** use minute precision (`### YYYY-MM-DD HH:MM`). Distinguishes the two at a glance.
- **`SCHEMA-SESSION.md`**: body example updated to second-precision timestamps; added "Multi-open prompt outcomes" subsection documenting `[c]/[n]/[e]/[a]` flow.
- **`CRITICAL-DEPENDENCIES.md`**: extended K (session invariants) with second-precision rule, `[e]` auto-note rule, exit-3-on-no-active rule; added new K2 (Session cache invariants — atomic writes, corruption recovery, cache-wins-on-mismatch); updated M (Memory invariants) with canonical-section list update, minute precision, prefix matching, State semantics, secret-redaction warn.
- **`CLI-VERBS.md`**: added three full verb blocks (Sessions, Memory, Handoffs) with flags, side-effects, and prompt outcomes. Fixed stale `## Log` reference in impediment-verb side-effect notes.

### Fixed

- **SQLite `DeprecationWarning` on Python 3.12+**: registered explicit ISO 8601 adapter/converter pairs for `date`, `datetime`, `DATE`, `TIMESTAMP`, `DATETIME` in `cli/src/octopus/db/connection.py`. Test suite now runs with **0 warnings** (was 11).

### Locked decisions

- **D40** — Index schema v1 frozen at `PRAGMA user_version = 1`; SQLite indexer shipped.
- **D41** — Sessions/memory/handoffs landed. 9 grilled questions resolved (handoffs-fs-only, second precision, prune 7/14 days, `[e]` drops-with-auto-note, lazy memory scaffolding, `log` exits 3 with no active, `show` active→most-recent fallback, `handoff new` requires activity, `--handoff` UX prompts unless `--non-interactive`). Memory schema change (Log → State) locked. Cache shape `{activity_id: session_filename}` locked.
- **D42** — Distribution: pipx-first, no PyPI auto-publish (manual gate). Log rotation: 1 MB × 5 backups at `$XDG_DATA_HOME/octopus/logs/octopus.log`. `octopus diagnose` redacts `$HOME` → `~/` and tails last 500 log lines. CI matrix: Python 3.11/3.12/3.13 (3.14 confirmed working post-install but not in matrix). Ruff loosened with documented per-rule ignores — full lint cleanup deferred.

### Test suite

- **183 tests passing**. Distribution: 72 baseline (init/capture/lifecycle/index) + 24 sessions + 38 memory + 24 handoffs + 10 cross-cutting + 6 logging + 9 diagnose.

### Dogfood

End-to-end validated against the octopus repo itself on 2026-05-23: real session created/logged/ended-with-handoff; memory entries appended to Decisions + State; handoff body template populated with symmetric backlink; `reindex` populated session row. Three friction items captured as backlog tasks (`memory-show-missing-blank-line-between-section`, `session-log-rapid-back-back-entries-can-share`, `reindex-output-clarify-n-sessions-is-reindex`).

### Out of scope (v1.5+ / v2)

- Handoff lifecycle verbs (`receive`, `resolve`, `stale`)
- `handoffs` table in SQLite index (currently filesystem-only)
- Two-way external sync (Reminders, GitHub, ICS calendar)
- Textual TUI (request #05)
- Auto-redactor for handoff body secrets
- PyPI auto-publish (deferred per D42 — wheel released on GitHub manually for v0.1.0; PyPI gated until first external pipx install confirmed clean)
- Full lint cleanup (96-error ruff backlog deferred — see `cli/pyproject.toml` ignore list)

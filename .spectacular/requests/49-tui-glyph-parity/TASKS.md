---
status: review
updated: 2026-07-17
related:
  - PLAN.md
---

# Tasks — tui-glyph-parity

<!--
  Executable checklist for one request.
  Lives at: .spectacular/requests/<slug>/TASKS.md

  Rules:
  - Group tasks by milestone using `### M<N> — <name>` headings.
  - Flush-left checkboxes are the COUNTED units: `- [ ]` open, `- [x]` done,
    `- [~]` deferred (not-open-not-done; shown separately in progress).
  - Indented `  - [ ]` sub-bullets are allowed as a nested acceptance checklist
    under a task, but are NOT counted — progress counts top-level only, so
    x/total stays comparable across requests.
  - `status:` in frontmatter should match parent PLAN.md.
  - Tasks are owned by the user. Engine never adds/removes/reorders tasks.
-->

## v1

### M1 — Bucket-idle glyph spec vs code (verification only — false alarm)
- [x] Re-read `TUI-GLYPHS.md` in full — confirmed bucket-idle table already reads `· □ ▣ ● ✕`, matching `icons.py:39-43`
- [x] Traced the false-alarm source: request 34's draft PLAN.md `minimal`-style row (`· o O X`), not the locked spec
- [x] → check: no edit needed; `TUI-GLYPHS.md` bucket-idle table matches `icons.py:39-43` byte-for-byte (confirmed 2026-07-17)

### M2 — Board mode glyph parity with Focus (verification only — false alarm)
- [x] Traced `board.py`'s row-build path — `_fill()` at `board.py:327` constructs every row via `_TaskListItem`
- [x] Confirmed `_TaskListItem` is imported directly from `focus.py` (`board.py:49-54`), not reimplemented
- [x] Confirmed `_TaskListItem.__init__` (`focus.py:339-364`) calls `_row_text()`/`_row_chips()` — the same glyph-rendering functions Focus uses
- [x] → check: no port needed; Board mode already renders identical glyphs/chips to Focus mode (confirmed 2026-07-17)

### M3 — `--glyphs` CLI flag + config surface (G3/G4)
- [x] Add `--glyphs` flag to `octopus list` (task-view paths: `list tasks`, bare `list` in-activity, cross-activity filtered view)
- [x] Add `--glyphs` flag to `octopus task show` (the real slug-detail command — `octopus show <slug>` at top level does not exist in code, spec drift noted separately)
- [x] Reuse `icons.py`'s `status_glyph()` for CLI rendering; added `_task_to_glyph_row()` adapter (Task dataclass ≠ sqlite3.Row shape) and `render_glyph_prefix()` for `task show`'s Task-object case
- [x] Implement `[ui.glyphs]` config keys (`style`, `progress_stages`, `use_color`, `session_marker`) in `config.py` — **TOML, not YAML** (decision: see PLAN.md Decisions; project has no YAML loader anywhere)
- [x] Implement resolution order: `--glyphs` flag presence > `.octopus/config.toml` > `~/.config/octopus/config.toml` > built-in default (reuses existing `load_config()` precedence)
- [x] Implement style presets: `collapsed` (default, reuses shipped Unicode resolver), `minimal` (new ASCII dictionary in `icons.py`), `combined` (falls back to `collapsed` — no distinct CLI rendering exists yet, documented as such)
- [x] Write tests covering the 4-tier config resolution order (`test_glyphs_config.py`, 4 tests) and CLI flag behavior (`test_glyphs_cli.py`, 4 tests)
- [x] Update `SCHEMA-CONFIG.md`, `CLI-VERBS.md`, `TUI-GLYPHS.md` (fixed stale YAML references while here) + synced `skills/octopus/references/{cli-verbs,tui-glyphs}.md`
- [x] → check: `octopus list tasks --glyphs` and `octopus task show <slug> --glyphs` render glyphs (manually verified); `pytest` — 771 passed, including 8 new tests

## v2 (deferred)

- [~] Flip `--glyphs` default from off to on (G3 says "re-evaluate" post-v1 — not this request)

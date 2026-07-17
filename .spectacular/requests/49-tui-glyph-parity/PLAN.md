---
status: review
priority: medium
owner: alex
updated: 2026-07-17
build: b1
summary: "Ship the --glyphs CLI flag locked in 34-tui-key-schema (G3/G4) but never built. (Two other suspected gaps — bucket-idle spec drift, Board-mode glyph parity — both verified as false alarms; see Understanding.)"
related:
  - PRD.md
  - 34-tui-key-schema
  - 41-tui-glyph-audit
gates:
  - 34-tui-key-schema
---

# Plan — tui-glyph-parity

<!--
  Canonical 7-slot PLAN template for a single request.
  Lives at: .spectacular/requests/<slug>/PLAN.md

  Rules:
  - PLAN is per-request. PRD is project-wide. Never put a PRD inside requests/.
  - This file's frontmatter `status:` is the single source of lifecycle state for the request.
  - The 7 required sections must appear IN ORDER, unnumbered:
      ## Goal, ## Constraints, ## Milestones, ## Tasks, ## Dependencies, ## Validation, ## Deliverables
    Extra sections (## Understanding, ## Decisions, request-specific) may appear
    BETWEEN them; doctor enforces the required set's presence + order, not a closed list.
  - All 7 required sections must be filled before this PLAN is considered usable.
  - Replace every <placeholder> with concrete content.
-->

## Goal

Ship the `--glyphs` CLI flag locked in 34-tui-key-schema (G3/G4) — `octopus list`/`show` output currently has no glyph mode despite the design being fully locked. (Two other suspected gaps — bucket-idle spec drift, Board-mode glyph parity — were investigated and found to be false alarms; see Understanding.)

## Constraints

- No new glyph characters — every glyph used below is already shipped in `icons.py` and already locked in `TUI-GLYPHS.md`; this request wires an existing dictionary into a new surface, it does not invent.
- `--glyphs` stays opt-in / default off per G3 (locked) — no behavior change for scripts parsing `octopus list`/`octopus show` output unless the flag is passed.
- G4's config resolution order is fixed: `--glyphs` CLI flag > `.octopus/config.yaml` `ui.glyphs.*` > `~/.config/octopus/config.yaml` `ui.glyphs.*` > built-in default.

<!-- ## Understanding and ## Decisions below are OPTIONAL extra sections,
     allowed between Constraints and Milestones. -->

## Understanding

<!--
  OPTIONAL authoring slot, but REQUIRED before `planned → active` by the
  `understand-before-change` policy (@Implementation). Fill it here for a
  typical request; escalate to a dedicated requests/<slug>/UNDERSTANDING.md
  (same three subheads) for large ones — the policy is satisfied by EITHER.
  Not one of the 7 required authoring slots; it gates implementation, not planning.
-->

### How it works now

- `TUI-GLYPHS.md` (as reconciled by 41-tui-glyph-audit, commit `fa4f7f8`) already documents bucket-idle glyphs as `· □ ▣ ● ✕`, matching `cli/src/octopus/tui/icons.py:39-43` exactly. **No drift.**
- `focus.py` renders slot-1 status glyph (`status_glyph()`/`status_glyph_color()`) and slot-2 flag chips (`_row_chips()`) inside module-level functions `_row_text()`/`_row_chips()`, called from `_TaskListItem.__init__` (`focus.py:339-364`).
- `board.py` imports `_TaskListItem` directly from `focus.py` (`board.py:49-54`) and builds every row with it (`board.py:327`) — same widget, same constructor, same glyph calls. **No parallel implementation, no drift possible.**
- `octopus list` / `octopus task show` in `cli.py` were pure text; no `--glyphs` flag existed anywhere in the CLI despite G3/G4 being locked in 34-tui-key-schema. **This was the one real gap — now closed.**
- **Naming correction found during implementation:** the locked spec's "`octopus show`" does not exist as a top-level command in code — the actual slug-detail command is `octopus task show <slug>` (`cli.py:902`). `--glyphs` was added to the real command name; `CLI-VERBS.md`/`TUI-GLYPHS.md` updated to say `octopus task show`, not the spec's original `octopus show`.

**Corrections (2026-07-17), same session:**
1. Suspected M1 (bucket-idle spec/code drift) does not exist. The assistant had compared shipped code against request `34-tui-key-schema`'s **draft** PLAN.md, which lists `· o O X` only as the `minimal` fallback style's dictionary (for monochrome terminals) — not the default `collapsed` style. The locked spec, `TUI-GLYPHS.md`, already carries the correct default set.
2. Suspected M2 (Board mode missing glyphs) does not exist either. The assistant's original check grepped `board.py` for direct `icons.py` imports and found none, missing that `board.py` renders every row through `_TaskListItem` — the identical widget `focus.py` uses, which already calls the glyph functions in its constructor. Board mode has always rendered the same glyphs as Focus mode.

Both are retained below as verification-only checkpoints rather than deleted outright, per user direction, so the false-alarm trail stays visible.

### What changed

- `cli/src/octopus/cli.py` — `octopus list` (task-view paths) and `octopus task show` gained `--glyphs`.
- `cli/src/octopus/config.py` — `Config.glyphs_*` fields + `[ui.glyphs]` TOML block resolution.
- `cli/src/octopus/tui/icons.py` — added `render_glyph_prefix()`, `_task_to_glyph_row()` adapter, `_minimal_glyph()` + `MINIMAL_*` ASCII dictionary (this preset didn't exist in code before — only `collapsed` was shipped).
- `SCHEMA-CONFIG.md`, `CLI-VERBS.md`, `TUI-GLYPHS.md` + both skill references — documented the flag and fixed stale YAML syntax to real TOML (the YAML in the original G4 lock was always aspirational, never built).
- Two new test files: `test_glyphs_config.py` (4 tests, resolution chain), `test_glyphs_cli.py` (4 tests, flag behavior).

### What stayed the same

- `board.py`, `focus.py` — no edits; confirmed already correct (M1/M2 false alarms).
- `--glyphs` default stays off; no output format changes for existing scripted callers.
- No new glyph characters for `collapsed` style; `minimal` style is new ASCII characters, but was already locked as a concept in G4, just never implemented.
- `combined` style is documented as falling back to `collapsed` for CLI output — the two-cell variant remains TUI-only, unbuilt (was never requested as in-scope; flagging for visibility, not silently skipping).

## Decisions

<!--
  Design calls made inside this request. Format: chose X over Y — because Z.
  Rejected alternatives stay listed; deleting them re-litigates them later.
  Project-wide calls go to DECISIONS.md via `spectacular decide` instead
  (see decisions-rules.md routing table). Empty is fine — no decisions yet.
-->

- Originally chose "update spec to match code" over "update code to match spec" for bucket-idle glyphs, believing `TUI-GLYPHS.md` locked `· o O X`. **Superseded 2026-07-17**: re-reading the actual spec (not request 34's draft table) showed no drift exists. M1 downgraded to a verification-only checkpoint; decision retired, no action taken.
- Originally chose "full port of Focus's glyph rendering to Board" over "leave Board text-only" or "flags-only port", believing `board.py` had no glyph rendering. **Superseded 2026-07-17**: `board.py` already renders via the shared `_TaskListItem` widget from `focus.py` — no port needed, no separate implementation exists to diverge. M2 downgraded to a verification-only checkpoint; decision retired, no action taken.
- Chose "build --glyphs full scope now" over "minimal flag only" or "defer" — because G3+G4 were already fully locked in 34-tui-key-schema; this request is closing a gap against a locked spec, not re-opening the design. Decided by user, 2026-07-17.

## Milestones

<!-- Ordered, demoable checkpoints. Outcomes, not tasks. -->
<!-- 3-7 milestones for a typical request. Each is something someone can see working. -->

- M1 — (verification-only, closed) confirmed `TUI-GLYPHS.md` bucket-idle table already matches `icons.py`; no drift, no edit needed.
- M2 — (verification-only, closed) confirmed Board mode already renders identical status glyph + flag chips to Focus mode via the shared `_TaskListItem` widget; no port needed.
- M3 — (closed) `octopus list tasks --glyphs` and `octopus task show <slug> --glyphs` render the glyph dictionary; config resolution chain (CLI flag > activity config > user config > default) works and is covered by 8 tests. Manually verified live plus full suite: 771 passed.

## Tasks

<!-- Pointer. The executable checklist lives in TASKS.md, grouped by milestone. -->

See `TASKS.md`.

## Dependencies

<!-- Other requests, skills, blocking decisions. Use [[request-slug]] notation. -->

- [[34-tui-key-schema]] — locks G3/G4 (the `--glyphs` flag + config surface this request implements) and the glyph dictionary itself. Gate: must stay `locked` (already is).
- [[41-tui-glyph-audit]] — prior audit marked `done`; this request is a follow-up correcting gaps it missed, not a reopen.

## Validation

<!--
  How each milestone is verified. Per-milestone checks.
  Each check states its AUTHORITY: a run: command, an assertable property,
  a judgable artifact, or a human-observable behavior (see verify.md kinds).
  A check with no authority can't fail. Aspiration verbs (improve, enhance,
  optimize, handle gracefully) are not checks.
-->

- M1 — observable: `TUI-GLYPHS.md` bucket-idle table (already) reads `· □ ▣ ● ✕`, matches `icons.py:39-43` byte-for-byte. Confirmed 2026-07-17; no further action.
- M2 — code-read: `board.py:327` builds every row via `_TaskListItem`, imported from `focus.py:49-54`; `_TaskListItem.__init__` (`focus.py:339-364`) calls `_row_text()`/`_row_chips()`, the same glyph functions Focus uses. Confirmed 2026-07-17; no further action.
- M3 — run: `octopus list tasks --glyphs` and `octopus task show <slug> --glyphs` print glyphs (manually verified); `pytest tests/test_glyphs_config.py tests/test_glyphs_cli.py` — 8/8 passed; full suite `pytest` — 771/771 passed.

## Deliverables

<!-- Artifacts that ship out of this request. Concrete files, docs, behaviors. -->

- `--glyphs` flag on `octopus list tasks` / `octopus task show` in `cli.py`, backed by `icons.py`.
- `[ui.glyphs]` TOML config resolution chain (CLI flag > activity config > user config > default) with `collapsed` (default) and `minimal` (new) style presets; `combined` documented as CLI-unbuilt (falls back to `collapsed`).
- `test_glyphs_config.py` (4 tests) + `test_glyphs_cli.py` (4 tests).
- Spec corrections: `SCHEMA-CONFIG.md`/`CLI-VERBS.md`/`TUI-GLYPHS.md` updated from aspirational YAML to real TOML syntax; `octopus show` → `octopus task show` naming fixed to match actual code.

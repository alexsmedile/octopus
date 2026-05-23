# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

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

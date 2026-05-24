# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

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

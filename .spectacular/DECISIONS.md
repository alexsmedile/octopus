---
updated: 2026-05-23
---

# Decisions log

Append-only record of resolved design decisions. Each entry summarizes a choice and links to the authoritative section in PRD.md.

For full reasoning and edge cases, see `PRD.md §13 Resolved Decisions`.

---

## 2026-05-21 — Initial v1 decision set (PRD §13)

### D1 — Activity ID format
- IDs are `<slugified-folder-name>-<4-hex-hash>`, persisted in `activity.md` frontmatter, stable across renames.
- Hash hidden from everyday UX; surfaces only in JSON, `--show-ids`, collision errors.
- See PRD §13.1.

### D2 — Sessions
- Multiple open sessions per activity allowed; one "active" at a time tracked in `~/.cache/octopus/active-sessions.json`.
- `session start` prompts when one is already open. `session prune` for stale.
- See PRD §13.2.

### D3 — Areas taxonomy
- Free-form strings with discovery (Levenshtein ≤ 2 warnings on reindex).
- Optional strict mode via config.
- `type:` stays enumerated.
- See PRD §13.3.

### D4 — Task slugs
- Auto-slugify with noise-word trim, 50-char cap (including `.md`), collision counter (`-2`, `-3`).
- Noise-word list configurable.
- Cross-refs use `<activity-slug>/<task-slug>` with prefix-match resolution.
- See PRD §13.4.

### D5 — Index sync model
- CLI-incremental + stale-check-on-read default.
- `octopus reindex` for full rebuild. `octopus watch` opt-in daemon (v1.5).
- See PRD §13.5.

### D6 — Obsidian `.base` ownership
- Octopus only writes files it owns by `octopus-` prefix or explicit registry.
- Backups + prompts before touching any user file.
- See PRD §13.6.

### D7 — memory.md write model
- Frontmatter `summary:` for human-curated summary.
- Five fixed body sections below `<!-- octopus-managed-below -->`: Decisions, Open Questions, Context, Notes, Log.
- Append-only via CLI; hand-edit fully supported. Not indexed in v1.
- See PRD §13.7.

### D8 — Claude Code plugin coupling
- External CLI install assumed; install assistant offers `[a]` auto / `[m]` manual / `[s]` skip.
- Plugin is markdown + shell only, no Python. CLI-first execution to save LLM tokens.
- See PRD §13.8.

### D9 — Telemetry
- None, ever. Local logs only. `octopus diagnose` for manual bug-report bundles.
- See PRD §13.9.

### D10 — License
- MIT, © 2026 Alessandro Smedile.
- See PRD §13.10.

---

## 2026-05-21 — Adapter architecture (PRD §7 rewrite)

### D11 — Adapter framework
- Common `Adapter` protocol with capability set (READ/WRITE/NOTIFY/TWO_WAY).
- `external_refs:` field on tasks maps adapter name → external ID.
- See PRD §7.

### D12 — v1 adapter scope
- v1 ships **read-only adapters only**: Obsidian (view via symlinks) and Apple Reminders (capture import).
- No push, no two-way sync in v1.
- See PRD §7.3.

### D13 — Sync modes — deferred design
- Two-way sync, conflict policy, sync triggers, identity dedup → PRD addendum required before v1.5.
- Captured as request `10-sync-modes-addendum`.
- See PRD §7.6.

### D14 — Future adapters
- GitHub Issues, ICS calendar, Todoist, Google Tasks, Linear, Notion: future requests, not v1 scope.
- Adapter SDK published in v2 enables community adapters.
- See PRD §7.7.

---

## 2026-05-21 — Request ordering

### D15 — TUI comes after Sessions/Memory
- PRD §12 order is reversed in the request graph: sessions land before TUI so the TUI can surface them on day one.
- Affects requests `04-sessions-memory` and `05-tui`.

---

## 2026-05-22 — Schema design (request 01 complete)

### D16 — Four-axis task model
- Task state modeled along orthogonal axes: pipeline (`bucket`), lifecycle (`status`), impediment (`issue`), attention (`open`).
- Plus non-axis visibility flag: `archived`.
- Structural framing in `specs/AXIS-MODEL.md`.

### D17 — Verb-driven CLI
- The CLI is verb-first (`capture`, `plan`, `focus`, `start`, `finish`, `drop`, `block`, `wait`, `pin`, etc.).
- `set` is the escape hatch for fields no verb covers.
- Views map intent → filters: `today`, `now`, `next`, `backlog`, `loops`, `stuck`, `stale`, `done`, `dropped`.
- See `specs/CLI-VERBS.md`.

### D18 — Storage modes per project
- Default: **folder mode**. Tasks live in bucket subfolders (`tasks/backlog/`, `next/`, `now/`, `done/`, `dropped/`). Pipeline verbs do atomic `mv` + frontmatter edit.
- Opt-in: **field mode**. Tasks live flat; bucket is frontmatter-only.
- Configured per activity in `.octopus/config.toml [storage] mode`.
- Sessions and handoffs are **always flat** (machine-readable artifacts, date-ordered).

### D19 — Field-name aliasing
- All five schemas (task, activity, session, handoff, memory) support field-name aliasing.
- Config: system-wide `~/.config/octopus/config.toml` and per-project `.octopus/config.toml`.
- Project config wins on conflict.
- Canonical names match Obsidian Tasks plugin convention; aliases let teams pick `creation_date`, `due_date`, etc.

### D20 — Memory append-only, two-zone
- Frontmatter `summary:` field (user-curated via explicit verb).
- Body has marker `<!-- octopus-managed-below -->`; five canonical sections below it (Decisions / Open Questions / Context / Notes / Log).
- CLI appends only; never reformats existing content.
- Not indexed in v1.

### D21 — Session lifecycle: open/closed + status + active
- `ended:` empty/populated = open/closed.
- `status: doing | done | dropped` = how it ended (productive vs abandoned).
- `active:` cache-mirrored; one active session per activity tracked in `~/.cache/octopus/active-sessions.json`.

### D22 — Handoff lifecycle
- Status: `open → received → resolved` (or `stale`).
- `from_actor` and `to_actor` fields support human ↔ AI handoffs explicitly.
- v1 may only support manual frontmatter edits; verbs (`handoff receive/resolve/stale`) pending v2.

### D23 — `.trash/` for soft delete
- `octopus forget <slug>` (draft, pending v2) moves to `.octopus/.trash/`.
- Trash is excluded from all retrieval (views, index, search).
- Use `archive` for v1 — `forget` semantics still in draft.

### D24 — SPEC.md as conceptual map; schema docs are authoritative
- SPEC.md §3-§7 contain summaries and point at the detailed schema docs in `specs/`.
- Schema docs are the contract; SPEC.md is the navigation layer.

---

## 2026-05-22 — Spec review pass (post-request-01)

### D25 — `set` verb is hand-edit equivalent with strict type/format/cross-field validation
- `set` accepts any frontmatter field, including those with dedicated verbs.
- Validation pipeline (hard reject → soft warn → informational tip), in order:
  1. Type validation: hard reject.
  2. Format validation: hard reject.
  3. Cross-field validation against `CRITICAL-DEPENDENCIES.md` MUST-rules: hard reject.
  4. Smell check (SHOULD-warn rules): write succeeds with stderr warning.
  5. Verb-overlap notice: informational only.
- `set` does NOT auto-apply verb side effects (date stamping, log entries, `open` flipping). Those remain verb-only.
- See `specs/CLI-VERBS.md` and `specs/CRITICAL-DEPENDENCIES.md` rule O.

### D26 — Symmetric `start_date` / `end_date` / `status` rules
- `status: doing` MUST have `start_date` set.
- `status: done` MUST have both `start_date` and `end_date`.
- `status: dropped` MUST have `end_date`; `start_date` only if work began.
- `end_date` present MUST have terminal status (`done` or `dropped`).
- See `specs/CRITICAL-DEPENDENCIES.md` rule A.

### D27 — Cross-reference resolution semantics across states
- Refs to archived tasks/activities: resolve with warning.
- Refs to `.trash/` files: MUST fail resolution.
- Refs to deleted files: MUST fail resolution as integrity error.
- Folder renames don't break refs (refs use `id`, not path).
- See `SPEC.md §8.2.1`.

### D28 — Checklist semantics: cosmetic only
- Task body `- [ ]` items are not parsed, counted, or indexed in v1.
- They exist for human readability.
- See `SPEC.md §4.7`.

### D29 — Activities use `status: archive`, not separate `archived` boolean
- Tasks have a boolean `archived` field for visibility.
- Activities use `status: archive` (one of 8 status enum values) for the same concept.
- Two different patterns because activities have a richer lifecycle.
- See `specs/SCHEMA-ACTIVITY.md` "On hiding activities".

### D30 — Datetime precision differs by file type
- Session frontmatter: `YYYY-MM-DDTHH:MM:SS` (with seconds, ISO 8601 datetime).
- Memory entries: `YYYY-MM-DD HH:MM` (minute precision, no seconds).
- Memory entries are journal-style — minute precision is sufficient and reads cleaner.

### D31 — SCHEMA-CONFIG.md added to spec family
- Covers `~/.config/octopus/config.toml`, `.octopus/config.toml`, and cache files under `~/.cache/octopus/`.
- Documents config precedence (project overrides user), cache semantics, XDG paths.
- Spec family is now 10 documents.

---

## 2026-05-23 — Schema collapse (request 02b)

### D32 — Bucket absorbs lifecycle; status field dropped
- Bucket is now five-valued: `backlog | next | now | done | dropped`.
- Lifecycle (started/finished/abandoned) is encoded via `start_date`, `end_date`, and terminal bucket values.
- `status` field removed entirely. Files containing it are rejected.
- Implementation simplification: `_folder_for()` helper removed; file location = `bucket`.

### D33 — kind field dropped from task schema
- Files in `tasks/` are tasks. Files in `handoffs/` are handoffs. Notes live in `memory.md`.
- Folder location determines type; no per-file `kind` field needed.
- Routines (was `kind: routine`) deferred — see `TODO.md`.

### D34 — open field renamed to pinned
- `open` → `pinned`. Verbs stay `pin` / `unpin`.
- Semantics shift: `pinned: true` means "surface to top of every list view," not "open loop."
- Open loops becomes a derived view (`octopus loops`): `bucket NOT IN (done, dropped) AND NOT archived`.
- Pinned tasks always sort first in any list, regardless of other order.

### D35 — Added stage field (domain workflow axis)
- Optional, free-form, per-activity.
- Captures activity-internal sub-stages (e.g. `idea`, `draft`, `editing`, `published`).
- No validation in v1. Per-activity strict mode deferred to `TODO.md`.

### D36 — Added run_state field (runtime axis)
- Optional, enum: `queued | running | finished | failed`. Absent = idle.
- Captures machine execution state, distinct from human workflow (`bucket`).
- Enables AI agents and automation to signal their state without touching pipeline axis.
- `finished` is distinct from `bucket: done`: a run can finish without the task itself being done.

### D37 — Default-omission principle for frontmatter
- Any field equaling its default value is omitted entirely from frontmatter.
- `actor: human` not written. `priority` for normal-priority tasks not written. `tags: []` not written.
- Result: minimal capture is 3 lines (`title`, `created`, `bucket`).

### D38 — actor enum expanded; priority enum reshaped
- `actor`: `human | ai | automation` (added `automation` for deterministic scripts).
- `priority`: `low | high | urgent`, absent = normal. (Previously `low | medium | high` with default `medium`.)
- Asymmetric default (normal is implicit) — preferred over symmetric explicit default.

### D39 — Walking-skeleton dogfood validated v1 schema
- Octopus initialized itself as an activity (`/Users/alex/vault/data/skills_db/octopus`).
- 13 real work items captured; full lifecycle round-trip verified.
- Three ergonomic gaps surfaced as backlog tasks (not schema issues):
  - Titles like "...request 03" duplicate metadata that belongs in tags/stage.
  - No tag-based linking to group tasks by parent request.
  - No view filter scoped by tag/activity-relative.
- Schema and verbs held under real use. Closing request 02.

### D40 — Index schema v1 frozen; SQLite indexer shipped (request 03)
- `~/.local/share/octopus/index.db` schema (activities/tasks/sessions) per `specs/SCHEMA-INDEX.md` frozen at `PRAGMA user_version = 1`.
- Python package is `cli/src/octopus/db/` (chosen over `index/` to avoid clash with `list.index`).
- Sync model: CLI-incremental upsert after every mutation verb + stale-check-on-read (mtime vs `indexed_at`); `--no-stale-check` opts out.
- `octopus reindex` is the full rebuild; `--prune` removes orphan rows and auto-accepts renames.
- `octopus where` deliberately stays file-native (resilience > consistency).
- `octopus list` is context-aware: scoped to the current activity when invoked inside one; cross-activity otherwise. `--all` forces cross-activity.
- Default roots empty; user opts in via `octopus config root add`. Missing roots warn, do not fail.
- Sessions table populated by `reindex` even though no v1 verb reads it (schema exercised — request 04 needs no re-index pass).
- `registry.json` (legacy concept) dropped entirely. `index.db` is the sole derived store.
- Dogfood: fresh reindex against `~/vault/projects`, `~/code`, `~/vault/data/skills_db` completed in ~2.9s, indexing the octopus project itself (1 activity, 13 tasks). 72-test suite passing (43 baseline + 29 db-layer).

### D41 — Sessions, memory, handoffs shipped (request 04)

**Sessions** — multi-open per activity; one "active" tracked in `~/.cache/octopus/active-sessions.json` (XDG-respectful). Cache wins on mismatch with frontmatter (per `SCHEMA-SESSION.md`). Lifecycle verbs: `start / log / end / switch / list / show / prune`.

- Q1 — Handoffs in SQLite index: **v1 = filesystem only.** No `handoffs` table yet. Tracked in `TODO.md` for v2.
- Q2 — Session log timestamp precision: **second** (`### YYYY-MM-DD HH:MM:SS`). Updated `SCHEMA-SESSION.md` body example.
- Q3 — Session prune window: **stale_warn at 7 days, prune at 14 days.** Both overridable via `[sessions] stale_warn_days` / `prune_days` in `~/.config/octopus/config.toml`. CLI `--days` wins over config.
- Q4 — `[e]` (end-previous) flow on `session start`: marks previous as `dropped` + auto-appends `### YYYY-... ended by session start --replace` to body.
- Q5 — Memory scaffolding: **lazy**, only the targeted section is created on first append. Canonical-order insertion is enforced via `_insert_section_in_canonical_order`.
- Q6 — `session log` with no active session: error + hint, exit 3.
- Q7 — `session show` default: active session, fall back to most-recent (ended desc, started desc) if none active.
- Q8 — `handoff new` outside an activity: error, exit non-zero. Must be inside an activity (or v2 will accept `--activity <id>`).
- Q9 — `session end --handoff` UX: prompts for title/to_actor/to_owner/summary; `--non-interactive` requires all flags.

**Memory** — schema change locked: dropped `## Log` (overlapped with session logs), added `## State` (5th canonical section). Canonical sections now: **Decisions / Open Questions / Context / Notes / State.** Default `memory append` target is `## Notes` (the catch-all). `## State` is append-only but the latest entry is treated as "current" by readers. `summary:` (frontmatter) = stable identity; `## State` = current paused state. Resolution of open questions is convention-only (`RESOLVED: ...` prefix). Two-zone parsing via `<!-- octopus-managed-below -->` marker; marker re-inserted with stderr warn if a user removes it.

Default `memory show` is a preview: `(showing latest N of M)` headers + `[K more — run \`octopus memory show --section <slug>\` for all]` footers, applied symmetrically to State, Open Questions, and Decisions.

**Handoffs** — filesystem-only in v1; verbs: `handoff new / list / show`. Lifecycle verbs (`receive`, `resolve`, `stale`) deferred to v2 — v1 covers manual frontmatter edits via `octopus set`. Symmetric backlink: `session end --handoff` writes both `session.related_handoff` and `handoff.from_session`.

**Pocock-influence refinement (post-research):** `default_body()` template now includes a `## Suggested next actions` section with machine-actionable `octopus ...` commands — handoffs are routers to existing artifacts, not duplicates. `SCHEMA-HANDOFF.md` body conventions explicitly say "Reference, don't restate" and "Make it executable." Secret-redaction is a SHOULD-warn in v1 (manual scrub); v2 may hook a redactor. Persistent in-activity storage is preserved as a deliberate contrast to ephemeral $TMPDIR handoffs.

**Cache shape locked:** `~/.cache/octopus/active-sessions.json` is `{activity_id: session_filename}`. Atomic writes via tmp + `os.replace`. Corruption → warn stderr, treat as empty map.

Dogfood: 168-test suite passing (72 baseline + 24 sessions + 38 memory + 24 handoffs + 10 cross-cutting). End-to-end smoke verified: session start/log/end, memory append/show preview, `session end --handoff` symmetric backlink, `handoff list` with arrow direction column. Closing request 04.

---

## D42 — Distribution: pipx-first, redacted diagnose, basic CI

**Date:** 2026-05-23
**Status:** Locked
**Closes:** request 11-distribution-pipx
**Bundled into:** v0.1.0 (no separate 0.2.0 — first published wheel is feature-complete)

### Locked choices

- **Distribution channel:** **pipx** as day-one install path. PyPI auto-publish deferred — manual gate until first external pipx install is confirmed clean on a fresh machine. The wheel is shipped as a GitHub release artifact via `softprops/action-gh-release@v2`.
- **Version source of truth:** `cli/pyproject.toml` only. `octopus/__init__.py` reads via `importlib.metadata.version("octopus-cli")` with a `PackageNotFoundError` fallback to `"0.0.0+unknown"`. No hardcoded version strings anywhere else.
- **Python matrix:** 3.11 / 3.12 / 3.13 in CI. 3.14 confirmed working post-install but not in CI matrix (would be flaky on actions until 3.14 is widely cached).
- **Logging:** rotating file handler at `$XDG_DATA_HOME/octopus/logs/octopus.log` (`~/.local/share/octopus/logs/` fallback). 1 MB × 5 backups. ISO 8601 second precision. `propagate=False` so logs never reach stdout. `setup_logging()` is idempotent and called once from the CLI root callback. Falls back to `NullHandler` if log dir is unwriteable — never crashes the CLI.
- **`octopus diagnose`:** collects version, spec_version, python, platform, paths, config (system path + raw + resolved), index stats (per-table row counts + db size), log tail (last 500 lines). All `$HOME` prefixes are redacted to `~/` before any payload write. Default output: `./octopus-diagnose-YYYY-MM-DD-HHMMSS.zip` in cwd. Flags: `--no-zip` (stdout only), `--out PATH` (skip prompt). Without flags, prompts before writing.
- **CI workflows:**
  - `.github/workflows/test.yml` — push to main + PRs, matrix 3.11/3.12/3.13, ruff + pytest, `working-directory: cli`, pip cache keyed on `cli/pyproject.toml`. `permissions: contents: read`.
  - `.github/workflows/release.yml` — `v*.*.*` tag trigger, `python -m build`, tag-version verification step, upload via `softprops/action-gh-release@v2`. `permissions: contents: write`. **No PyPI publish step — manual.**
- **Lint debt:** Ruff loosened to ignore `E501, B904, E402, F841, SIM108, SIM105, B008, B017, UP028, UP038` globally + per-file ignores for `tests/`. Documented inline in `cli/pyproject.toml`. Full cleanup deferred — each rule has its own reason recorded.

### Open follow-ups (non-blocking for v0.1.0 tag)

- **Clean-machine pipx test:** the dev install showed a PATH-shadowing warning because `pip install -e .` had already put `octopus` on `$PATH`. Need to verify pipx install on a fresh machine (Docker, fresh VM) before tagging v0.1.0 — and decide whether install docs should call out the shadowing risk for conda users who already `pip install`-ed.
  - **Attempt 2026-05-23 — inconclusive.** Tried Docker (`python:3.12-slim` pull hung 40+ min, no progress) and then a `/tmp` venv (system pip couldn't reach pypi.org — DNS resolution failed). Both failures environmental, not octopus-related. Sandbox removed, Docker quit, no residue. Retry from a different network.
- **PyPI publishing:** decide trigger conditions for the manual PyPI release step. Likely after one external user confirms the GitHub-release wheel installs cleanly via pipx.
- **Lint cleanup pass:** ~96 ruff errors deferred. Worth a dedicated mini-request once the surface area stabilizes.
- **Log noise audit:** currently INFO at reindex/session start-end/handoff new. Verify the file doesn't grow too fast in real use — adjust to DEBUG for chatty paths if needed.

### Test suite

183 passing (was 168 + 6 logging + 9 diagnose). Coverage now includes XDG paths, redaction guarantees, zip contents, idempotent setup, and child-logger naming.

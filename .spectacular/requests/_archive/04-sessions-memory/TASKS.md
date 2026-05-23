---
updated: 2026-05-23
status: done
closed: 2026-05-23
closes_decision: D41
---

# Tasks — 04-sessions-memory

> Activated 2026-05-23. See PLAN.md for resolved decisions table (9 questions grilled).
>
> Schema authoritative: `specs/SCHEMA-SESSION.md`, `SCHEMA-MEMORY.md`, `SCHEMA-HANDOFF.md`.
> Python packages: `cli/src/octopus/sessions/`, `memory/`, `handoffs/`.

## Models

- [x] Add `Session` dataclass to `core/models.py` (mirror SCHEMA-SESSION.md frontmatter).
- [x] Add `Memory` dataclass to `core/models.py` (frontmatter only: `activity`, `last_updated`, `summary`, plus opaque body).
- [x] Add `Handoff` dataclass to `core/models.py` (mirror SCHEMA-HANDOFF.md frontmatter).
- [x] Add validation rules: reject missing required fields, reject invalid enums, reject `ended < started`, `resolved_at < received_at`.

## Sessions — cache layer

- [x] `sessions/cache.py::load_active_map() -> dict[activity_id, session_slug]`.
- [x] `sessions/cache.py::set_active(activity_id, session_slug)` — atomic write (tmp + rename).
- [x] `sessions/cache.py::clear_active(activity_id)`.
- [x] `sessions/cache.py::get_active(activity_id) -> str | None`.
- [x] Path resolution: `~/.cache/octopus/active-sessions.json` (XDG-respectful).
- [x] Corruption recovery: malformed JSON → warn stderr + treat as empty map; don't crash.
- [x] Cache wins on mismatch with frontmatter (per SCHEMA-SESSION.md line 89).

## Sessions — I/O

- [x] `sessions/io.py::read_session(path) -> Session` — parse frontmatter + body.
- [x] `sessions/io.py::write_session(path, session, body)` — preserve body byte-for-byte.
- [x] `sessions/io.py::list_sessions(activity) -> list[Session]` — walk `<activity>/.octopus/sessions/*.md`.
- [x] `sessions/io.py::generate_filename(title) -> str` — `YYYY-MM-DD-<slug>.md`; collision counter on same-day same-title.
- [x] `sessions/io.py::append_log_entry(path, note)` — append `### YYYY-MM-DD HH:MM:SS\n<note>\n` to body. Second precision.

## Sessions — lifecycle

- [x] `sessions/lifecycle.py::start(activity, title=None) -> Session` — prompts `[c]/[n]/[e]/[a]` if any open; `[e]` marks previous as `dropped` with auto-note.
- [x] `sessions/lifecycle.py::log(activity, note)` — error+hint exit 3 if no active session.
- [x] `sessions/lifecycle.py::end(activity, slug=None, summary=None, status='done', handoff=False)` — defaults to active; `--handoff` triggers handoff creation flow.
- [x] `sessions/lifecycle.py::switch(activity, slug)` — flip cache + frontmatter `active` on both.
- [x] `sessions/lifecycle.py::prune(activity=None, days=None, dry_run=False)` — close stale opens; `days` defaults from config (`[sessions] prune_days`, default 14).
- [x] `sessions/lifecycle.py::show(activity, slug=None)` — active → most-recent fallback (ended desc, started desc).
- [x] Validation: `[e]` flow appends `### YYYY-... ended by session start --replace` to previous body.

## Sessions — CLI verbs

- [x] `octopus session start [--title "<text>"]`
- [x] `octopus session log "<note>"`
- [x] `octopus session end [<slug>] [--summary "<text>"] [--status done|dropped] [--handoff] [--non-interactive]`
- [x] `octopus session switch <slug>`
- [x] `octopus session list [--all] [--open|--closed] [--format json]`
- [x] `octopus session show [<slug>] [--format json]`
- [x] `octopus session prune [--dry-run] [--days N]`
- [x] Wire each mutation to `db.upsert.upsert_session` after file write.

## Memory — sections + parser

- [x] `memory/sections.py` — canonical list `["Decisions", "Open Questions", "Context", "Notes", "Log"]`.
- [x] `memory/sections.py::resolve_section(name) -> str` — partial-match (`open` → `Open Questions`); reject ambiguous.
- [x] `memory/io.py::read_memory(path) -> tuple[Memory, body_above, body_below]` — split on `<!-- octopus-managed-below -->`.
- [x] `memory/io.py::find_section(body_below, section_name) -> (start_idx, end_idx)` — returns insertion point at section bottom.
- [x] `memory/io.py::scaffold_new(activity_id) -> str` — fresh file with frontmatter + heading + marker (no section headings; lazy).
- [x] Marker preservation: missing marker on append → re-insert before first managed heading + warn stderr.

## Memory — verbs

- [x] `memory/io.py::append(path, section, note)` — validate non-empty; create section heading lazily; append dated entry; bump `last_updated`.
- [x] `memory/io.py::set_summary(path, text)` — write frontmatter `summary:` (multi-line `|` if newlines present).
- [x] `memory/io.py::set_summary_editor(path)` — open `$EDITOR` with current summary; save on close.
- [x] `memory/io.py::show(path, section=None) -> str` — full file or one section's content.

## Memory — CLI verbs

- [x] `octopus memory append "<note>" [--section log|decisions|open|context|notes]` (default `log`).
- [x] `octopus memory show [--section <name>] [--format json]`.
- [x] `octopus memory summary [show]`.
- [x] `octopus memory summary set ["<text>"]` (no arg → `$EDITOR`).
- [x] Datetime header format: `### YYYY-MM-DD HH:MM` (minute precision per SCHEMA-MEMORY.md line 153).

## Handoffs — I/O

- [x] `handoffs/io.py::write_handoff(path, handoff, body)` — preserve body byte-for-byte.
- [x] `handoffs/io.py::read_handoff(path) -> Handoff`.
- [x] `handoffs/io.py::list_handoffs(activity, status=None) -> list[Handoff]` — walk `<activity>/.octopus/handoffs/*.md`; filter by status.
- [x] `handoffs/io.py::generate_filename(title) -> str` — date-prefixed `YYYY-MM-DD-<slug>.md`; collision counter.
- [x] `handoffs/io.py::default_body(title) -> str` — render the recommended body template from SCHEMA-HANDOFF.md.

## Handoffs — CLI verbs

- [x] `octopus handoff new "<title>" [--from-session <slug>] [--to-actor human|ai|both] [--to-owner <name>] [--priority high|medium|low] [--summary "<text>"]`.
- [x] `octopus handoff list [--status open|received|resolved|stale] [--format json]`.
- [x] `octopus handoff show <slug> [--format json]`.
- [x] Error exit 3 when not inside an activity and no `--activity` global flag.
- [x] `session end --handoff` flow: prompts for title/to_actor/to_owner/summary; `--non-interactive` requires flags.
- [x] Writes session `related_handoff:` and handoff `from_session:` symmetrically.

## Config

- [x] Extend `config.py` with `[sessions]` block:
  - [x] `stale_warn_days: int = 7`
  - [x] `prune_days: int = 14`
- [x] Both readable from `~/.config/octopus/config.toml`.
- [x] CLI flag `--days N` on `session prune` overrides config.

## Scaffold

- [x] `fs/scaffold.py::init_activity` — ensure `.octopus/sessions/` and `.octopus/handoffs/` directories are created on `init` (empty).

## Spec updates

- [x] `specs/CLI-VERBS.md` — add `session`, `memory`, `handoff` verb blocks matching existing format.
- [x] `specs/SCHEMA-SESSION.md` line 176-177 — update body example timestamp to second precision (`### 2026-05-22 14:32:17`).
- [x] `specs/SCHEMA-SESSION.md` — note `[e]` flow appends auto-note + sets `dropped`.
- [x] `specs/CRITICAL-DEPENDENCIES.md` — add rules for session cache + memory marker invariants.

## Tests

- [x] `tests/test_sessions_lifecycle.py` — start (no-open), log, end (default + flags), switch happy paths.
- [x] `tests/test_sessions_multi_open.py` — `[c]/[n]/[e]/[a]` prompt outcomes; `[e]` sets previous to `dropped` + auto-note.
- [x] `tests/test_sessions_cache.py` — atomic write, corruption recovery, cache-wins-on-mismatch.
- [x] `tests/test_sessions_log_no_active.py` — error + hint, exit 3.
- [x] `tests/test_sessions_show.py` — active → most-recent fallback → error-if-zero-sessions.
- [x] `tests/test_sessions_prune.py` — closes >prune_days quiet; respects `--days`; respects config.
- [x] `tests/test_memory_append.py` — append to each section, partial-match resolution, lazy section creation.
- [x] `tests/test_memory_summary.py` — set via flag, set via $EDITOR (mocked), preserve unknown frontmatter.
- [x] `tests/test_memory_marker.py` — marker preservation; re-insertion + warn on missing.
- [x] `tests/test_memory_hand_edit.py` — user-added section preserved; renamed canonical heading warns + duplicates.
- [x] `tests/test_handoff_new.py` — happy path, with `--from-session`, validation rejects.
- [x] `tests/test_handoff_list_show.py` — status filter, JSON shape.
- [x] `tests/test_session_end_handoff.py` — symmetric `related_handoff` + `from_session`; `--non-interactive` flag behavior.
- [x] All 72 pre-existing tests still pass.

## Dogfood

- [x] Run a real session on the octopus project itself: `octopus session start`, `log` 2-3 entries, `end --summary "..."`.
- [x] Append a memory entry to `## Decisions` and `## State`; verify scaffolding. (Log was renamed to State per D41.)
- [x] Create a handoff with `--from-session`; verify symmetric refs.
- [x] Run `octopus reindex` and confirm the new session row appears.
- [x] Capture any friction as backlog tasks (3 captured 2026-05-23: memory-show blank line, session-log timestamp dedup, reindex output clarity).

## Close

- [x] Append DECISIONS D41 (session cache shape + memory marker + handoffs-fs-only + 9 grilled decisions).
- [x] Update `TODO.md` with v2 `handoffs` SQLite table entry.
- [x] Set PLAN.md `status: done`, add `closed:` and `closes_decision:` fields.
- [x] Set this TASKS.md `status: done`.

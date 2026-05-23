---
status: done
priority: medium
owner: alex
updated: 2026-05-23
summary: "Sessions (multi-open + sticky active in cache), handoffs, memory.md with 5 fixed sections + frontmatter summary."
related:
  - 02-cli-walking-skeleton
  - 03-index-sqlite
  - 05-tui
gates:
  - 03-index-sqlite
activated: 2026-05-23
closed: 2026-05-23
closes_decision: D41
---

# Sessions, handoffs, memory

## Goal

Implement the continuity layer that makes Octopus useful across days:

1. **Sessions** — multi-open per activity, one "active" tracked in `~/.cache/octopus/active-sessions.json`, full lifecycle (start / log / end / switch / prune / list / show).
2. **Memory** — append-only `memory.md` with the canonical 5 sections and a curated frontmatter `summary:`.
3. **Handoffs** — v1 file model + `octopus handoff new`. Lifecycle verbs (`receive`, `resolve`, `stale`) stay deferred; manual frontmatter editing via `octopus set` covers v1.

## Why

Sessions and memory are what turn Octopus from "another task list" into a continuity tool. After a week away from a project, `octopus context` should be able to reconstruct what was happening — that requires session records and a memory log. The index work in request 03 already populates the `sessions` table on reindex; this request makes verbs *write* those rows and surfaces the data.

## Approach

- **Schemas are frozen** in `specs/SCHEMA-SESSION.md`, `SCHEMA-MEMORY.md`, `SCHEMA-HANDOFF.md`. No schema changes in this request; if a contradiction is found, surface it for a `DECISIONS` entry before writing code.
- **Python package layout:**
  - `cli/src/octopus/sessions/` — session lifecycle module (read/write, cache management).
  - `cli/src/octopus/memory/` — memory.md two-zone parser/appender.
  - `cli/src/octopus/handoffs/` — handoff file writer.
  - All three follow the existing pattern: `models.py` is shared in `core/models.py`; this request *extends* that file rather than splitting it.
- **Cache management:** `~/.cache/octopus/active-sessions.json` is a flat JSON map `{activity_id: session_slug}`. Read on every session-aware verb; written atomically (tmp + rename). If cache and frontmatter disagree, **cache wins** (per SCHEMA-SESSION.md line 89).
- **Stale-detection:** stale-open sessions surfaced by `octopus reindex` (warn) and `octopus where` (already file-native). `session prune` auto-closes them with `ended: <last_log_time>`.
- **Marker enforcement:** memory.md's `<!-- octopus-managed-below -->` is the only invariant the CLI defends; if missing, re-insert on next append with a stderr warning.

## Commands in scope

```
# Sessions
octopus session start [--title "<title>"]
octopus session log "<note>"
octopus session end [<slug>] [--summary "<text>"] [--status done|dropped] [--handoff]
octopus session switch <slug>
octopus session list [--all] [--open|--closed] [--format json]
octopus session show [<slug>] [--format json]   # active by default
octopus session prune [--dry-run] [--days N]

# Memory
octopus memory append "<note>" [--section log|decisions|open|context|notes]
octopus memory show [--section <name>] [--format json]
octopus memory summary [show]                   # print current summary
octopus memory summary set ["<text>"]           # set summary; no arg → $EDITOR

# Handoffs (v1 minimal)
octopus handoff new "<title>" [--from-session <slug>] [--to-actor human|ai|both]
                              [--to-owner <name>] [--priority high|medium|low]
                              [--summary "<text>"]
octopus handoff list [--status open|received|resolved|stale] [--format json]
octopus handoff show <slug> [--format json]
```

`session end --handoff` is a convenience: ends the active session **and** creates a handoff in one shot, auto-populating `from_session:` and prompting (or accepting flags) for the rest.

## Out of scope

- `octopus handoff receive | resolve | stale` — v2; v1 expects manual frontmatter edits via `octopus set` if needed.
- Cross-activity handoffs UI (`related_activities`) — schema supports it; no dedicated verb in v1.
- FTS5 search across memory — v2.
- `octopus context` and `octopus daily` bundle commands — out of scope here (Claude-plugin request 08).
- TUI views of sessions/memory — request 05.
- Reflowing `memory.md` body or fixing user-renamed section headings — warn only.

## Deliverables

### Code (new modules)

- `cli/src/octopus/sessions/__init__.py`
- `cli/src/octopus/sessions/io.py` — read/write session files; merge cache + frontmatter.
- `cli/src/octopus/sessions/cache.py` — atomic read/write of `~/.cache/octopus/active-sessions.json`.
- `cli/src/octopus/sessions/lifecycle.py` — start / log / end / switch / prune semantics.
- `cli/src/octopus/memory/__init__.py`
- `cli/src/octopus/memory/io.py` — two-zone parse (marker split), append-to-section, summary set.
- `cli/src/octopus/memory/sections.py` — canonical section list + partial-match resolver.
- `cli/src/octopus/handoffs/__init__.py`
- `cli/src/octopus/handoffs/io.py` — write new handoff files; list/show.

### Code (extensions)

- `cli/src/octopus/core/models.py` — add `Session`, `Memory`, `Handoff` dataclasses (mirroring schema docs).
- `cli/src/octopus/cli.py` — wire `session`, `memory`, `handoff` command groups.
- `cli/src/octopus/db/upsert.py` — extend `upsert_session` was already present from request 03; add `upsert_handoff` (sessions table only; handoffs not indexed in v1 — but capture file existence for `handoff list`). **Confirm with Alessandro:** do we add a `handoffs` table now or list-from-filesystem?
- `cli/src/octopus/fs/scaffold.py` — ensure `init` creates empty `sessions/` and `handoffs/` directories.

### Tests

- `tests/test_sessions_lifecycle.py` — start/log/end/switch/prune happy + error paths.
- `tests/test_sessions_cache.py` — cache atomicity, mismatch resolution (cache wins), corruption recovery.
- `tests/test_sessions_multi_open.py` — multiple open sessions, prompt outcomes, switch behavior.
- `tests/test_memory_append.py` — append to each of 5 sections, partial-name match, lazy section creation, marker preservation.
- `tests/test_memory_summary.py` — set via flag, set via $EDITOR (mocked), preserve unknown frontmatter.
- `tests/test_memory_hand_edit.py` — user-added section preserved, renamed heading warning, marker re-insertion.
- `tests/test_handoff_new.py` — new from scratch, new from session (auto-fills `from_session`), validation.
- `tests/test_handoff_list_show.py` — filtering by status, JSON output shape.

### Spec updates

- `specs/CLI-VERBS.md` — add `session`, `memory`, `handoff` verb specifications inline with the existing block format.
- `DECISIONS.md` — D41 locking the session-cache JSON shape + memory marker behavior + handoff-table-vs-filesystem choice.

## Acceptance criteria

- `octopus session start` in an activity with no open sessions creates a session file, sets it active in cache, and frontmatter `active: true` matches.
- `octopus session start` with one already open prompts `[c]/[n]/[e]/[a]` per PRD §13.2.
- `octopus session log "<note>"` appends `### YYYY-MM-DD HH:MM\n<note>` to the body of the active session and is a no-op (error) if no session is active.
- `octopus session end` sets `ended:` to now, `active: false`, `status: done` (or `dropped` with flag), clears cache entry.
- `octopus session switch <slug>` flips `active` on both old and new (cache + frontmatter mirror).
- `octopus session prune` closes sessions with no append activity > N days (config default 7); writes an auto-generated note, sets `status: dropped`.
- `octopus memory append` creates `memory.md` from scaffold if absent; appends a dated entry to the named section (default `## Log`); creates the section lazily; preserves the marker.
- `octopus memory summary set "<text>"` writes the YAML `summary:` field; `octopus memory summary` prints it.
- `octopus memory append` errors with empty note.
- `octopus handoff new "<title>"` writes `handoffs/<slug>.md` with required fields populated and `status: open`.
- `octopus session end --handoff` creates a handoff, sets `related_handoff:` on the session and `from_session:` on the handoff.
- All 72 existing tests still pass.
- New tests cover all listed acceptance behaviors.

## Resolved decisions (grilled 2026-05-23)

| # | Question | Decision |
|---|---|---|
| 1 | Handoffs in SQLite? | **No** — filesystem only in v1. `octopus handoff list` walks `<activity>/.octopus/handoffs/*.md`. v2 table tracked in `TODO.md`. |
| 2 | `session log` timestamp granularity | **Second precision**: `### YYYY-MM-DD HH:MM:SS`. SCHEMA-SESSION.md body example (`### 2026-05-22 14:32`) to be updated to match. |
| 3 | `session prune --days` default | **14 days**. Overridable via `[sessions] prune_days = N` in `~/.config/octopus/config.toml`. CLI flag `--days N` always wins. |
| 3b | Stale-session warn threshold | **7 days** (warn earlier than auto-close). Overridable via `[sessions] stale_warn_days = N` in config. Two-stage: warn@7, prune@14, both user-configurable independently. |
| 4 | `[e]` end-previous status | **`dropped`** + auto-note `### YYYY-... ended by session start --replace`. Distinguishes interrupted from cleanly-finished. |
| 5 | `memory.md` first-append scaffold | **Lazy** — only the targeted section. Frontmatter + marker + `## <Targeted>` + entry. Schema line 130 already mandates this. |
| 6 | `session log` with no active session | **Error + hint**, exit 3. `no active session in <activity> — run \`octopus session start\` first`. |
| 7 | `session show` default (no slug) | **Active session**, fall back to **most-recent** (`ended:` desc, then `started:` desc) if none active. Error only if zero sessions exist. |
| 8 | `handoff new` outside any activity | **Error**. `not inside an activity — cd into one or pass --activity <id>`. Exit 3. |
| 9 | `session end --handoff` UX | **Interactive prompts** for title / `to_actor` / `to_owner` / `summary`. `--non-interactive` skips and uses flag values; missing required → error. |

## Specs to reference

- `specs/SCHEMA-SESSION.md` — session frontmatter contract.
- `specs/SCHEMA-MEMORY.md` — memory two-zone model.
- `specs/SCHEMA-HANDOFF.md` — handoff frontmatter + lifecycle.
- `PRD.md §13.2` — sessions resolved decisions.
- `PRD.md §13.7` — memory.md write model.
- `specs/CRITICAL-DEPENDENCIES.md` — validation rules across all three.

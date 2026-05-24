---
updated: 2026-05-24
---

# TODO

Two zones in this file:

1. **`## Friction`** — the live capture surface. Items here are pulled by `octopus bridge pull todo-md` (configured with `section_filter = ["friction"]`). Add anything that bugs you, misses, or feels wrong while using the system. Drop the rest of this section's surface to triage them.
2. **Everything below** — deferred design ideas surfaced during v1 work. **Not** pulled into the backlog. Re-open notes per item.

---

## Friction

<!-- Add `- [ ]` items here. They get pulled into the backlog on `octopus bridge pull todo-md`. -->



---

## Routines (recurring practice)

- A "routine" is something done repeatedly with flexible scheduling (weekly review, morning journal, monthly cleanup) — not a hard cron, more "I do this regularly."
- Originally proposed as `kind: routine` in the task schema; dropped in v1 along with the rest of `kind`.
- **Future shape**: probably a separate top-level concept (`.octopus/routines/` folder?) with its own schema and verbs (`octopus routine new`, `octopus routine run`). Not a flavor of task.
- **Re-open when**: routines start appearing in real use and feel like they want structure.

---

## The "Mind" view

- Originally proposed as `octopus mind` — a view that lists everything currently in mental focus.
- v1 drops this in favor of: `pinned: true` is the explicit user marker (always sorts to top of any list); "open loops" (unfinished work) is a derived view via `octopus loops`.
- **Future shape**: if `pinned` and `loops` together aren't enough, add `octopus mind` as a composite view combining them.
- **Re-open when**: there's a clear use case for a dedicated mental-load surface beyond what `loops` and `pinned` already provide.

---

## Per-activity strict validation for `stage`

- The `stage` field is free-form in v1 (any string accepted).
- Per `.octopus/config.toml`, an activity may want to restrict `stage` to a defined list (`["idea", "draft", "review", "publish"]`).
- **Future shape**: `[stage] strict = true` + `[stage] allowed = [...]` in `.octopus/config.toml`. Mirrors the `[areas]` strict-mode pattern.
- **Re-open when**: a project's `stage` values drift into typos / duplicates and discovery warnings aren't enough.

---

## `forget` verb (soft delete to `.trash/`)

- Captured in CLI-VERBS.md as draft. Pending v2.
- Use `archive` for v1.

---

## Notes as a separate file type

- A note belongs in `memory.md` (or future `memory/` if it grows), in the activity body, or as a standalone `.md` at the activity root.
- NOT in `tasks/`.
- If memory grows beyond a single file, consider `.octopus/memory/<topic>.md` as a future option.

---

## `octopus index info` command

- Show derived-store stats: row counts (activities/tasks/sessions), last reindex time, index.db file size, configured roots.
- Useful for debugging "is my index sane?"
- **Re-open when**: someone needs to debug stale or corrupt index state without using `sqlite3` directly.

---

## `config root add` auto-prompt to reindex

- After `octopus config root add <path>`, prompt "scan now? [y/N]" interactively (skip prompt when non-TTY).
- Not blocking for v1; just a minor UX improvement.
- **Re-open when**: friction surfaces from forgetting to reindex after adding a root.

---

## SQLite row-level locking strategy

- Currently rely on SQLite WAL mode handling concurrent reads + one writer.
- Two simultaneous CLI mutations would briefly serialize. Acceptable at personal-tool scale.
- **Re-open when**: TUI + watcher + agent all start writing concurrently and contention becomes visible.

---

## `handoffs` table in SQLite index

- v1 ships handoffs as filesystem-only (`handoffs/<slug>.md` per activity). `octopus handoff list` walks the directory; no SQL.
- A `handoffs` table mirroring `sessions` would unlock single-query cross-activity views — useful for `octopus context` (request 08) and TUI summaries.
- **Future shape**: bump SCHEMA-INDEX to v2, add `CREATE TABLE handoffs (...)`, ship migration runner. Reindex would populate it the same way sessions are populated now.
- **Re-open when**: cross-activity handoff queries become a real pattern (likely when request 08's plugin bundle commands land).

---

## JSON schema validation of `raw_frontmatter` blobs

- The index stores full original frontmatter as a JSON blob (forward-compat).
- v1 trusts that we always write valid JSON; no read-side validation.
- **Re-open when**: a third-party tool starts writing into index.db directly (unlikely; CLI is the only writer).

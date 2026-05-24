---
status: done
priority: medium
owner: alex
updated: 2026-05-24
summary: "Octopus reads tasks from a TODO.md markdown file at the activity root, importing checkbox lines into the backlog. Pull-only v1; co-resident with the Octopus task tree."
related:
  - 06-adapter-framework
  - 07-adapter-obsidian
  - 09-adapter-reminders-pull
gates:
  - 06-adapter-framework
---

# Adapter: TODO.md

## Goal

Allow Octopus to **import tasks from a `TODO.md` file** sitting at the activity root (or any configured path). Many repos and folders already have a free-form `TODO.md` — Octopus should be able to read those lines and surface them in the backlog without forcing the user to migrate.

Pull-only v1. The `TODO.md` file remains the source of truth for whatever wrote it; Octopus mirrors checkbox lines into its task tree.

## Why

`TODO.md` (and variants: `TODO`, `TASKS.md`, `BACKLOG.md`) is a near-universal convention in code repos. Asking the user to convert every existing one into Octopus-native tasks is friction. The adapter framework (#06) is designed for exactly this kind of read-source — `TODO.md` is the simplest case (plain markdown, no external API, no auth).

Shipping a `TODO.md` adapter early also serves as a **reference implementation** for the adapter framework: smallest possible surface, no network, fast to test end-to-end.

## Scope

### Phase 1 — Pull-only import

- `octopus pull todo-md` reads `TODO.md` from the activity root.
- Each unchecked checkbox line (`- [ ] something`) becomes a backlog task.
- Each checked line (`- [x] something`) is treated as already-done and either skipped or imported into `done/` (config-driven, default skip).
- Non-checkbox lines (headings, prose, plain bullets) are ignored.

### Phase 2 — Configurable source path

```toml
[adapters.todo-md]
enabled = true
path = "TODO.md"                  # default; relative to activity root
include_checked = false           # default: skip done items
section_filter = []               # optional list of heading slugs to include
```

`section_filter` lets the user say "only import checkboxes under the `## Backlog` heading" — useful for `TODO.md` files that mix planning notes with task lines.

### Phase 3 — Provenance fields

Every imported task carries provenance frontmatter so re-imports don't duplicate:

```yaml
imported_from: todo-md
import_date: 2026-05-23
external_refs:
  todo-md: "TODO.md#L42"          # file + line of the source checkbox
```

On re-pull, Octopus matches existing tasks by `external_refs.todo-md` and skips them (or updates the title if it changed in the source). New checkbox lines become new tasks.

### Phase 4 — Watcher hook (optional)

If the watcher daemon (#12-watcher-daemon) is running, file-changed events on `TODO.md` trigger an incremental pull. Out of scope for v1; deferred to whichever request lands second.

## Approach

1. Land #06 (adapter framework) first — this request gates on it.
2. Implement `todo-md` adapter as a reference example in the adapter directory.
3. Add `octopus pull todo-md` to the CLI (or generic `octopus pull <adapter-name>`).
4. Add config schema entries in `.octopus/config.toml` documentation.
5. Tests covering: empty file, all-unchecked, mixed checked/unchecked, section filtering, re-pull idempotency, malformed checkboxes.
6. Document in `skills/octopus/references/adapters/todo-md.md`.

## Out of scope (v1)

- **Two-way sync.** Octopus does not write checkmarks back into `TODO.md` when a task is finished. Pull-only.
- **Nested lists.** Only flat top-level checkbox lines. Sub-bullets are dropped.
- **Inline metadata syntax.** No parsing of `- [ ] task @due:2026-05-23 +tag` or other dataview-style annotations. Pure title.
- **Multiple TODO.md files per activity.** One path per config entry. Multiple files = multiple adapter entries (or future enhancement).
- **Globbing across the repo.** `TODO.md` files in subdirs are ignored unless the path is set explicitly.

## Deliverables

- [ ] `todo-md` adapter implementation in the adapter framework
- [ ] `octopus pull todo-md` CLI command (or via generic `pull <name>`)
- [ ] Config schema entries documented
- [ ] Provenance fields written on import
- [ ] Re-pull is idempotent (no duplicates)
- [ ] Tests covering happy path + edge cases
- [ ] `references/adapters/todo-md.md` in the skill
- [ ] D-entry in `DECISIONS.md` if any contract is locked

## Locked decisions (2026-05-24)

| # | Decision |
|---|---|
| Q1 | Default path: `TODO.md` at activity root. No upward scan. Configurable via `path =` in `bridges/todo-md.toml`. |
| Q2 | Checkbox marks: `[ ]` → backlog, `[x]`/`[X]` → done (skipped unless `include_checked = true`), `[-]`/`[/]` → in-progress (`bucket: now`). Any other char → treated as unchecked. |
| Q3 | Title cleanup: strip leading uppercase prefixes (`TODO:`, `FIXME:`, `BUG:`, `HACK:`, `NOTE:`) and map to `kind`: `BUG:` → `bug`, `HACK:` → `chore`. `NOTE:` items skipped (notes ≠ tasks). `TODO:`/`FIXME:` → no kind set. |
| Q4 | Missing `TODO.md`: soft no-op. `peek` returns empty; `pull` exits 0 with "no TODO.md found at <path>". Re-running after file creation just works. |
| Q5 | Section filter: heading slug-based (lowercase + slugify the heading text). Empty list = no filter (import everything). |
| Q6 | `external_id` format: `<path>#<slug-of-title>`. Survives line-number drift; collision risk on duplicate titles is acceptable and visible to the reader. |

Implementation maps cleanly: `_parse_checkbox(line)` and `_extract_title_meta(text)` are pure functions; the adapter wires them via `peek()` returning `PullResult.tasks` from the parsed file.

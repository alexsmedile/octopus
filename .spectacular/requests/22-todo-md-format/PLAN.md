---
status: done
priority: high
owner: alex
updated: 2026-05-24
summary: "TODO.md format spec: GFM + Obsidian Tasks emoji + Octopus `→` arrow. Two-way pull annotation rewrites the source file. Limited mutation verbs (add/complete)."
related:
  - 06-adapter-framework
  - 21-adapter-todo-md
  - 23-todo-md-crud
gates:
  - 21-adapter-todo-md
---

# TODO.md format spec + two-way annotation

## Goal

Make `TODO.md` an **honest** Octopus capture surface:

1. Adopt **GFM checklist + Obsidian Tasks emoji conventions** as the format. No invented syntax for the common stuff (priority, dates, tags).
2. Add **`→ <provider>:<slug>` arrow** as Octopus's one new convention — meaning "this item is now under another system's responsibility, exclude from re-import."
3. On pull, **Octopus annotates the source file** — rewrites successfully-imported `- [ ] thing` lines to `- [x] thing → octopus:<task-slug>`. The file becomes an at-a-glance map of "what's where."
4. Add **limited mutation verbs** (`octopus bridge add todo-md`, `octopus bridge complete todo-md`) so the user can manage the file without opening an editor — and without forcing import into the task tree.

Full CRUD (reorder, edit-in-place, section moves) is **out of scope** here — see request #23.

## Why

The current TODO.md adapter is one-way: it reads `- [ ]` and creates tasks. The user can't tell from the file which items are tracked, items must be re-classified manually after pull, and the parser doesn't understand the inline-metadata conventions every Obsidian user already writes.

Adopting GFM + Obsidian Tasks emoji means **zero format invention** for 95% of what users write. Adding the arrow gives Octopus one durable marker for "handed off." Rewriting on pull turns the file into a living index instead of an append-only inbox.

## Format spec

### 1. GFM checklist (base layer)

Every parsed item is a GFM task-list item. Universally rendered by GitHub, GitLab, Obsidian, VS Code, every static-site generator.

| Mark | Meaning in source | Pull behavior |
|---|---|---|
| `- [ ]` | open, not yet handled | import to `backlog` |
| `- [/]` | in progress (Obsidian Tasks convention) | import to `now` |
| `- [-]` | in progress (alt marker) | import to `now` |
| `- [x]` | **already in Octopus** (after pull) or done-in-source | skip if has `→` arrow; otherwise import to `done` |
| `- [!]` | abandoned (Obsidian Tasks convention) | skip |
| `- [?]` | question / unclear | treat as `- [ ]` (forgiving) |

Indented checkboxes (subtasks) are **ignored** in v1 — flat top-level only.

### 2. Inline metadata: Obsidian Tasks emoji conventions

[Reference](https://publish.obsidian.md/tasks/Reference/Task+Formats/Tasks+Emoji+Format). Adopted verbatim — no invention.

| Emoji | Meaning in source | Octopus field |
|---|---|---|
| `🔺` | highest priority | `priority: urgent` |
| `⏫` | high priority | `priority: urgent` |
| `🔼` | medium priority | (omitted — Octopus has no medium) |
| `🔽` | low priority | `priority: low` |
| `⏬` | lowest priority | `priority: low` |
| `📅 YYYY-MM-DD` | due date | `due` |
| `⏳ YYYY-MM-DD` | scheduled | `scheduled` |
| `🛫 YYYY-MM-DD` | start date | `start_date` |
| `➕ YYYY-MM-DD` | created | (kept as `created_external` in `ExternalTask`) |
| `✅ YYYY-MM-DD` | completed | (informational; combined with `[x]` for `bucket: done`) |
| `❌ YYYY-MM-DD` | cancelled | (combined with `[!]` → skip) |
| `🔁` recurrence | recurring (rule follows) | unused in v1; preserved on rewrite |
| `#tag` | tag | appended to `tags` |

Tags `#tag` are picked up anywhere in the line — multiple allowed.

### 3. Octopus's one addition: the `→` arrow

```
- [x] wire obsidian symlink bridge → octopus:wire-obsidian-symlink-bridge
- [x] design adapter framework → spectacular:06-adapter-framework
```

| Form | Meaning |
|---|---|
| `→ octopus:<task-slug>` | tracked as an Octopus task |
| `→ spectacular:<request-slug>` | promoted to a Spectacular request |
| `→ <provider>:<id>` | handed off to that provider (future) |

**Behavior:**

- Pulling skips any item with an arrow. It's already someone else's responsibility.
- Octopus writes the arrow itself on successful pull (mode A — annotation), so the round-trip is self-managed.
- Users can hand-write the arrow to **exclude an item from import** without deleting it — useful for "this is a note, not a task" or "I'm tracking this in Linear instead."

### 4. Carry-over: `BUG:` / `HACK:` / `FIXME:` / `NOTE:` prefixes

Keep the existing prefix mapping from #21 (v0.4.1):

| Prefix | Effect |
|---|---|
| `TODO:` / `FIXME:` | stripped; no kind set |
| `BUG:` | stripped; `kind: bug` |
| `HACK:` | stripped; `kind: chore` |
| `NOTE:` | skipped (not a task) |

The prefix and emoji metadata can coexist: `- [ ] BUG: marquee duplicates ⏫ 📅 2026-05-30 #tui` parses to title=`marquee duplicates`, kind=`bug`, priority=`urgent`, due=`2026-05-30`, tags=`["tui"]`.

## Two-way annotation (the new behavior)

### What changes on pull

For each `- [ ] thing` line that **successfully** materializes as an Octopus task:

1. The adapter rewrites the line in `TODO.md` to:
   ```
   - [x] thing → octopus:<task-slug>
   ```
2. Inline metadata is preserved as-is. The user's emoji + tags stay intact.
3. The original line position is preserved (in-place edit).

For items that are **already annotated** (`- [x] ... → octopus:...`), the adapter skips them.

For items annotated `- [x] ... → spectacular:...`, also skip — they're tracked by a different protocol.

### Why this is a protocol change

Currently the adapter framework's protocol has `pull()` returning data only — the framework's pipeline materializes tasks; the adapter doesn't write anything. This new behavior **does** write (to the source file, not the task tree). It's a side effect of pull.

To keep the protocol honest, add a new capability flag:

```python
class Capability(Enum):
    PULL = "pull"
    PUSH = "push"
    NOTIFY = "notify"
    RECONCILE = "reconcile"
    MARK_PULLED = "mark_pulled"   # NEW — adapter writes back to source on pull
```

Adapters declaring `MARK_PULLED` implement a new method:

```python
def mark_pulled(self, mapping: dict[str, str]) -> None:
    """After successful pull, annotate the source with the task slugs.

    Args:
        mapping: external_id → octopus task slug for items that successfully
                 materialized in this pull run.
    """
```

The pipeline calls `adapter.mark_pulled(mapping)` after a successful materialize, but only if the adapter declares the capability.

v1 adapters that declare `MARK_PULLED`: `todo-md`.
v1 adapters that do NOT: `obsidian` (viewer pattern; nothing to mark), `reminders` (write-back is two-way push, deferred to #14).

### Why the arrow target is `octopus:<task-slug>` not just `<task-slug>`

Symmetry with the `promoted_to: <provider>:<id>` convention from D48. Future-proofs for:
- `→ spectacular:<request-slug>` when a TODO item gets promoted directly to a request
- `→ linear:ENG-123` when a `linear` adapter ships and items get pushed there
- `→ github:owner/repo#42` when a GitHub adapter ships

A bare slug would block these future cases.

## Limited mutation verbs

Two new sub-verbs under `octopus bridge`:

### `octopus bridge add <adapter> <title> [flags]`

Append a new checkbox to the adapter's source (for `todo-md`, that's `TODO.md`). No import to the task tree.

```bash
octopus bridge add todo-md "fix that thing"
octopus bridge add todo-md "high prio thing" --priority high --due 2026-06-01 --tag urgent
octopus bridge add todo-md "scoped to friction" --section friction
octopus bridge add todo-md "in-progress thing" --state in-progress
```

The adapter is responsible for translating these flags into the right markdown syntax — for `todo-md`, that means GFM + Obsidian Tasks emoji + the configured section.

If `--section` isn't passed, the adapter uses the first section in `section_filter` from config, or appends to the file root if no filter is set.

### `octopus bridge complete <adapter> <match>`

Toggle a `- [ ]` line to `- [x]` in place. No octopus task creation.

`<match>` is a substring-search against existing open items. If multiple match, the CLI prompts unless `--first` is passed.

```bash
octopus bridge complete todo-md "fix that thing"
octopus bridge complete todo-md "high prio" --first
```

### `octopus bridge uncomplete <adapter> <match>`

Reverse: `- [x]` → `- [ ]`. Strips any `→ ...` arrow (since the item is now back as an open todo).

### Out of scope for #22

- `reorder`, `edit` (change title), `move-section` — all #23.
- Multi-line subtask editing.
- Bulk operations (`--all`, `--match-regex`).

Keep the verb surface tight; expand based on actual friction.

## Approach

1. **Lock D-entries** for: GFM-as-base, Obsidian Tasks emoji adoption, `→` arrow convention, `MARK_PULLED` capability.
2. **Spec docs:** new `SCHEMA-TODO-MD.md` (or fold into the existing `adapter-framework.md`?). Updates to `SCHEMA-ADAPTER.md` for `MARK_PULLED`.
3. **Parser upgrade:** `_parse_checkbox` extended to recognize `[/]`, `[!]`, `[?]`; `_parse_inline_metadata(text)` new function for emoji + tags + arrow.
4. **Pull-side rewrite:** `mark_pulled(mapping)` method on `TodoMdAdapter`. Rewrites the file in-place, preserves indentation and inline metadata.
5. **Pipeline hook:** after `materialize_pull_result`, if `MARK_PULLED in adapter.capabilities`, call `adapter.mark_pulled(mapping)` with the external_id → slug map.
6. **Mutation verbs:** add `add` / `complete` / `uncomplete` sub-commands on `bridge`. Dispatches to adapter method (new `add_item`, `mark_complete`, `mark_open` methods on adapters that declare `MARK_PULLED`).
7. **Tests:** parser unit tests for every emoji + arrow case; round-trip test (pull → file has arrow → re-pull skips); mutation verb tests.
8. **Skill mirror:** `references/adapters/todo-md.md` (new file, doc-only).
9. **Ship as v0.5.0** — minor bump because of the new capability flag and verbs.

## Out of scope

- Full CRUD (reorder, edit, section moves) — **request #23**.
- Two-way for Apple Reminders — #14.
- Two-way for Obsidian symlinks — N/A (viewer pattern).
- Hand-editing `→` to point at an arbitrary string Octopus doesn't know about — best effort: parser tolerates anything after `→`, but only `octopus:` and `spectacular:` slugs participate in dedup. Other providers are accepted silently.

## Deliverables

- [ ] `adapters/base.py` — `Capability.MARK_PULLED` enum value; `Adapter.mark_pulled(mapping)` optional method; `Adapter.add_item`, `mark_complete`, `mark_open` optional methods.
- [ ] `adapters/pipeline.py` — call `mark_pulled` after successful materialize if capability present.
- [ ] `adapters/todo_md.py`:
  - Extend parser for `[/]`, `[!]`, `[?]`.
  - New `_parse_inline_metadata(text)` for emoji + tags + arrow.
  - `→` arrow makes the parser skip the item (already handed off).
  - `mark_pulled(mapping)` rewrites source in place.
  - `add_item(title, **opts)` appends new checkbox under section.
  - `mark_complete(match)`, `mark_open(match)` toggle in place.
- [ ] `cli.py` — new `bridge add` / `complete` / `uncomplete` sub-commands.
- [ ] `SCHEMA-ADAPTER.md` — document `MARK_PULLED` + the new methods.
- [ ] `CLI-VERBS.md` — document the three new verbs.
- [ ] `references/adapter-framework.md` — mirror.
- [ ] New file `references/adapters/todo-md.md` (or fold into adapter-framework) — full format spec for skill consumers.
- [ ] Tests for parser, mutation verbs, round-trip annotation.
- [ ] CHANGELOG [0.5.0] entry.
- [ ] D-entries D72–D7? in `DECISIONS.md`.

## Open for grilling (resolved up-front by user input)

- ✅ Adopt Obsidian Tasks emoji as-is — locked.
- ✅ `MARK_PULLED` as a new capability flag — locked.
- ✅ Limited mutation verbs (add/complete/uncomplete) — locked. Full CRUD deferred to #23.
- ✅ Arrow target uses `<provider>:<slug>` for symmetry with promoted_to — locked.
- ✅ Items with `→` are skipped on pull — locked.

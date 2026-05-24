---
status: backlog
priority: low
owner: alex
updated: 2026-05-24
summary: "Full TODO.md mutation CRUD: reorder, edit-in-place, section moves, bulk operations. Built on the format spec + limited verbs from #22."
related:
  - 22-todo-md-format
  - 21-adapter-todo-md
gates:
  - 22-todo-md-format
---

# TODO.md full CRUD

## Goal

Extend `octopus bridge` mutation surface for `todo-md` (and any adapter declaring `MARK_PULLED`) beyond #22's limited verb set (`add`, `complete`, `uncomplete`). Make Octopus a full markdown task editor for projects where TODO.md is the canonical source of truth.

## Why

#22 ships the format + the minimal CRUD. After dogfooding, friction will surface around:
- Editing a task's title or inline metadata without opening `$EDITOR`.
- Moving items between sections (e.g. `friction` → `done`).
- Reordering items within a section (rare but real).
- Bulk operations (`--all`, `--matching <regex>`).

Until that friction is real, the minimal verbs cover the common case. This request is the pre-captured "when it surfaces" plan.

## Scope (when activated)

New `octopus bridge` sub-verbs:

- `bridge edit <adapter> <match> --title <new>` — change a checkbox line's title.
- `bridge edit <adapter> <match> --priority <urgent|high|low>` — update emoji-encoded priority.
- `bridge edit <adapter> <match> --due <YYYY-MM-DD>` — update `📅` date.
- `bridge edit <adapter> <match> --tag <name>` (repeatable, `--remove-tag`) — manage `#tags`.
- `bridge move <adapter> <match> --section <name>` — move a line under a different heading.
- `bridge reorder <adapter> <match> --before <other>` / `--after <other>` / `--top` / `--bottom` — within-section reorder.
- `bridge remove <adapter> <match>` — delete a line entirely (no soft-delete; the file is git-tracked).
- `--all` / `--matching <regex>` modifiers on the above.

## Out of scope

- Subtask hierarchy editing (still flat in TODO.md adapter).
- Recurrence rule editing.
- Custom checkbox marks beyond GFM + Obsidian Tasks set.

## Open questions

- Should `edit --title` write a note to the corresponding Octopus task (if `→ octopus:<slug>` is present)? Probably yes — closing the round-trip loop. Decide during grilling.
- Conflict policy when match is ambiguous: prompt (TTY) or `--first` flag.
- Whether `remove` should also archive the Octopus task linked via `→`. Probably yes with `--cascade` flag (default no).

## When to activate

After 4–6 weeks of dogfooding #22's verbs. If `add` and `complete` cover 95% of edits, this request stays in backlog forever — that's fine.

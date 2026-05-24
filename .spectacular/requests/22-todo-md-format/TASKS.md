---
request: 22-todo-md-format
status: done
updated: 2026-05-24
---

# Tasks — 22-todo-md-format

## Group 1 — Lock decisions ✅
- [x] D72 — GFM + Obsidian Tasks emoji conventions for TODO.md
- [x] D73 — `→ <provider>:<slug>` arrow convention
- [x] D74 — `MARK_PULLED` capability + adapter source rewrite
- [x] D75 — Limited mutation verbs (add/complete/uncomplete); full CRUD deferred to #23

## Group 2 — Parser upgrade ✅
- [x] Extended GFM marker set: `[ ]`, `[x]`/`[X]`, `[/]`, `[-]`, `[!]`, `[?]`
- [x] New `InlineMetadata` dataclass (title + priority + dates + tags + arrow)
- [x] `_parse_inline_metadata()`: priorities, dates, tags, arrows, no-op emoji
- [x] `CheckboxLine` now carries full `InlineMetadata`
- [x] `_parse_todo_md()` skips arrow-bearing items + cancelled items
- [x] BUG/HACK/etc. prefix mapping preserved (carry-over from #21)

## Group 3 — Source annotation (D74) ✅
- [x] `Capability.MARK_PULLED` added to base enum
- [x] `_annotate_pulled_line()` primitive (preserves indent/bullet/metadata; idempotent)
- [x] `TodoMdAdapter.mark_pulled(mapping)` rewrites source in place
- [x] Pipeline calls `mark_pulled` after successful materialize if capability declared
- [x] Pipeline errors from mark_pulled surfaced but don't undo materialization

## Group 4 — Mutation verbs (D75) ✅
- [x] `add_item(title, **opts)` appends with Obsidian Tasks emoji + section insertion
- [x] `mark_complete(match, first)` substring-match + toggle `[ ]` → `[x]`
- [x] `mark_open(match, first)` reverse + strip arrow
- [x] `_insert_under_section()` helper creates missing sections
- [x] `_flip_marker()` helper

## Group 5 — CLI verbs ✅
- [x] `octopus bridge add` with `--priority/--due/--tag/--section/--state`
- [x] `octopus bridge complete` with `--first`
- [x] `octopus bridge uncomplete` with `--first`
- [x] Gated on `MARK_PULLED` capability — clear error for non-capable adapters

## Group 6 — Tests ✅ (40 new, 404 total)
- [x] `_parse_inline_metadata` covers every emoji + tag + arrow path
- [x] Combined prefix-plus-emoji integration test
- [x] Arrow exclusion + cancelled-marker skip
- [x] In-progress marker → `bucket: now`
- [x] `_annotate_pulled_line` happy + idempotent + with-metadata
- [x] `_flip_marker` + `_insert_under_section` helpers
- [x] End-to-end `mark_pulled` rewrites file
- [x] `mark_pulled` no-op on empty mapping
- [x] `add_item` happy + with metadata + invalid due + new section
- [x] `mark_complete` happy + no-match + ambiguous + --first
- [x] `mark_open` strips arrow on revert
- [x] Capability declaration assertions for all three v1 adapters

## Group 7 — Spec + skill docs ✅
- [x] `SCHEMA-ADAPTER.md`: `MARK_PULLED` in enum, four new methods documented
- [x] `CLI-VERBS.md`: bridge add/complete/uncomplete documented
- [x] `references/cli-verbs.md`: new mutation verbs + TODO.md format section
- [x] `references/adapter-framework.md`: TODO.md format spec (GFM + Obsidian + arrow + prefixes)
- [x] `SKILL.md`: verb index updated

## Group 8 — Ship ✅
- [x] CHANGELOG [0.5.0] entry
- [x] `cli/pyproject.toml` 0.4.2 → 0.5.0
- [x] README status line
- [x] PLAN/TASKS status: active → done
- [x] Manual smoke against `/tmp/parser-smoke` and `/tmp/mutate-smoke` fixtures — every code path exercised
- [ ] Tag v0.5.0 (next step)

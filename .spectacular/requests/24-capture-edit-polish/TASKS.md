---
request: 24-capture-edit-polish
status: done
updated: 2026-05-24
---

# Tasks — 24-capture-edit-polish

## Group 1 — Lock decisions ✅
- [x] D76 Tag flag matrix
- [x] D77 set --bucket frontmatter-only; move/mv for moves
- [x] D78 set --slug cascading rename
- [x] D79 refs find helper
- [x] D80 Explicit-default values clear
- [x] D81 Drop auto-pin on capture --now
- [x] D82 Empty body on capture

## Group 2 — Tag parser ✅
- [x] `core/tag_parser.py` — normalize, split, mutex, apply, filter
- [x] 46 unit tests in `test_tag_parser.py`

## Group 3 — capture polish ✅
- [x] New flags: --due/--scheduled/--start-date/--end-date/--actor/--energy/--owner/--stage
- [x] Tag matrix flags wired in
- [x] D80 explicit-default-clear via `_is_explicit_default`
- [x] D81 no auto-pin on --now
- [x] D82 empty body
- [x] Shared `_parse_iso_date` helper

## Group 4 — set polish ✅
- [x] Tag matrix flags wired in
- [x] All explicit-default-clear paths consolidated
- [x] D77 frontmatter-only via new `_save_task_in_place` helper
- [x] Soft warning on bucket/folder mismatch
- [x] Verb-overlap tip preserved

## Group 5 — move/mv verb ✅
- [x] `octopus move <slug> <bucket>` and `mv` alias
- [x] Validates against schema (rejects mv to done/dropped without dates)
- [x] Points at lifecycle verbs in the error message
- [x] Reuses `_save_task` (the file-moving variant)

## Group 6 — refs find helper ✅
- [x] `core/refs.py` — scan helpers + categorization
- [x] Word-boundary regex (no substring false positives)
- [x] `octopus refs find <slug> [--all]` CLI verb
- [x] Splits output by managed vs user-prose categories

## Group 7 — slug rename cascade ✅
- [x] `core/slug_rename.py` — scan_rewrite_plan, apply_rewrite_plan
- [x] Auto-fix: filesystem, index, waiting_for, related_tasks, promoted_from, TODO.md arrows
- [x] Soft warn: sessions, memory, handoffs
- [x] `_handle_slug_rename` in cli.py: prompt, apply, re-index
- [x] `set --slug <new>` flag with `-y` confirmation skip
- [x] Combinable with other `set` flags (renames first, then edits)

## Group 8 — Tests ✅ (39 new)
- [x] `tests/test_capture_edit_polish.py` (39 CLI integration tests)
- [x] Empty body, no auto-pin
- [x] Explicit-default-clear (priority/actor variants)
- [x] Date flags (with terminal-bucket validation rejection)
- [x] All tag input forms (comma/space/repeated/nested/with-#/without-#)
- [x] Tag mutex rejection
- [x] set tag mutations (replace/add/remove/clear/combinations)
- [x] set --bucket frontmatter-only + warning
- [x] mv moves file + alias + done-validation
- [x] Slug rename happy + invalid + duplicate + identical-rejection
- [x] Slug rename cascades to waiting_for + TODO.md
- [x] refs find managed + warning categorization + word boundary

## Group 9 — Ship ✅
- [x] CHANGELOG [0.6.0] entry
- [x] `cli/pyproject.toml` 0.5.0 → 0.6.0
- [x] README status line
- [x] PLAN/TASKS status: active → done
- [ ] Tag v0.6.0 (next step)

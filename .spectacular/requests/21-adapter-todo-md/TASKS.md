---
request: 21-adapter-todo-md
status: done
updated: 2026-05-24
---

# Tasks — 21-adapter-todo-md

## Group 1 — Lock decisions ✅

- [x] Locked in PLAN: checkbox semantics (`[ ]`/`[x]`/`[X]`/`[-]`/`[/]`), title-cleanup prefix mapping (`BUG`/`HACK`/`NOTE`/`TODO`/`FIXME`), missing-file soft no-op, slug-based `external_id`. No new D-entries needed — all locked decisions are adapter-internal behavior, not framework contract.

## Group 2 — Parser (pure functions) ✅

- [x] `_parse_checkbox(line) -> CheckboxLine | None` — handles all five marker variants + unknown-as-unchecked
- [x] `_extract_title_meta(text) -> (cleaned_title, kind | None, skip: bool)` — 5 known prefixes + verbatim fallback
- [x] `_parse_todo_md(content, section_filter, include_checked, source_path) -> list[ExternalTask]`
- [x] `_slugify_heading()` for both heading slugs and title-based external_ids
- [x] Duplicate-title collision counter (`#title-2`, `#title-3`)

## Group 3 — Adapter implementation ✅

- [x] `cli/src/octopus/adapters/todo_md.py` — full replacement of the stub
- [x] `validate_config(data)` — rejects bad types on `path`, `include_checked`, `section_filter`
- [x] `status()` — reports healthy; reads journal for `last_pull`
- [x] `list_groups()` returns `[]` — single-file adapter, no groups concept
- [x] `peek()` reads file, returns parsed `PullResult`, no side effects
- [x] `pull()` same as `peek` — framework's pipeline does materialization
- [x] `search(query)` — peek + title-substring filter
- [x] `push()` returns `PushResult(error="todo-md is pull-only")`
- [x] **Framework fix:** `resolve_groups` now takes `adapter_has_groups: bool`. Single-source adapters skip the `--list`/`--capture-all` matrix; the CLI's discovery-mode branch only fires for multi-group adapters.

## Group 4 — Tests ✅ (30 new in `test_adapter_todo_md.py`)

- [x] Checkbox parser: all 5 marker variants, indent tolerance, alt bullet chars, rejects headings/prose/regular bullets
- [x] Title cleanup: all 5 known prefixes mapped correctly, unknown prefixes verbatim, `NOTE:` skips
- [x] Heading slugification: spaces, special chars, mixed case
- [x] Full content parse: default skips checked + notes, `include_checked` flag, section filter (heading slug)
- [x] Slug-based `external_id` stability + duplicate-title counter
- [x] Empty / no-checkbox content returns empty
- [x] Adapter status reports healthy
- [x] Adapter `list_groups` returns `[]`
- [x] `validate_config` happy path + rejection cases
- [x] End-to-end with real file fixture: peek + pull + search + missing-file no-op
- [x] Patched `test_stub_adapters_satisfy_protocol` to acknowledge TODO.md is real now

## Group 5 — Ship ✅

- [x] CHANGELOG [0.4.1] entry — first real adapter
- [x] `cli/pyproject.toml` 0.4.0 → 0.4.1
- [x] README status line updated
- [x] PLAN status: active → done
- [x] TASKS status: active → done
- [ ] Skill reference `skills/octopus/references/adapters/todo-md.md` — deferred (out of scope for v0.4.1; brief mention in changelog + existing `adapter-framework.md` is enough for now)
- [ ] Tag v0.4.1 (next step)

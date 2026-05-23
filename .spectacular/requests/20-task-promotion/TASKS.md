---
request: 20-task-promotion
status: active
updated: 2026-05-23
---

# Tasks — 20-task-promotion

Ordered top-to-bottom. Each group below should land in its own commit (or small commit cluster) so the migration is reviewable in steps.

---

## Group 1 — Lock decisions in DECISIONS.md ✅

- [x] D45 — F1 task naming formula (already in practice from v0.2.7; this just records it)
- [x] D46 — `kind` enum: `feat | bug | spec | polish | test | chore`. Optional. Mutable.
- [x] D47 — Task promotion is one-way (Octopus → Spectacular). Marker is `promoted_to: <provider>:<id>`. Body replaced. No new bucket. `kind: handoff` not used.
- [x] D48 — Provider-namespaced `promoted_to` (`<provider>:<id>`), config-driven chip aliases, `[providers]` config section. CLI input forms locked.
- [x] D49 — Hard-reject idempotency: `--force` repoints, `--revert` soft-clears; `promoted_from` historical.
- [x] D50 — Multi-task promotion atomic, positional args, `--force`/`--revert` global. Provider-only shorthand rejected with 2+ tasks.
- [x] D51 — Stub template hard-coded v1, body replaced entirely, no summary line.
- [x] D52 — `kind` survives promotion. Hidden from default filters by `done/`-exclusion. Surface via `--all`, `--promoted`, `--spec`.
- [x] D53 — Spec-native requests use absence-as-marker (no `promoted_from` field).
- [x] D54 — Reindex derives `related_tasks` on the request side.
- [x] D55 — Request #19 superseded by #20.

## Group 2 — Schema docs (Spectacular side) ✅

- [x] `SCHEMA-TASK.md`: add `kind` field to canonical order (taxonomy group) + field reference section
- [x] `SCHEMA-TASK.md`: add `promoted_to` field (integrations & provenance group) + format spec + field reference
- [x] `SCHEMA-TASK.md`: document `<provider>:<identifier>` format + validation rules
- [x] `CLI-VERBS.md`: document `octopus promote` (verb, flags, examples, exit codes)
- [x] `CLI-VERBS.md`: document `--revert` flag on `promote`
- [x] `CLI-VERBS.md`: document `list --kind`, `list --promoted`, `list --spec`, `list --all` scope rules
- [x] `CRITICAL-DEPENDENCIES.md`: validation rules for `promoted_to` (parse format, known provider, identifier shape) — section T
- [x] `CRITICAL-DEPENDENCIES.md`: validation rule for `kind` enum membership (soft — log warning on unknown, do not reject v1) — section S
- [x] `CRITICAL-DEPENDENCIES.md`: validation rule preventing manual edits to derived `related_tasks` on request PLAN.md — section T (Reindex)

## Group 3 — Schema docs (skill mirror) ✅

- [x] `skills/octopus/references/schemas/task.md`: mirror `kind` + `promoted_to` additions
- [x] `skills/octopus/references/cli-verbs.md`: mirror `promote` + new `list` flags
- [x] `skills/octopus/references/critical-dependencies.md`: mirror new validation rules (X4–X7)

## Group 4 — Config schema ✅

- [x] Add `[providers]` section to config docs: `default` field + registered provider enum
- [x] Add `[providers.chips]` section: aliases map, validation rules (ASCII, ≤6 chars)
- [x] Add `[providers.spectacular]` section: `auto_number` (default `true`)
- [x] Document config precedence (already covered by existing SCHEMA-CONFIG §1)
- [x] Ship default config values for v1 (`default = spectacular`, `chips.spectacular = spec`)

## Group 5 — Code: shared actions layer ✅

- [x] `octopus/actions.py`: add `promote_task(slugs, to, *, explicit_slug, force, revert) -> PromoteResult`
- [x] Pre-flight validation function (all tasks exist, none already promoted unless `--force`)
- [x] Target parser (`octopus/promotion.py`): `<provider>:<id>` | `<id>` | `<provider>` → canonical
- [x] Smart-resolve helper: existing dir → link; absent → scaffold (apply auto-numbering)
- [x] Stub template renderer (hard-coded string, substitutes title/target/date)
- [x] Body-replacement + frontmatter update primitive (uses existing `_save`)
- [x] File-move primitive (existing `_save` already handles bucket → folder move)
- [x] Request scaffolder: create `.spectacular/requests/<slug>/PLAN.md` from template with `promoted_from`
- [x] `kind` + `promoted_to` in Task model, `fs/io.py` round-trip, SQLite schema v2 migration
- [x] `[providers]` config in `Config` dataclass with defaults
- [x] All 225 existing tests pass

## Group 6 — Code: CLI verb ✅

- [x] `octopus promote` Typer command implemented inline in `cli.py` (positional task slugs, `--to`, `--slug`, `--force`, `--revert`)
- [x] Wired into `cli.py` between `restore` and `set` verb groups
- [x] Exit codes: 0/2/3/4 per PLAN — 4 (already promoted) verified end-to-end
- [x] Confirmation output: scaffolded/linked line + per-task promoted/repointed/reverted line
- [x] Refinement to D49: `--revert` also moves task to `bucket: backlog` (forced by validation rule that `done` requires `end_date`). Mirrored to spec + skill + PLAN.
- [x] Smoke-tested in /tmp fixture: capture → promote → repoint (--force) → revert all work end-to-end

## Group 7 — Code: list filters ✅

- [x] `db/queries.py`: `_apply_promotion_filters` helper; `tasks_for_activity` + `tasks_all` accept kinds/promoted/spec
- [x] `cli.py` `list` command: `--kind` (comma-sep multi), `--promoted`, `--spec` flags
- [x] `cli.py` `task list` command (file-native): same three filters
- [x] `cli.py` `set` command: `--kind` field added
- [x] `_print_grouped` (file-native) renders `[kind]` chip + `→ chip:id` promotion arrow
- [x] `_print_task_rows` (index-backed) renders `[kind]` chip + `→ chip:id` promotion arrow
- [x] Provider chip lookup via `_promoted_chip()` helper using `[providers.chips]` config
- [x] Smoke-tested: filter by single kind, multi-kind (comma), `--all` shows promoted tasks with arrow

## Group 8 — Code: reindex ✅

- [x] `db/reindex.py`: collect `(task_slug, promoted_to)` pairs during task scan
- [x] `_propagate_related_tasks()`: parse provider, route only spectacular:, group by slug
- [x] `_rewrite_related_tasks()`: write derived list to PLAN.md frontmatter (sorted, deduped)
- [x] Default-omit: remove `related_tasks` from PLAN.md when no tasks reference it
- [x] Skip `_archive/` requests
- [x] Malformed values surface as `promoted_to_warnings`, not aborts
- [x] CLI prints "→ propagated related_tasks to N request(s)" and warning lines
- [x] SQLite schema migration handled in Group 5 (v1→v2 ALTER TABLE)
- [x] Round-trip verified: promote → reindex (sets field) → revert → reindex (removes field)

## Group 9 — Code: TUI

- [ ] `tui/focus.py`: render `[kind]` chip in task rows when frontmatter has `kind`
- [ ] `tui/board.py`: same chip rendering in board columns
- [ ] Render promotion arrow on tasks in `done/` with `promoted_to`: `→ <chip>:<id>`
- [ ] Use `[providers.chips]` for chip rendering; fall back to full provider name
- [ ] Truncate target chip if column-width exceeded; keep provider visible

## Group 10 — Skill updates

- [ ] `skills/octopus/SKILL.md`: add "Task promotion" section explaining when + how to promote
- [ ] `skills/octopus/SKILL.md`: update "Presenting tasks in chat" — kind chip in compact list + promotion arrow
- [ ] `skills/octopus/SKILL.md`: add `kind` chip rendering rules
- [ ] `skills/octopus/SKILL.md`: ensure F1 naming section is consistent with new request linkage workflow

## Group 11 — Tests

- [ ] `tests/commands/test_promote.py`: happy path single-task, existing target
- [ ] `tests/commands/test_promote.py`: happy path single-task, scaffolds new request (smart-resolve)
- [ ] `tests/commands/test_promote.py`: shorthand input forms (`--to spec`, `--to <id>`, `--to <provider>`)
- [ ] `tests/commands/test_promote.py`: chip-alias input accepted, canonical written
- [ ] `tests/commands/test_promote.py`: auto-numbering on/off behavior
- [ ] `tests/commands/test_promote.py`: multi-task atomic, all-or-nothing pre-flight
- [ ] `tests/commands/test_promote.py`: multi-task with provider-only shorthand → exit 3
- [ ] `tests/commands/test_promote.py`: `--force` repoints already-promoted (single + multi)
- [ ] `tests/commands/test_promote.py`: `--revert` soft-clears
- [ ] `tests/commands/test_promote.py`: exit codes 2/3/4
- [ ] `tests/commands/test_list.py`: `--kind` filter (single + multi via comma)
- [ ] `tests/commands/test_list.py`: `--promoted` scope override
- [ ] `tests/commands/test_list.py`: `--spec <slug>` filter
- [ ] `tests/test_reindex.py`: `related_tasks` regenerates from task scan
- [ ] `tests/test_reindex.py`: malformed `promoted_to` warns but doesn't abort

## Group 12 — Data migration

- [ ] Assign `kind` to the 11 existing live tasks (best effort; optional field, can be deferred per-task)
- [ ] Verify F1 naming compliance across all task files; rename outliers via `octopus rename`
- [ ] Sanity-run `octopus reindex` after migration

## Group 13 — Ship

- [ ] Update CHANGELOG.md with 0.3.0 (minor — new verb, new flags, new schema fields)
- [ ] Bump `cli/pyproject.toml` version to 0.3.0
- [ ] Update README.md if any user-facing surface changed (verb list, config, kind chip)
- [ ] Run `/update-docs` workflow
- [ ] Tag v0.3.0, push

---

## Notes

- This is a large request — 13 groups. Realistic to split into multiple sub-shipments:
  - **v0.3.0-alpha:** Groups 1–4 (decisions + schema docs + config) → contract is published, no code yet
  - **v0.3.0-beta:** Groups 5–8 (actions layer + CLI verb + reindex) → verb works on disk
  - **v0.3.0:** Groups 9–13 (TUI + skill + tests + migration + ship)
- Or land it all in one v0.3.0 with internal milestones. User's call when starting Group 5.
- `D-??` numbers will be assigned at write-time based on the current last-locked D-number in DECISIONS.md.

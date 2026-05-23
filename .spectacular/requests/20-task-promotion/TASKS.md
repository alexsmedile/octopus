---
request: 20-task-promotion
status: done
updated: 2026-05-24
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

## Group 9 — Code: TUI ✅

- [x] `tui/focus.py` `_row_chips`: render `[kind]` chip (cyan #89DCEB) when kind present
- [x] `_provider_chip()` helper: format `<provider>:<id>` → `<chip>:<id>` via [providers.chips]
- [x] Promotion arrow `→ chip:id` rendered as right-most chip (dim grey)
- [x] FocusScreen + BoardScreen load `[providers.chips]` once in `__init__`, pass to `_TaskListItem`
- [x] `_TaskListItem` accepts `provider_chips` kwarg; same renderer used in both screens
- [x] Falls back to full provider name when no chip alias is configured
- [x] Text overflow=ellipsis already handles truncation (existing behavior)
- [x] Smoke-rendered: `[bug] → spec:20-task-promotion`, `⚐ → git:foo/bar#42`

## Group 10 — Skill updates ✅

- [x] `SKILL.md` v0.3.0 — version bump for substantive additions
- [x] Verb index: added "Promotion" group and `list --kind/--promoted/--spec`
- [x] New "Task `kind`" section (D46 enum, rules, soft validation)
- [x] New "Task promotion" section (when to use / not, --to forms, semantics, idempotency, multi-task, reverse flow)
- [x] "Presenting tasks in chat" glyphs updated with `[kind]` and `→ chip:id`
- [x] Chip + arrow rendering rules added
- [x] Layout C example updated with kind chips
- [x] Promoted-list sub-layout added
- [x] F1 naming section reconciled — kind metadata moved out of #19 reference into the live `kind` section

## Group 11 — Tests ✅ (271 passing, was 225 — +46)

- [x] `tests/test_promote.py` — 34 tests covering all of below:
  - [x] parse_target: explicit `provider:id`, chip alias, bare id, provider shorthand (single/multi), `:new`, unknown provider, empty id
  - [x] find_spectacular_request: live, archived, missing
  - [x] next_request_number: empty, gap-filling
  - [x] apply_auto_number: already-numbered, prepended, off-via-config
  - [x] scaffold_request: creates PLAN, refuses overwrite
  - [x] promote_task happy path: scaffolds, links existing, multi-task shared target
  - [x] promote_task: shorthand uses task slug, multi+shorthand rejected, already-promoted rejected
  - [x] `--force` repoints (body NOT re-rewritten — stub preserved)
  - [x] `--revert` moves to backlog and clears
  - [x] `--revert` idempotent on unpromoted task
  - [x] atomic pre-flight: aborts whole batch if any task fails
  - [x] `:new` requires `--slug`; explicit slug accepted
  - [x] derive_related_tasks: groups by spec slug, skips non-spectacular, skips malformed, sorted + deduped
- [x] `tests/test_db_queries.py` — 6 new tests:
  - [x] single-kind, multi-kind filter
  - [x] `--promoted` scope
  - [x] `--spec <slug>` scope, unknown spec → empty
  - [x] cross-activity (`tasks_all`) with kind filter
- [x] `tests/test_db_reindex.py` — 6 new tests:
  - [x] writes related_tasks to PLAN
  - [x] removes related_tasks when no promoted (default-omission)
  - [x] idempotent (second reindex doesn't rewrite if state unchanged)
  - [x] warns on malformed promoted_to without aborting
  - [x] skips archived requests
  - [x] non-spectacular providers are no-op

## Group 12 — Data migration ✅

- [x] `feat`: wire-obsidian-symlink-bridge, build-apple-reminders-pull-adapter, add-activity-relative-scoped-view-filter
- [x] `bug`: fix-blank-line-between-memory-sections, fix-duplicate-timestamps-in-rapid-session-log-entries
- [x] `spec`: define-forget-verb-semantics
- [x] `polish`: polish-error-messages-and-rich-output, clarify-n-sessions-output-in-reindex
- [x] `test`: verify-run-state-in-a-real-automation
- [x] `chore`: drop-request-nn-suffix-from-task-titles → **finished** (work was already complete from v0.2.7)
- [x] **dropped**: link-tasks-to-requests-via-tags (superseded by #20's `promoted_to` field)
- [x] F1 naming verified compliant on all live tasks (no renames needed)
- [x] Sanity-run `octopus reindex` — 2 activities (live + smoke fixture), 19 tasks

## Group 13 — Ship ✅

- [x] CHANGELOG.md `[0.3.0] — 2026-05-24` entry written (Added / Changed / Removed sections)
- [x] `cli/pyproject.toml` version 0.2.7 → 0.3.0
- [x] README.md status line + install command updated to 0.3.0 (mentions 271 tests)
- [x] Request PLAN status: active → done
- [x] TASKS.md status: active → done
- [x] Tag v0.3.0 (next step)

---

## Notes

- This is a large request — 13 groups. Realistic to split into multiple sub-shipments:
  - **v0.3.0-alpha:** Groups 1–4 (decisions + schema docs + config) → contract is published, no code yet
  - **v0.3.0-beta:** Groups 5–8 (actions layer + CLI verb + reindex) → verb works on disk
  - **v0.3.0:** Groups 9–13 (TUI + skill + tests + migration + ship)
- Or land it all in one v0.3.0 with internal milestones. User's call when starting Group 5.
- `D-??` numbers will be assigned at write-time based on the current last-locked D-number in DECISIONS.md.

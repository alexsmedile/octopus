---
status: done
priority: high
owner: alex
updated: 2026-05-24
summary: "Capture/edit polish: richer capture flags, atomic tag mutations, slug rename with cascading refs, `move`/`mv` verb, `set` becomes frontmatter-only, `refs find` helper."
related:
  - 22-todo-md-format
  - 25-kind-clarification
gates: []
---

# Capture + edit polish

## Goal

After dogfooding the first wave of Octopus, the add/edit surface has clear friction:
- `capture` is metadata-thin (no `--due`, `--tag`, `--kind`, etc.)
- `set --bucket` moves the file in folder mode — overloaded with `mv`/pipeline-verb behavior
- No way to rename a slug; the spec mentions it but it's not implemented
- `--tags` is a destructive replace; no incremental tag editing
- `--priority normal` is rejected even though it's logically a clear
- `capture --now` auto-pins, conflating bucket and attention axes
- New tasks get a hardcoded `## References` body for no good reason

This request closes all of those.

## Why

The friction shows up every time you triage a TODO.md pull, copy something from Reminders, or want to retro-tag a finished task. Five seconds of friction at every capture compounds. The fixes are small and individually obvious; bundling them avoids three sub-1.0 releases for trivial UX work.

## Scope

### Phase 1 — `capture` flags expansion

New flags on `octopus capture <title>`:

```
--due <YYYY-MM-DD>             sets `due`
--scheduled <YYYY-MM-DD>       sets `scheduled`
--start-date <YYYY-MM-DD>      sets `start_date` (NOT same as `start` verb)
--end-date <YYYY-MM-DD>        sets `end_date` (NOT same as `end`/`finish` verb)
--actor <human|ai|automation>  sets `actor` (or omits for human)
--energy <low|mid|high>        sets `energy`
--owner <name>                 sets `owner`
--stage <text>                 sets `stage`
--tag / --tags / --add-tag / --add-tags / --remove-tag / --remove-tags / --clear-tags
                               see "tag flag matrix" below
```

Flags that **don't** ship in #24 (deferred):
- `--body` — see #26 (body input from inline/file/stdin)
- `--kind` — see #25 (kind clarification)
- `--external-refs` — adapter responsibility, not capture's

### Phase 2 — Body defaults

Drop the hardcoded `\n## References\n` body. New captures get an **empty body**. The `## References` heading reappears only when needed (a task body has a body — leave that to the user or future `--body` flag).

### Phase 3 — Drop auto-pin on `capture --now`

`capture --now` currently sets `pinned: true`. **Drop that.** Pin stays orthogonal to bucket per AXIS-MODEL (D43). If the user wants a pinned-now task, they `capture X --now` then `pin X`.

### Phase 4 — Tag flag matrix

All edit verbs (`capture`, `set`) accept the same matrix:

| Flag | Behavior | Input forms |
|---|---|---|
| `--tag <X>` / `--tags <X[,Y…]>` | **Replace** the tag list | `--tag X` · `--tags X,Y` · `--tags "X Y"` · repeatable |
| `--add-tag <X>` / `--add-tags <X[,Y…]>` | **Append** (dedup) | same input forms |
| `--remove-tag <X>` / `--remove-tags <X[,Y…]>` | **Remove** (no-op if absent) | same input forms |
| `--clear-tags` | **Empty** the tag list | bare flag |

**Aliases:** singular and plural are the same parser — `--tag` ≡ `--tags`. Same for the add/remove pair.

**Storage:** stored with `#` prefix in frontmatter: `tags: ["#bug", "#tui/marquee"]` — Obsidian-compatible. Nested via `/`.

**Input normalization:** flag values are accepted with OR without leading `#`. `--tag bug`, `--tag "#bug"`, `--tag "#tui/marquee"` are all valid; normalizer adds `#` if missing.

**Order on multi-flag invocations** (when `--tag/--tags` is NOT used): `--clear-tags` first, then `--remove-tags`, then `--add-tags`. So `--clear-tags --add-tags X,Y` = `["X", "Y"]`; `--remove-tags X --add-tags Y` removes X then adds Y.

**Mutual exclusion:** `--tag/--tags` (replace) is mutually exclusive with **any** of `--add-tag/--remove-tag/--clear-tags`. Mixing them errors (`exit 1`) with a clear message — replace + incremental in the same invocation is almost always a typo. Forces clarity.

**Filter behavior** (already shipped in `list --tag`, clarifying): `--tag parent` matches `#parent` AND any `#parent/*`. Exact-only match deferred (future `--exact` modifier).

### Phase 5 — `set --priority normal` (and similar explicit-defaults)

Currently rejects `--priority normal` because `normal` isn't in the enum. **Change behavior:** treat any explicit-default value (`normal` for priority, `human` for actor, empty string for everything) as "clear the field." No rejection.

The same rule applies to:
- `--actor human` → clear (omits the field on write)
- `--priority normal` → clear
- `--energy normal` (we should add normal as a recognized clear-value)
- empty string → clear, on any field

### Phase 6 — `set --bucket` becomes frontmatter-only

Current behavior: `set --bucket next` MOVES the file in folder mode. New behavior: **edits frontmatter only**.

If the resulting state has `bucket` ≠ parent-directory name (folder mode), emit a **soft warning** with the discrepancy and a hint:

```
⚠ task at tasks/backlog/foo.md now has bucket: next.
  Run `octopus mv foo next` to move the file to match.
```

In field mode (flat storage), no warning fires — there's no folder concept.

### Phase 7 — `octopus move <slug> <bucket>` (with `mv` alias)

New verb. Pure file-move + frontmatter update.

```
octopus move <slug> <bucket>
octopus mv <slug> <bucket>     # alias
```

- Validates `<bucket>` is in the enum.
- In folder mode: moves the file to `tasks/<bucket>/<slug>.md`.
- In field mode: updates frontmatter only (no file move possible).
- Updates frontmatter `bucket` field to match.
- Updates the SQLite index.
- **No date stamps, no lifecycle side effects.** That's what `start`/`finish`/`drop` are for.
- Validates the resulting state (e.g. moving to `done` without `end_date` is rejected — you should use `finish` for that).

Backfill use case: `octopus mv old-task done` works if you also manually set `--end-date` via `set` first. Cleaner: just use `finish`.

### Phase 8 — `set --slug <new>` with cascading refs

New flag. Renames the task slug, with full auto-fix for Octopus-managed references.

```
octopus set <old-slug> --slug <new-slug>           # prompts to confirm
octopus set <old-slug> --slug <new-slug> -y        # skip prompt
```

**Auto-fix (always applies):**
1. Filesystem: rename `tasks/<bucket>/<old>.md` → `tasks/<bucket>/<new>.md`.
2. SQLite index: update `tasks.slug` + `tasks.id` (the id is `<activity>/<slug>`).
3. Other tasks' frontmatter: rewrite `waiting_for: <old>` → `<new>` in any task that references it.
4. Spectacular requests: rewrite `related_tasks: [..., <old>, ...]` → `[..., <new>, ...]` in any PLAN.md.
5. Spectacular requests: rewrite `promoted_from: <old>` → `<new>` in PLAN.md frontmatter.
6. TODO.md files: rewrite `→ octopus:<old>` → `→ octopus:<new>` in any TODO.md the adapter touches.

**Soft warning (name files, don't auto-fix):**
- Session bodies (`.octopus/sessions/*.md`) mentioning `<old-slug>` in prose.
- Memory body (`.octopus/memory.md`) mentioning `<old-slug>`.
- Handoff bodies (`.octopus/handoffs/*.md`) mentioning `<old-slug>`.

For these, print the line + file as a hint. User decides whether to update them.

**Inline grep for unmanaged tools** (Obsidian, IDE, etc.) is out of scope — print a one-line reminder ("the slug may also appear in external tools; check Obsidian backlinks, IDE bookmarks, etc.").

**Prompt format:**

```
$ octopus set wire-obsidian-bridge --slug obsidian-symlink-bridge
This will rename:
  tasks/backlog/wire-obsidian-bridge.md → tasks/backlog/obsidian-symlink-bridge.md

Octopus-managed refs to update automatically:
  - waiting_for in 2 tasks (build-symlink-cli, ship-obsidian-bridge)
  - related_tasks in 1 spectacular PLAN.md (07-adapter-obsidian)
  - → octopus:wire-obsidian-bridge in 1 TODO.md

Soft warnings (user-managed, may contain references):
  - sessions/2026-05-23-debug.md (3 mentions)
  - memory.md (1 mention)
  - handoffs/2026-05-22-pivot.md (2 mentions)

External tools (not touched): Obsidian backlinks, IDE bookmarks, git history.
  Run `octopus refs find wire-obsidian-bridge` to locate residual references later.

Proceed? [y/N]
```

`-y` skips the prompt entirely.

### Phase 9 — `octopus refs find <slug>` helper

New verb. Greps every Octopus-managed text file in the activity (and across activities with `--all`) for the given slug. Prints `file:line` with the matched line, ranked by file type:

```
$ octopus refs find wire-obsidian-bridge
tasks/now/build-symlink-cli.md:8        waiting_for: wire-obsidian-bridge
sessions/2026-05-23-debug.md:42        ### still blocked on wire-obsidian-bridge?
memory.md:127                          Decided: wire-obsidian-bridge waits for #07
handoffs/2026-05-22-pivot.md:8         related: wire-obsidian-bridge
.spectacular/requests/07-adapter-obsidian/PLAN.md:14    related_tasks: [wire-obsidian-bridge]
TODO.md:32                             - [x] wire bridge → octopus:wire-obsidian-bridge
```

Scope: this activity by default. `--all` for cross-activity. Read-only — no edits.

Used by the slug-rename warning, but also useful standalone for "where is this slug mentioned?"

## Approach

1. **Lock D-entries.** New decisions: tag flag matrix, mutual exclusion rule, slug-rename cascade scope, `move` vs `set --bucket` boundary, drop auto-pin on capture.
2. **Tag parser module** — pure functions for normalizing `#`, splitting comma/space/repeated values, dedup, error on mutex.
3. **`capture` flags** — add the new ones, share the tag parser with `set`.
4. **`set` cleanup** — apply explicit-default-clears, drop file-move on `--bucket`, add the soft warning, integrate tag parser.
5. **`octopus move` / `mv`** — new verb.
6. **`set --slug`** — full cascading rewrite. Touches multiple file types. Most complex piece.
7. **`octopus refs find`** — read-only grep verb.
8. **Tests** — every flag form, mutual exclusion, slug rename cascade, mv vs set --bucket separation, refs find output.
9. **Docs** — `SCHEMA-TASK.md` (tag format), `CLI-VERBS.md` (new verbs + flag matrix), skill mirror.

## Out of scope

- `--body` flag on capture — deferred to #26.
- `--kind` flag on capture — deferred to #25.
- Tag exact-match (`--tag X --exact`) — future.
- `octopus refs find` cross-tool (Obsidian, IDE) — manual user task.
- Auto-fix for session/memory/handoff body prose — too risky for v1.

## Deliverables

- [ ] D-entries D76–D8? locking all decisions.
- [ ] `tag_parser.py` (or extension to `set_/capture` helpers) — input normalization + mutex check.
- [ ] `capture` accepts `--due`, `--scheduled`, `--start-date`, `--end-date`, `--actor`, `--energy`, `--owner`, `--stage`, and the full tag flag matrix.
- [ ] `capture` body defaults to empty; no auto-pin on `--now`.
- [ ] `set` accepts tag flag matrix; clears on explicit-default values; warns instead of moving on `--bucket` mismatch.
- [ ] `octopus move <slug> <bucket>` + `mv` alias.
- [ ] `octopus set <slug> --slug <new> [-y]` with full cascading refs.
- [ ] `octopus refs find <slug> [--all]`.
- [ ] Spec docs: `SCHEMA-TASK.md` tag-with-#, `CLI-VERBS.md` new verbs.
- [ ] Skill mirror.
- [ ] Tests (estimate ~35–50 new).
- [ ] CHANGELOG [0.6.0] entry (minor — new verbs + behavior changes).
- [ ] Version bump 0.5.0 → 0.6.0.

## Behavioral compatibility risks

- **Tag storage change.** Existing tasks may have `tags: ["bug"]` (no `#`). The reader should accept both forms; the writer always emits with `#`. On any task write, existing tag values get normalized to include `#`. This is a quiet data migration; flag in CHANGELOG.
- **`set --bucket` behavior change.** Anyone scripting `set --bucket` and expecting the file to move will break. Mitigation: clear migration note in CHANGELOG + the soft warning.
- **`capture --now` no longer pins.** Anyone relying on the implicit pin breaks. Mitigation: CHANGELOG note + suggest `capture X --now && octopus pin X` if needed.

## Open for later grilling

- Whether `octopus refs find` should also rewrite (would become `octopus refs rewrite`). Probably too dangerous for v1 — keep read-only.
- Whether `set --slug` should support `--dry-run` to preview the cascade without committing. Probably yes; cheap to add.

---
status: done
priority: high
owner: alex
updated: 2026-05-23
summary: "Define the seam between Octopus (task/idea capture) and Spectacular (build protocol). One-way promotion via `octopus promote --to-spec`. Folds in #19 (naming + kinds) since both touch SCHEMA-TASK.md."
related:
  - 05-tui
  - 06-adapter-framework
  - 19-task-naming-and-kinds
supersedes:
  - 19-task-naming-and-kinds
gates: []
---

# Task promotion + naming/kinds schema

## Goal

Define a clean, **one-way** promotion path from Octopus tasks to Spectacular requests, and ship the schema additions that make it work — alongside the F1 naming formula and `kind` enum that were already in flight in #19.

Two systems, distinct domains, single seam.

## Why

### Two systems, two audiences

- **Octopus** is the human's task surface — system-wide capture, activities, sessions, logs. The "ideas + tracking" layer. Mature task manager; AI reads it for context but doesn't usually act on task lines.
- **Spectacular** is the AI's build-protocol surface — PLAN.md, specs, decisions, internal TASKS.md. Owns coding/build workflows. Doesn't need or want a generic task manager.

Until now, the seam has been *implicit*: tasks carrying `(request NN)` suffixes in their titles, no machine-readable link, no verb to move a task into the build pipeline. The audit on 2026-05-23 flagged this directly — 11 active tasks across four naming styles, with linkage hidden in title text.

### Why one-way

A task → request transition is a **rewrite, not a copy**. The task gets summarized; the request becomes the full PLAN with brainstorm + specs. Reverse promotion (request → task) doesn't happen — if a request ships 95% with stragglers, those become *new* Octopus tasks linking back. Not symmetric.

### Why fold #19

`kind` and `promoted_to` both land in `SCHEMA-TASK.md`. One schema migration is cleaner than two; agents reindex once, mirror once, lock once in DECISIONS.

---

## Model

```
┌──────────────────────────────── OCTOPUS ─────────────────────────────────┐
│  backlog/                                                                │
│  ▢ wire obsidian symlink bridge   ──┐                                    │
│                                     │ octopus promote                    │
│                                     │   --to-spec 20-task-promotion      │
│                                     ▼                                    │
│  done/                                                                   │
│  ✓ wire obsidian symlink bridge                                          │
│      promoted_to: 20-task-promotion                                      │
│      end_date: 2026-05-23                                                │
│      body: short summary + pointer to PLAN.md                            │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ scaffold + link
                               ▼
┌──────────────────────── SPECTACULAR ─────────────────────────────────────┐
│  .spectacular/requests/20-task-promotion/PLAN.md                         │
│  ---                                                                     │
│  promoted_from: wire-obsidian-symlink-bridge                             │
│  related_tasks: [wire-obsidian-symlink-bridge]   ← derived on reindex   │
│  ---                                                                     │
│                                                                          │
│  PLAN.md is now source of truth. Octopus stays out.                      │
└──────────────────────────────────────────────────────────────────────────┘
```

### Key properties

- **One-way.** Tasks promote into requests, never the reverse.
- **No new bucket.** Promotion = `done` from Octopus's perspective. Presence of `promoted_to` is the marker.
- **Task-side canonical.** The link lives in task frontmatter. `reindex` derives `related_tasks` on the request side.
- **Body rewrite.** On promotion, the task body becomes a 3–5 line stub pointing at the PLAN. Avoids drift.
- **`handoff` stays distinct.** `.octopus/handoffs/` and the handoff schema keep their original meaning (directed transfer with received → resolved lifecycle). Promotion is *not* a handoff.

---

## Scope

### Phase 1 — Naming formula (already locked in v0.2.7)

F1 `verb result` imperative. No prefixes, no `(request NN)` suffixes. Already shipped in:
- `skills/octopus/SKILL.md` — "Task naming — F1 imperative" section
- 11 existing tasks renamed
- D-entry pending in this request

This request **locks** what's already in practice — no code change, just a DECISIONS entry.

### Phase 2 — `kind` enum (carry-over from #19)

Add `kind` as an **optional** first-class frontmatter field on tasks.

#### Final enum

| `kind` | When to use |
|---|---|
| `feat` | new capability shipped to users |
| `bug` | something is broken |
| `spec` | a decision needs locking before code |
| `polish` | UX/output quality, not behavior |
| `test` | verification work |
| `chore` | maintenance, cleanup, deps, refactor, docs |

6 values. `chore` absorbs `doc` (small enough not to warrant its own). `polish` stays distinct from `feat` (urgency signal differs).

#### Rules

- Optional. Tasks without `kind` render with no chip — backward compatible.
- One value per task.
- Mutable. `octopus set kind=feat` works.
- Persisted in the index for `octopus list --kind bug`.

### Phase 3 — Promotion linkage (new)

#### Task frontmatter additions

```yaml
# ── integrations & provenance ────────────────────────────────────────
promoted_to:                  # optional, string — `<provider>:<identifier>` format
                              # presence = task was promoted; absence = normal task
                              # v1 providers: spectacular
                              # format scales to: github, linear, etc. (future)
```

Position: inside the existing "integrations & provenance" group, adjacent to `external_refs` / `imported_from`.

Default-omission: a non-promoted task never carries this field.

**Value format: `<provider>:<identifier>`.** Always namespaced, always stored canonical (long form), even when CLI input used a default or alias.

Examples:
- `spectacular:20-task-promotion`
- `github:alexsmedile/octopus#42` *(future)*
- `linear:ENG-123` *(future)*

Why slug, not path: requests can be archived (`_archive/`); slugs are stable, paths are not.

#### Provider config + chip aliasing

```toml
# ~/.config/octopus/config.toml      (system-wide)
#   OR
# .octopus/config.toml                (activity override)

[providers]
default = "spectacular"               # omitting prefix on CLI input resolves to this

[providers.chips]
spectacular = "spec"                  # short label for TUI + chat display
github      = "git"
linear      = "lin"
```

**Defaults shipped v1:**

```toml
[providers]
default = "spectacular"

[providers.chips]
spectacular = "spec"
```

**Rules:**
- `default` and chip keys must be registered providers (v1: only `spectacular`).
- Chip values: ASCII, ≤6 chars. Reject otherwise.
- Chip values do not need to be unique, but the CLI warns if two providers alias to the same chip.
- With no chip alias configured, fall back to the full provider name — never silently drop the namespace.

#### Request frontmatter additions

```yaml
promoted_from:                # optional, string — Octopus task slug (no prefix, no path)
                              # Octopus is the only origin; no namespace needed
                              # omitted entirely if request was spec-native
related_tasks:                # optional, list — derived by reindex from task scan
                              # READ-ONLY; do not hand-edit
```

Asymmetry note: `promoted_to` is namespaced (multiple possible targets); `promoted_from` is bare (Spectacular only knows Octopus as an origin).

#### CLI verb

```
octopus promote <task-slug> [<task-slug>...] --to <provider>:<identifier>
octopus promote <task-slug> --to <provider>                    # shorthand: use task slug (single-task only)
octopus promote <task-slug> [<task-slug>...] --to <identifier> # shorthand: use providers.default
octopus promote <task-slug> --to <provider>:new --slug <id>    # explicit "create new"

# Idempotency:
octopus promote <task-slug> --to ... --force                   # repoint already-promoted task
octopus promote <task-slug> --revert                           # clear promotion (soft)

# Examples:
octopus promote wire-obsidian-symlink-bridge --to spectacular:20-task-promotion
octopus promote wire-obsidian-symlink-bridge --to 20-task-promotion        # default provider
octopus promote wire-obsidian-symlink-bridge --to spec:20-task-promotion   # chip alias accepted
octopus promote wire-obsidian-symlink-bridge --to spec                     # use task slug, smart-resolve
octopus promote wire-obsidian-symlink-bridge --to spectacular              # same as above, full provider name
octopus promote build-watcher-daemon --to spectacular:new --slug 21-watcher-daemon
```

**Input parse rules:**

| Input form | Resolution |
|---|---|
| `--to <provider>:<id>` | use provider + identifier as given |
| `--to <chip-alias>:<id>` | resolve chip alias to canonical provider |
| `--to <id>` (no colon, default provider exists) | `<providers.default>:<id>` |
| `--to <provider>` (provider-only, no colon) | `<provider>:<task-slug>` — shorthand for "use task slug as identifier" |
| `--to <provider>:new --slug <id>` | scaffold new with explicit slug |

Storage is always canonical (`spectacular:...`), regardless of input form.

**Smart-resolve on identifier:** for any input that resolves to `spectacular:<slug>`:
- If `.spectacular/requests/<slug>/` exists → link to it.
- If not → scaffold a new request at that path.
- The user does not specify "new" vs "existing" — the filesystem decides.

The explicit `:new` form is only required when the user wants to *force* scaffolding with a different slug than would auto-resolve (rare).

**Auto-numbering** (config-driven, default on):

```toml
[providers.spectacular]
auto_number = true                    # default: true
```

When `auto_number = true` and the resolved slug has no leading number (`NN-`), prepend the next available number based on a scan of `.spectacular/requests/*/`. So `--to spec` on task `wire-obsidian-symlink-bridge` scaffolds `.spectacular/requests/21-wire-obsidian-symlink-bridge/`.

`--slug` overrides auto-numbering — the user-supplied slug is used verbatim.

**Idempotency:**

If the task already has `promoted_to:` set, `promote` rejects with exit 4 and a specific message:

```
ERROR: task is already promoted to spectacular:20-task-promotion (on 2026-05-22).
  Repoint to new target:   octopus promote <task> --to <new-target> --force
  Unlink and restore:      octopus promote <task> --revert
```

- `--force`: overwrite `promoted_to`, set new `end_date`, do **not** rewrite the body (it was already rewritten on the first promote — leave it). Reindex picks up the change and rewrites `related_tasks` on both old and new request PLAN.md files.
- `--revert`: clear `promoted_to`, clear `end_date`, **and move the task to `bucket: backlog`**. **Soft revert** — the task body stays rewritten as a promotion stub. If you want the original body back, use git. The forced bucket move is because `bucket: done` requires `end_date`; we can't keep the task in `done/` after clearing the date. The user can `octopus mv` to a different bucket from there.

`promoted_from` on the old request's PLAN.md is **historical** — not cleared on repoint. It records what originally scaffolded the request, not what currently links to it. The dynamic field is `related_tasks` (derived by reindex).

**Semantics (first promotion):**
1. Validate every named task exists; resolve current buckets.
2. Reject (exit 4) if any task already has `promoted_to` set and `--force` not given. Pre-flight check — no partial writes.
3. Parse `--to`: resolve default, aliases, shorthand → canonical `<provider>:<id>`. Reject (exit 3) if multiple tasks were given AND `--to` was the provider-only shorthand (ambiguous target).
4. For `spectacular:` targets:
   - Smart-resolve: existing dir → link; absent → scaffold (apply `auto_number` if enabled).
   - On scaffold: create `.spectacular/requests/<slug>/PLAN.md` from template. `promoted_from` records the *first* listed task; full list lives in `related_tasks` (derived on reindex).
5. For each task:
   - Set `promoted_to: <canonical>`.
   - Set `end_date: <today>`.
   - Move file → `tasks/done/`.
   - Rewrite body to promotion stub template.
6. Print summary line for the batch (count + target path), plus one line per promoted task.

**Multi-task semantics:**

| Tasks | `--to spec` (shorthand, provider only) | `--to spec:<slug>` (explicit) |
|---|---|---|
| 1 | OK — uses task slug as request slug | OK |
| 2+ | ERROR (exit 3) — ambiguous target, specify a slug | OK — all tasks fold into one request |

- All tasks in a batch share the same target. No per-task target supported.
- Atomic: pre-flight validation runs across all tasks before any write. Any failure (not found, already promoted without `--force`) aborts the whole batch.
- `--force` is global: applies to every listed task uniformly. Repoints all that were already promoted, normal-promotes the rest.
- `--revert` accepts multiple tasks: `octopus promote A B C --revert` reverts all listed tasks.

**Exit codes:**
- `0` — success
- `2` — task not found
- `3` — `--to` target invalid (unknown provider, malformed identifier, missing `--slug` when `:new` is explicit)
- `4` — task already promoted (use `--force` to repoint or `--revert` to unlink)

#### Promotion stub template

Hard-coded for v1 — no config surface. The task body is **replaced entirely** with:

```markdown
# <original title>

Promoted to **[<canonical-target>](../../.spectacular/requests/<request-slug>/PLAN.md)** on <date>.

The request PLAN.md is the source of truth from here on.
```

Three lines. Pure pointer. No summary line (would drift against the PLAN). The original body is preserved in git history; if needed, restore via `git diff`.

Future: if customization demand emerges, add an override path (`.octopus/templates/promote-stub.md`) with no schema migration — the built-in stays as the fallback. Not v1.

The relative path math: `tasks/done/<slug>.md` → `.spectacular/requests/<slug>/PLAN.md` is `../../.spectacular/requests/<slug>/PLAN.md` (assuming activity is the repo root).

#### Reindex behavior

`octopus reindex` scans all task files and:
- Parses `promoted_to: <provider>:<id>`; **only `spectacular:` entries** are routed into request `related_tasks:` regeneration. Other providers are no-op for now (until adapter logic ships per provider).
- Collects every `spectacular:<slug>` into a map `slug → [task-slugs]`.
- For each request `slug`, rewrites `related_tasks:` in its PLAN.md frontmatter to that list (sorted, deduped).
- If no tasks reference a request, `related_tasks:` is removed (default-omission).
- Malformed `promoted_to` values (no colon, unknown provider) emit a warning but do not abort reindex.

This makes the request side a read-only mirror — drift is impossible.

### Phase 4 — Filters + display

#### CLI

```
octopus list --kind <enum>           # filter by kind (active buckets only by default)
octopus list --kind bug,polish       # multi-kind
octopus list --all --kind bug        # include done + dropped + promoted in scope
octopus list --promoted              # only promoted tasks (presence of promoted_to)
octopus list --promoted --kind bug   # historical-analytics view
octopus list --spec <slug>           # tasks linked to a specific request (any bucket)
```

**Scope rules:**

| Flag | Buckets included |
|---|---|
| (default) | `backlog`, `next`, `now` |
| `--all` | all buckets including `done`, `dropped` (and therefore promoted tasks) |
| `--promoted` | only tasks with `promoted_to:` set (overrides default scope, since promoted tasks live in `done/`) |
| `--spec <slug>` | only tasks with `promoted_to: spectacular:<slug>` (overrides default scope) |

Classification fields (`kind`, `tags`, `priority`, `energy`) **survive promotion** — they're historical facts about the original task. They are *indexed* and queryable, but **hidden by default** because promoted tasks land in `done/`, which the default scope already excludes. To surface them, use `--all`, `--promoted`, or `--spec`.

#### TUI

Task rows render the kind chip when present:

```
▸ ▢ [feat] pull apple reminders into backlog
  ▢ [bug]  drop "(request NN)" suffix from task titles
  ⚐ [spec] define forget verb semantics
```

Promoted tasks (in `done/` with `promoted_to`) get a provider-chip glyph using `[providers.chips]`:

```
✓ wire obsidian symlink bridge   → spec:20-task-promotion
✓ pull apple reminders adapter   → git:alexsmedile/octopus#42
✓ migrate auth flow              → lin:ENG-123
```

With no chip alias configured, fall back to the full provider name.

#### Skill (chat layouts)

Update `skills/octopus/SKILL.md` "Presenting tasks in chat" section:
- Compact list shows `[kind]` chip after the bucket glyph.
- Focus/Board layouts render chip inside the task line, truncating title further if needed.
- Promoted tasks in `done/` get a `→ <slug>` suffix when shown.

---

## Approach

1. **D-entries first.** Lock the model in `DECISIONS.md`:
   - D-? F1 naming formula (already in practice)
   - D-? `kind` enum (final 6)
   - D-? Task promotion is one-way, marker is `promoted_to`
   - D-? No new bucket; promoted tasks live in `done/`
   - D-? `handoff` stays distinct from `promoted` (no schema overlap)
   - D-? Reindex makes `related_tasks` read-only/derived
2. **Schema docs.** Update:
   - `.spectacular/specs/SCHEMA-TASK.md` — add `kind`, `promoted_to`
   - `.spectacular/specs/CLI-VERBS.md` — document `promote`, `list --kind`, `list --promoted`, `list --spec`
   - `.spectacular/specs/CRITICAL-DEPENDENCIES.md` — validation rules
   - Mirror **all** of the above to `skills/octopus/references/` (skill-sync rule)
3. **Code changes** (`cli/src/octopus/`):
   - `commands/promote.py` — new verb
   - `commands/list.py` — `--kind`, `--promoted`, `--spec` flags
   - `actions.py` — `promote_task()` mutation entry point
   - `index.py` — collect `promoted_to`, regenerate `related_tasks` on reindex
   - `tui/focus.py` + `tui/board.py` — render kind chip + promotion arrow
4. **Skill updates** (`skills/octopus/SKILL.md`):
   - "Presenting tasks in chat" — kind chip + promotion arrow rules
   - Add "Promotion" section explaining when/how to use `octopus promote`
5. **Migrate existing tasks.** Assign `kind` to the 11 active tasks. The `(request NN)` suffix sweep already happened; this just adds the field.
6. **Tests.** `tests/commands/test_promote.py`, plus reindex coverage for `related_tasks` regen.

---

## Out of scope (this request)

- Multi-kind tasks (a task is one kind).
- Auto-inferring `kind` from the title verb. Brittle, defer.
- `area` as a first-class enum. Stays in `tags` (free-form), first tag = primary area by convention.
- Reverse promotion (request → task). Not modeled; stragglers from a finished request are *new* tasks.
- Two-way sync between Octopus and Spectacular beyond reindex.
- A `kind` validation that rejects unknown values — soft enum v1, allow free strings, log a warning.
- Title length enforcement in the CLI. F1 is convention, not validated.

---

## Deliverables

- [ ] `SCHEMA-TASK.md` updated with `kind` + `promoted_to`
- [ ] `CLI-VERBS.md` updated with `promote`, `list --kind/--promoted/--spec`
- [ ] `CRITICAL-DEPENDENCIES.md` updated with new validation rules
- [ ] Mirrored to `skills/octopus/references/schemas/task.md`, `cli-verbs.md`, `critical-dependencies.md`
- [ ] `octopus promote` verb shipped with tests
- [ ] `octopus list --kind/--promoted/--spec` shipped with tests
- [ ] Reindex regenerates `related_tasks` on request PLAN.md frontmatter
- [ ] TUI renders kind chip + promotion arrow
- [ ] `SKILL.md` updated (chat layouts + promotion section)
- [ ] 11 existing tasks: kind assigned, F1 naming verified
- [ ] D-entries appended to `DECISIONS.md`
- [ ] #19 archived as superseded by this request

---

## Open for grilling

- ~~**`promoted_to` value format.**~~ **Resolved:** `<provider>:<identifier>` namespaced format. Slug-based (not path) so it survives archive moves.
- ~~**Idempotency on `octopus promote`.**~~ **Resolved:** Hard reject (exit 4) on already-promoted, `--force` to repoint, `--revert` for soft unlink. `promoted_from` is historical.
- ~~**Should `promote` accept multiple tasks?**~~ **Resolved:** Yes, positional args. Atomic pre-flight check. `--force` and `--revert` apply globally. Multi-task with provider-only shorthand is rejected as ambiguous.
- ~~**Promotion stub template.**~~ **Resolved:** Hard-coded v1, body replaced entirely, no summary line. Override hook deferred.
- ~~**`kind` for promoted tasks.**~~ **Resolved:** Survives. Indexed and queryable. Hidden from default filters via the normal `done/`-exclusion rule; surface via `--all`, `--promoted`, or `--spec`. `kind` is not required to promote.
- ~~**Spec-native requests.**~~ **Resolved:** Absence is the marker. No `promoted_from` field → request was born in Spectacular. Consistent with default-omission principle. Tooling distinguishes by presence/absence; no positive `origin:` enum needed.

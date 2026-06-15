# D41 — Sessions, memory, handoffs shipped (request 04)


**Sessions** — multi-open per activity; one "active" tracked in `~/.cache/octopus/active-sessions.json` (XDG-respectful). Cache wins on mismatch with frontmatter (per `SCHEMA-SESSION.md`). Lifecycle verbs: `start / log / end / switch / list / show / prune`.

- Q1 — Handoffs in SQLite index: **v1 = filesystem only.** No `handoffs` table yet. Tracked in `TODO.md` for v2.
- Q2 — Session log timestamp precision: **second** (`### YYYY-MM-DD HH:MM:SS`). Updated `SCHEMA-SESSION.md` body example.
- Q3 — Session prune window: **stale_warn at 7 days, prune at 14 days.** Both overridable via `[sessions] stale_warn_days` / `prune_days` in `~/.config/octopus/config.toml`. CLI `--days` wins over config.
- Q4 — `[e]` (end-previous) flow on `session start`: marks previous as `dropped` + auto-appends `### YYYY-... ended by session start --replace` to body.
- Q5 — Memory scaffolding: **lazy**, only the targeted section is created on first append. Canonical-order insertion is enforced via `_insert_section_in_canonical_order`.
- Q6 — `session log` with no active session: error + hint, exit 3.
- Q7 — `session show` default: active session, fall back to most-recent (ended desc, started desc) if none active.
- Q8 — `handoff new` outside an activity: error, exit non-zero. Must be inside an activity (or v2 will accept `--activity <id>`).
- Q9 — `session end --handoff` UX: prompts for title/to_actor/to_owner/summary; `--non-interactive` requires all flags.

**Memory** — schema change locked: dropped `## Log` (overlapped with session logs), added `## State` (5th canonical section). Canonical sections now: **Decisions / Open Questions / Context / Notes / State.** Default `memory append` target is `## Notes` (the catch-all). `## State` is append-only but the latest entry is treated as "current" by readers. `summary:` (frontmatter) = stable identity; `## State` = current paused state. Resolution of open questions is convention-only (`RESOLVED: ...` prefix). Two-zone parsing via `<!-- octopus-managed-below -->` marker; marker re-inserted with stderr warn if a user removes it.

Default `memory show` is a preview: `(showing latest N of M)` headers + `[K more — run \`octopus memory show --section <slug>\` for all]` footers, applied symmetrically to State, Open Questions, and Decisions.

**Handoffs** — filesystem-only in v1; verbs: `handoff new / list / show`. Lifecycle verbs (`receive`, `resolve`, `stale`) deferred to v2 — v1 covers manual frontmatter edits via `octopus set`. Symmetric backlink: `session end --handoff` writes both `session.related_handoff` and `handoff.from_session`.

**Pocock-influence refinement (post-research):** `default_body()` template now includes a `## Suggested next actions` section with machine-actionable `octopus ...` commands — handoffs are routers to existing artifacts, not duplicates. `SCHEMA-HANDOFF.md` body conventions explicitly say "Reference, don't restate" and "Make it executable." Secret-redaction is a SHOULD-warn in v1 (manual scrub); v2 may hook a redactor. Persistent in-activity storage is preserved as a deliberate contrast to ephemeral $TMPDIR handoffs.

**Cache shape locked:** `~/.cache/octopus/active-sessions.json` is `{activity_id: session_filename}`. Atomic writes via tmp + `os.replace`. Corruption → warn stderr, treat as empty map.

Dogfood: 168-test suite passing (72 baseline + 24 sessions + 38 memory + 24 handoffs + 10 cross-cutting). End-to-end smoke verified: session start/log/end, memory append/show preview, `session end --handoff` symmetric backlink, `handoff list` with arrow direction column. Closing request 04.

---

## D42 — Distribution: pipx-first, redacted diagnose, basic CI

**Date:** 2026-05-23
**Status:** Locked
**Closes:** request 11-distribution-pipx
**Bundled into:** v0.1.0 (no separate 0.2.0 — first published wheel is feature-complete)

### Locked choices

- **Distribution channel:** **pipx** as day-one install path. PyPI auto-publish deferred — manual gate until first external pipx install is confirmed clean on a fresh machine. The wheel is shipped as a GitHub release artifact via `softprops/action-gh-release@v2`.
- **Version source of truth:** `cli/pyproject.toml` only. `octopus/__init__.py` reads via `importlib.metadata.version("octopus-cli")` with a `PackageNotFoundError` fallback to `"0.0.0+unknown"`. No hardcoded version strings anywhere else.
- **Python matrix:** 3.11 / 3.12 / 3.13 in CI. 3.14 confirmed working post-install but not in CI matrix (would be flaky on actions until 3.14 is widely cached).
- **Logging:** rotating file handler at `$XDG_DATA_HOME/octopus/logs/octopus.log` (`~/.local/share/octopus/logs/` fallback). 1 MB × 5 backups. ISO 8601 second precision. `propagate=False` so logs never reach stdout. `setup_logging()` is idempotent and called once from the CLI root callback. Falls back to `NullHandler` if log dir is unwriteable — never crashes the CLI.
- **`octopus diagnose`:** collects version, spec_version, python, platform, paths, config (system path + raw + resolved), index stats (per-table row counts + db size), log tail (last 500 lines). All `$HOME` prefixes are redacted to `~/` before any payload write. Default output: `./octopus-diagnose-YYYY-MM-DD-HHMMSS.zip` in cwd. Flags: `--no-zip` (stdout only), `--out PATH` (skip prompt). Without flags, prompts before writing.
- **CI workflows:**
  - `.github/workflows/test.yml` — push to main + PRs, matrix 3.11/3.12/3.13, ruff + pytest, `working-directory: cli`, pip cache keyed on `cli/pyproject.toml`. `permissions: contents: read`.
  - `.github/workflows/release.yml` — `v*.*.*` tag trigger, `python -m build`, tag-version verification step, upload via `softprops/action-gh-release@v2`. `permissions: contents: write`. **No PyPI publish step — manual.**
- **Lint debt:** Ruff loosened to ignore `E501, B904, E402, F841, SIM108, SIM105, B008, B017, UP028, UP038` globally + per-file ignores for `tests/`. Documented inline in `cli/pyproject.toml`. Full cleanup deferred — each rule has its own reason recorded.

### Open follow-ups (non-blocking for v0.1.0 tag)

- **Clean-machine pipx test:** the dev install showed a PATH-shadowing warning because `pip install -e .` had already put `octopus` on `$PATH`. Need to verify pipx install on a fresh machine (Docker, fresh VM) before tagging v0.1.0 — and decide whether install docs should call out the shadowing risk for conda users who already `pip install`-ed.
  - **Attempt 2026-05-23 — inconclusive.** Tried Docker (`python:3.12-slim` pull hung 40+ min, no progress) and then a `/tmp` venv (system pip couldn't reach pypi.org — DNS resolution failed). Both failures environmental, not octopus-related. Sandbox removed, Docker quit, no residue. Retry from a different network.
- **PyPI publishing:** decide trigger conditions for the manual PyPI release step. Likely after one external user confirms the GitHub-release wheel installs cleanly via pipx.
- **Lint cleanup pass:** ~96 ruff errors deferred. Worth a dedicated mini-request once the surface area stabilizes.
- **Log noise audit:** currently INFO at reindex/session start-end/handoff new. Verify the file doesn't grow too fast in real use — adjust to DEBUG for chatty paths if needed.

### Test suite

183 passing (was 168 + 6 logging + 9 diagnose). Coverage now includes XDG paths, redaction guarantees, zip contents, idempotent setup, and child-logger naming.

---

## D43 — Textual TUI v1 (Focus + Board, shared actions layer)

**Date:** 2026-05-23
**Request:** #05
**Scope:** `octopus tui` ships as the daily-driver view over the SQLite index.

### Locked

- **Two modes**: Focus (three quadrants — BACKLOG / NOW / NEXT) and Board (four-column kanban — backlog → next → now → done). Switch via `1` / `2`.
- **13-key mutation keymap** identical across modes. `n` captures into the focused pane; `m` advances one pipeline step; `M` opens a bucket picker.
- **Shared `octopus.actions` mutation layer** — TUI calls it directly. CLI port deferred (CLI still goes through Typer commands).
- **Theme**: Catppuccin Mocha palette, lavender (`#CBA6F7`) as primary accent, teal footer keys. Plain unicode glyphs only — no emoji, no Nerd Font dependency.
- **Header**: tall 7-row bar with a pixel-accurate octo mascot rendered via `rich-pixels` + PIL from a 16×14 ASCII pixel grid. Title, activity, CWD (collapsed to `~/`), session label, bucket counts, state, and mode tabs all live in the header.
- **Capture does not auto-pin** — pin is a separate axis (per AXIS-MODEL §ATTENTION).
- **Single-line rows** with marquee scroll for clipped titles. Cursor (`▸`) glyph scoped to the active quadrant's selected row only.

### Deferred

- CLI verbs ported to `octopus.actions` (only TUI uses it currently).
- Mascot animation — parked as request #18.
- Snapshot tests via `pytest-textual-snapshot` (no version pin yet).

---

## D44 — TUI polish: filter, help, quit-confirm (Groups 7 + 8)

**Date:** 2026-05-23
**Request:** #05 (closing groups 7 + 8)

### Locked

- **`/`** opens a bottom modal filter bar; live title-substring narrows the visible task lists (case-insensitive). Esc clears, Enter commits the value but leaves filter applied. `r` (reindex) also clears the filter.
- **`?`** opens a help overlay with the full keymap grouped by Navigation / Modes / Mutations / View. Esc or `?` again closes.
- **`q`** confirms before exit if the activity has an open session (per `sessions/cache.get_active`). No active session → exits immediately.
- **Broken task files** — the detail overlay already catches `read_task` failures and renders an inline error card. No crash path.
- **README** gains a "Daily driver — the TUI" section with the keymap table.

### Deferred

- Slide/fade animations on the filter and help overlays (Textual 0.46 supports `tcss` transitions but not all properties; skipped to ship).
- Snapshot tests (same reason as D43).

### Test suite

**221 passing** (was 212): +5 filter/help binding & substring tests, +4 polish/quit-confirm/broken-file tests.

---

## D45 — Task naming formula: F1 imperative `verb result`

**Date:** 2026-05-23
**Request:** #20 (folds in #19, superseded)

### Locked

Every task title is **`verb result`** in lowercase, imperative voice. No prefixes (`Friction:`, `Bug:`), no parenthetical suffixes (`(request NN)`), no trailing qualifiers.

- Start with a concrete imperative verb. Common set: `build / wire / port / pull / push / migrate / refactor / fix / drop / polish / verify / define / clarify / document / lint / link / add`.
- Don't over-use `add` — pick a sharper verb when the work transforms existing pieces.
- Lowercase by default. Sentence case only for proper nouns or identifiers in backticks.
- ~50-character soft cap.
- Kind/area metadata belongs in frontmatter, not the title.

Already practiced from v0.2.7. This entry records it as a locked convention.

---

## D46 — Task `kind` enum

**Date:** 2026-05-23
**Request:** #20

### Locked

Add `kind` as an **optional** first-class frontmatter field on tasks. Enum:

| `kind` | When to use |
|---|---|
| `feat` | new capability shipped to users |
| `bug` | something is broken |
| `spec` | a decision needs locking before code |
| `polish` | UX/output quality, not behavior |
| `test` | verification work |
| `chore` | maintenance, cleanup, deps, refactor, docs |

- Six values. `chore` absorbs `doc`. `polish` stays distinct from `feat` (urgency signal differs).
- Optional; tasks without `kind` render with no chip.
- One value per task.
- Mutable via `octopus set kind=...`.
- Persisted in the index for `octopus list --kind <enum>`.
- Soft validation v1: unknown values log a warning, do not abort.

### Deferred

- `area` as a first-class enum. Stays in `tags` (free-form); first tag = primary area by convention.
- Auto-inferring `kind` from verb. Brittle.
- Required-on-promote. `kind` is optional everywhere, including before promotion.

---

## D47 — Task promotion is one-way (Octopus → Spectacular)

**Date:** 2026-05-23
**Request:** #20

### Locked

A task can be **promoted** into a Spectacular request via `octopus promote`. Promotion is a rewrite, not a copy: the PLAN.md becomes the source of truth from then on; the task body is replaced with a short pointer stub.

- **One-way.** Requests never demote back to tasks. If a request ships 95% and leaves stragglers, those become *new* Octopus tasks linking back via `promoted_to`.
- **Marker:** `promoted_to: <provider>:<id>` on the task. Presence = promoted; absence = normal task.
- **No new bucket.** Promoted tasks live in `tasks/done/`. The `bucket` enum is unchanged.
- **Body replacement.** On promotion, the task body is replaced entirely with a hard-coded 3-line stub pointing to the PLAN.md. Original body preserved in git history.
- **`kind: handoff` not used.** `.octopus/handoffs/` and the handoff schema retain their original directed-transfer meaning. Promotion is not a handoff.

---

## D48 — Provider-namespaced `promoted_to` format

**Date:** 2026-05-23
**Request:** #20

### Locked

`promoted_to` value format is `<provider>:<identifier>`. Always namespaced, always stored canonical (long form) regardless of CLI input form.

- v1 registered providers: `spectacular`.
- Format scales to future providers (`github:`, `linear:`, etc.) without schema migration.
- Slug-based identifier (not path), so links survive archive moves (`_archive/<slug>/`).
- Asymmetric: `promoted_from` on the request side is a bare task slug, no namespace (Octopus is the only origin Spectacular knows about).

### Config

```toml
[providers]
default = "spectacular"               # CLI shorthand resolves to this when prefix omitted

[providers.chips]
spectacular = "spec"                  # short label for TUI + chat
github      = "git"
linear      = "lin"

[providers.spectacular]
auto_number = true                    # prepend NN- to scaffolded slugs
```

- Chip values: ASCII, ≤6 chars. CLI warns on duplicate chip aliases.
- With no chip configured, fall back to full provider name — never silently drop the namespace.
- Config precedence: activity `.octopus/config.toml` > system `~/.config/octopus/config.toml`.

### CLI input forms

| Input | Resolution |
|---|---|
| `--to <provider>:<id>` | use as given |
| `--to <chip>:<id>` | chip alias resolved to canonical provider before write |
| `--to <id>` (no colon) | `<providers.default>:<id>` |
| `--to <provider>` (provider-only) | `<provider>:<task-slug>` — single-task only |
| `--to <provider>:new --slug <id>` | explicit "scaffold new with this slug" |

Smart-resolve on `spectacular:<slug>`: existing dir → link; absent → scaffold (with `auto_number` if enabled and slug has no leading `NN-`).

---

## D49 — Idempotency: hard reject + `--force` + `--revert`

**Date:** 2026-05-23
**Request:** #20

### Locked

`octopus promote` is **not idempotent by default**. Already-promoted tasks reject with exit 4 and a specific actionable error.

- **`--force`** repoints to a new target. Updates `promoted_to`, sets new `end_date`, does **not** rewrite the body (already a stub). Reindex propagates `related_tasks` changes to both old and new request PLAN.md.
- **`--revert`** soft-clears: removes `promoted_to`, clears `end_date`, **and moves the task back to `backlog/`**. Why: `bucket: done` requires `end_date` (rule A in CRITICAL-DEPENDENCIES), so clearing `end_date` while staying in `done/` would fail validation. Body stays as the stub (full restore is via git). The user can `octopus mv` to a different bucket from there.
- **`promoted_from`** on requests is **historical** — records what originally scaffolded the request, not what currently links to it. Not cleared on repoint. The dynamic field is `related_tasks` (derived).

---

## D50 — Multi-task promotion: atomic, positional args

**Date:** 2026-05-23
**Request:** #20

### Locked

`octopus promote` accepts multiple positional task slugs.

- All tasks in a batch share the same `--to` target. No per-task target.
- **Atomic:** pre-flight validation across all tasks before any write. Any failure (not found, already promoted without `--force`) aborts the whole batch.
- **`--force` and `--revert` are global** — apply uniformly to every listed task.
- **Multi-task with provider-only shorthand** (`--to spec` with 2+ tasks) is rejected (exit 3) — ambiguous target, must specify slug.
- On scaffold from multi-task: `promoted_from` records the first listed task; the full list lives in `related_tasks` (derived).

---

## D51 — Promotion stub template hard-coded v1

**Date:** 2026-05-23
**Request:** #20

### Locked

Stub template is **hard-coded** in the CLI. No config surface in v1.

```markdown
# <original title>

Promoted to **[<canonical-target>](../../.spectacular/requests/<request-slug>/PLAN.md)** on <date>.

The request PLAN.md is the source of truth from here on.
```

- Three lines. Pure pointer. No summary line (would drift against the PLAN).
- Body replaced entirely. Original preserved in git history.

### Deferred

- Override hook (`.octopus/templates/promote-stub.md`) — one-line upgrade later if demand emerges. Built-in stays as fallback. Not v1.

---

## D52 — `kind` survives promotion; hidden by default scope

**Date:** 2026-05-23
**Request:** #20

### Locked

Classification fields (`kind`, `tags`, `priority`, `energy`, `pinned`, etc.) **survive promotion** as historical facts about the original task.

- Indexed and queryable.
- Hidden from default filters because promoted tasks live in `tasks/done/`, which the default `list` scope already excludes.
- Surface via `--all`, `--promoted`, or `--spec <slug>`.

### List scope rules

| Flag | Buckets included |
|---|---|
| (default) | `backlog`, `next`, `now` |
| `--all` | all buckets (`done`, `dropped`, promoted) |
| `--promoted` | only tasks with `promoted_to:` set (overrides default scope) |
| `--spec <slug>` | only tasks with `promoted_to: spectacular:<slug>` (overrides default scope) |

---

## D53 — Spec-native requests: absence-as-marker

**Date:** 2026-05-23
**Request:** #20

### Locked

A Spectacular request born inside Spectacular (no Octopus task origin) carries **no `promoted_from` field**. Absence is the marker; no positive `origin:` enum.

- Consistent with the default-omission principle used throughout the schema.
- Tooling distinguishes promoted vs spec-native by presence/absence of `promoted_from`.
- No second field needed; no schema noise for "I am the default."

---

## D54 — Reindex derives `related_tasks` on the request side

**Date:** 2026-05-23
**Request:** #20

### Locked

`related_tasks` on request PLAN.md is **derived**, not authored. Task-side `promoted_to` is canonical; reindex regenerates request-side `related_tasks` by scanning all task files.

- Reindex parses `promoted_to: <provider>:<id>`. Only `spectacular:` entries flow into `related_tasks` regeneration. Other providers are no-op until adapter logic ships.
- For each `spectacular:<slug>`, derive a sorted, deduped list of task slugs and write to that request's PLAN.md.
- If no tasks reference a request, `related_tasks` is removed (default-omission).
- Malformed `promoted_to` values emit a warning but do not abort reindex.
- Hand-edits to `related_tasks` are validated against the canonical task scan; conflicts are flagged in `CRITICAL-DEPENDENCIES.md`.

---

## D55 — Request #19 superseded by #20

**Date:** 2026-05-23

### Locked

Request #19 (`task-naming-and-kinds`) is **superseded** by #20 (`task-promotion`). The naming-formula and `kind` enum scope is folded into #20 since both touch `SCHEMA-TASK.md` on the same migration.

- #19 moved to `.spectacular/requests/_archive/19-task-naming-and-kinds/` with `status: superseded`, `superseded_by: 20-task-promotion`.
- #20 frontmatter records `supersedes: [19-task-naming-and-kinds]`.

---

## D56 — Capability enum: atomic verbs only

**Date:** 2026-05-24
**Request:** #06

### Locked

```python
class Capability(Enum):
    PULL = "pull"
    PUSH = "push"
    NOTIFY = "notify"
    RECONCILE = "reconcile"
```

Four atomic verbs. No `TWO_WAY` meta-capability — "two-way" is a *configuration* (the user enables both PULL and PUSH and accepts the reconcile policy), not an adapter property. PRD §7.1's `{READ, WRITE, NOTIFY, TWO_WAY}` is superseded.

v1 ships only `PULL` adapters. `PUSH`/`RECONCILE` are forward-stable. `NOTIFY` is a flag-only declaration in v1 — the listener machinery ships with #12 (watcher daemon).

---

## D57 — Adapter protocol shape

**Date:** 2026-05-24
**Request:** #06

### Locked

```python
class Adapter(Protocol):
    name: str
    capabilities: set[Capability]
    def status(self) -> AdapterStatus: ...
    def validate_config(self, data: dict) -> list[str]: ...
    def list_groups(self) -> list[str]: ...
    def peek(self, groups: list[str] | None = None) -> PullResult: ...
    def pull(self, groups: list[str] | None = None) -> PullResult: ...
    def push(self, task) -> PushResult: ...
    def search(self, query: str, groups: list[str] | None = None) -> PullResult: ...
```

Seven methods. PRD §7.1's `link()` is **removed** — it was pipeline glue, not adapter behavior. The pipeline writes `external_refs.<adapter> = <ref>` after a successful pull/push using the `ExternalRef` returned from those calls.

`groups` is opaque to the framework; each adapter interprets it (Reminders = list names, GitHub = repos, ICS = calendars).

---

## D58 — Hybrid config layout

**Date:** 2026-05-24
**Request:** #06

### Locked

Enable/disable lives in main `config.toml`. Per-adapter content lives in `bridges/<name>.toml`.

```
~/.config/octopus/
├── config.toml
│   [adapters.obsidian]
│   enabled = true
│
└── bridges/
    ├── obsidian.toml          # vault, link_dir
    ├── reminders.toml         # lists, default_activity
    └── todo-md.toml           # path
```

- `octopus bridge enable <name>` flips `enabled = true` AND writes/updates `bridges/<name>.toml`.
- `octopus bridge disable <name>` flips to `enabled = false`. `bridges/<name>.toml` is **kept** — re-enable is one command.
- `bridges/<name>.toml` without matching main-config section is tolerated (parked settings).
- Main-config `enabled = true` without matching `bridges/<name>.toml` → exit 3.

Supersedes the all-in-`config.toml` `[adapters.*]` layout currently documented in `SCHEMA-CONFIG.md`. The schema doc will be split in Group 2.

---

## D59 — Multi-list config + flag matrix

**Date:** 2026-05-24
**Request:** #06

### Locked

Each adapter's per-adapter config supports a `lists` (or adapter-equivalent) field. Default: empty array.

```toml
# bridges/reminders.toml
lists = []                       # default — no configured list
# lists = ["Inbox"]              # single
# lists = ["Inbox", "Work"]      # multiple
```

CLI flag matrix:

| Config | Flag | Behavior |
|---|---|---|
| `lists = []` | none, peek | discovery — list available groups |
| `lists = []` | none, pull | exit 3 — would create unbounded files |
| `lists = ["A"]` | none | use configured |
| `lists = ["A","B"]` | none | use both |
| any | `--list X` | override (single) |
| any | `--list X,Y` | override (multi) |
| any | `--capture-all` | every group `list_groups()` returns |
| any | `--list X --capture-all` | exit 1 — mutually exclusive |

Per-adapter flag naming: `--list` (Reminders), `--repo` (GitHub), `--calendar` (ICS future). No generic `--group`. Dispatched via per-adapter Typer sub-apps.

---

## D60 — `peek` vs `pull`: two distinct verbs

**Date:** 2026-05-24
**Request:** #06

### Locked

The PRD-era "pull" lumped two semantics together. Splitting:

- **`octopus bridge peek <name>`** — read-only display. No files created, no dedup, no index changes. Pure read.
- **`octopus bridge pull <name>`** — imports as Octopus task files. Deduped via `task_external_refs`.

`peek` is the safe exploration tool. `pull` is the commitment.

`peek` with no group AND no default-config groups → **discovery mode**: prints available groups so the user can choose.
`pull` in the same state → exit 3 (would create unbounded files).

No "watch" mode in v1. A `peek --watch` could ship later as a thin polling loop; subscription/notify-driven watch ships with #12.

---

## D61 — `octopus bridge search` as a dedicated verb

**Date:** 2026-05-24
**Request:** #06

### Locked

```
octopus bridge search <name> <query> [--list/--repo NAME] [--capture-all]
```

Adapter-side search. No imports, no side effects. Returns matching items as a `PullResult`.

Adapters with native search APIs (GitHub) implement it natively. Adapters without (TODO.md, basic Reminders) implement it as `peek() + filter` internally — the framework doesn't care, just calls `adapter.search(query, groups)`.

No new capability flag — `search` is a sub-operation of `PULL`. Adapters declare `PULL`; the framework offers `peek`/`pull`/`search` as the three read-side verbs that work against it.

---

## D62 — Stub adapters ship in #06

**Date:** 2026-05-24
**Request:** #06

### Locked

#06 ships three adapter stubs in addition to the framework:
- `cli/src/octopus/adapters/obsidian.py` — capabilities = `{PULL}`; all methods return clear "not implemented — see #07" errors.
- `cli/src/octopus/adapters/reminders.py` — same; points to #09.
- `cli/src/octopus/adapters/todo_md.py` — same; points to #21.

Each is registered in the built-in `REGISTRY` dict. `octopus bridge list` shows them as disabled-and-unhealthy. The framework is testable end-to-end on #06 ship; #07/#09/#21 each just replace the stub body.

---

## D63 — Pull pipeline + dedup index (schema v3)

**Date:** 2026-05-24
**Request:** #06

### Locked

New SQLite table:

```sql
CREATE TABLE task_external_refs (
  task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  adapter     TEXT NOT NULL,
  external_id TEXT NOT NULL,
  PRIMARY KEY (adapter, external_id)
);
CREATE INDEX idx_task_external_refs_task ON task_external_refs(task_id);
```

`upsert_task` populates the table from `task.external_refs`. Schema v2 → v3 migration:
- CREATE TABLE on existing v2 DBs.
- Backfill: scan existing tasks' `external_refs` column, populate new table.

Pipeline dedup: `SELECT task_id FROM task_external_refs WHERE adapter = ? AND external_id = ?` — fast indexed lookup.

Pipeline materialization defaults (per PRD §7.5 + locked):
- `actor: human`
- `imported_from: <adapter_name>`
- `import_date: <today>`
- `bucket: <ExternalTask.suggested_bucket or "backlog">`
- `external_refs.<adapter_name>: <external_id>`

---

## D64 — Adapter registry: hardcoded + entry-points

**Date:** 2026-05-24
**Request:** #06

### Locked

v1 ships with hardcoded `REGISTRY: dict[str, type[Adapter]]` containing the three built-in adapters. `load_registry()` also scans for `importlib.metadata.entry_points(group="octopus.adapters")` and merges them.

Conflict resolution: **built-in wins**. Third-party adapter declaring an existing name is logged + skipped, never overrides core behavior.

Entry-points are forward-stable for #15 (adapter SDK, v2). v1 finds none and the merge is a no-op.

---

## D65 — Sync journal v1 shape

**Date:** 2026-05-24
**Request:** #06

### Locked

One JSON file per adapter at `~/.local/share/octopus/sync/<name>.json`:

```json
{
  "adapter": "reminders",
  "last_pull": "2026-05-24T10:23:00",
  "last_push": null,
  "pull_count": 3,
  "push_count": 0,
  "cursor": null
}
```

Fixed-size; no rotation needed. Auto-created on first write. `adapter.status()` reads it to populate `last_pull`/`last_push`.

Cursor is opaque — the adapter writes it via `PullResult.cursor`; the framework persists; next `pull()` invocation has access. v1 adapters don't use cursors; field is forward-stable.

`#10` (sync modes addendum) decides whether v2 grows this into a directory of per-event files.

---

## D66 — Repo layout + exit codes

**Date:** 2026-05-24
**Request:** #06

### Locked

Flat modules under `cli/src/octopus/adapters/`:

```
adapters/
├── __init__.py    # exports
├── base.py        # protocol + dataclasses
├── registry.py    # hardcoded + entry-points
├── journal.py     # sync journal r/w
├── pipeline.py    # pull materialization + dedup
├── obsidian.py    # stub
├── reminders.py   # stub
└── todo_md.py     # stub
```

Promote to subpackages only when an adapter grows multi-file (osascript helpers, parsers, schema migrations).

Exit codes follow PRD §5: `0 success · 1 user error · 2 not in activity · 3 config error · 4 bridge error`. No new codes for #06 — "all-items-failed" folds into 4, "mutually exclusive flags" folds into 1.

`octopus link` is **not** part of #06's CLI surface — Obsidian-specific, ships with #07.

---

## D67 — Reminders adapter uses `remindctl`, not osascript

**Date:** 2026-05-24
**Request:** #09

### Locked

The PRD §7.5 sketch named `osascript` / `shortcuts run`. Replaced with [`steipete/remindctl`](https://github.com/steipete/remindctl) (MIT, EventKit-based, JSON output, stable UUIDs).

Reasons:
- Stable EventKit UUIDs map directly to `external_refs.reminders` — no title-hashing.
- `--json` output eliminates fragile string parsing.
- Multi-list discovery built in (`remindctl list --json`).
- Authorization check via `remindctl status`.

Hard dependency. `status()` reports `healthy=False` with `brew install steipete/tap/remindctl` hint when missing.

osascript fallback intentionally not vendored — doubles maintenance surface for marginal benefit; both paths are macOS-only.

---

## D68 — Reminders authorization cached in journal

**Date:** 2026-05-24
**Request:** #09

### Locked

`octopus bridge enable reminders` shells out to `remindctl status` once and writes the result to `~/.local/share/octopus/sync/reminders.json` under a new `auth_state` field:

```json
{
  "adapter": "reminders",
  "auth_state": "Full access",
  "last_pull": null,
  ...
}
```

`adapter.status()` reads the journal — only re-shells `remindctl status` if cache says `"Not Determined"` (means OS hasn't prompted yet). Stable states (`"Full access"`, `"Denied"`) are cached indefinitely.

If the user revokes access in System Settings, the cache becomes stale until the next failed pull surfaces a clear error — acceptable trade-off given how rare revocation is.

---

## D69 — Reminders `external_id` = bare EventKit UUID

**Date:** 2026-05-24
**Request:** #09

### Locked

Unlike TODO.md (which used slug-of-title because line numbers drift), Apple Reminders provides stable globally-unique UUIDs via EventKit. Use them bare:

```yaml
external_refs:
  reminders: "DF95D91C-7F56-47E4-8AAD-07335A5DC086"
```

No path prefix, no encoding. Dedup via `task_external_refs (adapter="reminders", external_id=<uuid>)`.

---

## D70 — Reminders → Octopus field mapping

**Date:** 2026-05-24
**Request:** #09

### Locked

Per-field translation from `remindctl show all --list X --json` rows to Octopus task frontmatter:

| Apple field | Octopus field | Rule |
|---|---|---|
| `id` (UUID) | `external_refs.reminders` | bare UUID |
| `title` | `title` | verbatim |
| `notes` | task body | multi-line preserved; URL-only verbatim; empty → no body |
| `priority: "none"` | absent | default omission |
| `priority: "low"` | `priority: low` | direct |
| `priority: "medium"` | absent | Octopus has no medium (existing spec) |
| `priority: "high"` | `priority: high` | direct |
| `dueDate` (ISO 8601 UTC) | `due` (YYYY-MM-DD) | time portion dropped; UTC → date as-is |
| `completionDate` | (skip-filter only) | if set → skip unless `include_completed = true` |
| `isCompleted: true` | (skip-filter only) | same |
| `listName` | `ExternalTask.source_group` | for the pipeline's display + materialized body annotation |
| `listID` | unused | listName is human-readable; ID kept only in the source data |
| `recurrenceRule` | unused | v2 |
| `alarmDate` | unused | not surfaced |
| `locationTrigger` | unused | not surfaced |
| `url` | unused | not surfaced |

Default `bucket: backlog` — Apple Reminders has no in-progress state. No auto-`now` mapping.

---

## D71 — Reminders sync journal cursor unused

**Date:** 2026-05-24
**Request:** #09

### Locked

`remindctl` has no resume token / since-cursor API. Each pull re-reads the full list per configured group.

This is fine because:
- `task_external_refs` makes dedup an O(N) indexed lookup, not O(file scan).
- Apple Reminders lists are typically <1000 items; the JSON parse is sub-second.
- v1 has no notion of incremental sync anyway (#10 sync-modes is deferred).

The `cursor` field in the journal stays `None` for reminders. Forward-compat reserved.


---

## D72 — TODO.md format: GFM + Obsidian Tasks emoji conventions

**Date:** 2026-05-24
**Request:** #22

### Locked

The TODO.md adapter parses two layers, both established standards:

1. **GFM checklist** (`- [ ]`, `- [x]`, `- [/]`, `- [-]`, `- [!]`, `- [?]`) — the universal base. Renders in every markdown viewer.

2. **Obsidian Tasks emoji format** for inline metadata — adopted verbatim, no invention:

| Emoji | Octopus mapping |
|---|---|
| `🔺` / `⏫` | `priority: urgent` |
| `🔼` | omitted (no medium in Octopus) |
| `🔽` / `⏬` | `priority: low` |
| `📅 YYYY-MM-DD` | `due` |
| `⏳ YYYY-MM-DD` | `scheduled` |
| `🛫 YYYY-MM-DD` | `start_date` |
| `➕ YYYY-MM-DD` | `created_external` |
| `✅ YYYY-MM-DD` | combined with `[x]` → `bucket: done` |
| `❌ YYYY-MM-DD` | combined with `[!]` → skip |
| `🔁 ...` | preserved on rewrite; unused in v1 |
| `#tag` | appended to `tags` |

Source: [Obsidian Tasks emoji format reference](https://publish.obsidian.md/tasks/Reference/Task+Formats/Tasks+Emoji+Format).

Replaces the v0.4.1 parser (#21) which only handled `[ ]` / `[x]` / `[-]` / `[/]` and BUG:/HACK:/etc. prefixes. Prefix mapping is **kept** — both conventions coexist on the same line.

---

## D73 — `→ <provider>:<slug>` arrow convention

**Date:** 2026-05-24
**Request:** #22

### Locked

A checkbox line followed by `→ <provider>:<identifier>` means **"this item is now under that protocol's responsibility — exclude from import."**

```
- [x] wire obsidian bridge → octopus:wire-obsidian-bridge
- [x] adapter framework → spectacular:06-adapter-framework
- [x] track via linear → linear:ENG-123     (future)
```

**Behavior:**

- **Parser skips items with arrows on pull** — already handed off, no double-import.
- **Adapter writes arrows on successful pull** (D74) — rewrites `- [ ] foo` to `- [x] foo → octopus:<slug>` in place.
- **Users can hand-write arrows** to exclude items from import without deleting them (e.g. "this is a note, not a task" or "I'm tracking this in another system").
- **Arrow target format mirrors `promoted_to`** (D48): `<provider>:<identifier>`. v1 providers: `octopus`, `spectacular`. Unknown providers are accepted by the parser but no-op for Octopus dedup logic.

Octopus's only invented syntax in the TODO.md format. Layered on top of GFM + Obsidian Tasks conventions.

---

## D74 — `MARK_PULLED` capability + adapter source rewrite

**Date:** 2026-05-24
**Request:** #22

### Locked

New capability flag:

```python
class Capability(Enum):
    PULL = "pull"
    PUSH = "push"
    NOTIFY = "notify"
    RECONCILE = "reconcile"
    MARK_PULLED = "mark_pulled"   # NEW (D74)
```

Adapters declaring `MARK_PULLED` implement:

```python
def mark_pulled(self, mapping: dict[str, str]) -> None:
    """Annotate the adapter's source with the task slugs for successfully
    imported items.

    Args:
        mapping: external_id → octopus task slug for items that materialized
                 in this pull run.
    """
```

The framework's pipeline calls `adapter.mark_pulled(mapping)` after a successful materialize, but only if the adapter declares the capability.

**v1 capability declarations:**

| Adapter | `MARK_PULLED`? | Why |
|---|---|---|
| `todo-md` | yes | Rewrites `- [ ]` → `- [x] → octopus:<slug>` |
| `reminders` | no | Source is Apple's database — write is two-way push (#14) |
| `obsidian` | no | Viewer pattern; nothing to annotate |

**Why this is a new flag, not just adapter-internal behavior:**

The current protocol's `pull()` is read-only — adapters return data, framework writes tasks. `mark_pulled` is a side-effect write to the **external source**. Making it a declared capability keeps the protocol honest: agents (and the CLI) can tell which adapters annotate their source vs. which don't.

It also forward-stabilizes the pattern for any future read-side adapter that wants similar behavior (e.g. an Obsidian dataview adapter could mark items in `.base` files).

---

## D75 — Limited mutation verbs on bridge

**Date:** 2026-05-24
**Request:** #22

### Locked

Three new sub-verbs under `octopus bridge`, dispatched per-adapter:

```
octopus bridge add <adapter> <title> [--priority X] [--due Y] [--tag T] [--section S] [--state <open|in-progress>]
octopus bridge complete <adapter> <match> [--first]
octopus bridge uncomplete <adapter> <match> [--first]
```

Adapters declaring `MARK_PULLED` MAY implement these protocol methods:

```python
def add_item(self, title: str, **opts) -> str: ...        # returns a description of where it landed
def mark_complete(self, match: str, first: bool = False) -> str: ...
def mark_open(self, match: str, first: bool = False) -> str: ...
```

**Scope discipline:** these are limited verbs by design. Full CRUD (`edit`, `move`, `reorder`, `remove`, `--all`/`--matching`) is **deferred to request #23**. Activation criterion for #23: 4–6 weeks of dogfooding #22 surfaces concrete friction. If `add` + `complete` cover 95% of real edits, #23 stays in backlog.

**Why not `$EDITOR` shell-out?** Considered (option A in grilling). Decided against: an editor shell-out solves "edit the file" but doesn't help with the common case of capturing a single item without leaving the terminal. The `add` verb specifically supports the inline-flag pattern (`--priority high --due tomorrow`) which an editor can't.

---

## D76 — Tag flag matrix (capture, set)

**Date:** 2026-05-24
**Request:** #24

### Locked

All edit verbs (`capture`, `set`) accept this tag-mutation matrix:

| Flag | Behavior |
|---|---|
| `--tag <X>` / `--tags <X[,Y…]>` | **Replace** the entire tag list |
| `--add-tag <X>` / `--add-tags <X[,Y…]>` | **Append** (dedup) |
| `--remove-tag <X>` / `--remove-tags <X[,Y…]>` | **Remove** (no-op if absent) |
| `--clear-tags` | **Empty** the tag list |

Singular and plural are aliases — `--tag` ≡ `--tags`. Same for add/remove pairs.

**Input forms:** all four flag families accept comma-separated, space-separated (in a single quoted arg), or repeated invocation. Examples:
- `--tag X` · `--tag X,Y` · `--tag "X Y"` · `--tag X --tag Y`

**Mutual exclusion:** `--tag/--tags` (replace) is mutually exclusive with **any** of `--add-tag/--remove-tag/--clear-tags`. Mixing them errors (exit 1).

Combinations of `--clear-tags`, `--remove-tags`, `--add-tags` ARE allowed; applied in that order.

### Storage format

Tags stored with leading `#` in frontmatter to match Obsidian conventions:

```yaml
tags:
  - "#bug"
  - "#tui/marquee"
```

Nested tags use `/` separator (Obsidian convention). Stored verbatim.

**Input normalization:** flag values accepted with OR without `#`. Normalizer adds `#` if missing. So `--tag bug`, `--tag "#bug"`, `--add-tag tui/marquee` are all valid.

**Backwards-compatibility:** the reader accepts both forms. On any task write, existing tag values are normalized to include `#`. Quiet data migration — flagged in CHANGELOG.

**Filter behavior:** `list --tag parent` matches `#parent` AND any `#parent/*` (prefix match on `/` boundary). Exact-only match (`--exact`) deferred.

---

## D77 — `set --bucket` is frontmatter-only; `move`/`mv` for file moves

**Date:** 2026-05-24
**Request:** #24

### Locked

`set` is the **frontmatter-only escape hatch**. It edits fields; it does not move files.

Previously: `set --bucket next` would MOVE the file in folder mode (and update SQLite). New behavior:

- `set --bucket next` edits the frontmatter `bucket` field only.
- In folder mode, if the resulting state has `bucket` ≠ parent directory, emit a **soft warning** with a hint to run `octopus mv`.
- In field mode (flat storage), no warning fires — no folder concept.

New verb for the file-move case:

```
octopus move <slug> <bucket>
octopus mv <slug> <bucket>     # alias
```

Behavior:
- Validates bucket against enum.
- Folder mode: moves the file to the right directory + updates frontmatter `bucket`.
- Field mode: updates frontmatter only.
- Updates SQLite index.
- **No date stamps, no lifecycle side effects** (use `start`/`finish`/`drop` for those).
- Validates resulting state (moving to `done` without `end_date` rejects).

Separation of concerns: `set` mutates fields, `mv` moves files, lifecycle verbs do both + stamps.

---

## D78 — `set --slug` cascading slug rename

**Date:** 2026-05-24
**Request:** #24

### Locked

`octopus set <slug> --slug <new>` renames a task's slug with full auto-fix of Octopus-managed references.

**Always auto-fixed (top 6):**
1. Filesystem: `tasks/<bucket>/<old>.md` → `tasks/<bucket>/<new>.md`
2. SQLite: `tasks.slug` + `tasks.id` columns
3. `waiting_for: <old>` in other tasks' frontmatter
4. `related_tasks: [..., <old>]` in spectacular PLAN.md
5. `promoted_from: <old>` in spectacular PLAN.md
6. `→ octopus:<old>` arrows in TODO.md files

**Soft-warned (named files, not auto-fixed):**
- Session bodies (`.octopus/sessions/*.md`)
- Memory body (`.octopus/memory.md`)
- Handoff bodies (`.octopus/handoffs/*.md`)

**External tools** (Obsidian, IDE, git history): named in the warning, never auto-touched.

**Interactive flow:** prompts with a preview of all changes. `-y` flag skips the prompt.

A companion read-only verb `octopus refs find <slug>` (D79) helps the user locate residual occurrences after a rename.

---

## D79 — `octopus refs find <slug>` helper verb

**Date:** 2026-05-24
**Request:** #24

### Locked

Read-only verb. Greps every Octopus-managed text file in the activity for a slug and prints `file:line` with the matched line.

```
octopus refs find <slug>          # this activity
octopus refs find <slug> --all    # cross-activity
```

Scope: task files, sessions, memory, handoffs, spectacular PLAN.md files, TODO.md files. **Read-only — never edits.** Companion to D78 slug rename for tracking down residual references.

Out of scope: external tools (Obsidian backlinks, IDE bookmarks, git history) — user task.

---

## D80 — Explicit-default values clear instead of reject

**Date:** 2026-05-24
**Request:** #24

### Locked

When the user passes a value that equals the field's default (and the schema uses default-omission), accept it and clear the field. Don't reject.

Applies to all `set`/`capture` flag values:

| Field | Explicit-default values that clear |
|---|---|
| `--priority` | `normal`, `none`, `""` |
| `--actor` | `human`, `""` |
| `--energy` | `normal`, `none`, `""` |
| `--run-state` | `idle`, `none`, `""` |
| `--issue` | `none`, `""` |
| `--bucket` | (no clear — bucket is required) |
| `--kind` | `none`, `""` |
| any optional date field | `""` |

Rationale: refusing the user's explicit-default is just adversarial. The result is the same as omitting the flag entirely. Match user intent.

---

## D81 — Drop auto-pin on `capture --now`

**Date:** 2026-05-24
**Request:** #24

### Locked

`capture --now` previously set `pinned: true` along with `bucket: now`. **Drop the auto-pin.**

Pin stays orthogonal to bucket per AXIS-MODEL (D43). If the user wants a pinned task, they `pin` it explicitly:

```
octopus capture "fire" --now && octopus pin fire
```

This restores the orthogonality the AXIS-MODEL is supposed to enforce. Behavior change is in the CHANGELOG.

---

## D82 — Empty body on `capture`

**Date:** 2026-05-24
**Request:** #24

### Locked

`capture` previously wrote `\n## References\n` as the default task body. **Drop that.** New captures have empty bodies.

`## References` reappears as a section when the user wants it — manually or via a future `--body` flag (deferred to #26).

Rationale: defaulting to a hardcoded section adds noise to every task. Empty is the honest default.

---

## D83 — `forget activity` verb + archived-by-default in list views

**Date:** 2026-05-24
**Request:** #30

### Locked

New verb `octopus forget activity <path-or-id>` removes an activity from the
SQLite index. Files on disk are NOT touched by default. Optional `--archive`
flag moves files to `<activity-parent>/_archive/<name>/`.

Resolution: path-or-id auto-detect. If the token starts with `/`, `~`, or
contains `/`, treat as a filesystem path; otherwise treat as activity ID
(or unambiguous prefix).

Flags:
- `--archive` / `--also-archive` — move files to `_archive/` as well as forgetting.
- `-y` — skip the interactive prompt. **Does NOT imply archive.** Bare `-y`
  forgets without archiving; combine with `--archive` to archive too.

Flag matrix:
- `--archive` + `-y` → forget + archive, no prompt
- `--archive` alone → forget + archive (no prompt needed; intent is explicit)
- `-y` alone → forget, do NOT archive, no prompt
- neither flag → interactive prompt "Also archive files to _archive/? [y/N]";
  suggests both flag-form equivalents for next time

Behavior:
- Always: delete the row from `activities` table. SQLite CASCADE drops
  related `tasks` and `task_external_refs` rows.
- With `--archive`: also move the activity folder to `<parent>/_archive/<name>/`.
- Re-running on an already-forgotten activity errors with "activity not in index".

**Activities only.** Tasks have their own lifecycle (`archive`/`drop`/`done`).
The verb noun is explicit (`forget activity`, not `forget`) — future-stable
for `forget task <slug>` if real demand ever surfaces.

### Archived-by-default in list views

Activities with `status: archived` are hidden by default in:
- `octopus list` / `octopus list activities` / `octopus list --all`
- `octopus dashboard` (when #27 ships)
- `octopus next` / `octopus impact` (when #27 ships)

Override flag: `--include-archived`.

The user can always look at a specific archived activity by name via
`octopus status <id>` or `octopus list tasks <id>`.


---

## D84 — One-target-axis-per-invocation rule for `set`

**Date:** 2026-05-24
**Request:** #26

### Locked

`octopus set` accepts three target shapes. Mixing them is rejected with a clear
error pointing at the offending combination.

| Form | Scope | Semantics |
|---|---|---|
| `set <slug> --flag X` | cwd activity, single target | "this activity, one" |
| `set --task t1 t2 ... --flag X` | cwd activity, multi-target tasks | "this activity, multiple" |
| `set --activity a1 a2 ... --flag X` | anywhere, multi-target activities | "anywhere, multiple" |

Rejection cases (all exit 1 with `--task and --activity are mutually exclusive`
or the analogous message):

- positional `<slug>` + `--task` → rejected
- positional `<slug>` + `--activity` → rejected
- `--task` + `--activity` → rejected
- no target at all (`set --priority high` alone) → rejected
- multiple positionals without `--task` (`set s1 s2 --flag X`) → rejected
- `set <slug>` from outside an activity → rejected with "not inside an activity"
- `set --task t1` from outside an activity → rejected with "not inside an activity"

Resolution rules:

- For `--task t1 t2 t3`: each slug is resolved against the **current** activity's
  task list only. Ambiguous matches print candidates from this activity, exit 1.
  Cross-activity task mutation is **not v1 scope**.
- For `--activity a1 a2 a3`: each id matches by exact id or unambiguous prefix
  against the index, using the same resolver as `forget activity` (`core/identify.py`).
- Each target in a multi-target invocation is processed independently; one
  invalid target does not abort the rest, but exits non-zero at the end.

### Activity-level fields on `set --activity`

`set --activity` only operates on activity-level frontmatter. Allowed flags:

- `--title`
- `--status <active|on_hold|done|cancelled|archived>`
- `--type <enum>`
- `--area <name>`
- `--tags / --tag / --add-tag / --remove-tag / --clear-tags` (D76 matrix)
- `--last-reviewed <date>`
- `--priority <enum>` — **stub-rejected until #27 lands the activity priority field**

Task-only flags (`--bucket`, `--stage`, `--run-state`, `--pinned`, `--issue`,
`--blocked-by`, `--waiting-for`, `--archived`, `--due`, `--scheduled`,
`--start-date`, `--end-date`, `--energy`, `--actor`, `--owner`, `--kind`,
`--slug`) passed to `set --activity` are rejected with the offending flag named.

---

## D85 — `add task` / `add activity` verbs

**Date:** 2026-05-24
**Request:** #26

### Locked

New Typer sub-app `octopus add` with two verbs:

```
octopus add task "<title>" [--activity <id>] [...full task flag matrix from #24]
octopus add activity "<name>" [--type <kind>] [--area <name>] [--path <dir>]
```

#### `add task`

Behavior:
- When `--activity` is **omitted**: cwd-walk-up. Same behavior as `capture`. If
  cwd is outside an activity, errors with the standard "not inside an activity"
  message — pointing at `--activity` as the way out.
- When `--activity` is **specified**: resolves via `core/identify.py`
  (`resolve_activity`). Errors on unknown / ambiguous match.
- Flag matrix identical to `capture` (v0.6.0): `--next/--now`, `--priority`,
  `--due/--scheduled/--start-date/--end-date`, `--actor/--energy/--owner/--stage`,
  full D76 tag matrix, `--slug`.

`capture` stays. `add task` is the "from anywhere" sibling; the two verbs share
the same underlying creation path (extracted into an action) and differ only in
which one feels ergonomic in which context. Behavior MUST be identical when
`add task` is called from inside an activity with no `--activity` flag.

#### `add activity`

Behavior:
- Creates a new activity. Equivalent to `octopus init` but in the `add` family
  for discoverability and consistency with `add task`.
- `--path <dir>` specifies where to init. Default: cwd. If `<dir>` doesn't exist,
  it's created.
- `--priority` is **deferred to #27** when the activity priority field lands.
  Passing it in v0.8.0 (#26 ships) errors with
  "activity priority not implemented yet — see #27".
- `--id` override carried over from `init` for compatibility.

`init` stays as an alias for backwards compatibility; the canonical form is
`add activity`.

---

## D86 — `--activity` flag on all write verbs

**Date:** 2026-05-24
**Request:** #26

### Locked

Every task-mutation verb accepts an optional `--activity <id>` flag that
redirects the operation to a specific activity instead of cwd-walking. Affected
verbs:

- `capture` (in addition to the new `add task`)
- `pin / unpin`
- `plan / focus / park / defer`
- `start / finish / drop`
- `archive / restore`
- `mv / move`
- `block / wait / unblock`
- `promote`

Behavior:
- When `--activity` is **omitted**: cwd-walk-up (current behavior).
- When `--activity` is **specified**: resolves via `core/identify.py`. The task
  slug is then resolved within the named activity, not the cwd one. cwd is no
  longer required.

These verbs remain **single-target on tasks**. Only `set` gets multi-target
shapes per D84. There is no `--task t1 t2` on `pin`/`finish`/etc — that would
encourage cross-cutting batch mutations the user probably doesn't actually want.
If real demand surfaces, add it then.

The `--activity` flag is rejected with a clear error if combined with the
existing positional in a way that contradicts cwd context (e.g.,
`pin slug --activity X` from inside activity Y → operates on X, but warns that
cwd is in Y).


---

## D87 — Activity `priority` field

**Date:** 2026-05-24
**Request:** #27

### Locked

`activity.md` frontmatter gains an optional `priority` field:

```yaml
priority: low | high | urgent       # optional; absent = normal
```

**Strict enum** (the empty/absent state IS "normal"; there is no `priority: normal`
in YAML — the field is omitted). Same convention as task priority (D80).
Invalid values rejected; explicit-defaults (`normal`/`none`/`""`) clear the
field via `set --activity --priority normal`.

Used by:
- `octopus set --activity <id> --priority X` (unblocks the D85 stub-reject)
- `octopus add activity --priority X` (unblocks the D85 stub-reject)
- `octopus list --all --priority urgent` (filter)
- `dashboard` / `next` / `impact` ranking inputs (D89)

Storage:
- `Activity` dataclass adds `priority: str | None = None`
- SQLite `activities` table adds a nullable `priority TEXT` column
- Schema migration v3 → v4 in `db/connection.py`

---

## D88 — Schema v3 → v4: priority + last_touched_at

**Date:** 2026-05-24
**Request:** #27

### Locked

Single migration bumping the index from v3 to v4. Two new columns on
`activities`:

```sql
ALTER TABLE activities ADD COLUMN priority TEXT;          -- D87
ALTER TABLE activities ADD COLUMN last_touched_at TEXT;   -- ISO 8601 datetime
```

`last_touched_at` is the most-recent of: any task write, any session write,
any memory write within the activity. Updated on every `sync_*_after_write`
call. Used by the ranking heuristic (R1) for tiebreaks and by the dashboard
"touched within" filter.

Migration is idempotent (`ALTER TABLE … ADD COLUMN` followed by an
existence check). Both columns default NULL — existing rows are
backfilled on next `reindex` (or stay NULL until next write).

---

## D89 — Ranking heuristic R1

**Date:** 2026-05-24
**Request:** #27

### Locked

Single-pass numeric score per task. Higher = more impact. Weights:

| Signal | Weight | Notes |
|---|---|---|
| `pinned: true` | +100 | D43 — pinned always near top |
| Overdue | +80 + days_overdue, cap +30 | Total cap = +110 |
| `bucket: now` | +40 | User already committed |
| Due soon (≤7 days) | +30 − days_until_due | 0 if not due-soon |
| `priority: urgent` | +50 | Task-level |
| `priority: high` | +25 | Task-level |
| Activity `priority: urgent` | +20 | Activity halo |
| Activity `priority: high` | +10 | Activity halo |
| `issue: blocked` or `waiting` | −30 | Can't act |
| Archived / done / dropped | excluded | Never appear in ranked views |

Ties broken by `last_touched_at` ascending (stale bubbles up).

Weights are **fixed for v1**. Configurable weights deferred to a future
request — the algorithm goes in `core/ranking.py` so the call sites stay
stable when weights become tunable.

---

## D90 — Dashboard / read-verb output conventions

**Date:** 2026-05-24
**Request:** #27

### Locked

#### `octopus dashboard`

Rich text by default. JSON via `--json` flag with two forms:

```
octopus dashboard               # rich text to stdout
octopus dashboard --json        # JSON to stdout (one-line, agent-friendly)
octopus dashboard --json <path> # JSON written to <path>; stdout silent on success
```

`--json` is a flag-with-optional-value: bare `--json` means stdout; with
a path argument it writes to that file. Typer convention: `--json` is
`bool | str` resolved by post-parse logic (peek argv).

#### `octopus next`

Top **3** tasks across all activities by default. `--limit N` to change.
Same ranking as `impact`. Rich text output; `--json` follows the same
flag convention as `dashboard`.

#### `octopus impact`

Full ranked list, default **top 20**. `--limit N` to change (use `--limit 0`
for unlimited). `--show-score` reveals the numeric score per row.

#### `octopus list activities` and `octopus list tasks`

Noun-explicit subcommands of `list`. Default scope is context-aware:
inside an activity, bare `octopus list` defaults to tasks; outside, to
activities. The noun-explicit forms always work regardless of cwd.

#### `octopus status <path-or-id>`

Extended rich text view: activity metadata + bucket counts + first N
titles for now/pinned/overdue + active session + last_touched + adapter
status. No format flag in v1 — `octopus get activity <path-or-id>` is
the JSON-shaped equivalent.

#### `octopus get activity <path-or-id>`

JSON output. TTY → pretty-printed (2-space indent). Pipe → compact
single-line. `--format pretty|compact` to override. Noun-explicit form
(`get activity`, not `get`) — future-stable for `get task <slug>`.

---

## D91 — Header glyph vocabulary (Slot 3)

The TUI header bar gets a dedicated glyph slot, distinct from the row-level status (Slot 1) and flag (Slot 2) glyphs.

**Active glyphs (in use):**

- **`◇` (lavender)** — Activity row, activity-name prefix.
- **`⬡` (lavender)** — Activity row, repo-name prefix. Shown when the activity root is inside a git repo (walk-up `.git/` detection).
- **`▶` (cyan)** — Human session running. Reused from the existing row-level session glyph (Slot 1 override). One glyph, one meaning across both scopes.
- **`⌂` (dim)** — Path row. Unchanged.
- **`⟳` (dim / yellow when busy)** — Tui state. Unchanged.

Activity row layout: `◇ <activity-name>   ⬡ <repo-name>`. The repo segment is omitted when no git toplevel is found above the activity root.

**Reserved glyphs (defined, not yet rendered):**

- **`◆` (filled diamond)** — Activity row variant. Reserved for a future activity-state encoding (e.g. "activity has unread alerts").
- **`⬢` (filled hexagon)** — Activity row variant. Reserved for a future repo-state encoding (e.g. "repo has uncommitted changes").
- **`»` (chevron)** — State row. Reserved for an "agent is acting on this activity / task" indicator. Pairs with `▶` (human session) — same cyan, distinct silhouette.

The previous `SESSION = "◆"` constant in `tui/icons.py` is retired — `◆` is now an activity-row variant, not a session glyph. `SESSION_RUN = "▶"` is the single canonical session glyph.

**Rationale — hollow over filled.** Both the activity-name and repo-name segments carry permanent context (which activity, which repo), not a transient state. Hollow shapes (`◇`, `⬡`) read as labels / markers; filled shapes (`◆`, `⬢`) read as active states. Reserving the filled variants for future state encodings keeps the hollow/filled contrast available as a typed-state vocabulary when we need it.

**Rationale — `»` for agent, not `⏩`.** The fast-forward emoji renders as a color emoji on most terminals, breaking the plain-glyph palette. `»` (U+00BB right double angle) reads as "fast-forward / auto-advancing," is ASCII-grade, and renders consistently. Will use the same cyan color as `▶` to signal "live activity," with shape distinguishing "human at the wheel" from "agent at the wheel."

**Rationale — walk-up git detection.** Activity folders commonly live inside a larger repo (e.g. `~/repo/projects/foo/`). Walking up from the activity root surfaces the enclosing repo without the user having to flag it. Stop at filesystem root or `$HOME` (whichever comes first) so we don't accidentally surface a remote-mounted parent. `.git/config` parsing for "is this actually a GitHub remote" is deliberately not done — `⬡` means "git-tracked," not "GitHub-hosted." Hexagon was picked because the platform popularized the motif, but the trigger is generic git.

**Implementation pointer.** `tui/icons.py` defines:

- `ACTIVITY = "◇"` (in use)
- `REPO = "⬡"` (in use)
- `ACTIVITY_FILLED = "◆"` (reserved)
- `REPO_FILLED = "⬢"` (reserved)
- `AGENT_RUN = "»"` (reserved)
- `SESSION_RUN = "▶"` (in use)

`HeaderBar.set_repo_name(name)` shows the `⬡ <name>` segment. Empty string hides it. `set_git_detected(False)` is a back-compat shim that clears the repo name. Detection helper `_git_repo_name(path)` lives in `tui/focus.py` and is called from both `focus.py` and `board.py` on mount.

See `.spectacular/specs/TUI-GLYPHS.md` Slot 3 for the full spec.

---

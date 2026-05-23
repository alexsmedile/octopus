---
version: 1.0.0
spec_version: 1
status: stable
updated: 2026-05-21
---

# Octopus `.octopus/` folder specification

This document is the **canonical contract** for the on-disk format of an Octopus activity. Implementations in any language MUST conform to this spec to be interoperable with the reference Python CLI and with each other.

PRD.md describes *what* Octopus is and *why*. This document describes *what a conformant `.octopus/` folder looks like, exactly*.

Throughout this document, the key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** follow [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) conventions.

---

## 1. Scope and versioning

### 1.1 What this spec covers

- The structure of an `.octopus/` directory.
- The frontmatter schema of every file inside it.
- Discovery rules (how to find activities from any working directory).
- Cross-references between activities and tasks.
- Identifier formats and uniqueness rules.
- Validation an implementation MUST perform, and validations it SHOULD perform.

### 1.2 The spec family

This SPEC.md is the conceptual map. The full contract is split across companion documents under `specs/`:

| Doc | Covers |
|---|---|
| `SPEC.md` (this file) | Folder layout, discovery, IDs, slugs, cross-refs, versioning |
| `SCHEMA-ACTIVITY.md` | Full `activity.md` frontmatter contract |
| `SCHEMA-TASK.md` | Full task frontmatter contract |
| `SCHEMA-SESSION.md` | Full session frontmatter contract |
| `SCHEMA-HANDOFF.md` | Full handoff frontmatter contract |
| `SCHEMA-MEMORY.md` | Full memory contract (two-zone structure) |
| `SCHEMA-CONFIG.md` | `.octopus/config.toml` + cache files |
| `AXIS-MODEL.md` | Four-axis structural framing for task state |
| `CLI-VERBS.md` | CLI verb surface and side effects |
| `CRITICAL-DEPENDENCIES.md` | Validation rules across all schemas |

All ten documents together are the **v1 spec**. Conformant implementations MUST honor all of them.

### 1.3 What is NOT in scope

- The SQLite index schema (internal implementation, see `PRD.md` §8).
- Viewers, TUI, web dashboards, or any presentation layer.
- Adapter implementations (Obsidian, Reminders, etc.) — see `PRD.md` §7.

### 1.4 Versioning

Each activity file declares `spec_version: <integer>` in its frontmatter. v1 of this spec defines `spec_version: 1`.

- An implementation MUST refuse to mutate a file whose `spec_version` is greater than the version it supports.
- An implementation MAY read such a file in read-only mode if it can parse the frontmatter safely.
- The spec version is an integer, not semver. The document itself is versioned with semver (`version: 1.0.0` in this file's frontmatter) for change tracking, but the on-disk field stays integer.

### 1.5 Compatibility commitments

For `spec_version: 1`:
- No required field will be removed in patch or minor revisions of this document.
- New optional fields MAY be added in minor revisions.
- Breaking changes require `spec_version: 2` and a migration path documented in `PRD.md`.

---

## 2. Folder layout

An **activity** is any directory containing a subdirectory named `.octopus/` with at minimum an `activity.md` file inside it.

### 2.1 Required structure

```
<any-folder>/.octopus/
└── activity.md                  # required
```

A `.octopus/` directory without `activity.md` is INVALID. Implementations MUST skip such directories during discovery and MAY surface a warning.

### 2.2 Full structure (all optional except activity.md)

```
<any-folder>/.octopus/
├── activity.md                  # REQUIRED
├── config.toml                  # optional — per-activity overrides (storage mode, field aliases)
├── tasks/                       # optional — one file per task
│   ├── backlog/                 # ──┐
│   │   └── <slug>.md            #   │
│   ├── next/                    #   │ folder mode (default)
│   │   └── <slug>.md            #   │ subfolders mirror the bucket field
│   ├── now/                     #   │
│   │   └── <slug>.md            #   │
│   ├── done/                    #   │
│   │   └── <slug>.md            #   │
│   └── dropped/                 # ──┘
│       └── <slug>.md
├── sessions/                    # optional — one file per session
│   └── YYYY-MM-DD-<slug>.md
├── handoffs/                    # optional
│   └── <slug>.md
├── memory.md                    # optional
└── .trash/                      # optional — soft-deleted files, excluded from retrieval
    └── (mirrors the structure above)
```

All subdirectories and `memory.md` MUST be created lazily — an implementation MUST NOT require their existence to consider an activity valid.

### 2.3 Storage mode: folder vs field

Each activity declares a storage mode in `.octopus/config.toml`:

```toml
[storage]
mode = "folders"     # default. Tasks live in bucket subfolders (backlog/, next/, now/, done/, dropped/).
# OR
mode = "fields"      # Tasks live flat in tasks/. Bucket is frontmatter-only.
```

- **Folder mode (default)**: pipeline verbs (`plan`, `focus`, `park`, `defer`) MUST both edit the frontmatter `bucket` field AND `mv` the file into the matching subfolder. The path and the frontmatter MUST always agree; mismatch is invalid (see `CRITICAL-DEPENDENCIES.md` rule F).
- **Field mode**: tasks live in a flat `.octopus/tasks/` directory. Subfolders are absent. The `bucket` frontmatter field is the sole source of truth.
- Conversion between modes is done via `octopus storage convert --to folders|fields`.
- Repair of mismatches is done via `octopus storage repair`.

Whether folder or field mode, the `bucket` frontmatter field is REQUIRED. Folder mode adds defensive path-vs-field consistency.

### 2.4 File naming

- File names use lowercase ASCII with hyphens.
- File names MUST be valid on the lowest-common-denominator filesystem (case-insensitive APFS / NTFS).
- File names MUST NOT exceed 50 characters including the `.md` extension (see §10 for slug rules).
- Reserved file names at the `.octopus/` root: `activity.md`, `memory.md`, `config.toml`. Implementations MUST NOT create other files there.
- The `.trash/` directory is reserved and MUST be excluded from all retrieval. See `CRITICAL-DEPENDENCIES.md` rule H.

---

## 3. `activity.md`

The identity file for an activity. Exactly one per `.octopus/` directory.

**Full schema**: `specs/SCHEMA-ACTIVITY.md`. The schema doc is authoritative; this section is a summary.

### 3.1 Required fields (summary)

| Field | Type | Notes |
|---|---|---|
| `id` | string | `<slug>-<4-hex-hash>` (see §9). Immutable. |
| `title` | string | Human display name. |
| `created` | ISO date | Set once at init. |
| `kind` | enum | `activity` (fixed in v1). |
| `spec_version` | integer | `1`. |
| `type` | enum | `code | business | content | skill | automation | research | personal | other` |
| `status` | enum | `active | next | paused | planning | maintenance | reference | archive | unknown` |
| `last_known_path` | absolute path | Enables rename detection (§9.3). |
| `source_of_truth` | string | Path or URL; `"."` means this folder. |

### 3.2 Optional fields (summary)

`area` (free-form, discovery-validated), `last_reviewed` (ISO date), `locations` (list), `linked_activities` (list of activity IDs), `tags` (list).

### 3.3 Validation

See `specs/CRITICAL-DEPENDENCIES.md` rule J.

### 3.4 Body

Free-form markdown. Implementations MUST preserve it byte-for-byte on read-write cycles.

---

## 4. `tasks/<slug>.md`

One file per task. Activity is implicit from folder location — there is no `activity:` field.

**Full schema**: `specs/SCHEMA-TASK.md`. The schema doc is authoritative.

### 4.1 Five-axis model (summary)

Task state is modeled along **five orthogonal axes**:

| Axis | Field | Values |
|---|---|---|
| Pipeline | `bucket` | `backlog | next | now | done | dropped` |
| Domain workflow | `stage` | (absent) | free-form per activity |
| Runtime | `run_state` | (absent = idle) | `queued | running | finished | failed` |
| Attention | `pinned` | (absent/false) | `true` |
| Impediment | `issue` | (absent) | `blocked | waiting` |

Plus a non-axis visibility flag: `archived` (absent or `true`).

Lifecycle is **not** an axis — it is encoded via dates (`start_date`, `end_date`) and the terminal `bucket` values (`done`, `dropped`).

Full structural framing in `specs/AXIS-MODEL.md`.

### 4.2 Required fields (summary)

Only three: `title`, `created`, `bucket` (default `backlog`).

### 4.3 Optional fields (summary)

`stage`, `run_state`, `pinned`, `issue`, `blocked_by`, `waiting_for`, `archived`, `due`, `scheduled`, `start_date`, `end_date`, `priority`, `energy`, `actor`, `owner`, `tags`, `external_refs`, `import_date`, `imported_from`.

**Default-omission principle**: any field that equals its default value is omitted entirely from frontmatter. `actor: human` is not written. `priority: <normal>` is not written. Captures with all defaults produce 3-line frontmatter.

### 4.4 Storage mode

Activities default to **folder mode**: tasks live in bucket subfolders (`tasks/backlog/`, `tasks/next/`, `tasks/now/`, `tasks/done/`, `tasks/dropped/`). The `bucket` frontmatter field MUST match the parent folder. See §2.3.

Activities may opt into **field mode** via `.octopus/config.toml [storage] mode = "fields"` — tasks live flat, `bucket` is frontmatter-only.

### 4.5 CLI surface

Verbs (`capture`, `plan`, `focus`, `start`, `finish`, etc.) and views (`today`, `now`, `next`, `backlog`, `loops`, `stuck`, etc.) operate on this schema. See `specs/CLI-VERBS.md`.

### 4.6 Validation

See `specs/CRITICAL-DEPENDENCIES.md` rules A-I.

### 4.7 Body

Free-form markdown. Convention: a `## References` section near the end for navigation targets.

Checklist steps use plain `- [ ]` markdown checkboxes. **Checklist items have no structural meaning** in v1 — they are not parsed, counted, or indexed. They exist for human readability. Completing all checkboxes does not auto-promote anything.

---

## 5. `sessions/<file>.md`

One file per session. Filenames are date-prefixed: `YYYY-MM-DD-<slug>.md`.

### 5.1 Frontmatter schema

```yaml
---
title: debugging-export
started: 2026-05-21T14:32:00
ended:
related_tasks:
  - fix-webhook-auth-bug
---
```

### 5.2 Required fields (summary)

`title`, `started` (ISO datetime).

### 5.3 Optional fields (summary)

`ended` (ISO datetime — absence means OPEN), `active` (boolean, cache-mirrored), `status` (`doing | done | dropped`), `related_tasks` (list of task slugs), `related_handoff` (handoff slug), `summary` (string).

### 5.4 Storage mode

Sessions are **always stored flat** in `.octopus/sessions/`, regardless of the activity's storage mode. Sessions are machine-readable artifacts ordered by date, not user-navigated piles.

### 5.5 Open / closed / active

| Concept | Indicator | Meaning |
|---|---|---|
| Open / closed | `ended:` empty or populated | Has the session been formally ended? |
| Active | cache file at `~/.cache/octopus/active-sessions.json` (mirrored to `active:`) | Which open session in this activity am I currently in? |
| Status | `status:` field | Was the session productive (`doing` / `done`) or abandoned (`dropped`)? |

Multiple OPEN sessions per activity allowed. At most one ACTIVE session per activity (PRD §13.2).

### 5.6 CLI verbs

`session start`, `session log`, `session end`, `session switch`, `session prune`. See `specs/CLI-VERBS.md`.

### 5.7 Validation

See `specs/CRITICAL-DEPENDENCIES.md` rule K.

### 5.8 Body

Free-form markdown. Convention: chronological notes. `session log "<note>"` appends timestamped entries to the body.

---

## 6. `handoffs/<slug>.md`

One file per handoff. Optional. A deliberate context-transfer note (vs sessions, which are passive recordings).

**Full schema**: `specs/SCHEMA-HANDOFF.md`.

### 6.1 Required fields (summary)

`title`, `created` (ISO date), `from_actor` (default `human`), `status` (default `open`).

### 6.2 Optional fields (summary)

`from_session`, `to_actor`, `to_owner`, `related_tasks`, `related_activities`, `received_at`, `resolved_at`, `summary`, `priority`, `tags`.

### 6.3 Storage mode

Handoffs are **always stored flat** in `.octopus/handoffs/`. Low cardinality per activity; subfolder buckets would be overkill.

### 6.4 Lifecycle

`open → received → resolved` (or `stale`). State transitions populate `received_at` and `resolved_at`. See `specs/SCHEMA-HANDOFF.md` for the full state machine.

### 6.5 Validation

See `specs/CRITICAL-DEPENDENCIES.md` rule L.

### 6.6 Body

Free-form markdown. Recommended sections: TL;DR, What's done, What's next, Open questions, References.

---

## 7. `memory.md`

One file per activity. Optional. Stores accumulated context that survives sessions.

**Full schema**: `specs/SCHEMA-MEMORY.md`.

### 7.1 Two-zone structure

A two-zone file separated by the literal marker `<!-- octopus-managed-below -->`.

| Zone | Contents | Who writes |
|---|---|---|
| Above marker | Frontmatter + `# Memory: <title>` heading + user-authored intro | User. CLI may only update `last_updated` and `summary` via explicit verb. |
| Below marker | Five canonical sections with dated entries | CLI appends only; never reformats. User may hand-edit. |

### 7.2 Frontmatter

Required: `activity`, `last_updated`. Optional: `summary` (single-line or YAML block scalar).

### 7.3 Canonical sections (below the marker)

Exactly five sections, in this order:

1. `## Decisions`
2. `## Open Questions`
3. `## Context`
4. `## Notes`
5. `## Log` (default target for `memory append`)

### 7.4 Entry format

Each entry is a level-3 heading with a datetime, followed by free-form body:

```markdown
### YYYY-MM-DD HH:MM
<entry body>
```

Local time, no timezone suffix. Implementations MUST use exactly this format on write.

### 7.5 CLI verbs

`memory append`, `memory show`, `memory summary set`. See `specs/CLI-VERBS.md`.

### 7.6 Validation

See `specs/CRITICAL-DEPENDENCIES.md` rules M and N.

---

## 8. Discovery and cross-references

### 8.1 Discovery rules

Implementations MUST support two discovery modes:

**Walk-up (from cwd)**: Given a starting directory, traverse parent directories until either:
- A directory containing `.octopus/activity.md` is found → that is the current activity.
- The filesystem root is reached → no current activity.

**Walk-down (from configured roots)**: Given a list of root directories (e.g. `~/code`, `~/vault/projects`), recursively find all `.octopus/activity.md` files. Implementations:
- MUST skip directories matching common ignore patterns (`.git`, `node_modules`, `.venv`, `__pycache__`, `_archive`, `_backups`).
- SHOULD honor `.gitignore` rules when present.
- MAY define additional ignore patterns in implementation config.

### 8.2 Task cross-references

A task references another task using the form:

```
<activity-slug>/<task-slug>
```

Examples:

```yaml
waiting_for: carousel-studio/fix-export-sizing
```

```markdown
Blocked by [[shift/draft-landing-page-copy]] until pricing is validated.
```

Resolution rules:

- `<activity-slug>` matches against activity `id` by **unambiguous prefix**. `shift` resolves to `shift-a3f9` if no other activity has slug `shift-*`.
- Ambiguous prefixes MUST produce an error listing all candidates.
- The full `id` (with hash) MAY always be used and MUST always be unambiguous.
- `<task-slug>` matches against task filename without `.md`.

### 8.2.1 Resolution semantics across activity / task states

| Target state | Cross-reference resolves? | Behavior |
|---|---|---|
| Target task in any bucket folder (`backlog/`, `next/`, `now/`, `done/`, `dropped/`) | Yes | Normal resolution. Bucket changes do not break the reference because the slug is unique within the activity. |
| Target task `archived: true` | Yes | Resolves with a SHOULD-warn ("referenced task is archived"). |
| Target task in `.octopus/.trash/` | No | Resolution MUST fail with "task not found." Trash is excluded from retrieval (rule H). |
| Target activity `status: archive` | Yes | Resolves with a SHOULD-warn ("referenced activity is archived"). |
| Target activity's folder moved (path change) | Yes | The cross-reference uses `id`, not path; resolution is unaffected. |
| Target activity ID renamed | N/A | IDs are immutable. This case cannot occur. |
| Target activity or task deleted | No | Resolution MUST fail. Implementations SHOULD surface this as an integrity error on reindex. |

Implementations MUST follow these rules at read, write, and reindex time. A cross-reference to a non-resolvable target is invalid; implementations MUST surface it as an error, never silently drop or rewrite it.

### 8.3 External references — `external_refs:`

Tasks MAY carry a map of external system references:

```yaml
external_refs:
  reminders: "x-apple-reminderkit://REMCD/<uuid>"
  obsidian: "data/activities/_links/shift/tasks/fix-bug.md"
  github: "alexsmedile/octopus#42"
  todoist: "7843029174"
```

Rules:

- Keys are adapter names. Each adapter defines its own key (lowercase, hyphen-allowed).
- Values are opaque strings. The format is defined by each adapter's documentation.
- The field is omitted entirely when no external refs exist. An empty map (`external_refs: {}`) is also valid.
- Implementations MUST preserve unknown keys on read-write cycles — adapters not known to a given implementation MUST NOT have their refs stripped.

---

## 9. Activity identifiers

### 9.1 Format

```
<slug>-<4-hex-hash>
```

Where:

- `<slug>` is the slugified folder name at creation time (lowercase ASCII, hyphens, see §10).
- `<4-hex-hash>` is the first four hexadecimal characters of `sha256(absolute_path + iso8601_creation_timestamp)`.

Example: `shift-a3f9`.

### 9.2 Persistence and stability

- The `id` is written into `activity.md` frontmatter at creation time and MUST NOT change thereafter.
- Folder renames MUST NOT change the `id`. The `last_known_path` field absorbs path changes.
- Implementations MAY override the hash at creation time via user-provided `--id <slug>`, but the resulting `id` MUST still be unique within the configured roots.

### 9.3 Rename detection

The `last_known_path:` field stores the activity's path at the time of its last reindex.

On reindex:
- If the current path of an activity differs from `last_known_path`, the implementation MUST surface the difference (prompt, warning, or error — per implementation policy).
- If the user confirms the rename, `last_known_path` MUST be updated to the current path. The `id` MUST NOT change.
- Cross-references in other activities' `linked_activities:` use `id`, not paths, so renames do not break them.

### 9.4 Display rules

- Everyday user-facing output (CLI, TUI, web) SHOULD display the slug portion only (`shift`, not `shift-a3f9`).
- Machine-readable output (`--format json`, log lines, error messages on collision) MUST include the full `id`.
- An explicit user option (e.g. `--show-ids`) MUST be available to reveal full IDs on demand.

### 9.5 Collisions

If two activities share the same `id` (extremely unlikely but possible):

- Implementations MUST detect this during reindex.
- Implementations MUST surface both paths.
- Implementations MUST NOT silently choose one; user intervention is required (typically a rename).

---

## 10. Slug rules

### 10.1 Slugification algorithm

Given an input string (e.g. a task title), produce a slug by:

1. Lowercase.
2. Convert non-ASCII characters via Unicode NFKD decomposition, dropping combining marks. Other unicode (emoji, CJK) MUST be stripped.
3. Replace any non-alphanumeric sequence with a single hyphen.
4. Trim leading and trailing hyphens.
5. Trim noise words (see §10.2).
6. Truncate at the last word boundary so the slug plus `.md` extension MUST NOT exceed 50 characters total. The slug body MUST NOT exceed 47 characters.

### 10.2 Noise words

Implementations MUST trim noise words during slugification. The default list:

**English**: `a`, `an`, `the`, `of`, `to`, `for`, `in`, `on`, `at`, `with`, `and`, `or`, `but`

**Italian**: `il`, `la`, `lo`, `i`, `gli`, `le`, `un`, `una`, `di`, `da`, `in`, `con`, `su`, `per`, `e`, `o`, `ma`

Implementations MUST allow the user to override or extend the list via config.

### 10.3 Collision handling

When the resulting slug collides with an existing file in the same target directory:

- Append `-2`, `-3`, etc. to the slug body.
- If the counter would push the filename over the 50-char cap, truncate the slug body further to fit.
- Counter increments until a free name is found.

### 10.4 Examples

| Input title | Slug |
|---|---|
| `Fix the webhook auth bug` | `fix-webhook-auth-bug.md` |
| `Draft the landing page copy for the Shift launch` | `draft-landing-page-copy-shift-launch.md` |
| `Aggiornare la documentazione di Octopus per il primo rilascio` | `aggiornare-documentazione-octopus-primo.md` |
| `Fix bug` (twice in same activity) | `fix-bug.md`, `fix-bug-2.md` |

### 10.5 Validation

Implementations MUST reject:
- A slug that, after slugification, is empty (e.g. title `"!!!"`).
- A slug containing characters outside `[a-z0-9-]`.

---

## 11. Validation contract — summary

The full validation contract lives in `specs/CRITICAL-DEPENDENCIES.md`, organized as rules A through N covering all file types. This section gives the high-level summary.

### 11.1 At write time

- Implementations MUST reject files violating any MUST-reject rule across all schema docs.
- Implementations MUST enforce file naming and slug rules (see §10).
- Implementations MUST validate `id` format in `activity.md` (see §9).
- Implementations MUST enforce field-aliasing rules (`CRITICAL-DEPENDENCIES.md` rule I).

### 11.2 At read time

- Implementations MUST reject `spec_version` greater than supported.
- Implementations MUST preserve unknown frontmatter fields on read-write cycles (forward compatibility).
- Implementations MUST preserve body content byte-for-byte except when explicitly editing it.

### 11.3 At reindex time

- Implementations MUST detect ID collisions (§9.5).
- Implementations MUST detect path changes against `last_known_path` (§9.3).
- Implementations MUST exclude `.trash/` from all retrieval (`CRITICAL-DEPENDENCIES.md` rule H).

### 11.4 SHOULD-warn conditions

Per-schema warnings are documented in `CRITICAL-DEPENDENCIES.md`. Highlights:

- Task: stale `next` items, stalled `doing` tasks, haunting `backlog` items (rules E).
- Activity: stale `active` activities, near-duplicate areas (rule J).
- Session: stale open sessions, cache/file `active:` mismatches (rule K).
- Handoff: aging `open` handoffs, orphan handoffs (rule L).
- Memory: non-canonical sections, section reorder (rule M).

---

## 12. Compatibility commitments

For `spec_version: 1`:

- All required fields listed in this document remain required.
- No required field will be removed.
- No enum value will be removed.
- New enum values MAY be added in minor revisions of this document, but implementations MUST tolerate unknown values gracefully (treat as if absent, or surface as warning).
- New optional fields MAY be added.

Breaking changes (removing fields, removing enum values, changing semantics) require:

- A new `spec_version: 2`.
- A documented migration path in `PRD.md`.
- A grace period during which conformant tools support both versions.

---

## 13. Examples

### 13.1 Minimal activity

```
my-project/
└── .octopus/
    └── activity.md
```

`activity.md`:

```markdown
---
id: my-project-a3f9
title: My Project
type: other
status: active
created: 2026-05-21
last_known_path: /Users/alex/code/my-project
spec_version: 1
---

# My Project
```

### 13.2 Full activity

For complete, canonical frontmatter examples per file type, see the schema docs:

- Activity → `specs/SCHEMA-ACTIVITY.md`
- Task → `specs/SCHEMA-TASK.md`
- Session → `specs/SCHEMA-SESSION.md`
- Handoff → `specs/SCHEMA-HANDOFF.md`
- Memory → `specs/SCHEMA-MEMORY.md`

---

## 14. Changelog

- **1.0.0** (2026-05-21) — Initial release of `spec_version: 1`.

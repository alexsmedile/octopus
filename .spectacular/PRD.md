# Octopus — Product Requirements Document

Status: draft
Owner: Alessandro Smedile
Last updated: 2026-05-21

---

## 1. Problem & Vision

### The problem

Personal and professional work is scattered across many surfaces: Apple Reminders, Obsidian notes, local project folders, code repos, sticky notes, browser tabs, and chats with AI coding agents. Each surface is good at one thing and bad at the others:

- Reminders captures fast but cannot hold context.
- Obsidian holds context but is awkward to capture into on mobile.
- Local project folders contain the real work but are invisible to any system-wide overview.
- Coding agents (Claude Code, Codex) have no persistent sense of *what activity* a session belongs to or where it left off.

The result is a fractured operating layer: tasks duplicated, projects forgotten, sessions lost, and constant friction figuring out *what is alive in my world*.

### The vision

Octopus is a **filesystem-native, local-first project and task orchestration system**. It treats any folder on disk as a potential activity, stores its operational state in a self-contained `.octopus/` directory next to the work, and indexes everything into a system-wide registry that any viewer (terminal, web, Obsidian, Raycast, Claude Code) can read.

Three principles drive every decision:

1. **The folder is the activity.** Work and its operational state live together. Move the folder, the activity moves with it.
2. **The protocol, not the tool, is the product.** The `.octopus/` folder spec is plain markdown + YAML. Any future tool in any language can read it.
3. **Local-first, viewer-pluggable.** Source of truth is on disk. Obsidian, terminals, web dashboards, and coding agents are all interchangeable lenses.

---

## 2. Users & Use Cases

### Primary user

Alessandro: technical, runs many parallel projects (code repos, content, business, skill libraries), uses Obsidian as a vault, uses Apple Reminders for capture, and works with AI coding agents daily.

### Secondary users (eventual)

Anyone who:
- Lives in the terminal and works on many local projects.
- Wants persistent project/task state without depending on a SaaS.
- Already uses an editor/notes system but lacks coordination across them.
- Uses AI coding agents and wants session continuity across them.

### Use cases (v1)

| # | Use case | Today's friction | With Octopus |
|---|---|---|---|
| 1 | Start work on a project | Where did I leave off? Which task was I on? | `octopus where` → activity, last session, current task |
| 2 | Capture a task while inside a project | Open Obsidian, create note, set frontmatter | `octopus task new "fix bug"` — done |
| 3 | See everything I'm working on across the machine | Manually scan folders | `octopus list` or `octopus tui` |
| 4 | End a session with handoff context | Manual note-taking | `octopus session end` prompts for handoff summary |
| 5 | View the same data inside Obsidian | Manually maintain dashboards | `octopus link` symlinks the activity into the vault |
| 6 | Let Claude Code understand my project state | Re-explain every session | `/octopus where` in any folder, agent reads `.octopus/` |

---

## 3. Core Concepts

```
Area
└── Activity                    (a folder with .octopus/)
    ├── Outcome / Milestone     (long-arc target)
    ├── Task / Next Action      (one file in .octopus/tasks/)
    │   └── Checklist Step      (checkbox inside the task body)
    └── Session Log / Handoff   (one file in .octopus/sessions/ or /handoffs/)
```

| Concept | Definition | Where it lives |
|---|---|---|
| **Area** | Stable life/work domain (e.g. *work*, *learning*, *home*). | Tag/field on activities. No folder. |
| **Activity** | An open stream of work tied to a folder. | `<folder>/.octopus/activity.md` |
| **Outcome / Milestone** | Desired result inside an activity. | Section in `activity.md` or separate file. |
| **Task** | A concrete action with a finish line. | `<folder>/.octopus/tasks/<slug>.md` |
| **Checklist step** | Sub-step inside a task body. | Markdown checkbox in task file. |
| **Session log** | Point-in-time continuation note. | `<folder>/.octopus/sessions/<date>-<slug>.md` |
| **Handoff** | Context transfer to future-self or another agent. | `<folder>/.octopus/handoffs/<slug>.md` |
| **Memory** | Accumulated context that survives sessions. | `<folder>/.octopus/memory.md` |

Tasks have schema; checklist steps don't. That distinction is intentional — checkboxes are cheap and ephemeral; tasks are durable, queryable, and reviewable.

Full schema and routing rules: `docs/TASK_SYSTEM.md`, `docs/ROUTING_RULES.md`.

---

## 4. The `.octopus/` Folder Spec (the contract)

This is the load-bearing artifact. The CLI is an implementation; this spec is the product.

### Layout

```
<any-folder>/.octopus/
├── activity.md              # required — frontmatter + body
├── tasks/                   # optional — one file per task
│   └── <slug>.md
├── sessions/                # optional — one file per session
│   └── YYYY-MM-DD-<slug>.md
├── handoffs/                # optional
│   └── <slug>.md
├── memory.md                # optional — append-only context
└── .octopusrc               # optional — per-activity overrides (TOML)
```

All files are markdown with YAML frontmatter. No proprietary formats. Any text editor, grep, or future tool can read everything.

### `activity.md` frontmatter

```yaml
---
id: shift                       # required, slug-unique within roots
title: Shift                    # required
type: code | business | content | skill | automation | research | personal | other
status: active | next | paused | planning | maintenance | reference | archive | unknown
area: work | learning | home | ...
created: 2026-05-21
last_reviewed: 2026-05-21
source_of_truth: .              # path or URL — "." means this folder
locations:                      # additional places this activity also lives
  - ~/vault/projects/shift
linked_activities: []           # ids of related activities
tags: []
---
```

### `tasks/<slug>.md` frontmatter

Follows the existing schema in `docs/_task.schema.md`:

```yaml
---
title:
kind: task                      # task | routine | recurring | handoff | note
bucket: backlog                 # backlog | next | open | now
status: todo                    # todo | doing | done
priority: medium                # high | medium | low
due:                            # YYYY-MM-DD
scheduled:
issue:                          # blocked | waiting | dropped
waiting_for:
actor: human                    # human | ai | both
owner: alex
tags: []
archived: false
external_refs:                  # optional — pointers to this task in other systems
  reminders:                    #   e.g. "x-apple-reminderkit://REMCD/<uuid>"
  github:                       #   e.g. "alexsmedile/octopus#42"
  todoist:                      #   e.g. "7843029174"
---
```

`activity` is implicit from folder location — not a field on the task.

`external_refs:` is the cross-system identity map. Keys are adapter names (matching the bridge filename in config); values are opaque strings each adapter defines. Optional and omitted when empty. A task may carry multiple refs simultaneously (it can live in several external systems). The field exists in v1 even though only read-side adapters use it, so the schema is stable when two-way sync arrives.

### Discovery rules

- An "activity" is any folder containing `.octopus/activity.md`.
- Octopus walks **up** from cwd to find the nearest one (like git finds `.git/`).
- `octopus reindex` walks **down** from configured roots to find all of them.
- A `.octopus/` directory without `activity.md` is invalid and skipped.

### Versioning

The spec is versioned. `activity.md` may include `spec_version: 1`. The CLI checks compatibility and refuses to corrupt unknown future versions.

---

## 5. CLI Surface

### Naming

Binary: `octopus`. Short alias: `octo` (installed alongside as a second entry point — identical behavior).

### Global flags

```
--root <path>           Override cwd as starting point
--format json|table     Machine vs human output
--quiet / -q
--verbose / -v
```

### Command surface (v1 scope)

**Activity lifecycle**
```
octopus init [--type TYPE] [--title TITLE]
octopus where                         # show current activity + last session + active task
octopus list [--status active] [--type code] [--area work]
octopus status                        # detailed view of current activity
octopus rename <new-slug>
octopus archive
```

**Tasks**
```
octopus task new <title> [--bucket now] [--due 2026-06-01]
octopus task list [--bucket now] [--all]
octopus task show <slug>
octopus task edit <slug>              # opens in $EDITOR
octopus task move <slug> --bucket next
octopus task done <slug>
octopus task drop <slug>
```

**Sessions**
```
octopus session start [<title>]
octopus session log "<note>"           # append to current open session
octopus session end                    # prompts for handoff summary
octopus session list
```

**Handoffs & memory**
```
octopus handoff new <title>
octopus memory append "<note>"
octopus memory show
```

**Index & views**
```
octopus reindex                       # rebuild SQLite index from configured roots
octopus tui                           # terminal dashboard
octopus serve [--port 7777]           # web dashboard
```

**Bridges (opt-in)**
```
octopus bridge list
octopus bridge enable obsidian --vault ~/vault --link-dir data/activities/_links
octopus bridge enable reminders
octopus bridge disable <name>
octopus link [--all]                  # bridge-aware: symlinks into Obsidian vault
octopus unlink
octopus reminders pull                # if reminders bridge active
octopus reminders push <task-slug>
```

**Config**
```
octopus config show
octopus config edit
octopus config root add <path>
octopus config root remove <path>
```

### Exit codes

`0` success · `1` user error · `2` not in an activity · `3` config error · `4` bridge error.

### Output discipline

- Default output is human-readable, color-aware (NO_COLOR respected).
- `--format json` produces machine-stable JSON for piping (`jq`, scripts, agents).
- Errors go to stderr; data to stdout.

---

## 6. Viewers

### Primary: TUI (`octopus tui`)

Built with **Textual**. Default daily driver.

Panes:
- **Left**: activity list (filterable by status/area).
- **Center**: tasks for selected activity, grouped by bucket (Now / Next / Open / Backlog).
- **Right**: detail pane — task body, last session, memory excerpt.

Keys: `j/k` navigate · `Enter` open in `$EDITOR` · `n` new task · `s` start session · `/` filter · `g` reindex · `?` help.

### Secondary: Web (`octopus serve`)

v1: use Textual's built-in `textual serve` to expose the TUI over HTTP. Zero extra code.

v2: dedicated FastAPI dashboard if richer UI is justified.

### Tertiary: Bridges (other viewers)

Obsidian (via symlinks), Apple Reminders (via AppleScript), Claude Code (via plugin) — see Section 7.

### Non-goals for viewers

- No native macOS app (v1, v2).
- No mobile app — capture happens via Apple Reminders, which is already mobile-native.
- No real-time multi-user collaboration.

---

## 7. Adapters & Integrations

Octopus is the source of truth. External systems (Obsidian, Apple Reminders, GitHub, calendars, cloud task apps) are reached via **adapters** that share a common protocol. Core CLI never assumes any adapter exists; every adapter is opt-in and config-driven.

### 7.1 The Adapter protocol

Every adapter implements a small Python interface:

```python
class Adapter(Protocol):
    name: str                                       # "obsidian", "reminders", "github"
    capabilities: set[Capability]                   # subset of {READ, WRITE, NOTIFY, TWO_WAY}

    def status(self) -> AdapterStatus: ...          # health check, last-sync time, error
    def pull(self) -> list[ExternalTask]: ...       # fetch external state (READ)
    def push(self, task: OctopusTask) -> ExternalRef: ...   # write to external (WRITE)
    def link(self, octopus_id: str, ref: ExternalRef) -> None: ...  # record external_refs
```

Adapters declare their capabilities; the CLI gates commands accordingly. A read-only adapter cannot be invoked for push; a NOTIFY-only adapter (e.g. a calendar feed) cannot be invoked for sync.

### 7.2 The `external_refs:` field

Cross-system identity lives in task frontmatter (see §4):

```yaml
external_refs:
  reminders: "x-apple-reminderkit://REMCD/<uuid>"
  obsidian: "data/activities/_links/shift/tasks/fix-bug.md"
  github: "alexsmedile/octopus#42"
  todoist: "7843029174"
```

This map is the bridge between the Octopus canonical task and its mirrors in external systems. v1 only populates these refs for read-side adapters; v1.5+ uses them for two-way reconciliation.

### 7.3 v1 adapter scope

| Adapter | v1 mode | Capabilities (v1) | Future |
|---|---|---|---|
| **Obsidian** | one-way pull (view) | READ | — (no two-way ever planned; viewer is enough) |
| **Apple Reminders** | one-way pull (capture import) | READ | TWO_WAY in a later phase |
| GitHub Issues | — | — | future request, design TBD |
| ICS Calendar | — | — | future request (write-only feed) |
| Todoist / Google Tasks / Linear / Notion | — | — | community via adapter SDK in v2 |

Only Obsidian and Reminders ship in v1. Everything else is captured as a future request — explicitly non-blocking for v1.

### 7.4 Obsidian adapter (v1)

- Configured with vault path + link directory (see §13.6 for the full file-ownership contract).
- `octopus link` symlinks the current activity's `.octopus/` folder into `<vault>/<link-dir>/<activity-id>`.
- `octopus link --all` syncs every active activity.
- On `bridge enable`, writes `octopus-tasks.base` and `octopus-activities.base` (Octopus-owned, prefixed). Never touches user-authored `.base` files unless explicitly registered as a target.
- Symlinks only — no copies. Edits via Obsidian flow into the underlying `.octopus/` files directly.

### 7.5 Apple Reminders adapter (v1 — pull only)

- **Pull only in v1.** Imports a designated capture list ("Octopus Capture" by default) into the configured activity's backlog as new tasks with `bucket: backlog`, `actor: human`, and `external_refs.reminders: <uuid>`.
- Implemented via `osascript` / `shortcuts run`.
- **No push, no two-way sync in v1.** Marking a task done in Octopus does not complete the reminder. Editing in Reminders does not update Octopus.
- Configured in `~/.config/octopus/bridges/reminders.toml` with capture list name, target activity (or "ask each time"), and default fields.

### 7.6 Sync modes — deferred design

Two-way sync, conflict resolution, and the full mode taxonomy (one-way pull, one-way push, two-way, federation) are **deferred design work**, not v1 scope. The v1 framework provisions the structure (`Capability` enum, `external_refs:`, `mode:` field in adapter config) so that adding two-way later does not break the schema.

A dedicated **PRD addendum** will resolve before v1.5:

- Conflict policy per adapter: `octopus_wins | external_wins | newest_wins | ask`.
- Sync triggers: manual (`octopus sync`), scheduled, reactive — and which is default.
- Identity dedup: how a task created twice in two systems gets reconciled into one.
- Sync journal format and recovery semantics.
- Privacy/scope disclaimer for cloud adapters (task content leaves the machine).

Until that addendum lands, no two-way adapter ships.

### 7.7 Adapter SDK (v2)

Once the v1 framework proves itself with Obsidian + Reminders, the adapter interface is published as a separate Python package (`octopus-adapter-sdk`) so third parties (and future-you) can implement Todoist, Google Tasks, Linear, Notion, Raycast, Alfred, VS Code, and so on without touching the core CLI.

### 7.8 Claude Code plugin

A thin wrapper that teaches Claude how to call the CLI. Not an adapter in the §7.1 sense — it is a client of Octopus, not an external system Octopus syncs *to*. See §10 for details.

---

## 8. Architecture

### Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| CLI framework | Typer (Click under the hood) |
| TUI | Textual |
| Web | Textual `serve` (v1); FastAPI (v2 if needed) |
| Index | SQLite (stdlib) |
| Frontmatter | `python-frontmatter` |
| Config | TOML (stdlib `tomllib`) |
| Distribution (v1) | `pipx install octopus-cli` |
| Distribution (v2) | Homebrew tap; single-binary via `shiv` or `pyinstaller` |

### Why Python

1. Best TUI ecosystem (Textual is unmatched in Go/Rust/Node).
2. Mature markdown/YAML/frontmatter libraries.
3. Easiest Apple Reminders integration (subprocess to `osascript`).
4. Fastest iteration speed for a still-evolving design.
5. Consistent with vault tooling (`core/tools/` is Python).
6. **The spec, not the implementation, is the lock-in.** A Go or Rust reimplementation is welcome later; the `.octopus/` format won't change.

### System layout

```
~/.config/octopus/
├── config.toml                    # roots, viewer prefs, enabled bridges
└── bridges/
    ├── obsidian.toml
    └── reminders.toml

~/.local/share/octopus/
├── index.db                       # SQLite, derived from filesystem (sole derived store)
└── logs/

~/.cache/octopus/                  # transient: active-sessions.json, watcher.pid
```

### Index schema (SQLite)

Full authoritative schema lives in `specs/SCHEMA-INDEX.md`. Summary:

```sql
CREATE TABLE activities (
  id TEXT PRIMARY KEY,              -- <slug>-<4-hex>
  path TEXT NOT NULL UNIQUE,
  title TEXT, type TEXT, status TEXT, area TEXT,
  created DATE, last_reviewed DATE,
  raw_frontmatter TEXT,             -- JSON blob, full original frontmatter
  indexed_at DATETIME
);

CREATE TABLE tasks (
  id TEXT PRIMARY KEY,              -- activity_id + "/" + slug
  activity_id TEXT REFERENCES activities(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  slug TEXT NOT NULL,
  title TEXT,
  bucket TEXT,                      -- backlog | next | now | done | dropped
  stage TEXT,                       -- free-form
  run_state TEXT,                   -- queued | running | finished | failed | NULL
  pinned BOOLEAN,
  issue TEXT,                       -- blocked | waiting | NULL
  archived BOOLEAN,
  due DATE, scheduled DATE,
  start_date DATE, end_date DATE,
  priority TEXT,                    -- low | high | urgent | NULL (= normal)
  energy TEXT,
  actor TEXT,
  owner TEXT,
  raw_frontmatter TEXT,             -- JSON blob, full original frontmatter
  indexed_at DATETIME
);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY,              -- activity_id + "/" + filename
  activity_id TEXT REFERENCES activities(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  started DATETIME, ended DATETIME,
  title TEXT,
  raw_frontmatter TEXT,
  indexed_at DATETIME
);

CREATE INDEX idx_tasks_bucket ON tasks(bucket);
CREATE INDEX idx_tasks_pinned ON tasks(pinned);
CREATE INDEX idx_tasks_due ON tasks(due);
CREATE INDEX idx_tasks_activity ON tasks(activity_id);
CREATE INDEX idx_activities_status ON activities(status);
CREATE INDEX idx_sessions_activity ON sessions(activity_id);

PRAGMA user_version = 1;
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
```

The index is **always derivable** — `octopus reindex` rebuilds from scratch. Never edited by hand.

### Package layout

```
octopus/                            # this folder, monorepo
├── cli/                            # Python package, the system tool
│   ├── pyproject.toml
│   ├── src/octopus/
│   │   ├── __main__.py
│   │   ├── cli.py                  # Typer entrypoint
│   │   ├── core/                   # models: Activity, Task, Session
│   │   ├── fs/                     # filesystem walking + IO
│   │   ├── db/                     # SQLite index (schema, sync, queries)
│   │   ├── viewers/
│   │   │   ├── tui.py
│   │   │   └── web.py
│   │   ├── adapters/
│   │   │   ├── obsidian.py
│   │   │   └── reminders.py
│   │   └── config.py
│   └── tests/
│
├── plugin/                         # Claude Code plugin (wrapper)
│   ├── .claude-plugin/plugin.json
│   ├── skills/octopus/SKILL.md
│   ├── agents/
│   └── commands/octopus.md
│
├── .spectacular/                   # design workspace + shipped specs
│   ├── PRD.md
│   ├── SPEC.md
│   └── specs/              # SCHEMA-*.md, CLI-VERBS.md, etc.
│
└── README.md
```

---

## 9. Distribution & Install

### v1 (Alessandro + early users)

```
pipx install octopus-cli
```

Requires Python 3.11+. `pipx` installs into an isolated venv, exposes `octopus` on PATH.

### v2 (broader audience)

- Homebrew tap: `brew install alexsmedile/octopus/octopus`.
- Single-file binary via `shiv` (Python zipapp) or `pyinstaller`.
- Optional: rewrite the CLI core in Go for true single-binary distribution. The `.octopus/` spec guarantees data portability.

### Updates

`pipx upgrade octopus-cli` (v1). `octopus self-update` wrapper (v2).

### Uninstall

`pipx uninstall octopus-cli` removes the binary. User data (`~/.config/octopus`, `~/.local/share/octopus`, all `.octopus/` folders) is left untouched and can be hand-removed.

---

## 10. Claude Code Integration

A separate plugin in `plugin/` that wraps the CLI.

### Components

- **Skill** (`skills/octopus/SKILL.md`): operational decision tree, knows which CLI commands to call for which intent.
- **Command** (`commands/octopus.md`): `/octopus` slash command — passthrough to CLI with conversation context.
- **Agents**:
  - `octopus-triage` — convert raw capture into structured task.
  - `octopus-reviewer` — weekly/daily review report.
  - `octopus-scanner` — detect untracked projects across configured roots.

### Behavior

When Claude Code starts in a folder containing `.octopus/`, the skill auto-loads activity context (via `octopus where --format json`). The agent then knows: what activity, last session, active task, open handoffs. No re-explaining.

### Distribution

Plugin lives in `plugin/` and is installed via the user's chosen plugin tool (`skizl`, `apm`, manual symlink). The CLI must already be on PATH; the plugin assumes nothing else.

---

## 11. Non-Goals

Explicitly **out of scope** for v1 and v2:

- Cloud sync or multi-device sync (Git already solves this for folders that need it).
- Real-time multi-user collaboration.
- Native mobile app.
- Calendar/email integrations in v1 (ICS export, GitHub Issues, Todoist, Google Tasks, Linear, Notion are all explicitly *future requests* — not committed for v1, possible in v2 via the adapter SDK).
- **Two-way sync, conflict resolution, and any push-side adapter behavior in v1.** v1 ships read-only adapters only (Obsidian view, Reminders capture import). The full sync mode taxonomy is deferred to a PRD addendum before v1.5 — see §7.6.
- Replacing Obsidian, Apple Reminders, or any existing tool — Octopus is a coordination layer, not a competitor.
- A general-purpose "everything bucket" or wiki.
- Project management features aimed at teams (assignees beyond `owner`, permissions, comments).

---

## 12. Phased Rollout

### Phase 0 — Spec
- Finalize this PRD.
- Extract Section 4 into `docs/SPEC.md` as the canonical contract.

### Phase 1 — Walking skeleton (CLI only, no DB, no TUI)
- `octopus init`, `octopus where`, `octopus task new`, `octopus task list`, `octopus task done`.
- Pure file operations on `.octopus/` folders.
- Goal: dogfood the protocol for a week.

### Phase 2 — Index + list views
- SQLite indexer + `octopus reindex`.
- `octopus list`, `octopus status`, `octopus task list --bucket now` querying the DB.

### Phase 3 — TUI
- `octopus tui` with Textual.
- Activity list / task list / detail panes.
- Becomes the daily driver.

### Phase 4 — Sessions & memory
- `octopus session start/log/end`, `octopus memory`, `octopus handoff`.

### Phase 5 — Adapter framework + Obsidian adapter (read-only)
- `Adapter` protocol, capability enum, config-driven enable/disable.
- `external_refs:` field active on tasks (only Obsidian writes to it in this phase).
- `octopus bridge enable obsidian`, `octopus link`, generated `octopus-tasks.base` / `octopus-activities.base`.

### Phase 6 — Claude Code plugin
- Skill, command, three agents.
- Validate end-to-end Claude Code workflow.

### Phase 7 — Apple Reminders adapter (pull only)
- Pull capture list → propose tasks with `external_refs.reminders` populated.
- **No push, no two-way sync in this phase.** Marking a task done in Octopus does not complete the reminder.

### Phase 7.5 — Sync modes design (PRD addendum)
- Resolve conflict policy taxonomy, sync triggers, identity dedup, sync-journal semantics.
- Dogfood the v1 read-only adapters first; let the addendum reflect what was actually learned.
- Gate to v1.5: no two-way adapter ships until the addendum is signed off.

### Phase 8 — Two-way Reminders + Web view + polish
- Reminders push side + completion round-trip (first two-way adapter, validates the addendum).
- `octopus serve` (Textual web preview, then maybe FastAPI).
- Performance pass, tests, docs.

### Phase 9+ — Future adapters via SDK
- Publish `octopus-adapter-sdk` package.
- Land GitHub Issues, ICS calendar feed, and any community adapters that arrive.

Each phase is independently shippable.

---

## 13. Resolved Decisions

All ten v1 open questions were resolved through structured review on 2026-05-21. The decisions below are load-bearing for implementation; subsections of this PRD that conflict with them defer to this section.

### 13.1 Activity IDs

- **Format**: `<slugified-folder-name>-<4-hex-hash>`, where the hash is `sha256(absolute_path + creation_timestamp)[:4]`. Example: `shift-a3f9`.
- **Persistence**: written into `activity.md` frontmatter at `octopus init` and never changes thereafter — folder renames do not change the ID.
- **Override**: `octopus init --id <custom-slug>` accepts any unique slug.
- **Collisions**: `octopus reindex` surfaces duplicates as errors showing both paths; resolved via `octopus rename`.
- **Rename detection**: `activity.md` carries `last_known_path:`. On reindex, mismatch prompts the user to update path + cross-references. ID itself never changes.
- **Display rules**: all everyday UX shows the slug only (`shift`, not `shift-a3f9`). Full ID surfaces only in `--format json`, in `--show-ids`, in collision errors, and inside frontmatter / SQLite. CLI accepts unambiguous prefix-match (`--activity shift`).

### 13.2 Sessions

- **Multiple open sessions per activity are allowed** when work is genuinely distinct.
- **`session start` prompts** when any session is already open in the current activity, with options: `[c]` continue, `[n]` start new, `[e]` end previous and start new, `[a]` abort.
- **One active session per activity** tracked in `~/.cache/octopus/active-sessions.json`. Cache-tier — losing it loses no data, only the "which one am I in" pointer.
- **`session log "<note>"`** writes to the active session in the current activity. Errors if none open.
- **`session switch <slug>`** changes which session is active.
- **`session end`** ends the active session by default; accepts an explicit slug to end a non-active one.
- **Stale open sessions** (no activity for N days, configurable) are flagged on reindex. `octopus session prune` auto-closes them with `ended: <last_log_time>` and an auto-generated note.
- **File schema**: empty `ended:` field means open. No separate state file required.

### 13.3 Areas taxonomy

- **`area:`** is **free-form** at write time. Any string accepted; no validation at `init`.
- **`octopus reindex` warns** on near-duplicate areas (Levenshtein edit distance ≤ 2) with counts and a hint to clean up.
- **`octopus areas`** lists distinct areas with activity counts.
- **`octopus areas rename <from> <to>`** bulk-rewrites the `area:` field across activities.
- **Optional strict mode** in `~/.config/octopus/config.toml`:
  ```toml
  [areas]
  strict = true
  allowed = ["work", "personal", "learning"]
  ```
  Off by default. When on, unknown areas error at write time.
- **`type:`** remains a fixed enum (`code | business | content | skill | automation | research | personal | other`) — structural metadata, not user taxonomy.

### 13.4 Task slugs

- **Auto-slugify the title** to lowercase ASCII with hyphens.
- **Trim noise words** before slugifying. Defaults shipped for English (`a`, `an`, `the`, `of`, `to`, `for`, `in`, `on`, `at`, `with`, `and`, `or`, `but`) and Italian (`il`, `la`, `lo`, `i`, `gli`, `le`, `un`, `una`, `di`, `da`, `in`, `con`, `su`, `per`, `e`, `o`, `ma`).
- **50-char hard cap including extension** (slug body limited to 47 chars). Truncate at the last word boundary inside the budget.
- **Collision handling** within an activity: append `-2`, `-3`, etc. The counter eats into the slug budget; truncate further if needed.
- **No hash suffix** on task slugs.
- **Override**: `octopus task new "<title>" --slug <custom>`, still subject to the 50-char cap.
- **Cross-references** use `<activity-slug>/<task-slug>` in frontmatter (e.g. `waiting_for: carousel-studio/fix-export-sizing`), resolved via prefix-match against the index.
- **Noise list is overridable** in config:
  ```toml
  [slug]
  noise_words = ["a", "an", "the", "il", "la", ...]
  max_length = 50
  ```

### 13.5 Index synchronization

- **Default model**: CLI-incremental writes + stale-check-on-read.
  - Every CLI mutation updates SQLite rows directly.
  - Every CLI read does a per-file mtime check; rows whose source `.md` is newer than `indexed_at` are re-parsed inline (millisecond cost).
- **`octopus reindex`** rebuilds the full index from filesystem truth, prunes deleted rows, reparses everything. Run manually after `git pull`, bulk hand-edits, or anything that feels off.
- **`octopus watch`** is an opt-in background daemon using `watchdog` for real-time fsevents. Off by default. Lands alongside `octopus serve` in v1.5.
  - `octopus watch start | stop | status`
  - PID at `~/.cache/octopus/watcher.pid`
  - Logs at `~/.local/share/octopus/logs/watcher.log`
- **`--no-stale-check`** flag on read commands for deterministic pure-SQLite output (scripting, agents).
- **No daemon required** for v1 to feel responsive.

### 13.6 Obsidian bridge — `.base` file ownership

- **Octopus never writes to a `.base` file it does not explicitly own.**
- **Default-owned files use the `octopus-` prefix**: `octopus-tasks.base`, `octopus-activities.base`. These are regenerated freely on `bridge sync`.
- **`octopus bridge target add <path>`** registers an existing user file as Octopus-managed. First overwrite prompts and writes a timestamped backup to `.octopus-backups/`. Every subsequent regeneration also prompts unless `--auto-only` is passed (which skips targets entirely).
- **Registry** of managed files lives in `~/.config/octopus/bridges/obsidian.toml`:
  ```toml
  [managed_files]
  auto = [ "data/activities/_links/octopus-tasks.base", "..." ]
  targets = []

  [backups]
  dir = ".octopus-backups"
  keep = 10
  ```
- **Backups** are timestamped (`tasks.base.2026-05-21T14-32-00.bak`), kept to N (configurable, default 10).
- **`BRIDGE.md`** is generated as an Octopus-owned file at the link directory root, explaining the contract.
- **No marker-line trickery, no surgical YAML patching.** Ownership is determined entirely by name prefix or registry membership.
- **Commands**: `octopus bridge generate | sync | target add | target remove | backups list | backups restore`.

### 13.7 `memory.md` write model

- **Frontmatter `summary:` field** holds the human-readable summary. Set via `octopus memory summary set` (one-line) or `octopus memory summary set` without argument (opens `$EDITOR`). Append never touches it.
- **Five fixed body sections** below `<!-- octopus-managed-below -->`:
  - `## Decisions`
  - `## Open Questions`
  - `## Context`
  - `## Notes`
  - `## Log` (default target for `octopus memory append`)
- **Append-only via CLI**: `octopus memory append "<note>" [--section <name>]`. Defaults to `log`. Partial section names accepted (`--section open` matches "Open Questions").
- **CLI never edits in place** — only appends timestamped entries (`### YYYY-MM-DD HH:MM`) to the bottom of the targeted section.
- **Hand-editing fully supported** below the marker. Octopus respects existing content; future appends still go to the bottom of the matched section.
- **Marker preservation**: if `<!-- octopus-managed-below -->` is deleted, the next append re-inserts it before the first section heading with a stderr warning.
- **`last_updated:` frontmatter field** is bumped on every CLI write.
- **Not indexed in v1.** SQLite tracks only file existence and mtime. v2 may add FTS5 full-text search.

### 13.8 Claude Code plugin / CLI coupling

- **External CLI install assumed.** Plugin contains no Python code and no bundled venv.
- **Plugin is markdown + shell hooks only.** All execution is `octopus <subcommand>` via subprocess.
- **Install assistant** activates when `octopus --version` fails on plugin load:
  - `[a]` Auto-install (runs `pipx install octopus-cli` with confirmation)
  - `[m]` Show install commands for manual run
  - `[s]` Skip until next session
- **Upgrade assistant** mirrors the same pattern on version mismatch (declared in `plugin.json` as `requires.octopus-cli >= <version>`).
- **CLI-first execution rule**: skill, agents, and hooks delegate to the CLI for all state queries and mutations. LLM tokens are spent only on interpretation and synthesis (summaries, handoff prose, review reports, triage recommendations).
- **Pre-built bundle commands** for common agent flows — one shell call per intent, never four:
  - `octopus context` — current activity + last sessions + open tasks + memory summary
  - `octopus daily` — reindex + now + overdue + waiting, bundled
  - `octopus suggest` — heuristic prioritization, no LLM
- **`on-session-start` hook** runs `octopus context --format json` and injects the result as a system message so the agent starts every session with full state.
- **SKILL.md anti-pattern guard** explicitly forbids the agent from reading or writing `.octopus/` files directly via `Read`/`Write`/`Edit` — the CLI is the only legal interface.

### 13.9 Telemetry

- **None, ever.** No analytics, no error reporting, no version pings, no opt-in beacons.
- **Local logs only** in `~/.local/share/octopus/logs/`. Never transmitted.
- **`octopus diagnose`** bundles relevant logs into a zip the user can manually attach to bug reports. Shows zip contents before creating.
- **Privacy contract stated explicitly** in README, in `octopus --help`, and in `octopus config show`:
  > Octopus never sends data over the network. No telemetry. No error reporting. No analytics. No version pings.

### 13.10 License

- **License**: MIT.
- **Copyright**: `© 2026 Alessandro Smedile`.
- **File**: `LICENSE` at repo root, standard MIT text, unmodified.
- **`pyproject.toml`**: `license = "MIT"`.
- **No CLA in v1.** A contributor license agreement may be added later if and when external contributions arrive and relicensing optionality becomes valuable.
- **Rationale**: protocol-is-the-product strategy benefits most from permissive licensing; no commercial moat to defend; dependencies (Typer, Textual, etc.) are MIT/Apache-compatible.

---

## 14. References

- `docs/TASK_SYSTEM.md` — full system design (longer-form predecessor to this PRD).
- `docs/ROUTING_RULES.md` — task routing conventions.
- `docs/GLOSSARY.md` — terminology.
- `docs/_task.schema.md` — task frontmatter schema.
- `SKILL.md` — current operational skill stub.
- `/Users/alex/vault/tasks` — live task database (will be progressively folded into `.octopus/` folders).

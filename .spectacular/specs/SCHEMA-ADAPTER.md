---
status: draft
updated: 2026-05-24
relates_to: SPEC.md §7, CLI-VERBS.md, CRITICAL-DEPENDENCIES.md, SCHEMA-CONFIG.md
---

# Adapter framework — v1

This document defines the contract every external integration (Obsidian, Apple Reminders, TODO.md, future GitHub/Linear/Notion) implements. Operating verbs are in `CLI-VERBS.md`; per-adapter config layout in `SCHEMA-CONFIG.md`; validation rules in `CRITICAL-DEPENDENCIES.md`.

---

## 1. Capability enum

```python
from enum import Enum

class Capability(Enum):
    PULL = "pull"            # adapter.pull() works
    PUSH = "push"            # adapter.push() works
    NOTIFY = "notify"        # external change events (flag only in v1)
    RECONCILE = "reconcile"  # has a conflict-resolution policy (flag only in v1)
    MARK_PULLED = "mark_pulled"  # adapter annotates its source after a successful pull (D74)
```

Five atomic verbs. No `TWO_WAY` meta-capability — "two-way" is a configuration (the user enables both PULL and PUSH and accepts the reconcile policy), not an adapter property.

v1 adapters that ship as real (not stub):
- `todo-md` → `{PULL, MARK_PULLED}` — rewrites `- [ ]` lines to `- [x] → octopus:<slug>` after pull.
- `reminders` → `{PULL}` — Apple's database isn't a markdown file to annotate; round-trip is two-way push, deferred to #14.

`PUSH` and `RECONCILE` are forward-stable. `NOTIFY` is a flag-only declaration in v1; the listener machinery ships with #12 (watcher daemon).

See `DECISIONS.md D56, D74`.

---

## 2. The Adapter protocol

```python
from typing import Protocol

class Adapter(Protocol):
    name: str                                       # short identifier ("reminders")
    capabilities: set[Capability]                   # declared abilities

    def status(self) -> AdapterStatus: ...
    def validate_config(self, data: dict) -> list[str]: ...
    def list_groups(self) -> list[str]: ...
    def peek(self, groups: list[str] | None = None) -> PullResult: ...
    def pull(self, groups: list[str] | None = None) -> PullResult: ...
    def push(self, task) -> PushResult: ...
    def search(self, query: str, groups: list[str] | None = None) -> PullResult: ...

    # Optional — required only for adapters declaring MARK_PULLED (D74)
    def mark_pulled(self, mapping: dict[str, str]) -> None: ...

    # Optional — mutation verbs (D75); adapters declaring MARK_PULLED SHOULD provide
    def add_item(self, title: str, **opts) -> str: ...
    def mark_complete(self, match: str, *, first: bool = False) -> str: ...
    def mark_open(self, match: str, *, first: bool = False) -> str: ...
```

### Method reference

#### `status() -> AdapterStatus`

Health check + provenance metadata. MUST NOT touch the external system if unhealthy.

#### `validate_config(data: dict) -> list[str]`

Return a list of human-readable error messages for the given config dict. Empty list = valid. Called by `octopus bridge enable` before persisting any state.

#### `list_groups() -> list[str]`

Discover the groups (lists, repos, calendars, …) the external system currently offers. Used by `peek` discovery mode and `--capture-all` resolution.

#### `peek(groups) -> PullResult`

Read-only display. MUST NOT create files, write to the index, or modify external state. Returns `ExternalTask` entries the user would see if they pulled.

`groups=None` means "use configured defaults" (`lists` field in adapter config). When no default is configured, callers may invoke `peek` for discovery; the CLI handles that branch.

#### `pull(groups) -> PullResult`

Same semantic shape as `peek` but the framework's pipeline materializes the results as Octopus task files. The adapter doesn't write files itself — it returns data; the pipeline (`adapters/pipeline.py`) handles creation, dedup, and provenance fields.

#### `push(task) -> PushResult`

Write a single Octopus task to the external system. Returns the resulting `ExternalRef` or an error. v1 adapters return `PushResult(error="not supported")`.

#### `search(query, groups) -> PullResult`

Adapter-side search. Same result shape as `pull` but no side effects. Adapters with native search APIs use them; adapters without may implement as `peek(groups) + filter` internally.

#### `mark_pulled(mapping: dict[str, str]) -> None` *(MARK_PULLED capability only)*

Annotate the adapter's source after a successful pull. `mapping` is `{external_id → octopus_task_slug}` for items the pipeline materialized in this run.

For file-based sources (`todo-md`), this means rewriting `- [ ] thing` lines in place to `- [x] thing → octopus:<slug>`, so the file becomes an at-a-glance map of "what's in Octopus."

Idempotent: running `mark_pulled` twice with the same mapping must produce identical file output. Items already annotated must be left alone.

The framework's pipeline calls this method after `materialize_pull_result` if and only if `MARK_PULLED in adapter.capabilities`.

See `DECISIONS.md D74`.

#### `add_item(title, **opts) -> str` *(D75 mutation verb)*

Append a new item to the adapter's source. No Octopus task is created — this is direct source mutation. Returns a human-readable description of where the item was placed.

Standard `opts` accepted by all `MARK_PULLED` adapters:
- `section: str | None` — heading to append under.
- `priority: "urgent" | "low" | None` — encoded per the adapter's native syntax.
- `due: str | None` — ISO date.
- `tags: list[str]` — list of bare tag names.
- `state: "open" | "in-progress"` — initial checkbox state.

Adapter-specific options are allowed via `**opts`.

#### `mark_complete(match, first=False) -> str` *(D75 mutation verb)*

Find a matching open item by substring and toggle it to checked, in place. Raises `ValueError` if no match or if multiple matches and `first=False`.

#### `mark_open(match, first=False) -> str` *(D75 mutation verb)*

Reverse: toggle a checked item back to open. MUST strip any `→ <provider>:<slug>` arrow on the line — the item is no longer handed off.

### `link()` is NOT in the protocol

The PRD §7.1 sketch listed `link(octopus_id, ref)`; that's pipeline glue, not adapter behavior. The pipeline writes `external_refs.<adapter_name> = <ref>` to the task frontmatter after a successful pull/push.

See `DECISIONS.md D57`.

---

## 3. Data types

```python
from dataclasses import dataclass, field
from datetime import datetime

ExternalRef = str       # opaque, adapter-defined (uuid, URL, path, etc.)

@dataclass
class ExternalTask:
    external_id: str                    # becomes external_refs.<adapter>
    title: str
    body: str | None = None
    suggested_bucket: str | None = None
    suggested_kind: str | None = None
    suggested_tags: list[str] = field(default_factory=list)
    created_external: datetime | None = None
    source_group: str | None = None     # which list/repo this came from

@dataclass
class PullResult:
    tasks: list[ExternalTask] = field(default_factory=list)
    cursor: str | None = None           # opaque resume token (forward-stable)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (external_id, reason)
    errors: list[str] = field(default_factory=list)

@dataclass
class PushResult:
    ref: ExternalRef | None = None
    error: str | None = None

@dataclass
class AdapterStatus:
    name: str
    healthy: bool
    last_pull: datetime | None = None
    last_push: datetime | None = None
    error: str | None = None
    capabilities: set[Capability] = field(default_factory=set)
```

`PullResult` is also returned by `peek()` and `search()` — same shape, distinguished by which verb the user invoked (the framework, not the adapter, decides whether to materialize).

---

## 4. Config layout

Per-adapter config is split between two files for separation of concerns.

### 4.1 Enable/disable flag — main `config.toml`

```toml
# ~/.config/octopus/config.toml

[adapters.obsidian]
enabled = true

[adapters.reminders]
enabled = true

[adapters.todo-md]
enabled = false
```

Flipped by `octopus bridge enable <name>` / `octopus bridge disable <name>`.

### 4.2 Per-adapter content — `bridges/<name>.toml`

```toml
# ~/.config/octopus/bridges/reminders.toml

default_activity = "shift-abc1"     # optional; cwd activity used when absent
lists = ["Inbox", "Octopus Capture"] # default groups to pull; [] = none configured
```

Each adapter defines its own keys (Obsidian has `vault`, `link_dir`; Reminders has `lists`, `default_activity`; etc.). The framework just stores TOML; the adapter's `validate_config` enforces the shape.

### 4.3 The `lists` field convention

Adapters supporting groups (Reminders' lists, GitHub's repos, ICS's calendars) all read from a `lists` array in their per-adapter config (or an adapter-specific equivalent — but `lists` is the convention).

- `lists = []` (default) → no configured group. User must pass `--list NAME` or `--capture-all` per invocation.
- `lists = ["A"]` → single configured group.
- `lists = ["A", "B"]` → multiple configured groups.

CLI flag matrix is in `CLI-VERBS.md §bridge peek/pull/search`.

### 4.4 Lifecycle

- `octopus bridge enable obsidian --vault /path` writes BOTH the main-config `enabled = true` AND `bridges/obsidian.toml`. Adapter's `validate_config` runs first; rejection aborts with exit 3 and the error messages.
- `octopus bridge disable obsidian` flips `enabled = false`. **`bridges/obsidian.toml` is kept.** Re-enable is one command.
- `bridges/<name>.toml` without a matching main-config section is tolerated silently — parked settings.
- `enabled = true` in main config without a matching `bridges/<name>.toml` → exit 3 with hint to run `octopus bridge enable <name> --<required-flag>`.

See `DECISIONS.md D58, D59` and `SCHEMA-CONFIG.md §3`.

---

## 5. Registry

```python
# cli/src/octopus/adapters/registry.py

REGISTRY: dict[str, type[Adapter]] = {
    "obsidian": ObsidianAdapter,
    "reminders": RemindersAdapter,
    "todo-md": TodoMdAdapter,
}

def load_registry() -> dict[str, type[Adapter]]:
    """Built-in registry + any entry-point contributions."""
    from importlib.metadata import entry_points
    result = dict(REGISTRY)
    for ep in entry_points(group="octopus.adapters"):
        if ep.name in result:
            continue  # built-in wins on conflict
        try:
            result[ep.name] = ep.load()
        except Exception:
            pass  # third-party adapter broke; log + skip
    return result
```

**Built-in wins on name conflict.** Third-party adapters declaring an existing name are logged and skipped. The conflict surfaces in `octopus bridge list --verbose`.

v1 finds no entry points (no SDK published yet); the merge is a no-op. #15 (adapter SDK) makes this loader meaningful.

See `DECISIONS.md D64`.

---

## 6. Sync journal

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

- Fixed schema, no rotation in v1.
- Auto-created on first write.
- `adapter.status()` reads this to populate `last_pull` / `last_push`.
- Cursor is opaque — adapter writes via `PullResult.cursor`; framework persists; next pull reads it.

v1 adapters don't use cursors; the field is forward-stable.

`#10` (sync modes addendum) decides whether v2 grows this into a directory of per-event files.

See `DECISIONS.md D65`.

---

## 7. Pull pipeline

The framework's `pipeline.py` materializes `PullResult.tasks` into Octopus task files.

### 7.1 Activity resolution

1. `default_activity` from `bridges/<name>.toml` → use it.
2. Else: cwd's activity (`find_activity_root`) → use it.
3. Else: exit 2 with hint to either `cd` into an activity or set `default_activity`.

### 7.2 Group resolution

Per `CLI-VERBS.md`'s flag matrix:

| Config | Flag | Resolved groups |
|---|---|---|
| `lists = []` | none | discovery for `peek` only; exit 3 for `pull` |
| `lists = ["A"]` | none | `["A"]` |
| `lists = ["A","B"]` | none | `["A", "B"]` |
| any | `--list X` | `["X"]` |
| any | `--list X,Y` | `["X", "Y"]` |
| any | `--capture-all` | `adapter.list_groups()` |
| any | `--list X --capture-all` | exit 1 (mutually exclusive) |

### 7.3 Per-task materialization

For each `ExternalTask` in `PullResult.tasks`:

1. Look up `task_external_refs` for `(adapter_name, external_id)`.
2. **Match found:** record as skipped (already imported). Do NOT update the existing task in v1 — that's two-way sync, deferred to #14.
3. **No match:** create a new task with:
   - `title` = `external_task.title`
   - `bucket` = `external_task.suggested_bucket or "backlog"`
   - `kind` = `external_task.suggested_kind` (if present)
   - `tags` = `external_task.suggested_tags`
   - `actor: human`
   - `imported_from: <adapter_name>`
   - `import_date: <today>`
   - `external_refs.<adapter_name>: <external_id>`
4. Write task file, sync to index, write `task_external_refs` row.

### 7.4 Output

```
$ octopus bridge pull reminders
pulled 3 new · 7 already-known · 0 errors  (from list "Octopus Capture")
  + buy milk
  + reply to alex
  + schedule dentist
```

### 7.5 Dedup index

```sql
CREATE TABLE task_external_refs (
  task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  adapter     TEXT NOT NULL,
  external_id TEXT NOT NULL,
  PRIMARY KEY (adapter, external_id)
);
CREATE INDEX idx_task_external_refs_task ON task_external_refs(task_id);
```

Schema v2 → v3 migration:
1. `CREATE TABLE` on existing v2 DBs.
2. Backfill: scan existing tasks; for each `external_refs.<adapter>: <id>` entry, insert a row.

`upsert_task` keeps this table in sync with frontmatter on every task write.

See `DECISIONS.md D63`.

---

## 8. Stub adapter shape

```python
# cli/src/octopus/adapters/<name>.py (placeholder until #07/#09/#21)

class FooAdapter:
    name = "foo"
    capabilities = {Capability.PULL}

    def status(self) -> AdapterStatus:
        return AdapterStatus(
            name=self.name, healthy=False,
            error="Foo adapter not implemented — see request #NN",
            capabilities=self.capabilities,
        )

    def validate_config(self, data: dict) -> list[str]:
        return ["Foo adapter not implemented yet (see #NN)"]

    def list_groups(self) -> list[str]:
        return []

    def peek(self, groups=None) -> PullResult:
        return PullResult(errors=["not implemented — see request #NN"])

    def pull(self, groups=None) -> PullResult:
        return PullResult(errors=["not implemented — see request #NN"])

    def search(self, query, groups=None) -> PullResult:
        return PullResult(errors=["not implemented — see request #NN"])

    def push(self, task) -> PushResult:
        return PushResult(error="not implemented — see request #NN")
```

The framework is testable end-to-end on #06 ship. #07 (Obsidian), #09 (Reminders pull), #21 (TODO.md) each replace the stub body with a real implementation.

See `DECISIONS.md D62`.

---

## 9. Repo layout

```
cli/src/octopus/adapters/
├── __init__.py         # exports load_registry, Adapter, Capability, ExternalTask, PullResult
├── base.py             # protocol + dataclasses
├── registry.py         # hardcoded + entry-points
├── journal.py          # sync journal read/write
├── pipeline.py         # pull materialization + dedup + activity resolution
├── obsidian.py         # stub (#07)
├── reminders.py        # stub (#09)
└── todo_md.py          # stub (#21)
```

Flat modules per adapter. Promote to subpackage only when an adapter grows multi-file (osascript helpers, parsers, schema migrations).

See `DECISIONS.md D66`.

---

## 10. Reference

- `SPEC.md §7` — high-level adapter overview
- `CLI-VERBS.md` — `octopus bridge` verb reference
- `SCHEMA-CONFIG.md §3` — adapter config layout
- `CRITICAL-DEPENDENCIES.md §U` — adapter framework invariants
- `SCHEMA-INDEX.md` — `task_external_refs` table
- `DECISIONS.md D56–D66` — locked design

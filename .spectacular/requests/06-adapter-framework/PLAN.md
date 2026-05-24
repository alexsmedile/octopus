---
status: active
priority: medium
owner: alex
updated: 2026-05-24
summary: "Adapter protocol, capability enum, bridge CLI surface (list/enable/disable/status/peek/pull/search), per-adapter config + multi-list support, sync journal scaffold, dedup join table."
related:
  - 07-adapter-obsidian
  - 09-adapter-reminders-pull
  - 21-adapter-todo-md
gates:
  - 03-index-sqlite
---

# Adapter framework

## Goal

Ship the **shared protocol** every external integration implements (Obsidian, Apple Reminders, TODO.md, future GitHub/Linear/Notion), plus the CLI surface that operates them generically. This is framework-only — no working adapter ships in #06; the three known adapters (#07/#09/#21) get stub implementations that satisfy the protocol but raise `NotImplementedError`.

Critical that this lands *before* any adapter is built — designing the framework around one hardcoded bridge produces the wrong abstractions.

## Why

The current `cli/src/octopus/adapters/` directory is empty. Both #07 (Obsidian) and #09 (Apple Reminders pull) are blocked on having a shared protocol to implement against. Without #06:
- Every adapter would reinvent config loading, status reporting, and CLI surface.
- The pipeline that takes external items and creates Octopus tasks would have N implementations instead of one.
- The dedup, sync-journal, and provenance logic would diverge per adapter.

#06 absorbs all of that into one framework so each adapter implementation is small and focused on its external-system specifics.

## Locked design (from grill session 2026-05-24)

### Capability enum

```python
class Capability(Enum):
    PULL = "pull"           # adapter.pull() works
    PUSH = "push"           # adapter.push() works
    NOTIFY = "notify"       # external change events (flag only in v1; method ships with #12)
    RECONCILE = "reconcile" # has a conflict-resolution policy (flag only in v1; method ships with #10)
```

Four atomic verbs. No `TWO_WAY` meta-capability. v1 ships only `PULL` adapters; `PUSH`/`RECONCILE` are forward-stable.

### Adapter protocol

```python
class Adapter(Protocol):
    name: str
    capabilities: set[Capability]

    def status(self) -> AdapterStatus: ...
    def validate_config(self, data: dict) -> list[str]: ...        # config validation errors
    def list_groups(self) -> list[str]: ...                        # discovery (lists, repos, calendars…)
    def peek(self, groups: list[str] | None = None) -> PullResult: ...  # read-only display
    def pull(self, groups: list[str] | None = None) -> PullResult: ...  # import as Octopus tasks
    def push(self, task) -> PushResult: ...                        # write to external (stubbed v1)
    def search(self, query: str, groups: list[str] | None = None) -> PullResult: ...  # adapter-side search
```

`groups` is opaque to the framework. Each adapter interprets it (Reminders = list names, GitHub = repos, ICS = calendars). `groups=None` means "use the configured default lists." `groups=[]` is invalid and rejects.

`link()` from the PRD sketch is **removed** — it was pipeline glue, not adapter behavior. The pipeline writes `external_refs.<adapter> = <ref>` after a successful pull/push.

### Data types

```python
ExternalRef = str   # opaque, adapter-defined (uuid, URL, path, etc.)

@dataclass
class ExternalTask:
    external_id: str                              # becomes external_refs.<adapter>
    title: str
    body: str | None = None
    suggested_bucket: str | None = None           # default: backlog
    suggested_kind: str | None = None
    suggested_tags: list[str] = field(default_factory=list)
    created_external: datetime | None = None
    source_group: str | None = None               # which list/repo this came from

@dataclass
class PullResult:
    tasks: list[ExternalTask] = field(default_factory=list)
    cursor: str | None = None                     # opaque resume token
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

### Config layout

Hybrid: enable/disable in main config; per-adapter content in `bridges/<name>.toml`.

```
~/.config/octopus/
├── config.toml
│   [adapters.obsidian]
│   enabled = true
│
│   [adapters.reminders]
│   enabled = true
│
└── bridges/
    ├── obsidian.toml          # vault, link_dir
    ├── reminders.toml         # lists, default_activity
    └── todo-md.toml           # path
```

Per-adapter config supports a **`lists = []` field** (or its adapter-specific equivalent):
- `lists = []` (default) — no configured default; user must pass `--list <name>` or `--capture-all` per invocation.
- `lists = ["Inbox"]` — pull from this one list when no flag given.
- `lists = ["Inbox", "Work", "Errands"]` — pull from all three when no flag given.

### CLI surface

```
octopus bridge list                                 # show all registered adapters
octopus bridge enable <name> [adapter-flags]        # configure + turn on
octopus bridge disable <name>                       # turn off, keep config
octopus bridge status [<name>]                      # health check (all if no name)

octopus bridge peek <name> [--list NAME[,NAME...]] [--capture-all]
                                                    # READ-ONLY display; no files created
octopus bridge pull <name> [--list NAME[,NAME...]] [--capture-all]
                                                    # import as Octopus tasks; deduped
octopus bridge search <name> <query> [--list NAME] [--capture-all]
                                                    # adapter-side search; no imports
```

#### Flag matrix for peek/pull/search

| State | Behavior |
|---|---|
| `lists = []` in config, no `--list`, no `--capture-all` | Error: "no list configured; specify `--list <name>` or `--capture-all`" |
| `lists = ["A"]` in config, no flags | Pull from `A` |
| `lists = ["A", "B"]` in config, no flags | Pull from both |
| Any config, `--list "X"` | Pull from `X` (overrides config) |
| Any config, `--list "X,Y"` | Pull from `X` and `Y` |
| Any config, `--capture-all` | Pull from **every** group `list_groups()` returns |
| Both `--list` and `--capture-all` | Error: mutually exclusive |

#### Per-adapter flag naming

- Reminders: `--list` (matches Apple Reminders terminology)
- GitHub (future): `--repo`
- ICS (future): `--calendar`
- TODO.md: no flag — only one file, no concept of groups

The CLI dispatches to per-adapter Typer sub-apps; each adapter exposes the flags it cares about.

#### `bridge peek` with no group

If `lists = []` AND no `--list` AND no `--capture-all`, **`peek` discovers**: prints what groups the adapter can see. This makes `peek` the natural exploration tool:

```
$ octopus bridge peek reminders
no default list configured. Available lists:
  - Inbox
  - Octopus Capture
  - Errands
  - Work

Specify --list <name> to peek into one, or --capture-all to peek into every list.
```

`pull` in the same state errors hard (would create unbounded files).

### Adapter registry

Hybrid hardcoded + entry-points:

```python
REGISTRY: dict[str, type[Adapter]] = {
    "obsidian": ObsidianAdapter,
    "reminders": RemindersAdapter,
    "todo-md": TodoMdAdapter,
}

def load_registry() -> dict[str, type[Adapter]]:
    """Built-in registry + any entry-point contributions (v2+)."""
    from importlib.metadata import entry_points
    result = dict(REGISTRY)
    for ep in entry_points(group="octopus.adapters"):
        try:
            result[ep.name] = ep.load()
        except Exception:
            pass  # third-party adapter broke; log + skip
    return result
```

Built-in wins on name conflict.

### Sync journal

Minimal v1 — one JSON per adapter at `~/.local/share/octopus/sync/<name>.json`:

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

No event-level history in v1. #10 (sync modes addendum) will decide whether to grow this into a directory of per-event files.

### Pull pipeline behavior

1. Resolve target activity:
   - `default_activity` from bridge config → that activity.
   - Else: cwd's activity if any.
   - Else: error exit 2 with hint.
2. Resolve groups (per flag matrix above).
3. Call `adapter.pull(groups=...)`.
4. For each `ExternalTask` in `result.tasks`:
   - Look up `task_external_refs` for `(adapter_name, external_id)`.
   - **Match found** → skip; record in pipeline output.
   - **No match** → create new task with:
     - `title` = external_task.title
     - `bucket` = external_task.suggested_bucket or `"backlog"`
     - `kind` = external_task.suggested_kind (if any)
     - `tags` = external_task.suggested_tags
     - `actor: human` (per PRD §7.5)
     - `imported_from: <adapter_name>`
     - `import_date: <today>`
     - `external_refs.<adapter_name>: <external_id>`
     - `source_group` (if multi-list) recorded in `tags` or in a comment block
5. Update sync journal: `last_pull`, increment `pull_count`, store `cursor` if returned.
6. Print summary: `pulled N new · M already-known · K errors (from G group(s))`.

### Dedup index

New SQLite table (schema v2 → v3 migration):

```sql
CREATE TABLE task_external_refs (
  task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  adapter     TEXT NOT NULL,
  external_id TEXT NOT NULL,
  PRIMARY KEY (adapter, external_id)
);
CREATE INDEX idx_task_external_refs_task ON task_external_refs(task_id);
```

`upsert_task` populates from `task.external_refs`. Reindex rebuilds.

Pipeline dedup query (fast indexed lookup):
```sql
SELECT task_id FROM task_external_refs
WHERE adapter = ? AND external_id = ?
```

### Error model / exit codes

Per PRD §5 conventions:

| Scenario | Exit |
|---|---|
| Success (any items processed) | 0 |
| Successful with skipped (dedup) | 0 |
| Adapter not configured (`bridges/<name>.toml` missing) | 3 |
| Adapter disabled | 3 |
| `--list` flag value not found in `list_groups()` | 3 |
| Adapter doesn't declare `PULL` (or relevant) capability | 1 |
| Adapter `status()` unhealthy (e.g. macOS-only adapter on Linux) | 4 |
| Adapter raises uncaught exception | 4 |
| All items failed (PullResult.tasks empty AND errors non-empty) | 4 |
| Target activity unresolvable | 2 |
| `--list X` AND `--capture-all` both passed | 1 |
| `lists=[]` AND no flag AND `pull` (not `peek`) | 3 |

### Stub adapters

#06 ships `obsidian.py` / `reminders.py` / `todo_md.py` as **honest stubs**:

```python
class ObsidianAdapter:
    name = "obsidian"
    capabilities = {Capability.PULL}

    def status(self) -> AdapterStatus:
        return AdapterStatus(
            name=self.name, healthy=False,
            error="Obsidian adapter not implemented — see request #07",
            capabilities=self.capabilities,
        )

    def validate_config(self, data: dict) -> list[str]:
        return ["Obsidian adapter not implemented yet (see #07)"]

    def list_groups(self) -> list[str]:
        return []

    def peek(self, groups=None) -> PullResult:
        return PullResult(errors=["not implemented — see request #07"])

    def pull(self, groups=None) -> PullResult:
        return PullResult(errors=["not implemented — see request #07"])

    def search(self, query: str, groups=None) -> PullResult:
        return PullResult(errors=["not implemented — see request #07"])

    def push(self, task) -> PushResult:
        return PushResult(error="not implemented — see request #07")
```

`octopus bridge list` shows them as disabled-and-unhealthy; the framework is testable end-to-end.

## Repo layout

```
cli/src/octopus/adapters/
├── __init__.py         # exports load_registry, Adapter, Capability, ExternalTask, PullResult
├── base.py             # protocol + dataclasses
├── registry.py         # hardcoded + entry-points
├── journal.py          # sync journal read/write
├── pipeline.py         # pull → tasks materialization, dedup, activity resolution
├── obsidian.py         # stub (#07)
├── reminders.py        # stub (#09)
└── todo_md.py          # stub (#21)
```

## Approach

1. **Spec mirror first** — write `SCHEMA-ADAPTER.md` to `.spectacular/specs/` capturing protocol + dataclasses + config layout.
2. **Skill mirror** — `skills/octopus/references/adapter-framework.md` with the operational version (CLI flow + verb reference).
3. **Code: base + registry + journal + dedup table** before any CLI work.
4. **CLI: `octopus bridge` subcommand group** with all seven verbs.
5. **Per-adapter Typer sub-apps** for `enable` flags.
6. **Pipeline: pull materialization + dedup**.
7. **Stub adapters**: obsidian.py, reminders.py, todo_md.py.
8. **Tests**: protocol conformance, registry, journal, pipeline (mock adapter), every CLI path.
9. **DECISIONS entries** for the choices locked in the grill.

## Out of scope (this request)

- **Watch mode** (live tail, daemon, subscription) — deferred to #12 (watcher daemon).
- **NOTIFY method** — capability flag only in v1; method ships with #12.
- **RECONCILE method** — capability flag only; ships with #10.
- **Cross-adapter `--all` search/pull** — `octopus bridge search --all` deferred. v1 is one-adapter-at-a-time.
- **Per-event sync journal entries** — minimal counter+timestamp file in v1; rich event log ships with #10.
- **`octopus link`** verb — Obsidian-specific; ships with #07.
- Working `pull()` / `peek()` / `search()` for any adapter. v1 stubs only — #07/#09/#21 implement.

## Deliverables

- [ ] `cli/src/octopus/adapters/base.py` — protocol, enum, dataclasses
- [ ] `cli/src/octopus/adapters/registry.py` — hardcoded + entry-points loader
- [ ] `cli/src/octopus/adapters/journal.py` — sync journal read/write
- [ ] `cli/src/octopus/adapters/pipeline.py` — pull materialization + dedup
- [ ] `cli/src/octopus/adapters/{obsidian,reminders,todo_md}.py` — stubs
- [ ] `cli/src/octopus/db/schema.sql` — `task_external_refs` table (schema v3 migration)
- [ ] `cli/src/octopus/db/upsert.py` — populate `task_external_refs` from `external_refs`
- [ ] `cli/src/octopus/cli.py` — `bridge list|enable|disable|status|peek|pull|search` commands
- [ ] `cli/src/octopus/config.py` — adapter config loading + `lists` field handling
- [ ] `.spectacular/specs/SCHEMA-ADAPTER.md` — formal spec
- [ ] `skills/octopus/references/adapter-framework.md` — skill-side mirror
- [ ] Tests: `tests/test_adapters_base.py`, `tests/test_adapters_registry.py`, `tests/test_adapters_journal.py`, `tests/test_adapters_pipeline.py`, `tests/test_cli_bridge.py`
- [ ] D-entries in `DECISIONS.md` locking the design

## Locked design decisions (preview — to be assigned D-numbers on commit)

1. Capability enum: `{PULL, PUSH, NOTIFY, RECONCILE}` — atomic verbs only.
2. Adapter protocol: `status / validate_config / list_groups / peek / pull / push / search`. No `link()`.
3. Config split: enable flag in main config; per-adapter content in `bridges/<name>.toml`.
4. `bridge enable` is non-destructive; settings persist on disable.
5. Verb noun: `bridge` (not `adapter`); hidden alias `adapter` honored.
6. Per-adapter Typer sub-apps for `enable` flags.
7. Stub adapters ship in #06; #07/#09/#21 replace stub bodies.
8. `peek` ≠ `pull`: peek is read-only display, pull creates files.
9. Multi-list config (`lists = []`) + `--list NAME[,NAME...]` flag + `--capture-all` override.
10. `peek` with no group + no default = discovery (lists available groups).
11. `pull` with no group + no default = error exit 3.
12. Per-adapter flag names (`--list`, `--repo`, etc.) — no generic `--group`.
13. `octopus bridge search` is a dedicated verb; adapters with no native search fall back to peek+filter.
14. NOTIFY and RECONCILE: capability flags only in v1; methods ship with #12 / #10.
15. Pull pipeline: dedup via `task_external_refs` join table (schema v3).
16. Pulled tasks: `actor: human`, `imported_from: <adapter>`, `import_date: today`, `bucket: backlog` (unless suggested), `external_refs.<adapter>: <external_id>`.
17. Sync journal: minimal JSON per adapter with `last_pull`, `last_push`, counters, cursor.
18. Adapter registry: hardcoded built-in + entry-point overlay (v2+). Built-in wins on conflict.
19. Repo layout: flat modules under `cli/src/octopus/adapters/`.
20. Exit codes follow PRD §5 — 0/1/2/3/4. No new codes.

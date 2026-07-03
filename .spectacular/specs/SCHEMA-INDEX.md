---
status: draft
updated: 2026-07-03
schema_version: 6
relates_to: SPEC.md, SCHEMA-TASK.md, SCHEMA-ACTIVITY.md, SCHEMA-SESSION.md, CLI-VERBS.md, CRITICAL-DEPENDENCIES.md
---

# SQLite index schema — v6

The derived index at `~/.local/share/octopus/index.db`. Source of truth is the filesystem; the index is rebuildable at any time via `octopus reindex`.

This document specifies:
1. The SQLite schema (DDL).
2. ID conventions.
3. Sync semantics (incremental + stale-check + full reindex).
4. Migration policy.
5. Performance contract.

---

## 1. Location

- Path: `~/.local/share/octopus/index.db`
- WAL files: `index.db-wal`, `index.db-shm` (sibling, managed by SQLite).
- Logs: `~/.local/share/octopus/logs/reindex.log`.
- The index file may be deleted at any time. The next CLI command rebuilds from the configured roots.

The system-wide DB at this single path is the only derived store. There is **no** `registry.json` (dropped per DECISIONS D40).

---

## 2. Schema (DDL)

```sql
-- Activities: one row per discovered .octopus/activity.md
CREATE TABLE activities (
  id              TEXT    PRIMARY KEY,        -- <slug>-<4-hex>
  path            TEXT    NOT NULL UNIQUE,    -- absolute folder path
  title           TEXT,
  type            TEXT,                       -- code | business | content | …
  status          TEXT,                       -- active | next | paused | …
  area            TEXT,
  created         DATE,
  last_reviewed   DATE,
  raw_frontmatter TEXT,                       -- JSON blob of the full frontmatter
  indexed_at      DATETIME NOT NULL,
  priority        TEXT,                       -- v4 (D87): low | high | urgent | NULL
  last_touched_at DATETIME                    -- v4 (D88): last mutation, feeds ranking
);

-- Tasks: one row per tasks/<slug>.md
CREATE TABLE tasks (
  id              TEXT    PRIMARY KEY,        -- <activity_id>/<slug>
  activity_id     TEXT    NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  path            TEXT    NOT NULL,           -- absolute file path
  slug            TEXT    NOT NULL,           -- filename without .md
  title           TEXT,
  bucket          TEXT,                       -- backlog | next | now | done | dropped
  stage           TEXT,                       -- free-form
  run_state       TEXT,                       -- queued | running | finished | failed | NULL
  pinned          BOOLEAN,
  issue           TEXT,                       -- blocked | waiting | NULL
  archived        BOOLEAN,
  due             DATE,
  scheduled       DATE,
  start_date      DATE,
  end_date        DATE,
  priority        TEXT,                       -- low | high | urgent | NULL (= normal)
  energy          TEXT,
  actor           TEXT,                       -- human | ai | automation | NULL (= human)
  owner           TEXT,
  raw_frontmatter TEXT,                       -- JSON blob of the full frontmatter
  indexed_at      DATETIME NOT NULL,
  kind            TEXT,                       -- v2 (D46): task | request | …
  promoted_to     TEXT,                       -- v2 (D48): activity ID a request promoted into
  parent          TEXT,                       -- v5 (D104): parent task slug (subtask graph)
  subtasks        TEXT,                       -- v6: JSON array of child slugs (derived)
  blocked_by      TEXT,                       -- v6: JSON array of blocking task refs
  waiting_for     TEXT,                       -- v6: JSON array of external waits
  UNIQUE(activity_id, slug)
);

-- Sessions: one row per sessions/<file>.md
CREATE TABLE sessions (
  id              TEXT    PRIMARY KEY,        -- <activity_id>/<filename_without_md>
  activity_id     TEXT    NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  path            TEXT    NOT NULL,
  title           TEXT,
  started         DATETIME,
  ended           DATETIME,                   -- NULL = open
  raw_frontmatter TEXT,
  indexed_at      DATETIME NOT NULL
);

-- External refs dedup table (schema v3, D63)
CREATE TABLE task_external_refs (
  task_id     TEXT     NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  adapter     TEXT     NOT NULL,
  external_id TEXT     NOT NULL,
  PRIMARY KEY (adapter, external_id)
);

-- Indexes for query-shaped reads
CREATE INDEX idx_tasks_bucket           ON tasks(bucket);
CREATE INDEX idx_tasks_pinned           ON tasks(pinned);
CREATE INDEX idx_tasks_due              ON tasks(due);
CREATE INDEX idx_tasks_activity         ON tasks(activity_id);
CREATE INDEX idx_tasks_kind             ON tasks(kind);          -- v2 (D46)
CREATE INDEX idx_tasks_promoted_to      ON tasks(promoted_to);   -- v2 (D48)
CREATE INDEX idx_tasks_parent           ON tasks(parent);        -- v5 (D104)
CREATE INDEX idx_activities_status      ON activities(status);
CREATE INDEX idx_activities_priority    ON activities(priority);       -- v4 (D87)
CREATE INDEX idx_activities_last_touch  ON activities(last_touched_at);-- v4 (D88)
CREATE INDEX idx_sessions_activity      ON sessions(activity_id);
CREATE INDEX idx_sessions_ended         ON sessions(ended);  -- NULL filter for open sessions
CREATE INDEX idx_task_external_refs_task ON task_external_refs(task_id);

-- v6: composite + partial indexes for the hot list/next queries
CREATE INDEX idx_tasks_activity_bucket
  ON tasks(activity_id, bucket, archived, pinned DESC, due, slug);
CREATE INDEX idx_tasks_open
  ON tasks(bucket, activity_id, pinned DESC, due, slug)
  WHERE bucket NOT IN ('done', 'dropped')
    AND (archived IS NULL OR archived = 0);

-- Pragmas applied on every connection open
PRAGMA user_version  = 6;     -- see §5 for the v1→v6 migration chain
PRAGMA journal_mode  = WAL;
PRAGMA foreign_keys  = ON;
```

### Column notes

- **`raw_frontmatter`**: JSON-encoded original frontmatter (after read-time aliasing resolution). Lets adapters / future tools read fields that aren't columnized. Forward-compat insurance.
- **`indexed_at`**: set on every upsert. Used for stale-check (compare against file `mtime`).
- **Booleans** (`pinned`, `archived`): stored as `0` or `1`. `NULL` means absent.
- **`actor`, `priority`**: `NULL` means default (`human`, normal). The columns match the file's default-omission principle.
- **`bucket`**: always populated (it's required in the file too).

### Trash exclusion

Files under `.octopus/.trash/` MUST NOT be inserted into the index. The reindexer skips that directory tree entirely (`CRITICAL-DEPENDENCIES.md` rule H).

---

## 3. ID conventions

| Table | ID format | Stability |
|---|---|---|
| `activities` | `<slug>-<4-hex>` (e.g. `shift-a3f9`) | Immutable from creation. Folder renames update `path`, not `id`. |
| `tasks` | `<activity_id>/<slug>` (e.g. `shift-a3f9/fix-bug`) | Slug is the filename (sans `.md`). Bucket moves don't change the ID. |
| `sessions` | `<activity_id>/<filename>` (e.g. `shift-a3f9/2026-05-22-debug`) | Filename includes date prefix. |

### Slug stability under bucket moves

In folder mode, when a task moves between bucket folders (e.g. `next/fix-bug.md` → `done/fix-bug.md`):
- The **slug** stays the same.
- The **task ID** stays the same.
- Only `tasks.path` and `tasks.bucket` are updated in the DB.

This means cross-references like `shift/fix-bug` resolve identically regardless of which bucket the task is currently in.

---

## 4. Sync semantics

There are three sync paths.

### 4.1 CLI-incremental writes

Every mutation verb (`capture`, `plan`, `focus`, `park`, `defer`, `start`, `finish`, `drop`, `block`, `wait`, `unblock`, `pin`, `unpin`, `archive`, `restore`, `set`) MUST update the corresponding index row after the file write, in the same process.

Order:
1. Write file to disk.
2. Upsert row in SQLite with new `indexed_at`.
3. Print result.

If step 2 fails (DB locked, schema mismatch), the file write stands but a warning surfaces. The next `octopus reindex` reconciles.

### 4.2 Stale-check-on-read

Read commands (`octopus list`, `octopus status`, `octopus task list`, `octopus loops`, etc.) operate against the index, but stat() each row's source file and compare `mtime` against `indexed_at`. If `mtime > indexed_at`:
1. Re-parse the file.
2. Upsert the row.
3. Continue with the updated data.

This catches edits made by hand in `$EDITOR`, by Obsidian, or by `git pull`.

**Granularity**: stale-check applies to the rows about to be displayed, not the whole table. A filter `bucket=now` only stats now-bucket rows.

**Opt-out**: `--no-stale-check` skips the mtime comparison entirely. Returns pure SQLite reads. Useful for scripts and agents that need deterministic output.

### 4.3 Full reindex

`octopus reindex` does the following:

1. Walk configured roots (`config.toml [roots] paths`).
2. For each `.octopus/activity.md` found:
   - Upsert the activity row.
   - For each file in `tasks/**/*.md`: upsert task row.
   - For each file in `sessions/*.md`: upsert session row.
3. **With `--prune`**: delete any rows whose `path` no longer exists on disk.
4. Detect ID collisions (two activities sharing the same ID — surfaces both paths, exit code 4).
5. Detect renames (activity's `path` differs from the file's `last_known_path`).

Reindex is idempotent. Running it twice in a row writes the same rows.

### 4.4 Empty index hint

If a read command targets an empty index (e.g. `octopus list` after fresh install), the CLI MUST emit:

```
no activities indexed.
Run `octopus reindex` to scan configured roots.
```

Exit code 0. The hint avoids the "is something broken?" UX.

### 4.5 Missing-source-file behavior

If stale-check finds a row whose source file no longer exists:

1. **Warn** to stderr: `⚠ task <slug>: source file missing at <path> — run reindex --prune to clean up`.
2. **Keep the row** in the index (do not silently delete).
3. **Continue** with the operation; the row appears in output but is flagged.

`octopus reindex --prune` is the explicit cleanup. Silent deletion is forbidden — it would mask user error (e.g. accidental `mv` outside the CLI).

### 4.6 Default-roots policy

Default config ships with `[roots] paths = []` (empty list).

- First `octopus reindex` without roots configured → error: `no roots configured; add one with: octopus config root add <path>`. Exit code 3.
- AI-agent contexts (non-TTY callers) detect the error and surface it to the user.
- Once any root is added, `reindex` proceeds normally.
- Roots whose paths don't exist on disk: skip silently, warn at end of reindex if **any** were skipped.

### 4.7 Interactive vs non-interactive reindex

`octopus reindex` behaves differently based on whether stdin is a TTY:

| Context | Behavior |
|---|---|
| Interactive TTY | Prompts y/N on rename detection. Asks for confirmation before destructive actions (e.g., `--prune` in v2 might warn before deleting many rows). |
| Non-interactive (pipe, agent, CI) | Never prompts. Honors flags only: `--prune` forces rename acceptance + deletion. Without `--prune`, renames are detected but not applied; collisions still exit 4. |

This means AI agents call `octopus reindex --prune --format json` and parse the structured output. Humans call `octopus reindex` and get prompts.

---

## 5. Migration policy

Migrations run **in-place** on every connection open (`db/connection.py`), forward-chained: each block reads `PRAGMA user_version`, applies its `ALTER TABLE` / `CREATE` statements, and bumps `user_version` by one. A fresh DB is created at the current `SCHEMA_VERSION` directly; an existing DB is walked up one version at a time. No drop-and-rebuild is required for a schema bump — though deleting `index.db` and running `octopus reindex` is always a valid recovery, since the index is fully derivable.

Migration chain to date (`SCHEMA_VERSION = 6`):

| From→To | Decision | Change |
|---|---|---|
| 1→2 | D46/D48 | `tasks.kind`, `tasks.promoted_to` + their indexes |
| 2→3 | D63 | `task_external_refs` join table (adapter dedup) |
| 3→4 | D87/D88 | `activities.priority`, `activities.last_touched_at` + their indexes |
| 4→5 | D104 | `tasks.parent` (subtask graph) + `idx_tasks_parent` |
| 5→6 | — | `tasks.subtasks`, `tasks.blocked_by`, `tasks.waiting_for` + composite/partial task indexes |

Rules:
- If the CLI opens an index with `user_version > SCHEMA_VERSION` (DB written by a newer CLI), it MUST refuse rather than corrupt it — see `connection.py`.
- The index file is **always derivable**. Users should never fear losing it.

---

## 6. Performance contract

| Scenario | Target |
|---|---|
| `octopus reindex` cold (1000 tasks across 50 activities) | < 2 seconds |
| `octopus list` warm (any size up to ~10k rows) | < 100ms |
| `octopus where` (file-native, NOT index-backed) | < 50ms |
| Per-mutation index update | < 10ms |
| Stale-check on a single row | < 5ms (one stat call + maybe one parse) |

Measured on macOS APFS / SSD. Linux ext4 / btrfs should be comparable.

---

## 7. What the index is NOT

- **Not the source of truth.** The filesystem is. The index is regenerable.
- **Not user-editable.** Hand-editing `index.db` is unsupported. Use the CLI.
- **Not shared across machines.** Each machine has its own index, derived from its filesystem.
- **Not indexed for full-text search.** Memory/handoff bodies aren't full-text indexed in v1 (deferred to v2 via FTS5).

---

## 8. `octopus where` is file-native, not index-backed

`octopus where` walks up from cwd, reads the single `activity.md` directly, and prints it. It does NOT consult the index.

Rationale:
- The cost is microseconds (one file read).
- `where` works even when the index is missing, broken, or stale.
- Removes a dependency from the most-frequently-invoked command.

This is a deliberate exception. Every other read command (`list`, `status`, `task list`, `loops`, etc.) uses the index.

---

## 9. Sessions table population (v1 scope)

In v1, `octopus reindex` MUST populate the `sessions` table by walking `sessions/*.md` files in each activity. There is no v1 verb that *reads* from this table (session commands land in request 04), but the schema is exercised so request 04 doesn't need a re-reindex.

If session frontmatter is malformed during reindex:
- Log a warning to `~/.local/share/octopus/logs/reindex.log`.
- Skip the file (do not insert).
- Continue with other files.

---

## 10. Reference

- `../SPEC.md` — on-disk contract (this is the derived view of that).
- `SCHEMA-TASK.md`, `SCHEMA-ACTIVITY.md`, `SCHEMA-SESSION.md` — the file schemas that populate this index.
- `CLI-VERBS.md` — verbs that mutate the index and views that read it.
- `CRITICAL-DEPENDENCIES.md` — index consistency rules.
- `PRD.md §8` — architectural summary (points here for the authoritative schema).

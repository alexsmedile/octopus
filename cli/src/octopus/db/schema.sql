-- Octopus index schema v1
-- Authoritative: .spectacular/current/specs/SCHEMA-INDEX.md
-- Apply pragmas (journal_mode, foreign_keys) on every connection open,
-- not here — they are connection-scoped.

CREATE TABLE IF NOT EXISTS activities (
  id              TEXT     PRIMARY KEY,
  path            TEXT     NOT NULL UNIQUE,
  title           TEXT,
  type            TEXT,
  status          TEXT,
  area            TEXT,
  priority        TEXT,                -- D87 (low|high|urgent; NULL = normal)
  created         DATE,
  last_reviewed   DATE,
  last_touched_at DATETIME,            -- D88 most-recent write within activity
  raw_frontmatter TEXT,
  indexed_at      DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  id              TEXT     PRIMARY KEY,
  activity_id     TEXT     NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  path            TEXT     NOT NULL,
  slug            TEXT     NOT NULL,
  title           TEXT,
  bucket          TEXT,
  stage           TEXT,
  run_state       TEXT,
  pinned          BOOLEAN,
  issue           TEXT,
  archived        BOOLEAN,
  due             DATE,
  scheduled       DATE,
  start_date      DATE,
  end_date        DATE,
  priority        TEXT,
  energy          TEXT,
  actor           TEXT,
  owner           TEXT,
  kind            TEXT,   -- D46 work-classification (soft enum)
  promoted_to     TEXT,   -- D48 "<provider>:<identifier>" — presence = promoted
  parent          TEXT,   -- D104 slug of parent task (activity-scoped, 1-level max)
  subtasks        TEXT,   -- D104 JSON list of child slugs (derived, managed by reindex)
  blocked_by      TEXT,   -- impediment detail (promoted from raw_frontmatter)
  waiting_for     TEXT,   -- impediment detail (promoted from raw_frontmatter)
  raw_frontmatter TEXT,
  indexed_at      DATETIME NOT NULL,
  UNIQUE(activity_id, slug)
);

CREATE TABLE IF NOT EXISTS sessions (
  id              TEXT     PRIMARY KEY,
  activity_id     TEXT     NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  path            TEXT     NOT NULL,
  title           TEXT,
  started         DATETIME,
  ended           DATETIME,
  raw_frontmatter TEXT,
  indexed_at      DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_bucket       ON tasks(bucket);
CREATE INDEX IF NOT EXISTS idx_tasks_pinned       ON tasks(pinned);
CREATE INDEX IF NOT EXISTS idx_tasks_due          ON tasks(due);
CREATE INDEX IF NOT EXISTS idx_tasks_activity     ON tasks(activity_id);
CREATE INDEX IF NOT EXISTS idx_tasks_kind         ON tasks(kind);
CREATE INDEX IF NOT EXISTS idx_tasks_promoted_to  ON tasks(promoted_to);
CREATE INDEX IF NOT EXISTS idx_tasks_parent       ON tasks(parent);

-- Fix 1: composite covering index for tasks_for_activity (eliminates temp B-tree sort).
-- Covers: activity_id filter + archived guard + bucket filter + sort (pinned, priority, due, slug).
CREATE INDEX IF NOT EXISTS idx_tasks_activity_bucket
  ON tasks(activity_id, bucket, archived, pinned DESC, due, slug);

-- Fix 2: partial index for open tasks (fixes SCAN in loops / tasks_all).
-- Only indexes rows that are not done/dropped and not archived — keeps the index small.
CREATE INDEX IF NOT EXISTS idx_tasks_open
  ON tasks(bucket, activity_id, pinned DESC, due, slug)
  WHERE bucket NOT IN ('done', 'dropped') AND (archived IS NULL OR archived = 0);

-- External refs dedup index (schema v3, D63)
CREATE TABLE IF NOT EXISTS task_external_refs (
  task_id     TEXT     NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  adapter     TEXT     NOT NULL,
  external_id TEXT     NOT NULL,
  PRIMARY KEY (adapter, external_id)
);
CREATE INDEX IF NOT EXISTS idx_task_external_refs_task ON task_external_refs(task_id);
CREATE INDEX IF NOT EXISTS idx_activities_status     ON activities(status);
CREATE INDEX IF NOT EXISTS idx_activities_priority   ON activities(priority);
CREATE INDEX IF NOT EXISTS idx_activities_last_touch ON activities(last_touched_at);
CREATE INDEX IF NOT EXISTS idx_sessions_activity     ON sessions(activity_id);
CREATE INDEX IF NOT EXISTS idx_sessions_ended        ON sessions(ended);

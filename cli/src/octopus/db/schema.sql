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
  created         DATE,
  last_reviewed   DATE,
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

-- External refs dedup index (schema v3, D63)
CREATE TABLE IF NOT EXISTS task_external_refs (
  task_id     TEXT     NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  adapter     TEXT     NOT NULL,
  external_id TEXT     NOT NULL,
  PRIMARY KEY (adapter, external_id)
);
CREATE INDEX IF NOT EXISTS idx_task_external_refs_task ON task_external_refs(task_id);
CREATE INDEX IF NOT EXISTS idx_activities_status  ON activities(status);
CREATE INDEX IF NOT EXISTS idx_sessions_activity  ON sessions(activity_id);
CREATE INDEX IF NOT EXISTS idx_sessions_ended     ON sessions(ended);

# D104 — Subtask graph: 1-level-deep parent/child task relationships

- `parent: <slug>` on a child task is the **source of truth** (activity-scoped slug only, no `/`).
- `subtasks: [slug, ...]` on a parent is a **derived managed index** — rebuilt by CLI on every write that changes parent/child relationships; never hand-edited.
- Maximum nesting depth is **1**. A task with `parent:` set cannot also have `subtasks:`. Validated at model level + `subtask-depth` lint rule.
- Slug uniqueness remains activity-scoped (D4); no special collision logic for subtasks.
- Cross-activity parent references (containing `/`) are structurally invalid: `subtask-cross-activity` lint rule fires ERROR.
- `finish`/`drop` on a parent with open children returns `OpenSubtasksWarning` (non-exception). CLI exits with user-error unless `--force` or `--cascade` is passed.
  - `--force`: proceeds on parent only; children are orphaned (parent link preserved historically).
  - `--cascade`: finishes/drops all open children first, then the parent. Children keep their `parent:` field post-cascade.
- **CLI verbs**: `capture --parent <slug>`, `add task --parent <slug>`, `set --parent <slug>` (attach), `set --parent ""` (detach), `subtasks <slug>` (list children), `finish/drop --force/--cascade`.
- **DB**: `parent TEXT` added as explicit column (schema v5 migration) for efficient querying. `subtasks:` not a column — read from `raw_frontmatter` JSON.
- Reindex rebuilds `subtasks:` lists from `parent:` fields post-scan.

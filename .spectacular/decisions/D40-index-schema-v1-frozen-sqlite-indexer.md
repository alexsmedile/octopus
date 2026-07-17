# D40 — Index schema v1 frozen; SQLite indexer shipped (request 03)

- `~/.local/share/octopus/index.db` schema (activities/tasks/sessions) per `specs/SCHEMA-INDEX.md` frozen at `PRAGMA user_version = 1`.
- Python package is `cli/src/octopus/db/` (chosen over `index/` to avoid clash with `list.index`).
- Sync model: CLI-incremental upsert after every mutation verb + stale-check-on-read (mtime vs `indexed_at`); `--no-stale-check` opts out.
- `octopus reindex` is the full rebuild; `--prune` removes orphan rows and auto-accepts renames.
- `octopus where` deliberately stays file-native (resilience > consistency).
- `octopus list` is context-aware: scoped to the current activity when invoked inside one; cross-activity otherwise. `--all` forces cross-activity.
- Default roots empty; user opts in via `octopus config root add`. Missing roots warn, do not fail.
- Sessions table populated by `reindex` even though no v1 verb reads it (schema exercised — request 04 needs no re-index pass).
- `registry.json` (legacy concept) dropped entirely. `index.db` is the sole derived store.
- Dogfood: fresh reindex against `~/vault/projects`, `~/code`, `~/vault/data/skills_db` completed in ~2.9s, indexing the octopus project itself (1 activity, 13 tasks). 72-test suite passing (43 baseline + 29 db-layer).

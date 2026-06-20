---
bucket: backlog
created: '2026-06-20'
kind: chore
priority: medium
title: Prune stale pytest-temp activities from the index DB
tags:
  - index
  - reindex
  - test-hygiene
---

## Problem

The Octopus index (`~/.local/share/octopus/index.db`) is polluted with ~135
activities pointing at non-existent pytest temp dirs:
`/private/tmp/.../pytest-of-alex/pytest-NN/test_*` and one
`/private/var/folders/.../tmp.*`. Only **18** rows are real activities.

These rows come from the test suite running `reindex`/`init` against `tmp_path`
fixtures whose paths share the user's real index DB instead of an isolated one.
They never get cleaned up, so the index grows monotonically with dead rows.
Surfaced 2026-06-20 while building the D110 fleet migration
([[init-auto-gitignore-config-local-toml]], [[reindex-force-migrate-last-known-path]]).

## Two issues, two fixes

1. **Cleanup (now):** `octopus reindex --prune` should drop rows whose `path`
   no longer exists on disk. Verify `--prune` already does this; if so, a single
   run clears the 135 dead rows. If not, add the prune-missing-paths behaviour.

2. **Root cause (prevent recurrence):** the test suite must point at an isolated
   index, not the real one. Set `OCTOPUS_DATA_DIR` (or equivalent) to a temp dir
   in the pytest fixture / conftest so `init`/`reindex` never write to
   `~/.local/share/octopus/index.db`. This is the durable fix.

## Acceptance

- After `reindex --prune`, the index contains only the 18 real activities
  (no `/private/tmp/`, no `/private/var/folders/`).
- Running the full test suite leaves the user's real `index.db` untouched
  (test runs use an isolated data dir).

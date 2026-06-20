# D110 — Machine-local state in config.local.toml


**Locked.** Separates machine-specific state from versionable activity metadata.

**Problem:** `last_known_path` in `activity.md` embeds an absolute path (e.g. `/Users/alex/...`). When `.octopus/` is committed to git, this path leaks into history and trips commit-guard path scanners. It also means a clone on another machine has a stale (wrong-machine) `last_known_path` in a file that should be shareable.

**Schema change:**
- `last_known_path` is **removed from `activity.md`** on write. It is no longer emitted by `write_activity`.
- A new file `.octopus/config.local.toml` holds machine-local state:
  ```toml
  last_known_path = "/absolute/path/to/activity"
  ```
- `config.local.toml` follows `config.toml` naming — TOML throughout, clearly named, easy to hand-edit.
- **`octopus init` auto-gitignores `.octopus/config.local.toml`** (D110.1): after writing the local-state file, init adds the ignore rule to the git root's `.gitignore` (creating it if absent), idempotently. Skipped when the folder is not inside a git repo (nothing to leak into). Supersedes the original "users add it themselves" stance — manual gitignoring proved unreliable and re-leaked the path.

**Read precedence:**
1. `config.local.toml` → `last_known_path` (primary)
2. `activity.md` frontmatter → `last_known_path` (fallback, backwards compat — never written)
3. Missing entirely → empty string (reindex infers from current walk path)

**Migration strategy — reindex self-heals (D110.1):**
- `octopus reindex` reads `last_known_path` from `activity.md` when `config.local.toml` is absent, then writes `config.local.toml` with the value.
- **Active self-heal:** when `activity.md` still physically carries a `last_known_path` line, reindex rewrites the file to drop it (via `write_activity`, which never emits the field) and gitignores `config.local.toml`. Pre-D110 repos converge to clean on the next reindex — no manual step, no waiting for an incidental write. Counted in `ReindexResult.migrated_local_state` and reported in CLI output.
- The detection pivots on the **raw file** (`frontmatter.load`), not the parsed `Activity` (whose `last_known_path` is always populated from the fallback chain), so a clean file is never needlessly rewritten.

> Note: the original decision deferred cleanup to "the next write that touches the file" (lazy). That left committed `activity.md` files leaking the path indefinitely, so the strategy was upgraded to active self-heal (D110.1).

**Validation change:**
- `activity.last_known_path` remains on the `Activity` dataclass (runtime state).
- `Activity.validate()` **no longer errors** on missing `last_known_path` in frontmatter — it may come from `config.local.toml` instead.
- Reindex uses the runtime value regardless of source.

**Rename detection (unchanged contract):**
- `reindex_all` compares `activity.last_known_path` (populated from either source) to the current walk path. Logic is identical; the source of the value changed, not the logic.

**`activity.md` after D110 (no `last_known_path` field):**
```yaml
---
id: my-project-a1b2
title: My Project
created: 2026-06-15
kind: activity
spec_version: 1
type: code
status: active
source_of_truth: "."
---
```

**Files changed:**
- `fs/io.py` — `read_activity`: try `config.local.toml` first, fall back to `activity.md`; `write_activity`: do not emit `last_known_path`
- `fs/scaffold.py` — `init_activity`: write `config.local.toml` instead of `last_known_path` in `activity.md`
- `db/reindex.py` — update `config.local.toml` (not `activity.md`) when accept_renames writes the new path
- `core/models.py` — remove `last_known_path` from `Activity.validate()` required check

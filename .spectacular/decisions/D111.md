# D111 — `octopus_version` stamp on activity.md

**Locked.** Every project records which Octopus CLI version last wrote it.

**Problem:** there was no way to tell, looking at a project folder, which Octopus version last operated on it. `spec_version` answers "which *folder contract*" (currently always `1`, changes almost never), not "which *CLI build*." When schema or behavior shifts between releases, you couldn't see whether a given `.octopus/` was written by an old or new CLI — which matters for diagnosing stale data, knowing whether a folder needs a reindex/migration, and auditing a fleet of projects.

**Decision:** add an auto-managed `octopus_version` field to `activity.md` that records the CLI version (`__version__`) that last wrote the folder. Updated on the **next edit** — i.e. every `activity.md` write — so it always reflects the last CLI to touch the project.

**Why a new field (not reuse `spec_version`):**
- `spec_version` = the on-disk **folder contract** version. Integer, bumped only on breaking schema changes (v1 → v2). Validated strictly.
- `octopus_version` = the **CLI release** that last wrote the folder. Semver string, changes every release. A record, not a constraint — never validated.

These answer different questions and must not be conflated.

**Two-location model (mirrors D110):**
- `activity.md` → `octopus_version: 1.6.0` — **shared**, committed to git. "Last version that wrote this in *any* clone."
- `.octopus/config.local.toml` → `octopus_version = "1.6.0"` — **machine-local**, gitignored. "Last version on *this* machine."

The machine-local stamp is genuinely useful when a repo is cloned across machines running different CLI versions: the committed stamp tells you what last wrote it anywhere, the local stamp tells you what this machine last ran.

**Read precedence** (identical to `last_known_path`):
1. `config.local.toml` → `octopus_version` (machine-local truth wins)
2. `activity.md` frontmatter → `octopus_version` (shared fallback)
3. Missing → `""` (pre-D111 folders, until their next write)

**Update trigger — "on next edit":** stamped in `write_activity()`, the single chokepoint for all `activity.md` writes. This covers `init`, reindex self-heal, status/field edits — no new write paths introduced. `write_local_state()` stamps the local mirror alongside `last_known_path`.

**Always overwrite, never preserve:** `write_activity` stamps the *running* `__version__`, ignoring any (stale) `octopus_version` carried on the in-memory `Activity` from a prior read. A read→write cycle therefore advances the stamp to the current CLI, which is the whole point — the field tracks the *last writer*, not the *first*.

**Surfacing:** `octopus status` shows it. The value is read from the index's stored `raw_frontmatter` JSON (which already serializes every dataclass field) — **no DB schema migration needed**.
- Rich view: row `Octopus version`.
- `--json`: key `octopus_version`.

**Not validated:** any string is accepted. A pre-D111 folder reads `""` and gains a real stamp on its next write — graceful, no migration command required.

**Files changed:**
- `core/models.py` — `Activity.octopus_version: str = ""` (after `spec_version`).
- `fs/io.py` — `write_activity` stamps `__version__`; `read_activity` reads with config.local → activity.md precedence; `octopus_version` added to `ACTIVITY_FIELDS`; `write_local_state` mirrors the stamp.
- `cli.py` — `status` surfaces it via `_activity_octopus_version()` (parses `raw_frontmatter`); added to rich table and `--json`.
- `tests/test_d111_octopus_version_stamp.py` — 7 tests (init stamp both locations, round-trip, always-overwrite, local-wins precedence, empty for pre-D111, not-in-extra).

**Relationship to D110:** D111 reuses D110's two-tier split (shared `activity.md` + machine-local `config.local.toml`) and its read-precedence pattern. The `octopus_version` line *is* committed to `activity.md` (unlike `last_known_path`, which D110 removed) — it carries no machine-specific data, so it is safe and useful to share.

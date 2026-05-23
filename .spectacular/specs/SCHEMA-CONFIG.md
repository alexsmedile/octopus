---
status: draft
updated: 2026-05-22
relates_to: SPEC.md §2.3, SCHEMA-TASK.md, SCHEMA-SESSION.md
---

# Config & cache files schema — v1

Specifies the format of:
1. The system-wide config at `~/.config/octopus/config.toml`.
2. Per-activity overrides at `.octopus/config.toml`.
3. Runtime cache files under `~/.cache/octopus/`.

---

## 1. Config precedence

When a setting is requested by the CLI:

1. Look in `.octopus/config.toml` (project) — if set, use it.
2. Otherwise look in `~/.config/octopus/config.toml` (user) — if set, use it.
3. Otherwise use the shipped default.

Per-project config **overrides**, never **extends**, the user config. If user config sets `noise_words = [...]` and project config sets `noise_words = [...]`, the project list replaces the user list entirely. (Exception: aliases are merged because they map distinct keys.)

## 2. System-wide config (`~/.config/octopus/config.toml`)

All sections are optional. Defaults apply when omitted.

```toml
# ── roots indexed by `octopus reindex` ───────────────────────────────
# Default ships EMPTY. Users opt in to scanning specific paths:
#   octopus config root add ~/vault/projects
[roots]
paths = []

# ── slug rules ───────────────────────────────────────────────────────
[slug]
max_length = 50                  # cap including .md extension (default 50)
noise_words = [
    "a", "an", "the", "of", "to", "for", "in", "on", "at",
    "with", "and", "or", "but",
    "il", "la", "lo", "i", "gli", "le", "un", "una",
    "di", "da", "con", "su", "per", "e", "o", "ma",
]

# ── areas taxonomy ───────────────────────────────────────────────────
[areas]
strict = false                   # default: false (free-form with discovery)
allowed = []                     # required if strict = true
near_duplicate_threshold = 2     # Levenshtein distance threshold for warning

# ── default storage mode for new activities ──────────────────────────
[storage]
default_mode = "folders"         # folders | fields (default: folders)

# ── field-name aliases ───────────────────────────────────────────────
[task.fields]
# Override the default frontmatter field names. Defaults shown.
# created     = "creation_date"
# due         = "due_date"
# scheduled   = "do_date"
# start_date  = "started"
# end_date    = "completed"

[activity.fields]
# created       = "creation_date"
# last_reviewed = "reviewed_at"

[session.fields]
# started = "start_time"
# ended   = "end_time"

[handoff.fields]
# created = "creation_date"

[memory.fields]
# last_updated = "modified"
# summary      = "tldr"

# ── stale-detection thresholds (days) ────────────────────────────────
[warnings]
stale_session_days = 7           # session with ended: empty and no activity
stale_next_days = 30             # bucket: next without status
haunting_backlog_days = 14       # bucket: backlog with open: true
stale_activity_days = 60         # status: active with no task touched
unreviewed_activity_days = 90    # last_reviewed too long ago
aging_handoff_days = 30          # handoff status: open

# ── adapters (opt-in) ────────────────────────────────────────────────
[adapters.obsidian]
enabled = false
vault = ""                       # absolute path
link_dir = "data/activities/_links"

[adapters.reminders]
enabled = false
capture_list = "Octopus Capture"
default_activity = ""            # if empty, CLI prompts per import

# ── promotion providers (D48) ────────────────────────────────────────
# Controls where tasks can be promoted via `octopus promote --to ...`.
# v1 ships with `spectacular` as the only registered provider.
[providers]
default = "spectacular"          # CLI --to <id> (no colon) resolves to this provider

[providers.chips]
# Short display labels for the TUI + chat skill. ASCII, ≤6 chars.
# Falls back to the full provider name when no chip is configured.
spectacular = "spec"
# github = "git"                 # future
# linear = "lin"                 # future

[providers.spectacular]
auto_number = true               # prepend next-available NN- to scaffolded slugs
```

## 3. Per-activity config (`.octopus/config.toml`)

Only the keys that differ from system-wide need appear. All keys above can be overridden.

The most common per-activity setting is storage mode:

```toml
[storage]
mode = "fields"                  # this activity is field-mode (overrides system default)
```

Or area-strict for a specific project:

```toml
[areas]
strict = true
allowed = ["client-work", "internal", "research"]
```

Or custom task-field aliases for an Obsidian-heavy project:

```toml
[task.fields]
due = "due_date"
scheduled = "do_date"
```

## 4. Validation

### MUST reject

- Missing `[areas] allowed` when `strict = true`.
- `default_mode` value outside `{folders, fields}`.
- Field-alias maps where two canonical fields map to the same alias.
- Field-alias maps where an alias clashes with a canonical field name (e.g., aliasing `due` to `scheduled`).
- `[providers] default` set to a value that is not a registered provider. v1 registry: `spectacular`.
- `[providers.chips]` key that is not a registered provider.
- `[providers.chips]` value that is non-ASCII or longer than 6 characters.

### MUST tolerate

- Unknown top-level sections — preserved on rewrite, ignored at read time. (Forward compatibility.)
- Unknown keys within known sections — same.

### SHOULD warn

- `[roots] paths` containing entries that don't exist on disk.
- `[adapters.obsidian] enabled = true` without a valid `vault` path.
- `[providers.chips]` values that collide (two providers mapped to the same chip) — render becomes indistinguishable.

---

## 5. Cache files (`~/.cache/octopus/`)

Cache files are runtime-only. They MAY be deleted at any time without data loss; the CLI rebuilds them as needed.

### 5.1 `active-sessions.json`

Tracks one active session per activity (PRD §13.2).

```json
{
  "shift-a3f9": "2026-05-22-debugging-export",
  "carousel-studio-b71c": "2026-05-20-export-bugs"
}
```

**Schema**:

- Top-level object, keys = activity IDs (full `<slug>-<hash>`), values = session filenames (without `.md`).
- An activity with no active session simply has no key. Empty object `{}` is valid.

**Semantics**:

- If the cache file is missing or unparseable: the CLI treats no sessions as active, warns, and rebuilds an empty cache.
- If a cache entry references a session that doesn't exist: the entry is dropped silently on next CLI command, with a stderr note.
- If a session's frontmatter `active: true` disagrees with the cache: the cache wins (PRD §13.2). The CLI MAY refresh the frontmatter to match.
- The cache is the source of truth. Frontmatter `active:` is a courtesy mirror for users who grep files directly.

### 5.2 `watcher.pid`

Present only when `octopus watch` is running. Contains the PID of the watcher daemon.

```
12345
```

### 5.3 Logs

`~/.local/share/octopus/logs/` (note: under `share`, not `cache` — these persist across cache wipes).

- `cli.log` — recent CLI invocations and errors.
- `reindex.log` — last reindex output.
- `watcher.log` — fsevents activity (when watcher running).

Log retention is implementation-defined; suggested rotation: 7 days or 10 MB per file.

---

## 6. Path conventions

| Purpose | Path | Lifetime |
|---|---|---|
| User config | `~/.config/octopus/config.toml` | Persistent, hand-edited |
| Adapter configs | `~/.config/octopus/adapters/<name>.toml` | Persistent |
| SQLite index | `~/.local/share/octopus/index.db` | Persistent, rebuildable |
| Logs | `~/.local/share/octopus/logs/` | Persistent, rotated |
| Active-sessions cache | `~/.cache/octopus/active-sessions.json` | Transient, rebuildable |
| Watcher PID | `~/.cache/octopus/watcher.pid` | Process lifetime |
| Per-activity config | `<activity>/.octopus/config.toml` | Persistent, per-project |
| Activity trash | `<activity>/.octopus/.trash/` | Persistent, manually pruned |

Paths follow [XDG Base Directory specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) on Linux. On macOS, the same paths apply (Octopus does not use macOS-specific `~/Library/Application Support`).

---

## Reference

- `../SPEC.md §2.3` — storage mode contract.
- `SCHEMA-TASK.md` — task-field aliasing.
- `SCHEMA-SESSION.md` — active-session semantics.
- `CRITICAL-DEPENDENCIES.md` rule I — aliasing validation.

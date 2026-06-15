---
updated: 2026-06-15
mode: index
---

# Decisions

Index of all locked decisions. One line per entry.
Full ADR prose: `decisions/D<N>.md` (or `decisions/DTUI-<N>.md` for TUI key decisions).

---

- **D1** — Activity ID format — IDs are `<slugified-folder-name>-<4-hex-hash>`, stable across renames.
- **D2** — Sessions — Multiple open per activity; one "active" tracked in `~/.cache/octopus/active-sessions.json`.
- **D3** — Areas taxonomy — Free-form strings; Levenshtein ≤ 2 warnings on reindex. `type:` stays enumerated.
- **D4** — Task slugs — Auto-slugify, 50-char cap, noise-word trim, collision counter (`-2`, `-3`).
- **D5** — Index sync model — CLI-incremental + stale-check-on-read default. `reindex` for full rebuild.
- **D6** — Obsidian `.base` ownership — Octopus only writes files it owns by `octopus-` prefix or explicit registry.
- **D7** — memory.md write model — Frontmatter `summary:`, five fixed body sections, append-only via CLI.
- **D8** — Claude Code plugin coupling — External CLI install assumed; install assistant offers auto/manual/skip.
- **D9** — Telemetry — None, ever. Local logs only. `octopus diagnose` for bug-report bundles.
- **D10** — License — MIT, © 2026 Alessandro Smedile.
- **D11** — Adapter framework — Common `Adapter` protocol with capability set (READ/WRITE/NOTIFY/TWO_WAY).
- **D12** — v1 adapter scope — v1 ships read-only adapters only: Obsidian (symlinks) and Apple Reminders (capture import).
- **D13** — Sync modes deferred — Two-way sync, conflict policy, sync triggers → PRD addendum required before v1.5.
- **D14** — Future adapters — GitHub Issues, ICS, Todoist, Google Tasks, Linear, Notion: not v1 scope.
- **D15** — TUI after Sessions/Memory — Sessions land before TUI so the TUI can surface them on day one.
- **D16** — Four-axis task model — pipeline (`bucket`), domain workflow (`stage`), runtime (`run_state`), attention (`pinned`).
- **D17** — Verb-driven CLI — CLI is verb-first (`capture`, `plan`, `focus`, `start`, `finish`, `drop`, `block`, `wait`, `pin`…).
- **D18** — Storage modes per project — Default: folder mode. Tasks in bucket subfolders. Field mode optional.
- **D19** — Field-name aliasing — All five schemas support field-name aliasing via config.toml.
- **D20** — Memory append-only, two-zone — Frontmatter `summary:` (user-curated). Body: managed below marker.
- **D21** — Session lifecycle — `ended:` empty/populated = open/closed. One "active" at a time per activity.
- **D22** — Handoff lifecycle — Status: `open → received → resolved` (or `stale`).
- **D23** — `.trash/` for soft delete — `octopus forget <slug>` moves to `.octopus/.trash/` (v2 feature).
- **D24** — SPEC.md as conceptual map — SPEC.md §3-§7 are summaries; schema docs in `specs/` are authoritative.
- **D25** — `set` verb is hand-edit equivalent — Accepts any frontmatter field; strict type/format/cross-field validation.
- **D26** — Symmetric start/end date rules — `status: doing` MUST have `start_date` set.
- **D27** — Cross-reference resolution — Refs to archived tasks/activities: resolve with warning.
- **D28** — Checklist semantics: cosmetic only — Task body `- [ ]` items not parsed or indexed in v1.
- **D29** — Activities use `status: archive` — Not a separate `archived` boolean (tasks have `archived: true` instead).
- **D30** — Datetime precision — Sessions: `YYYY-MM-DDTHH:MM:SS`. Tasks/activities: `YYYY-MM-DD` date only.
- **D31** — SCHEMA-CONFIG.md added — Covers system config, per-activity config, and cache files.
- **D32** — Bucket absorbs lifecycle; status field dropped — Five-valued: `backlog | next | now | done | dropped`.
- **D33** — kind field dropped from task schema — File location (tasks/ handoffs/ memory.md) determines type.
- **D34** — open field renamed to pinned — `open` → `pinned`. Verbs stay `pin` / `unpin`.
- **D35** — stage field added — Optional, free-form, per-activity domain workflow axis.
- **D36** — run_state field added — Optional enum: `queued | running | finished | failed`. Absent = idle.
- **D37** — Default-omission principle — Fields at default value are omitted from frontmatter entirely.
- **D38** — actor + priority enums reshaped — `actor`: `human | ai | automation`. `priority`: `low | high | urgent` (omit = normal).
- **D39** — Walking-skeleton dogfood passed — v1 schema validated by initializing the Octopus repo itself as an activity.
- **D40** — Index schema v1 frozen — `~/.local/share/octopus/index.db` schema (activities/tasks/sessions) per SCHEMA-INDEX.md.
- **D41** — Sessions, memory, handoffs shipped — request 04 complete; all three subsystems landed and validated.
- **D80** — Explicit-default values clear fields — Passing `--priority normal` / `--actor human` / `""` clears the field (D80 convention).
- **D81** — `--now` does not auto-pin — Moving to `now` bucket is separate from pinning. Explicit `pin` required.
- **D82** — Empty body by default — `capture` creates tasks with no body content. Body is opt-in.
- **D83** — Archive hidden by default — Activities with `status: archive | reference | unknown` excluded from default views.
- **D84** — Cross-activity reads — `dashboard`, `next`, `impact`, `list activities`, `list tasks` work across all indexed activities.
- **D85** — `add task` / `add activity` — "From anywhere" siblings of `capture` and `init` (D85). Accept `--activity` flag.
- **D86** — `--activity` flag on all task-mutation verbs — Explicit cross-activity targeting. Token = path, id, or unambiguous prefix.
- **D87** — Activity priority field — Optional enum `low | high | urgent` on activities. Contributes +10/+20 to task ranking.
- **D88** — `octopus next` ranking — Composite score across pinned, overdue, now_bucket, due_soon, priority, activity_priority, blocked signals.
- **D89** — `octopus impact` verb — Lists tasks ranked by impact score across all activities.
- **D90** — Noun-explicit list forms — `octopus list tasks` and `octopus list activities` as explicit noun forms alongside context-aware bare `list`.
- **D91** — Retire `◆ session` — Session live is `▶` everywhere. `◆` reserved for future activity-state encoding.
- **D92** — Bucket idle glyphs (slot 1) — Collapsed hybrid: exception > session > progress. See TUI-GLYPHS.md.
- **D93** — `now` color is pink — `now` renders in `#F38BA8` (now-pink). Earlier yellow `#FACC15` retired.
- **D94** — Pinned glyph is `*` everywhere — Both chip row and inline preview row.
- **D95** — Diamond + hexagon families reserved — `◇ ◆` = activity. `⬡ ⬢` = git/repo. Families locked permanently.
- **D96** — Slot-1 exception triggers follow schema — Code reads canonical schema field, not heuristics.
- **D97** — Chrome glyphs are not status glyphs — `▸ ✓ ✗ ⟳ ⌂` are affordances; never task state.
- **D98** — `progress` field is forward-spec — Renderer shipped; field not yet in SCHEMA-TASK.md. Reserved.
- **D99** — Pin color is lavender `#CBA6F7` — Pinned chip + preview row. Same palette family as `◇ activity`.
- **D100** — Blocked/waiting tasks can sit in any bucket — Human-set `issue: blocked` is a signal, not a misfiling.
- **D101** — View 0 "Activities" joins Focus (1) and Board (2) — TUI has three top-level views. Digits `0/1/2` switch.
- **D102** — Diamond family fully activated — `◆` = active state, `◈` = containment. Scope: activities only.
- **D103** — TODO.md Layer 2: shorthand sigils + body block + YAML expansion — See `specs/TODO-MD-FORMAT.md`.
- **D104** — Subtask graph: 1-level-deep parent/child — `parent: <slug>` on child is source of truth; `subtasks:` is derived.
- **D105** — TODO.md Layer 2: indented checkboxes → subtasks — Indented `  - [ ]` lines map to children of last top-level checkbox.
- **D106** — TUI subtask display: expand/collapse inline under parent — Child rows render inline in all quadrant lists.
- **D107** — Orphan/drop behavior for subtask children — `--cascade` drops children first; `--force` leaves them orphaned.
- **D108** — TODO.md Layer 2: `%kind` inline sigil — `%feat`, `%bug`, etc. Sets `kind` field. `%` chosen to avoid markdown conflicts.
- **D109** — Inbox activity type + default capture routing — `type: inbox` first-class; `[inbox].default` config fallback when outside any activity.
- **D110** — Machine-local state in config.local.toml — `last_known_path` removed from `activity.md`; lives in `.octopus/config.local.toml` (gitignored).

---

## TUI key decisions (scoped, from request 34)

- **DTUI-1** — Detail-pane key — `,` toggles detail pane. `d` stays as drop.
- **DTUI-2** — Block / unblock — `b` = block, `B` = unblock. Capital-pair idiom.
- **DTUI-3** — Arrow chip glyphs — `← → ↑ ↓` Unicode geometric.
- **DTUI-4** — Enter / Tab / Esc labels — `CR` / `TAB` / `ESC` ASCII labels.
- **DTUI-5** — Enter semantics under 4-pane Focus — Enter focuses/opens detail pane.
- **DTUI-6** — Undo — `u` reverses most recent mutation. `Ctrl+*` rejected (multiplexer clash).
- **DTUI-7** — Yank slug — `y` (vim idiom). Platform clipboard detection.

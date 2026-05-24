# Roadmap & release history

v1 ships when phases **06** (adapter framework) and **07** (Obsidian symlink bridge) are done. The protocol — `.octopus/` on disk — is the lock-in, not the Python. Anything that speaks the contract is "Octopus".

For per-release detail see [CHANGELOG.md](../CHANGELOG.md). For locked decisions see [`.spectacular/DECISIONS.md`](../.spectacular/DECISIONS.md).

## Build phases

| Phase | What | State |
|---|---|---|
| 01 | Extract the spec from PRD into SCHEMA-*.md docs | ✅ done |
| 02 | Walking-skeleton CLI (`init`, `capture`, `plan`, `focus`, `start`, `finish`, `drop`, `set`, …) | ✅ done |
| 02b | Schema collapse — five-value bucket; `pinned`/`stage`/`run_state` added | ✅ done |
| 03 | SQLite index, `reindex`, `list`, `status`, config root | ✅ done |
| 04 | Sessions + memory + handoffs (multi-open cache, 5-section memory, fs-only handoffs) | ✅ done |
| — | Self-contained Claude Code skill at `skills/octopus/` | ✅ done |
| 11 | pipx distribution + `octopus diagnose` + CI + logging | ✅ done |
| 05 | Textual TUI — Focus + Board modes, animated pixel mascot, shared `octopus.actions` write layer | ✅ done |
| 08 | Claude Code + Codex plugin scaffold (6 commands, 3 agents, 2 hooks) | ✅ done |
| 30 | Index hygiene — `forget activity`, `--archive`, archived hidden by default | ✅ done |
| 31 | Mascot ASCII animations (calm, capovolta, moonwalk) | ✅ done |
| **06** | **Adapter framework** (full implementation, all built-in adapters) | 🟢 **next-up** |
| 07 | Obsidian symlink bridge | queued |
| 09 | Apple Reminders pull (deeper integration) | queued |
| 12 | Lint cleanup (re-tighten ruff — debt deferred from #11) | queued |
| 18 | Mascot animation polish + more poses | backlog |
| 19 | Task naming formula + kind/area schema exploration | backlog |
| 32 | Mascot design system docs (gates on #31) | backlog |

## Recent releases

### v0.9.2 — 2026-05-24 — animated TUI mascot
Three locked animations shipped: calm idle (deterministic body bob + independent blink channel), capovolta-B (squish + flip on `f`), moonwalk-D6 (subtle body sway + ratcheting legs + blink-at-apex on `p`). Dynamic eye-row detection in `apply_blink` so blink direction stays correct across body shifts. State machine pattern: idle → triggered → idle. 601 tests passing.

### v0.7.0 — 2026-05-24 — index hygiene (#30)
New `octopus forget activity <path-or-id>` removes from the SQLite index without touching files; `--archive` moves files to `<parent>/_archive/<name>/`. Path-or-id auto-detection. Archived activities hidden by default; pass `--include-archived` to surface them. **508 tests passing** (was 489).

### v0.6.1 — 2026-05-24 — skill documentation patch
`skills/octopus/SKILL.md` brought from v0.4.0 → v0.6.1, reflecting every shipped surface (kind enum, task promotion, adapter framework, three adapters, capture/edit polish).

### v0.6.0 — 2026-05-24 — capture + edit polish (#24)
Richer `capture` flags (`--due/--scheduled/--start-date/--end-date/--actor/--energy/--owner/--stage` + tags). Atomic Obsidian-compatible tag mutations (`--tag/--add-tag/--remove-tag/--clear-tags`). New `octopus move`/`mv` verb (separates file-move from frontmatter-edit). Cascading slug rename via `set --slug` updates all Octopus-managed refs. New `octopus refs find` helper. Explicit-default values clear instead of reject. **489 tests passing** (was 404).

### v0.5.0 — 2026-05-24 — TODO.md becomes a living index (#22)
Adopts GFM + Obsidian Tasks emoji conventions for parsing. Adds `→ provider:slug` arrow as the "handed off elsewhere" marker. Rewrites the source file in place on pull so every imported `- [ ] thing` becomes `- [x] thing → octopus:<slug>`. New mutation verbs `bridge add/complete/uncomplete` edit `TODO.md` directly without importing. New capability flag `MARK_PULLED` on the adapter protocol.

### v0.4.2 — 2026-05-24 — Apple Reminders adapter ships (#09)
Pull-only via [`remindctl`](https://github.com/steipete/remindctl). Stable EventKit UUIDs for dedup. Multi-list aggregation. Native priority + due-date + notes mapping into Octopus fields.

### v0.4.1 — 2026-05-24 — first real adapter ships
`todo-md` (#21) replaces its stub with a working pull-only adapter that reads `- [ ] task` checkbox lines from a `TODO.md` file, maps `BUG:`/`HACK:` prefixes to `kind`, honors `[-]`/`[/]` in-progress markers, supports heading-slug section filtering, stays idempotent via slug-based `external_id`s.

### v0.4.0 — 2026-05-24 — the adapter framework
New `octopus bridge` subcommand group with seven verbs (`list`/`enable`/`disable`/`status`/`peek`/`pull`/`search`). `Capability` enum + `Adapter` Protocol. Hybrid config layout: `[adapters.<name>] enabled` in main config, content in `~/.config/octopus/bridges/<name>.toml`. Per-adapter sync journal. Dedup index via new `task_external_refs` join table. SQLite schema v2 → v3 migrated in-place.

For older versions, see [CHANGELOG.md](../CHANGELOG.md).

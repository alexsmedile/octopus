# D103 — TODO.md Layer 2: shorthand sigils + body block + YAML expansion


**Locked.** See `specs/TODO-MD-FORMAT.md` for full spec.

Three-layer format. Layer 1 is plain GFM (current behavior, unchanged). Layer 2
adds three opt-in extensions per item, all additive and non-destructive:

**Shorthand sigils** (inline on the checkbox line):
- `#tag` → `tags` (already Layer 1)
- `@owner` → `owner`
- `~bucket` → `bucket` (shorthand: `~b` `~n` `~!`)
- `!priority` → `priority` (shorthand: `!l` `!h` `!!`)
- `%kind` → `kind` (full names only: `%feat` `%bug` `%spec` `%chore` `%refactor` `%polish` `%test` `%docs` `%idea`) — D108
- `📅` `🗓️` `📆` + date → `due` (ISO, DD-MM-YYYY, or DD/MM/YYYY)

`!` as priority sigil: no collision with `[!]` cancelled state — the checkbox
marker is extracted before body parsing runs; `!word` in the body is unambiguous.

**Body block** — `> text` lines immediately after the checkbox are captured
as the task body. Renders as a blockquote in all markdown viewers.

**YAML expansion block** — fenced ` ```yaml ``` ` block immediately after
the checkbox (or body block) sets any Task field not covered by sigils.
Supported keys: all non-provenance Task fields (`bucket`, `stage`, `pinned`,
`issue`, `blocked_by`, `waiting_for`, `due`, `scheduled`, `priority`,
`energy`, `actor`, `owner`, `kind`, `tags`).

**Precedence (high → low):** sigils/emoji → YAML block → section_map config.

**Implementation scope:**
1. `ExternalTask` (base.py) — add `suggested_*` fields for all new keys.
2. `todo_md.py` — parse sigils, body block, YAML block; populate new fields.
3. `pipeline.py` — wire all new `suggested_*` fields into the materialized Task.
4. Per-activity `section_map` in `.octopus/config.toml` for section-level defaults.

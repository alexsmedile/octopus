# D109 — Inbox activity type + default capture routing


**Locked.** Adds `inbox` as a first-class activity type and defines how `capture` routes when no `--activity` flag is given.

**Schema:**
- `inbox` added to the `type` enum in `activity.md`: `code | business | content | skill | automation | research | personal | inbox | other`
- No new frontmatter fields — scope is expressed via the existing `area` field (e.g. `area: alex`, `area: shift`)
- An activity can be both `type: inbox` and have any `area` value — `area` is the differentiator for multi-inbox setups

**Config — default inbox (`~/.config/octopus/config.toml` or project-local):**
```toml
[inbox]
default = "~/vault/inbox"    # activity path or id — used when cwd has no activity
```
- `default` key is the global catch-all inbox
- No per-brand config keys — brand routing uses `--area` flag at capture time
- Config is optional; absence means "no default inbox"

**Capture routing (no `--activity` flag):**
```
octopus capture "idea"
  ├─ cwd has .octopus/activity.md? → capture here (unchanged, cwd wins)
  └─ no activity in cwd?
       ├─ [inbox].default set in config? → route to default inbox
       └─ no config?  → error: "not in an activity — use --activity or configure a default inbox"
```
- cwd activity always wins — inbox default is only the fallback when outside any activity
- `--activity` always overrides both cwd and config default

**Capture to a specific inbox:**
```bash
octopus capture "idea"                       # cwd activity or default inbox
octopus capture "idea" --activity inbox      # explicit by id/prefix
octopus capture "idea" --activity ~/vault/inbox-shift   # explicit by path
```
No `--area` routing at capture time — brand selection is done via `--activity`. `area` is metadata on the inbox activity, not a routing key.

**CLI — new commands:**
```bash
octopus init --title "Inbox" --type inbox [--area alex]   # create an inbox activity
octopus list activities --type inbox                       # list all inboxes
```
All other verbs (`next`, `dashboard`, `status`, `stuck`) work as-is — inbox activities are normal activities.

**`octopus init` prompt:** `type` selector includes `inbox` as a valid option.

**What needs building:**
1. `inbox` added to `type` enum + validation in schema and CLI
2. `[inbox]` config block + `default` key parsing in `config.toml`
3. `capture` routing: check cwd activity first, then config default, then error
4. `octopus init` prompt includes `inbox` type
5. `octopus list activities --type inbox` filter

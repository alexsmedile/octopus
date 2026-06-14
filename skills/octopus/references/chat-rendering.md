# Chat Rendering — Task Display in ASCII

When the user asks to see their tasks (overview, status, what's in backlog, focus view, board, kanban, etc.), render them as **ASCII layouts** that mirror the `octopus tui` glyphs and structure — not generic markdown lists. Visual continuity with the TUI is part of the brand.

## Sourcing
- Always pull from `octopus list` (or read `.octopus/tasks/<bucket>/*.md` directly when the CLI isn't enough). Never invent rows.
- For counts, prefer `octopus status` output. For per-task chips, read frontmatter (`pinned`, `run_state`).

## Glyphs (match the TUI exactly)
- `▢` task row · `▸` cursor (only if you're highlighting a specific task)
- `⚐` pinned · `⏸` blocked · `✓` done · `✗` dropped
- `●` NOW · `○` NEXT (bucket headers)
- `[kind]` work-classification chip (cyan in TUI; plain in chat)
- `→ chip:id` promotion arrow on tasks with `promoted_to` (dim in TUI; plain in chat)
- `…N more` when truncating

## Chip + arrow rendering rules
- **`[kind]` chip:** show in compact list and Focus quadrants. In Board (narrow columns), omit if it forces title truncation past the 50% mark.
- **Promotion arrow:** only show in `--all` / `--promoted` / `--spec` scopes. Use the configured chip alias (`spec:` not `spectacular:`).
- Both chips are inline AFTER the title in compact list (`▢ pull apple reminders into backlog [feat] · reminders`), or as a right-aligned suffix in quadrant/board cells when space permits.

## Layout routing

Pick the layout based on the user's phrasing — don't ask, just match.

| User phrasing contains… | Use layout |
|---|---|
| "focus", "overview", "what should I work on", "active" | **Focus quadrants (A)** |
| "board", "kanban", "all buckets", "everything" | **Board kanban (B)** |
| "backlog", "what's in X", "list", default | **Compact list (C)** |

## Layout A — Focus quadrants (BACKLOG | NOW/NEXT)

```
┌─ BACKLOG ──────────────────────────┬─ ● NOW ────────────────────────────┐
│   ▢ wire obsidian symlink bridge   │   ▢ ship the TUI                   │
│   ⚐ polish error messages          │   ⏸ verify run_state semantics     │
│   ▢ apple reminders pull adapter   ├─ ○ NEXT ───────────────────────────┤
│   …5 more                          │   ▢ build sqlite migrations        │
└────────────────────────────────────┴────────────────────────────────────┘
  9 backlog · 2 now · 1 next · 1 blocked
```

## Layout B — Board kanban (four columns)

```
┌─ BACKLOG ──────┬─ ○ NEXT ───────┬─ ● NOW ────────┬─ ✓ DONE ───────┐
│ ▢ wire obsid…  │ ▢ verify run…  │ ▢ ship the…    │ ✓ add textual… │
│ ⚐ polish err…  │                │ ⏸ build sqli…  │ ✓ build sqli…  │
│ ▢ apple remi…  │                │                │ ✓ implement…   │
│ …5 more        │                │                │ …2 more        │
└────────────────┴────────────────┴────────────────┴────────────────┘
```

## Layout C — Compact list (default)

```
backlog (9)
  ▢ [feat] wire obsidian symlink bridge
  ⚐ [polish] polish error messages and rich output
  ▢ [feat] pull apple reminders into backlog
  …6 more — ask to see all

next (1)
  ▢ [test] verify run_state in a real automation

now (0)
  (empty — use m from next to activate)
```

If the user asked for `--promoted` or `--spec <slug>`, append the arrow:

```
promoted (2)
  ✓ [chore] drop "(request NN)" suffix → spec:20-task-promotion
  ✓ [feat]  wire obsidian symlink bridge → spec:20-task-promotion
```

## Rendering rules
- Truncate titles to fit the column. Use `…` to indicate truncation; never wrap.
- Cap each column at **5 rows** in chat — append `…N more` if exceeded. Show the full list only when the user explicitly asks ("show all", "everything in backlog").
- One blank line between buckets in layout C.
- Strip the "(request NN)" suffix from titles when it crowds the column.
- Wrap the block in a code fence so monospace renders correctly.
- After the block, add **one short sentence** of context (next action, what's blocked) — not a re-summary of what's already on screen.

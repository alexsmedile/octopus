---
status: done
priority: high
owner: alex
updated: 2026-05-26
summary: "View 0 'Activities' — cross-activity TUI surface with three vertical collapsible panels (Index / Current / Nested). Drill into an activity to enter its per-activity TUI without leaving octopus."
related:
  - 27-cross-activity-reads-and-dashboards
  - 30-index-hygiene
  - 44-cursor-view-state-persistence
gates: []
---

# Tab 0 — Activities

## Goal

Promote octopus from a per-activity TUI to a multi-activity TUI by adding **Tab 0 "Activities"** — a cross-activity navigation surface, runnable from anywhere (no `cd` required). Stacked 3-row activity blocks in three vertically collapsible panels: **Index**, **Current**, **Nested**. `Enter` on any activity replaces the screen with that activity's per-activity TUI (Focus/Board); `Esc` returns to Tab 0.

Tab 0 is the new "where am I in the whole system" anchor. Existing per-activity modes (Focus, Board) become Tabs 1 and 2.

## Why

Today: `octopus tui` requires being inside an activity (walks up to find `.octopus/`). From `~`, there is no TUI surface — only the `octopus list --all`, `octopus dashboard`, etc. CLI verbs. To navigate between projects you `cd`, then `octopus tui` again.

After this request: launch octopus from anywhere → land on Tab 0 → see every indexed activity stacked, the one you're "in" (if any), and any sub-activities under your cwd. `Enter` drills in. The TUI becomes the primary surface for cross-activity work, with the CLI verbs as the underlying engine.

This is also the foundation for future tabs (calendar, agenda, agent recommendations) — once Tab 0 establishes the multi-tab paradigm.

## Locked decisions

| # | Locked |
|---|---|
| 1 | Tab 0 is **Activities**. Tabs 1+ are existing per-activity modes (Focus, Board). |
| 2 | Three panel names: **Index** / **Current** / **Nested**. Each gets a header glyph from the diamond family (D95): `◇ INDEX` (outline — activities as labels), `◆ CURRENT` (filled — lights up the D95-reserved "activity state" slot; state = "I'm in this one"), `◈ NESTED` (outline-with-interior — diamonds-inside-a-diamond, sub-activities live inside this one). |
| 3 | Each activity block = **3 rows** vertically: title line, stats line (type · status · NOW/NEXT/BACKLOG counts), path line. |
| 4 | Drill behavior on `Enter` = **(a)** internal context switch — replace screen with that activity's Focus/Board TUI; `Esc` returns to Tab 0. No shell cd. |
| 5 | Panels are **vertically collapsible** (Space toggles). |
| 6 | `Tab` cycles panel focus: Index → Current → Nested → Index (wraps). |
| 7 | Cursor position on first launch = top of Index. Cursor memory across tab switches is **out of scope** for this request — see request #44. |
| 8 | When `Current` is empty (launched from outside any activity), the panel still renders with a placeholder "(no current activity)". Never hidden — empty-state is information. |
| 9 | When `Nested` is empty, same pattern — visible with placeholder "(no sub-activities)". |
| 10 | Tab 0 reads from the **SQLite index** (`octopus list --all`'s data source), not by walking the filesystem on every render. Refresh on `r` re-runs the query. |
| 11 | `Nested` source: walk-down from cwd using the existing `find_all_activities` helper, **excluding** the current activity itself. Lives outside the index query (filesystem-side). |
| 12 | Archived activities hidden by default in Index (mirrors `list --all` per #30); `A` toggles include-archived. |

## Scope

### In

- New tab `Activities` registered as Tab 0 in the TUI app shell.
- Three panel widgets: `IndexPanel`, `CurrentPanel`, `NestedPanel`.
- Activity-block renderer: title / stats / path (3 rows).
- Tab key handler — cycles between panels.
- Enter handler — pushes the per-activity TUI onto the screen stack.
- Esc handler — pops back to Tab 0.
- `r` refresh, `/` filter (filters Index by title/path substring; doesn't filter Current/Nested), `Space` collapse panel.
- `A` toggle include-archived in Index.
- Empty-state rendering for Current and Nested.
- Launching `octopus tui` from outside any activity → defaults to Tab 0 (Activities) instead of erroring.
- Launching `octopus tui` from inside an activity → defaults to Tab 0 with Current populated; user can press `1` or `2` to go straight to Focus/Board.

### Out

- **Cursor memory between tab switches** — request #44.
- **Cross-session persistence of which tab was last active** — request #44.
- Cross-activity writes from Tab 0 (e.g., add task to activity X without entering it) — request #26 territory.
- Live file-watcher refresh — refresh-on-demand (`r`) only for v1.
- Grouping / sorting controls beyond the default (Index = ranked by `octopus impact` heuristic; Current = single row; Nested = file-system order).
- Calendar / timeline / agent-recommendation tabs (future tabs, separate requests).
- Web/HTML view of activities.

## Layout

```
┌─ Activities ─ Focus ─ Board ──────────────────────── octopus 1.x ─┐
│ [0]            [1]     [2]                                        │
│                                                                   │
│  ▼ ◇ INDEX (4)                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ ▸ octopus              Octopus                              │  │
│  │     code · active   NOW 2  NEXT 3  BACKLOG 11               │  │
│  │     ~/vault/data/skills_db/octopus                          │  │
│  ├─────────────────────────────────────────────────────────────┤  │
│  │   smedile.com         Personal site                         │  │
│  │     code · active   NOW 0  NEXT 1  BACKLOG 4                │  │
│  │     ~/code/smedile.com                                      │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ▼ ◆ CURRENT (1)                                                  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │   octopus              Octopus                              │  │
│  │     code · active   NOW 2  NEXT 3  BACKLOG 11               │  │
│  │     ~/vault/data/skills_db/octopus                          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ▶ ◈ NESTED (0)                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │   (none)                                                    │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
└── Tab next · Enter drill · Space collapse · / filter · q quit ────┘
```

- `▼` open panel, `▶` collapsed panel.
- `▸` cursor (per D97: cursor is chrome, not status).
- Diamond family per D95 lights up here: `◇` outline = label (Index), `◆` filled = active state (Current, "I'm in this one" — formally activates the D95-reserved filled-diamond slot), `◈` outline-with-interior = containment (Nested, sub-activities inside this one).

## Keys (delta vs current TUI; full schema lives in `TUI-KEYS.md`)

| Key | Action |
|---|---|
| `0` | Jump to Tab 0 (Activities) from any tab |
| `1` | Jump to Tab 1 (Focus) — requires a selected activity |
| `2` | Jump to Tab 2 (Board) — requires a selected activity |
| `Tab` | Cycle panel focus within Tab 0: Index → Current → Nested → Index |
| `Shift+Tab` | Reverse cycle |
| `↑` `↓` | Move cursor within the active panel |
| `Enter` | Drill into the selected activity (push Focus mode onto screen stack) |
| `Esc` | Pop back to Tab 0 from a drilled-in activity |
| `Space` | Collapse / expand the active panel |
| `r` | Refresh (re-query index + walk-down Nested) |
| `/` | Filter Index by title/path substring |
| `A` | Toggle include-archived in Index |
| `q` | Quit octopus |

`1` and `2` from Tab 0 with no selected activity → error toast: "no activity selected — Enter on an activity first."

## Module layout

```
cli/src/octopus/tui/
├── app.py                       # extend OctopusApp: add switch_to_activities()
├── focus.py                     # unchanged
├── board.py                     # unchanged
└── activities_screen.py         # NEW — ActivitiesScreen + 3 panels + ActivityBlock
```

Single new file. Internal classes (`IndexPanel`, `CurrentPanel`, `NestedPanel`, `ActivityBlock`) live inside `activities_screen.py` unless one exceeds ~200 lines, at which point split.

## Data sources

| Panel | Source | Refresh trigger |
|---|---|---|
| Index | `db.queries.list_activities()` with archived filter | `r`, `A`, on Tab 0 entry |
| Current | `find_activity_root(cwd)` → `read_activity()` → SQLite enrich | `r`, on Tab 0 entry |
| Nested | `find_all_activities([cwd])` minus current activity | `r`, on Tab 0 entry |

Nested deliberately doesn't go through the index — it walks the filesystem so sub-activities show up even if the user hasn't reindexed yet. Trade-off: walking is slower than a query. Acceptable since Nested is bounded by cwd's subtree.

## Activity block — 3-row format

```
Row 1: ▸ <id-short>          <title>
Row 2:     <type> · <status>   NOW <n>  NEXT <n>  BACKLOG <n>
Row 3:     <path-shortened>
```

- Row 1: cursor + short activity id (8 chars, hash stripped per D1) + title. No chip — panel header (`◇ ◆ ◈`) already encodes scope.
- Row 2: type + status + bucket counts. Uses existing chip styling from current TUI.
- Row 3: path with `$HOME` → `~` replacement; truncated middle if >60 chars.

## Method

1. Write this PLAN.md (✓).
2. Generate `TASKS.md`.
3. **No prep refactor.** The existing TUI uses screen-stack navigation (Focus and Board are `Screen` subclasses pushed on `OctopusApp`), so "tabs" are implemented as additional screens. `ActivitiesScreen` joins `FocusScreen` and `BoardScreen` at the same level. The original PLAN sketched a `tui/tabs/` reorg around `TabbedContent`; dropped after reading the code — screen-stack approach already implements what we need with no churn.
4. Create `tui/activities_screen.py` (3 panels live in one file at first; split if it grows). Wire `switch_to_activities()` into `OctopusApp` and bind `0` in Focus/Board. Launching octopus from outside any activity → boot into ActivitiesScreen instead of erroring.
5. Implement `ActivityBlock` renderer end-to-end as the smallest reusable unit. Visual review.
6. Implement `IndexPanel` (most complex — pulls from SQLite, handles archived toggle, supports filter).
7. Implement `CurrentPanel` (single-row, simplest).
8. Implement `NestedPanel` (filesystem walk-down).
9. Wire keybindings: `Tab`, `↑↓`, `Enter`, `Esc`, `r`, `/`, `A`, `Space`, `0/1/2`.
10. Wire drill behavior — push Focus mode onto Textual's screen stack with the selected activity's path.
11. Test from `~`, from inside `octopus/`, and from a hypothetical parent dir with sub-activities.
12. Sync `TUI-KEYS.md` + skill mirror.
13. Update `TUI-GLYPHS.md` (+ skill mirror) — diamond family now: `◇` label (Index, existing), `◆` active (Current, new — activates D95-reserved slot), `◈` containment (Nested, new). Add a new D-entry to DECISIONS.md locking this.
14. CHANGELOG entry under `[Unreleased]`.
15. Close request.

## Risks

- **Screen stack semantics in Textual.** Pushing a per-activity TUI onto the stack and popping back must preserve Tab 0's panel + cursor state. Without #44, "preserve cursor" means re-rendering at the top of Index. Acceptable for v1 — full memory comes in #44.
- **Diamond family activation (D95 → new D-entry).** This request formally activates the D95-reserved `◆ filled-diamond` slot for "active activity state" (the Current panel header), and introduces `◈ outline-with-interior` for "nested containment" (the Nested panel header). `◇` outline stays as the existing activity label. This is a single, scoped extension — diamond family stays activity-only, hexagon stays git-only. Lock as a new D-entry on close (post-implementation, after visual verification).
- **Refresh-on-demand staleness.** If the user edits files in another terminal while Tab 0 is open, counts go stale until `r`. Acceptable trade-off vs file-watcher complexity. The TUI's existing per-activity views have the same trade-off.
- **Performance with 100+ activities.** SQLite query is cheap; rendering 100 × 3-row blocks might tax Textual's diff engine. Soft cap at 50 visible rows + scrolling; full list still queried but virtualized in the view.

## Deliverables

- `cli/src/octopus/tui/tabs/activities/` module (4 files)
- `cli/src/octopus/tui/app.py` extended with multi-tab shell
- `cli/src/octopus/tui/tabs/focus.py`, `board.py` (moved, behavior unchanged)
- Updated `.spectacular/specs/TUI-KEYS.md` + skill mirror
- Possibly updated `TUI-GLYPHS.md` (depends on hexagon decision)
- `cli/tests/tui/test_activities_tab.py` (snapshot tests for block + panels)
- CHANGELOG entry
- DECISIONS entry if hexagon family is extended

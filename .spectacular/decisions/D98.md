# D98 — `progress` field is forward-spec

- The renderer for the progress ladder is shipped, but `progress` is not yet in `SCHEMA-TASK.md`. The field is **reserved** for v1.x.
- Bucket idle glyph fills the gap until then — every task is treated as idle on its bucket until `progress` is wired through schema + import.

### Specs synced
- `.spectacular/specs/TUI-GLYPHS.md` rewritten (slot-1 resolver, bucket idle glyphs, retired allocations).
- `skills/octopus/references/tui-glyphs.md` mirrored (operational subset).
- Code: `cli/src/octopus/tui/icons.py` (resolver + constants), `header_bar.py`, `board.py`, `focus.py`.

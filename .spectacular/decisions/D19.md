# D19 — Field-name aliasing

- All five schemas (task, activity, session, handoff, memory) support field-name aliasing.
- Config: system-wide `~/.config/octopus/config.toml` and per-project `.octopus/config.toml`.
- Project config wins on conflict.
- Canonical names match Obsidian Tasks plugin convention; aliases let teams pick `creation_date`, `due_date`, etc.

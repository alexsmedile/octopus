# D18 — Storage modes per project

- Default: **folder mode**. Tasks live in bucket subfolders (`tasks/backlog/`, `next/`, `now/`, `done/`, `dropped/`). Pipeline verbs do atomic `mv` + frontmatter edit.
- Opt-in: **field mode**. Tasks live flat; bucket is frontmatter-only.
- Configured per activity in `.octopus/config.toml [storage] mode`.
- Sessions and handoffs are **always flat** (machine-readable artifacts, date-ordered).

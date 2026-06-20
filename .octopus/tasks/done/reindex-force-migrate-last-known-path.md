---
bucket: done
created: '2026-06-20'
end_date: '2026-06-20'
kind: feat
priority: medium
title: reindex should actively strip last_known_path from activity.md
tags:
  - d110
  - migration
---

## Problem

D110's migration is **lazy**: the stale `last_known_path:` line in an existing
`activity.md` is *"left in place (not removed — `write_activity` will drop it on
the next write that touches the file)."* `octopus reindex` writes
`config.local.toml` but does **not** rewrite `activity.md`.

Consequence: any activity created before D110 keeps leaking its absolute path in
the committed `activity.md` until some unrelated write verb happens to touch it.
This repo carried the leaked line for days after D110 shipped (fixed by hand on
2026-06-20). See [[init-auto-gitignore-config-local-toml]] and the origin task
[[separate-machine-local-state-last-known-path]].

## Proposal

- On `octopus reindex`, when `config.local.toml` is written/refreshed AND
  `activity.md` still carries a `last_known_path` field, rewrite `activity.md`
  to drop the field (a real write, not lazy).
- Keep it safe: only touch the field, preserve all other frontmatter + body.
- Optionally gate behind a one-time `reindex --migrate` if a silent rewrite of
  many activities feels too aggressive.

## Acceptance

- After one `octopus reindex`, no managed `activity.md` contains
  `last_known_path`.
- Body and other frontmatter untouched.
- Rename detection still works (value now sourced from `config.local.toml`).

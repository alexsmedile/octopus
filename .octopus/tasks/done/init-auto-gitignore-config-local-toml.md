---
created_at: '2026-06-20'
extensions:
  octopus.core:
    bucket: now
id: 6e5a1176-3cd3-4065-b681-65bcc7167113
kind: feat
labels:
- d110
- dx
otf_version: 0.1.0
priority: high
project: octopus
state: active
status: done
title: octopus init should auto-add config.local.toml to .gitignore
type: task
---

## Problem

D110 moved `last_known_path` out of `activity.md` into a machine-local
`.octopus/config.local.toml`, but made the gitignore step **manual** — the
decision says *"Users add `.octopus/config.local.toml` to `.gitignore`
themselves (documented, not auto-written)."*

The original proposal ([[separate-machine-local-state-last-known-path]]) had this
as an explicit acceptance criterion: *"`octopus init` aggiunge automaticamente
quel path a `.gitignore` (creandolo se manca)."* It was dropped in the final
decision. Result: every fresh `octopus init` still risks committing the
machine-local file (or, pre-write, the stale `activity.md` line). Hit again in
this very repo on 2026-06-20.

## Proposal

- `octopus init` (and the D110 lazy migration in `reindex`) ensures
  `.octopus/config.local.toml` is listed in the nearest `.gitignore`, creating
  `.gitignore` if absent.
- Idempotent: don't duplicate the line if already present.
- Respect an opt-out flag (`--no-gitignore`) for users who manage ignores
  centrally.

## Acceptance

- Fresh `octopus init` in a git repo leaves `.octopus/config.local.toml`
  gitignored with no manual step.
- Re-running init does not duplicate the ignore line.
- Update D110 detail + SCHEMA-ACTIVITY.md to reflect auto-gitignore.

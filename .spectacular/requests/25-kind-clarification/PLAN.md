---
status: backlog
priority: medium
owner: alex
updated: 2026-05-24
summary: "Clarify `kind`: when it drives behavior, capture flag, auto-inference rules, validation policy, enum extensions."
related:
  - 21-adapter-todo-md
  - 22-todo-md-format
  - 24-capture-edit-polish
gates: []
---

# Kind clarification

## Goal

`kind` shipped in v0.3.0 (D46) as an optional work-classification enum: `feat | bug | spec | polish | test | chore`. After dogfooding, it's unclear:

- When `kind` actually drives behavior (right now it's just a chip in display + a filter on `list`).
- Whether `capture` should accept `--kind` at create time (currently you must `capture` then `set --kind`).
- Auto-inference rules: `todo-md` adapter already maps `BUG:` → `kind: bug`, `HACK:` → `kind: chore`. Should `capture` do the same? Should there be a registry of mappings?
- Validation policy: unknown values currently warn forever (D46 "soft validation v1"). When do we lock the enum strictly? Or do we ever?
- Whether new kinds (`idea`, `question`, `note`) should be added.

## Why

`kind` is a metadata field a user will touch on every task. Soft validation + no capture flag + ad-hoc inference makes its semantics fuzzy. Either we commit to making it useful or we drop it.

## Scope when activated

### Phase 1 — `capture --kind` flag

```
octopus capture "fix login crash" --kind bug
octopus capture "explore audio worklets" --kind spec
```

Accepts the enum values verbatim. Validates against the soft enum (warns on unknown but accepts — matching `set --kind` semantics).

### Phase 2 — Auto-inference rules

`todo-md` already infers from prefixes. Should `capture` do the same?

```
octopus capture "BUG: marquee duplicates"
```

Should this set `kind: bug` automatically? Three positions:

- **A) No.** Inference only at the adapter boundary (todo-md, reminders). `capture` is the explicit-intent path.
- **B) Yes, when the prefix is unambiguous.** `BUG:`, `HACK:`, `FIXME:` infer; otherwise no.
- **C) Yes, but require confirmation.** `capture "BUG: …"` prompts "Set kind: bug? [Y/n]".

Open.

### Phase 3 — Validation policy

When (if ever) does the enum become strict?

- **A) Stay soft forever.** Unknown values are valid, just warn.
- **B) Lock at v1.0.** From then on, unknown values reject.
- **C) Make it configurable.** `[task.kind] strict = true` in config.

### Phase 4 — Enum extensions?

Candidates that surfaced in dogfooding:

| New kind | Why | Risk |
|---|---|---|
| `idea` | distinguish "exploratory" tasks from `spec` | overlap with `spec` |
| `question` | "I don't know yet what this is" | overlap with `idea` |
| `note` | a task that's mostly informational | conflicts with #21 NOTE: prefix being "skip" |
| `refactor` | refactor work is different from `feat` and `chore` | possibly overlap with `chore` |
| `meta` | meta-task about the project itself | rare; probably tags |

### Phase 5 — Behavior driven by kind

What changes based on `kind`? Currently: display chip + `list --kind` filter. Could:

- Default bucket per kind? (`spec` → backlog; `bug` → next?) — probably no, decoupling axes is by design.
- Default priority? (`bug` → high?) — no, same reasoning.
- Different default body templates per kind? — yes, useful (e.g. bug template has Steps to Reproduce; feat template has Acceptance Criteria).
- Different TUI rendering? — probably yes, color per kind.

## When to activate

After 4+ weeks of #24 shipped + dogfooding. If `kind` is being filled in consistently and the soft enum holds up, we lock decisions and ship a tight #25. If `kind` is rarely used, we revisit whether to keep it at all.

## Open questions for grilling later

- Should `kind` be required? Currently optional everywhere.
- Should there be per-activity custom kinds? (e.g. a writing activity might have `chapter`, `scene`.)
- Should auto-inference be configurable (registry of prefix→kind mappings in config)?
- Should `kind` drive the chip color in TUI/chat-rendering?

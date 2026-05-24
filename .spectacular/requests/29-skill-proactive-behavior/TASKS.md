---
request: 29-skill-proactive-behavior
status: done
updated: 2026-05-24
---

# Tasks — 29-skill-proactive-behavior

## Group 1 — Frontmatter + hard rules ✅
- [x] Bump SKILL.md version 0.6.1 → 0.9.1
- [x] Expand `description` to include dashboards, ranking, cross-activity routing
- [x] Hard rule 10 — never `forget` or `--slug` rename without confirmation
- [x] Hard rule 11 — cross-activity writes use `--activity <id>`
- [x] Hard rule 12 — when intent is ambiguous, ASK or fall back to inbox

## Group 2 — Proactive behaviors section ✅
- [x] Intent → verb routing table (11 user phrasings)
- [x] Three framing rules: read before write, JSON for agents, never grep what a verb knows

## Group 3 — Triage rituals ✅
- [x] Morning review
- [x] End of day
- [x] Inbox triage
- [x] Weekly stale check
- [x] Cross-project sweep

## Group 4 — Decision trees ✅
- [x] Adding a task
- [x] Editing a task (positional / --task / --activity axis selection)
- [x] Moving between buckets (lifecycle / pipeline / mv / set --bucket)
- [x] Reading a project (status / get / list tasks / dashboard / next / impact)

## Group 5 — Reading vs writing safety section ✅
- [x] Read-first reminder
- [x] Confirmation list for forget / --slug / init / bulk set

## Group 6 — Verb index refresh ✅
- [x] add task/activity, dashboard/next/impact, get activity, list tasks/activities, forget activity
- [x] Cross-activity flag callout inline

## Group 7 — Ship ✅
- [x] CHANGELOG [0.9.1] entry
- [x] SKILL.md version 0.9.1
- [x] PLAN/TASKS status: queued → done
- [ ] Commit (manual, user-initiated)

## Out of scope (deferred)

- **Inbox activity convention**: deferred to a separate request — needs a config schema decision (`[inbox] activity = "..."` vs an env var vs a "designated activity" flag in `activity.md`) plus CLI changes. Rule 12 covers the ambiguous-intent case for now.
- **`references/dashboards.md`** dedicated file: the dashboard surface is small enough that the table in `cli-verbs.md` plus the SKILL.md routing section suffice. Revisit if the dashboard family grows.
- **Manual smoke test** with a fresh agent session: not automatable; left for the user to verify in real usage.

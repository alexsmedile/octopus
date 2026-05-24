---
status: queued
priority: high
owner: alex
updated: 2026-05-24
summary: "Upgrade SKILL.md to teach agents proactive task-management behaviors. Lands after #26 and #27 ship the verbs."
related:
  - 26-cross-activity-writes
  - 27-cross-activity-reads-and-dashboards
gates:
  - 26-cross-activity-writes
  - 27-cross-activity-reads-and-dashboards
---

# Skill upgrade — proactive agent behaviors

## Goal

`skills/octopus/SKILL.md` currently documents verbs. After #26/#27 ship, the CLI has the surface to be **the** task-management protocol for agents — but the skill doesn't teach agents how to use it proactively. This request closes that gap.

The goal: an agent loading the skill can do all five things the user expects without further coaching:

1. See all open activities from anywhere.
2. Navigate to any activity and understand its status.
3. Add tasks remotely without `cd`.
4. Manage projects from a global view OR focus on a specific one.
5. Surface high-impact next actions across all activities.

## Why

After #26/#27 land, the verbs exist. The skill doesn't currently tell agents WHEN to use them. This request adds a "Proactive behaviors" section + behavioral playbook that maps user intents to verb invocations.

Without this, agents will continue to either:
- Refuse the global-shell case ("I'm not inside an activity") even though they could now use `--activity`.
- Pick the wrong verb (e.g. `octopus list --all | grep` instead of `octopus dashboard`).
- Fail to suggest next actions (no awareness that `octopus next` exists).

## Scope

### Phase 1 — New SKILL.md sections

#### 1. "Proactive behaviors" — top-level intent mapping

A new section after "Agent workflow" that explicitly maps user phrasing to verb choice:

| User says | Agent runs |
|---|---|
| "what should I do" / "what's next" / "what's on my plate" | `octopus next` (top 3), then suggest `octopus impact` for more |
| "what's the status of <project>" | `octopus status <project>` (rich) |
| "show me everything" / "dashboard" / "overview" | `octopus dashboard` |
| "add a task to <project>" / "remind me to X for <project>" | `octopus add task "X" --activity <project>` |
| "add this to the inbox" / no project named | ask which activity; OR fall back to a designated inbox activity if configured |
| "what's open" / "what's in progress" | `octopus activities` (card layout) |
| "give me JSON of <project>" | `octopus get <project>` |
| "I'm working on <project>" | `octopus status <project>` first, then proceed |
| "what's overdue" | `octopus list --all --has-overdue` |
| "what's blocked" | `octopus stuck` |
| "what's in my mind" (pinned + now + overdue) | `octopus dashboard` (composite) |

#### 2. "Triage rituals" — recurring patterns

A section on common multi-step workflows:

- **Morning review:** `octopus dashboard` → drill into top-priority activity with `octopus status` → `octopus next` for what to pick up.
- **End of day:** `octopus activities --touched-within 1` to see what got worked on; record observations in memory via `octopus memory append`.
- **Inbox triage:** pull all TODO.md / Reminders → review the resulting backlog → promote anything that needs a spec to spectacular.
- **Stale check:** `octopus stale` weekly; archive or drop the truly dead.

#### 3. "Choosing the right verb for write operations"

A decision tree:

```
User wants to add a task.
  ├─ Cwd inside the target activity? → octopus capture or octopus add task
  ├─ Cwd outside, but user named the activity? → octopus add task "X" --activity <id>
  └─ No clear activity? → ASK ("which project?") or use inbox fallback if configured

User wants to edit a task.
  ├─ Cwd inside the activity, single target? → octopus set <slug> --field X
  ├─ Multiple tasks across activities? → octopus set --task t1 t2 --field X
  └─ Activity-level field (priority, status, etc.)? → octopus set --activity <id> --field X

User wants to move a task between buckets.
  ├─ With lifecycle side effects (dates, etc.) → octopus start/finish/drop/plan/focus
  ├─ Pure file move + frontmatter? → octopus mv <slug> <bucket>
  └─ Frontmatter only (warns about mismatch) → octopus set <slug> --bucket <name>
```

#### 4. "Reading vs writing" — never blow up the user's data

A reaffirmation, expanded:

- **Always read first.** Before writing, agents should `octopus status` or `octopus get` to confirm the activity and target.
- **Never `octopus init`** without explicit confirmation from the user.
- **Never `octopus forget`** without explicit confirmation.
- **Never `octopus set --slug`** (slug rename) without explicit confirmation and `-y` flag.
- **Never bulk-update** without explicit confirmation; the multi-target `set --task t1 t2 t3` is powerful.
- **JSON output is for agents.** Default to `octopus get` when programmatic, `octopus status` when the user is watching.

### Phase 2 — `references/cli-verbs.md` updates

Already mirrors the verb surface. After #26/#27, add the new verbs to the reference table with one-line behavior summaries. Cross-link to the dashboard's locked ranking heuristic.

### Phase 3 — `references/dashboards.md` (new file)

A dedicated reference for the dashboard family:

- The locked ranking heuristic (from #27).
- Output formats for `dashboard`, `next`, `impact`.
- When to use which one (next: instant decision; impact: planning session; dashboard: open-ended status check).
- How `--format json` shapes are documented.

### Phase 4 — Inbox activity convention (optional)

If the user has configured an "inbox" activity (in `~/.config/octopus/config.toml`):

```toml
[inbox]
activity = "inbox-a3f9"
```

Agents fall back to it when:
- User says "add this idea" with no project named.
- User says "remember to X" with no clear home.

When `[inbox]` is not configured, agents ASK ("which project?") rather than picking arbitrarily.

This phase is **optional in #29**. Could be a separate request if scope balloons.

### Phase 5 — Hard rules updates

Already-locked hard rules in SKILL.md need additions:

- **Rule 5 (filenames are CLI-owned)** — already says use `set --slug`. Reaffirmed.
- **NEW Rule 10:** "Never call `forget` or `--slug` cascading rename without explicit user confirmation."
- **NEW Rule 11:** "Cross-activity writes use `--activity <id>`. Never assume cwd context when the user has named a target."
- **NEW Rule 12:** "When user intent is ambiguous (no clear target activity), ASK or use the inbox fallback. Do NOT pick arbitrarily."

## Out of scope

- **New verbs** — all verbs ship in #26/#27. #29 is documentation only.
- **Behavior changes** to existing verbs.
- **Inbox concept implementation** in code — if the inbox config is needed, that's a separate request.
- **TUI changes** — separate request.

## Approach

1. Draft the "Proactive behaviors" intent-mapping table.
2. Write the triage-rituals section.
3. Add the write-verb decision tree.
4. Update hard rules.
5. Mirror to `references/cli-verbs.md` where verb info changes.
6. Write `references/dashboards.md` from scratch.
7. Smoke-test the skill: load it in a fresh agent session, give it open-ended user prompts, check it picks the right verbs.

## Deliverables

- [ ] `skills/octopus/SKILL.md` v0.6.1 → v0.9.0:
  - [ ] New "Proactive behaviors" section.
  - [ ] New "Triage rituals" section.
  - [ ] New "Choosing the right verb" decision-tree section.
  - [ ] Hard rules 10/11/12 added.
- [ ] `references/cli-verbs.md` — new verbs from #26/#27 documented inline.
- [ ] `references/dashboards.md` — new file with the ranking heuristic and verb usage.
- [ ] Manual smoke test (agent loaded with skill responds correctly to 5 example prompts).
- [ ] CHANGELOG [0.9.0] section.

## Open for grilling

- **Inbox activity** in this request or separate? My pick: **separate** if it needs config + code; **here** if it's just a SKILL.md convention with no code.
- **Whether to ship #29 as patch (0.8.x) or minor (0.9.0).** Patch if it's pure docs; minor if it adds inbox config or any code. Lean minor since the skill version bump is non-trivial.
- **"Triage rituals" vs "Workflows"** — name bikeshed.

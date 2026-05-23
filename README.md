<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="140" height="140" role="img" aria-label="Octopus mascot">
  <defs>
    <radialGradient id="head" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0%" stop-color="#ff9a8b"/>
      <stop offset="100%" stop-color="#e07a6a"/>
    </radialGradient>
    <linearGradient id="arm" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e07a6a"/>
      <stop offset="100%" stop-color="#c4604f"/>
    </linearGradient>
  </defs>
  <!-- arms -->
  <g fill="url(#arm)" opacity="0.9">
    <path d="M55,120 Q35,140 30,170 Q40,175 55,160 Q60,145 65,135 Z"/>
    <path d="M75,130 Q65,160 55,185 Q68,188 78,170 Q82,155 82,140 Z"/>
    <path d="M100,135 Q98,165 95,190 Q108,190 108,170 Q108,150 108,140 Z"/>
    <path d="M125,130 Q135,160 145,185 Q132,188 122,170 Q118,155 118,140 Z"/>
    <path d="M145,120 Q165,140 170,170 Q160,175 145,160 Q140,145 135,135 Z"/>
  </g>
  <!-- head -->
  <ellipse cx="100" cy="85" rx="55" ry="50" fill="url(#head)"/>
  <!-- subtle highlight -->
  <ellipse cx="82" cy="68" rx="14" ry="10" fill="#fff" opacity="0.25"/>
  <!-- eyes -->
  <circle cx="82" cy="85" r="9" fill="#fff"/>
  <circle cx="118" cy="85" r="9" fill="#fff"/>
  <circle cx="84" cy="87" r="4.5" fill="#2d3142"/>
  <circle cx="120" cy="87" r="4.5" fill="#2d3142"/>
  <circle cx="85.5" cy="85.5" r="1.5" fill="#fff"/>
  <circle cx="121.5" cy="85.5" r="1.5" fill="#fff"/>
  <!-- smile -->
  <path d="M88,108 Q100,118 112,108" stroke="#2d3142" stroke-width="2.5" fill="none" stroke-linecap="round"/>
</svg>

# Octopus

**A folder-first task system.**

*Tentacles fan out into every folder you care about. Each project gets its own task structure — captured, organized, alive — right where the work belongs.*

*Octopus reaches into each folder, understands what it is, smartly organizes the tasks inside it — and also acts as the central system that ties them all together. One brain, eight arms. Backed by a CLI and a Claude Code skill.*

![Status](https://img.shields.io/badge/status-active%20build-coral)
![Spec](https://img.shields.io/badge/spec-v1-teal)
![License](https://img.shields.io/badge/license-MIT-blue)
![Local-first](https://img.shields.io/badge/local--first-yes-success)
![No SaaS](https://img.shields.io/badge/no%20SaaS-ever-lightgrey)

</div>

---

## The pitch

You have folders. Lots of folders. A code repo here. A side project there. A vault of notes. A client gig. Each one is a *thing you're doing*.

Most task apps make you describe those things twice — once as folders on disk, once as records in some app's database. Then they drift apart and you spend Sunday afternoon reconciling them.

Octopus skips the middleman.

```
cd ~/code/shift
octopus init
octopus capture "fix the webhook auth bug" --now
```

That's it. The folder is now a tracked **activity**. Tasks live inside it as plain markdown files. State travels with the folder. Move it, rename it, sync it through Dropbox — the activity moves too.

Open the same folder in Obsidian? Symlink it. Open it in the terminal? `octopus where`. Hand it to Claude Code? The agent reads the same files. **Every viewer is just a lens on the same disk truth.**

> [!NOTE]
> The folder *is* the activity. The protocol — not the implementation — is the product. The CLI is Python today; nothing stops a Go or Rust rewrite tomorrow.

---

## Why this exists

We tried the alternatives. Each one solved one slice and broke three others:

| | Captures fast | Holds context | Lives with the work | Knows your AI sessions |
|---|:-:|:-:|:-:|:-:|
| Apple Reminders | ✅ | ❌ | ❌ | ❌ |
| Obsidian | ⚠️ | ✅ | ⚠️ | ❌ |
| Random `TODO.md` files | ✅ | ⚠️ | ✅ | ❌ |
| SaaS task apps | ✅ | ✅ | ❌ | ❌ |
| **Octopus** | ✅ | ✅ | ✅ | ✅ |

The fracture is the problem. Octopus is the seam.

---

## What an `.octopus/` folder looks like

Every tracked folder gets a hidden `.octopus/` directory. That's where the brain lives.

<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 460" width="100%" role="img" aria-label="Octopus folder scaffold">
  <defs>
    <linearGradient id="rootGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#fff7ed"/>
      <stop offset="100%" stop-color="#fef3c7"/>
    </linearGradient>
    <linearGradient id="brainGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#ffe1dc"/>
      <stop offset="100%" stop-color="#ffd1c7"/>
    </linearGradient>
  </defs>
  <style>
    .label { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 14px; fill: #2d3142; }
    .note  { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11px; fill: #6b7280; }
    .head  { font-family: -apple-system, system-ui, sans-serif; font-size: 13px; font-weight: 600; fill: #2d3142; }
    .tag   { font-family: -apple-system, system-ui, sans-serif; font-size: 11px; fill: #6b7280; }
  </style>

  <!-- Outer folder (your project) -->
  <rect x="20" y="20" width="680" height="420" rx="14" fill="url(#rootGrad)" stroke="#f59e0b" stroke-width="1.5"/>
  <text x="40" y="48" class="head">📁 ~/code/shift &nbsp; (any folder on disk)</text>
  <text x="40" y="68" class="note">your code, your notes, your stuff — Octopus doesn't touch it</text>

  <!-- The .octopus/ brain -->
  <rect x="40" y="90" width="640" height="330" rx="10" fill="url(#brainGrad)" stroke="#e07a6a" stroke-width="1.5"/>
  <text x="60" y="118" class="head">🐙 .octopus/ &nbsp; (the brain — hidden, self-contained, plain markdown)</text>

  <!-- activity.md -->
  <rect x="60" y="135" width="280" height="36" rx="6" fill="#fff" stroke="#e07a6a" stroke-width="1"/>
  <text x="74" y="158" class="label">📄 activity.md</text>
  <text x="350" y="158" class="tag">required • identity card for this folder</text>

  <!-- config.toml -->
  <rect x="60" y="178" width="280" height="32" rx="6" fill="#fff" stroke="#e07a6a" stroke-width="0.8" stroke-dasharray="3,3"/>
  <text x="74" y="199" class="label">⚙️  config.toml</text>
  <text x="350" y="199" class="tag">optional • per-activity overrides</text>

  <!-- tasks/ -->
  <rect x="60" y="218" width="280" height="32" rx="6" fill="#fff" stroke="#e07a6a" stroke-width="1"/>
  <text x="74" y="239" class="label">📂 tasks/</text>
  <text x="350" y="239" class="tag">one .md per task, sorted by bucket</text>

  <!-- bucket subfolders -->
  <g>
    <rect x="90" y="258" width="60" height="22" rx="5" fill="#f0fdfa" stroke="#5eead4"/>
    <text x="100" y="274" class="note">backlog/</text>
    <rect x="155" y="258" width="48" height="22" rx="5" fill="#f0fdfa" stroke="#5eead4"/>
    <text x="165" y="274" class="note">next/</text>
    <rect x="208" y="258" width="44" height="22" rx="5" fill="#fef9c3" stroke="#facc15"/>
    <text x="218" y="274" class="note">now/</text>
    <rect x="257" y="258" width="48" height="22" rx="5" fill="#f3f4f6" stroke="#9ca3af"/>
    <text x="267" y="274" class="note">done/</text>
    <rect x="310" y="258" width="64" height="22" rx="5" fill="#f3f4f6" stroke="#9ca3af"/>
    <text x="320" y="274" class="note">dropped/</text>
  </g>

  <!-- sessions/ -->
  <rect x="60" y="290" width="280" height="32" rx="6" fill="#fff" stroke="#e07a6a" stroke-width="0.8" stroke-dasharray="3,3"/>
  <text x="74" y="311" class="label">📂 sessions/</text>
  <text x="350" y="311" class="tag">optional • where work happened, dated</text>

  <!-- handoffs/ -->
  <rect x="60" y="330" width="280" height="32" rx="6" fill="#fff" stroke="#e07a6a" stroke-width="0.8" stroke-dasharray="3,3"/>
  <text x="74" y="351" class="label">📂 handoffs/</text>
  <text x="350" y="351" class="tag">optional • notes for future-you or another agent</text>

  <!-- memory.md -->
  <rect x="60" y="370" width="280" height="32" rx="6" fill="#fff" stroke="#e07a6a" stroke-width="0.8" stroke-dasharray="3,3"/>
  <text x="74" y="391" class="label">📄 memory.md</text>
  <text x="350" y="391" class="tag">optional • accumulated context that survives sessions</text>

  <!-- Side panel: the principle -->
  <rect x="445" y="135" width="225" height="267" rx="8" fill="#fff" stroke="#cbd5e1"/>
  <text x="460" y="160" class="head">The radical bit</text>
  <text x="460" y="185" class="note">There's no database file you</text>
  <text x="460" y="200" class="note">can lose. Just folders and</text>
  <text x="460" y="215" class="note">markdown.</text>
  <text x="460" y="245" class="note">Move the folder?</text>
  <text x="460" y="260" class="note">→ the activity moves too.</text>
  <text x="460" y="285" class="note">Open it in Obsidian?</text>
  <text x="460" y="300" class="note">→ symlink, no copy.</text>
  <text x="460" y="325" class="note">Hand it to an AI agent?</text>
  <text x="460" y="340" class="note">→ it reads the same files.</text>
  <text x="460" y="370" class="note">grep, find, git, diff —</text>
  <text x="460" y="385" class="note">all your tools just work.</text>
</svg>

</div>

Everything optional except `activity.md`. The CLI creates folders lazily as you use them.

---

## Five buckets — that's the whole pipeline

Octopus has one big idea about workflow: **five piles**, and tasks move between them. No fancy kanban columns. No custom states. Just five buckets that match how humans actually think.

<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 280" width="100%" role="img" aria-label="The five-bucket pipeline">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8"/>
    </marker>
  </defs>
  <style>
    .b-title { font-family: -apple-system, system-ui, sans-serif; font-size: 16px; font-weight: 700; fill: #2d3142; }
    .b-desc  { font-family: -apple-system, system-ui, sans-serif; font-size: 11px; fill: #4b5563; }
    .arrow-l { font-family: ui-monospace, monospace; font-size: 10px; fill: #94a3b8; }
    .head    { font-family: -apple-system, system-ui, sans-serif; font-size: 13px; fill: #6b7280; font-style: italic; }
  </style>

  <text x="380" y="30" class="head" text-anchor="middle">a task flows left → right, with one side exit</text>

  <!-- BACKLOG -->
  <rect x="20" y="60" width="125" height="110" rx="12" fill="#f0f9ff" stroke="#7dd3fc" stroke-width="2"/>
  <text x="82.5" y="100" class="b-title" text-anchor="middle">backlog</text>
  <text x="82.5" y="125" class="b-desc" text-anchor="middle">ideas, intents,</text>
  <text x="82.5" y="140" class="b-desc" text-anchor="middle">stuff you'd</text>
  <text x="82.5" y="155" class="b-desc" text-anchor="middle">maybe do</text>

  <!-- arrow -->
  <line x1="148" y1="115" x2="180" y2="115" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="164" y="105" class="arrow-l" text-anchor="middle">plan</text>

  <!-- NEXT -->
  <rect x="185" y="60" width="125" height="110" rx="12" fill="#f0fdfa" stroke="#5eead4" stroke-width="2"/>
  <text x="247.5" y="100" class="b-title" text-anchor="middle">next</text>
  <text x="247.5" y="125" class="b-desc" text-anchor="middle">decided, ready,</text>
  <text x="247.5" y="140" class="b-desc" text-anchor="middle">queued up,</text>
  <text x="247.5" y="155" class="b-desc" text-anchor="middle">not started yet</text>

  <line x1="313" y1="115" x2="345" y2="115" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="329" y="105" class="arrow-l" text-anchor="middle">focus</text>

  <!-- NOW -->
  <rect x="350" y="60" width="125" height="110" rx="12" fill="#fef9c3" stroke="#facc15" stroke-width="2.5"/>
  <text x="412.5" y="100" class="b-title" text-anchor="middle">now</text>
  <text x="412.5" y="125" class="b-desc" text-anchor="middle">today's pile,</text>
  <text x="412.5" y="140" class="b-desc" text-anchor="middle">small, focused,</text>
  <text x="412.5" y="155" class="b-desc" text-anchor="middle">clearing soon</text>

  <line x1="478" y1="115" x2="510" y2="115" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="494" y="105" class="arrow-l" text-anchor="middle">finish</text>

  <!-- DONE -->
  <rect x="515" y="60" width="125" height="110" rx="12" fill="#f0fdf4" stroke="#86efac" stroke-width="2"/>
  <text x="577.5" y="100" class="b-title" text-anchor="middle">done</text>
  <text x="577.5" y="125" class="b-desc" text-anchor="middle">finished work,</text>
  <text x="577.5" y="140" class="b-desc" text-anchor="middle">end_date</text>
  <text x="577.5" y="155" class="b-desc" text-anchor="middle">stamped</text>

  <!-- DROPPED (side exit) -->
  <rect x="515" y="200" width="125" height="60" rx="12" fill="#f3f4f6" stroke="#9ca3af" stroke-width="2"/>
  <text x="577.5" y="225" class="b-title" text-anchor="middle">dropped</text>
  <text x="577.5" y="245" class="b-desc" text-anchor="middle">intentionally abandoned</text>

  <!-- side exit arrows from now and next -->
  <path d="M 412 170 Q 412 230 515 230" stroke="#94a3b8" stroke-width="2" fill="none" marker-end="url(#arrow)"/>
  <text x="455" y="220" class="arrow-l" text-anchor="middle">drop</text>

  <!-- backward arrow: park (now/next -> backlog) -->
  <path d="M 350 170 Q 250 220 145 175" stroke="#cbd5e1" stroke-width="1.5" fill="none" stroke-dasharray="4,3" marker-end="url(#arrow)"/>
  <text x="248" y="215" class="arrow-l" text-anchor="middle" fill="#94a3b8">park (any → backlog)</text>

  <text x="380" y="275" class="head" text-anchor="middle" fill="#94a3b8">resume? `octopus start` on done/dropped → back to now</text>
</svg>

</div>

The verbs that move tasks between buckets:

| You say | Bucket goes to | What it means |
|---|---|---|
| `octopus capture "..."` | → backlog | "Catch this idea before I forget." |
| `octopus plan <slug>` | → next | "I'm committing to this." |
| `octopus focus <slug>` | → now | "This is for right now." Also pins it. |
| `octopus defer <slug>` | now → next | "Not today after all." |
| `octopus park <slug>` | any → backlog | "Let it cool. I'm not ready." |
| `octopus finish <slug>` | → done | "🎉" |
| `octopus drop <slug>` | → dropped | "Nope. Moving on." |
| `octopus start <slug>` | (resumes from done/dropped) | Idempotent. Just stamps `start_date`. |

That's the whole pipeline. Eight verbs, five buckets.

---

## A task's life, end to end

<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 480" width="100%" role="img" aria-label="A typical task lifecycle">
  <defs>
    <marker id="arr2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#9ca3af"/>
    </marker>
  </defs>
  <style>
    .step-num { font-family: -apple-system, system-ui, sans-serif; font-size: 22px; font-weight: 800; fill: #fff; }
    .step-cmd { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 13px; fill: #2d3142; font-weight: 600; }
    .step-meta { font-family: ui-monospace, monospace; font-size: 11px; fill: #6b7280; }
    .step-desc { font-family: -apple-system, system-ui, sans-serif; font-size: 12px; fill: #4b5563; }
    .axis { font-family: -apple-system, system-ui, sans-serif; font-size: 11px; fill: #94a3b8; font-style: italic; }
  </style>

  <!-- Step 1: capture -->
  <circle cx="60" cy="60" r="22" fill="#0ea5e9"/>
  <text x="60" y="68" class="step-num" text-anchor="middle">1</text>
  <rect x="100" y="35" width="620" height="50" rx="8" fill="#f0f9ff" stroke="#7dd3fc"/>
  <text x="115" y="55" class="step-cmd">$ octopus capture "fix the webhook auth bug"</text>
  <text x="115" y="73" class="step-desc">📥 A file appears: .octopus/tasks/backlog/fix-webhook-auth-bug.md</text>

  <!-- arrow -->
  <line x1="60" y1="85" x2="60" y2="115" stroke="#9ca3af" stroke-width="2" marker-end="url(#arr2)"/>

  <!-- Step 2: focus -->
  <circle cx="60" cy="140" r="22" fill="#14b8a6"/>
  <text x="60" y="148" class="step-num" text-anchor="middle">2</text>
  <rect x="100" y="115" width="620" height="50" rx="8" fill="#f0fdfa" stroke="#5eead4"/>
  <text x="115" y="135" class="step-cmd">$ octopus focus fix-webhook-auth-bug</text>
  <text x="115" y="153" class="step-desc">🎯 Moved to tasks/now/. Pinned: true. Sorts to top of every list.</text>

  <line x1="60" y1="165" x2="60" y2="195" stroke="#9ca3af" stroke-width="2" marker-end="url(#arr2)"/>

  <!-- Step 3: start -->
  <circle cx="60" cy="220" r="22" fill="#f59e0b"/>
  <text x="60" y="228" class="step-num" text-anchor="middle">3</text>
  <rect x="100" y="195" width="620" height="50" rx="8" fill="#fef9c3" stroke="#facc15"/>
  <text x="115" y="215" class="step-cmd">$ octopus start fix-webhook-auth-bug</text>
  <text x="115" y="233" class="step-desc">⏱️  start_date stamped (today). Idempotent — run it again, nothing changes.</text>

  <line x1="60" y1="245" x2="60" y2="275" stroke="#9ca3af" stroke-width="2" marker-end="url(#arr2)"/>

  <!-- Step 4: block -->
  <circle cx="60" cy="300" r="22" fill="#ef4444"/>
  <text x="60" y="308" class="step-num" text-anchor="middle">4</text>
  <rect x="100" y="275" width="620" height="50" rx="8" fill="#fef2f2" stroke="#fca5a5"/>
  <text x="115" y="295" class="step-cmd">$ octopus block fix-webhook-auth-bug --reason "missing test creds"</text>
  <text x="115" y="313" class="step-desc">🚧 issue: blocked. Also logged a dated entry into memory.md.</text>

  <line x1="60" y1="325" x2="60" y2="355" stroke="#9ca3af" stroke-width="2" marker-end="url(#arr2)"/>

  <!-- Step 5: unblock -->
  <circle cx="60" cy="380" r="22" fill="#14b8a6"/>
  <text x="60" y="388" class="step-num" text-anchor="middle">5</text>
  <rect x="100" y="355" width="620" height="50" rx="8" fill="#f0fdfa" stroke="#5eead4"/>
  <text x="115" y="375" class="step-cmd">$ octopus unblock fix-webhook-auth-bug</text>
  <text x="115" y="393" class="step-desc">✅ creds arrived. Cleared the impediment. Back at it.</text>

  <line x1="60" y1="405" x2="60" y2="435" stroke="#9ca3af" stroke-width="2" marker-end="url(#arr2)"/>

  <!-- Step 6: finish -->
  <circle cx="60" cy="460" r="22" fill="#22c55e"/>
  <text x="60" y="468" class="step-num" text-anchor="middle">6</text>
  <rect x="100" y="435" width="620" height="40" rx="8" fill="#f0fdf4" stroke="#86efac"/>
  <text x="115" y="455" class="step-cmd">$ octopus finish fix-webhook-auth-bug</text>
  <text x="115" y="470" class="step-desc">🎉 Moved to done/. end_date stamped. pinned cleared.</text>
</svg>

</div>

The file at `.octopus/tasks/done/fix-webhook-auth-bug.md` ends up looking like this:

```yaml
---
title: Fix the webhook auth bug
created: 2026-05-22
bucket: done
start_date: 2026-05-22
end_date: 2026-05-23
---

## References
```

Three lines added beyond the capture defaults. Everything else is omitted because **defaults don't get written**. The file stays small. Hand-edit it whenever — Octopus rolls with it.

---

## Five axes — how a task knows where it stands

Tasks have five independent ways of being "in motion." Each one answers a different question. None of them overlap.

<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 380" width="100%" role="img" aria-label="The five axes of task state">
  <style>
    .axis-name { font-family: -apple-system, system-ui, sans-serif; font-size: 14px; font-weight: 700; fill: #2d3142; }
    .axis-q    { font-family: -apple-system, system-ui, sans-serif; font-size: 12px; fill: #4b5563; font-style: italic; }
    .axis-field { font-family: ui-monospace, monospace; font-size: 12px; fill: #c4604f; font-weight: 600; }
    .axis-val { font-family: ui-monospace, monospace; font-size: 11px; fill: #6b7280; }
    .num { font-family: -apple-system, system-ui, sans-serif; font-size: 24px; font-weight: 800; fill: #fff; }
  </style>

  <!-- AXIS 1 — PIPELINE -->
  <circle cx="40" cy="50" r="24" fill="#0ea5e9"/>
  <text x="40" y="58" class="num" text-anchor="middle">1</text>
  <text x="80" y="40" class="axis-name">PIPELINE</text>
  <text x="80" y="58" class="axis-q">Where in my workflow does this live?</text>
  <text x="80" y="76" class="axis-field">bucket:</text>
  <text x="140" y="76" class="axis-val">backlog · next · now · done · dropped</text>

  <!-- AXIS 2 — DOMAIN WORKFLOW -->
  <circle cx="40" cy="130" r="24" fill="#14b8a6"/>
  <text x="40" y="138" class="num" text-anchor="middle">2</text>
  <text x="80" y="120" class="axis-name">DOMAIN WORKFLOW</text>
  <text x="80" y="138" class="axis-q">What sub-stage within this kind of work?</text>
  <text x="80" y="156" class="axis-field">stage:</text>
  <text x="140" y="156" class="axis-val">free-form (e.g. idea · draft · editing · published)</text>

  <!-- AXIS 3 — RUNTIME -->
  <circle cx="40" cy="210" r="24" fill="#a855f7"/>
  <text x="40" y="218" class="num" text-anchor="middle">3</text>
  <text x="80" y="200" class="axis-name">RUNTIME</text>
  <text x="80" y="218" class="axis-q">Is a machine actively executing this?</text>
  <text x="80" y="236" class="axis-field">run_state:</text>
  <text x="160" y="236" class="axis-val">queued · running · finished · failed   (absent = idle)</text>

  <!-- AXIS 4 — ATTENTION -->
  <circle cx="40" cy="290" r="24" fill="#f59e0b"/>
  <text x="40" y="298" class="num" text-anchor="middle">4</text>
  <text x="80" y="280" class="axis-name">ATTENTION</text>
  <text x="80" y="298" class="axis-q">Should this jump to the top of every list?</text>
  <text x="80" y="316" class="axis-field">pinned:</text>
  <text x="140" y="316" class="axis-val">true   (absent = not pinned)</text>

  <!-- AXIS 5 — IMPEDIMENT -->
  <circle cx="40" cy="370" r="24" fill="#ef4444"/>
  <text x="40" y="378" class="num" text-anchor="middle">5</text>
  <text x="80" y="360" class="axis-name">IMPEDIMENT</text>
  <text x="80" y="378" class="axis-q">Is anything stuck?</text>
  <text x="80" y="0" class="axis-field"></text>
  <!-- (drawn at very edge so we keep box compact) -->

  <!-- right side: visibility flag -->
  <rect x="540" y="20" width="200" height="120" rx="10" fill="#fefce8" stroke="#facc15" stroke-dasharray="4,3"/>
  <text x="640" y="50" class="axis-name" text-anchor="middle">+ VISIBILITY</text>
  <text x="640" y="72" class="axis-q" text-anchor="middle">Should I see this at all?</text>
  <text x="640" y="98" class="axis-field" text-anchor="middle">archived:</text>
  <text x="640" y="118" class="axis-val" text-anchor="middle">true   (default: visible)</text>
  <text x="640" y="135" class="axis-val" text-anchor="middle" fill="#94a3b8">— not really an axis;</text>

  <!-- right side: derived -->
  <rect x="540" y="160" width="200" height="200" rx="10" fill="#f0fdfa" stroke="#5eead4"/>
  <text x="640" y="190" class="axis-name" text-anchor="middle">📐 derived, not stored</text>
  <text x="555" y="220" class="axis-val">"started?"</text>
  <text x="555" y="236" class="axis-val" fill="#4b5563">→ start_date present</text>
  <text x="555" y="262" class="axis-val">"finished?"</text>
  <text x="555" y="278" class="axis-val" fill="#4b5563">→ bucket: done</text>
  <text x="555" y="304" class="axis-val">"open loop?"</text>
  <text x="555" y="320" class="axis-val" fill="#4b5563">→ bucket NOT IN</text>
  <text x="555" y="335" class="axis-val" fill="#4b5563">   (done, dropped)</text>
</svg>

</div>

The trick is that all five are *independent*. A task can be `bucket: backlog` (haven't committed) AND `pinned: true` (nagging at me) AND `issue: waiting` (need someone else's input) AND `run_state: queued` (an agent will pick it up tonight) — all at once. Each axis carries information no other axis can.

> [!TIP]
> **Default-omission**: if a field is at its default, Octopus doesn't write it. So a normal-priority human task captured with no fuss has *three lines* of frontmatter: `title`, `created`, `bucket`. The file stays small. The signal stays loud.

---

## The verb cheat sheet

Octopus thinks in verbs, not field edits. The full list, organized by what they do:

### Capture
```
octopus capture "..."           # → backlog
octopus capture "..." --next    # → next
octopus capture "..." --now     # → now, pinned
```

### Move through the pipeline
```
octopus plan <slug>             # → next
octopus focus <slug>            # → now, pinned
octopus defer <slug>            # now → next
octopus park <slug>             # any → backlog, unpinned
```

### Lifecycle
```
octopus start <slug>            # stamp start_date (idempotent)
octopus finish <slug>           # → done, stamp end_date
octopus drop <slug>             # → dropped
```

### When something's stuck
```
octopus block <slug> --reason "..."
octopus wait  <slug> --for "..."
octopus unblock <slug>
```

### Attention
```
octopus pin <slug>              # surface to top of every list
octopus unpin <slug>
```

### Visibility
```
octopus archive <slug>          # hide from default views
octopus restore <slug>
```

### Look around
```
octopus where                   # what's the current activity?
octopus list                    # what's on my plate? (context-aware)
octopus list --all              # everything, everywhere
octopus loops                   # all open loops (unfinished)
octopus status <slug>           # detailed view, one activity
octopus task show <slug>        # the raw file
```

### Manage the index
```
octopus reindex                 # rebuild the SQLite index from disk
octopus config root add <path>  # tell Octopus where to look
octopus config root list
```

### Escape hatch
```
octopus set <slug> --priority urgent --due 2026-06-01 --stage editing
```

Type `octo` instead of `octopus` if you're in a hurry. Same thing.

---

## Installation

Octopus ships as a Python package. Requires Python **3.11+**.

### pipx (recommended)

```bash
pipx install octopus-cli
octopus --version
```

> Until octopus-cli lands on PyPI, install from a built wheel:
>
> ```bash
> git clone https://github.com/alexsmedile/octopus
> cd octopus/cli
> python -m build              # produces dist/octopus_cli-X.Y.Z-py3-none-any.whl
> pipx install ./dist/octopus_cli-*.whl
> ```

### From source (editable)

For development:

```bash
git clone https://github.com/alexsmedile/octopus
cd octopus/cli
pip install -e ".[dev]"
```

### Upgrade / uninstall

```bash
pipx upgrade octopus-cli      # or: pipx install --force ./dist/*.whl
pipx uninstall octopus-cli
```

### Sanity check

```bash
octopus --version             # → octopus X.Y.Z
octopus diagnose --no-zip     # prints version, config, index stats — for bug reports
```

`octopus diagnose` bundles a redacted report (paths under `$HOME` are rewritten to `~/`) into a zip you can attach to GitHub issues.

---

## How an `.octopus/` folder is born

```bash
cd ~/code/shift
octopus init --type code --area work
# ✓ Initialized activity shift at /Users/you/code/shift
#   storage mode: folders (backlog, done, dropped, next, now)
```

Now drop in a few tasks:

```bash
octopus capture "Fix the webhook auth bug" --next --priority urgent
octopus capture "Write release notes" --next
octopus capture "Refactor the auth middleware"
octopus focus fix-the-webhook-auth-bug
```

Where you are now:

```bash
$ octopus where

  Activity  shift
  Title     Shift
  Path      /Users/you/code/shift
  Type      code
  Status    active
  Area      work
  Storage   folders

  now      1
  next     1
  backlog  1

  Pinned:
    fix-the-webhook-auth-bug  Fix the webhook auth bug
```

Open `~/code/shift` in any editor. The `.octopus/` folder is right there. Open `~/code/shift/.octopus/tasks/now/fix-the-webhook-auth-bug.md` and you'll find clean YAML frontmatter + an empty body waiting for notes. Edit it. Octopus will roll with whatever you do.

---

## Where things live in this repo

```
octopus/
├── README.md                       ← you are here
├── CLAUDE.md                       ← agent rules + spec navigation map
├── AGENTS.md                       ← repo-wide agent rules
├── TODO.md                         ← deferred ideas (mind-view, routines, …)
│
├── cli/                            ← the Python CLI itself
│   ├── pyproject.toml
│   ├── src/octopus/                ← cli.py, core/, fs/, db/, config.py
│   └── tests/
│
├── skills/octopus/                 ← standalone Claude Code skill
│
├── .spectacular/                   ← design workspace + shipped specs
│   ├── PRD.md                      ← product vision
│   ├── SPEC.md                     ← the .octopus/ folder contract
│   ├── STACK.md                    ← Python 3.11+, Typer, Textual, SQLite
│   ├── DECISIONS.md                ← every locked decision, dated
│   ├── specs/              ← SCHEMA-*.md, CLI-VERBS.md, AXIS-MODEL.md
│   └── requests/                   ← PLAN.md / TASKS.md per build phase
│
└── _archive/                       ← old design drafts (kept, not active)
```

If you want to see how the sausage is made: **`.spectacular/PRD.md`** for vision, **`.spectacular/SPEC.md`** for the on-disk contract, **`.spectacular/specs/SCHEMA-TASK.md`** for the task frontmatter, **`.spectacular/DECISIONS.md`** for the play-by-play.

---

## Daily driver — the TUI

`octopus tui` opens a Textual TUI scoped to the current activity (CWD walk-up to the nearest `.octopus/`). Two modes, one keymap.

**Focus mode** (default, `1`) — three quadrants for the act loop:

```
┌── BACKLOG ───────────┬── ● NOW ─────────────┐
│   ▸ ship the TUI      │   handoff template   │
│     wire skill ref…   ├── ○ NEXT ────────────┤
│     refactor router   │   sqlite migrations  │
└──────────────────────┴─────────────────────┘
```

**Board mode** (`2`) — four-column kanban (`backlog → next → now → done`).

### Keymap

| Key | What |
|---|---|
| `1` / `2` | Focus / Board mode |
| `←` `→` | move between quadrants / columns |
| `↑` `↓` | move within a list (edges jump panes) |
| `Tab` / `S-Tab` | cycle panes |
| `Enter` | open task detail overlay |
| `n` | capture new task into focused pane |
| `m` | advance one step along the pipeline |
| `M` | move to a chosen bucket |
| `f` | finish task |
| `d` | drop (with y/n confirm) |
| `p` | toggle pin |
| `e` | open in `$EDITOR` |
| `s` / `S` | start session (quick / with title) |
| `/` | filter by title substring |
| `r` | refresh from index (clears filter) |
| `?` | help overlay (full keymap) |
| `q` | quit (confirms if a session is open) |

All mutations route through `octopus.actions` — the same write layer the CLI uses. There is no second source of truth.

---

## Status & what's next

**v0.3.0** released 2026-05-24 — the **Octopus → Spectacular promotion seam**. New `octopus promote` verb, `kind` work-classification field (`feat/bug/spec/polish/test/chore`), `list --kind/--promoted/--spec` filters, reindex-derived `related_tasks` on request PLAN.md, `[providers]` config with chip aliases. SQLite schema v1→v2 migrated in-place. **271 tests passing** (was 225). Install with `pipx install ./dist/octopus_cli-0.3.0-py3-none-any.whl`. See [CHANGELOG.md](CHANGELOG.md).

| Phase | What | State |
|---|---|---|
| 01 | Extract the spec from PRD into SCHEMA-*.md docs | ✅ done |
| 02 | Walking-skeleton CLI (init, capture, plan, focus, start, finish, drop, set, …) | ✅ done |
| 02b | Schema collapse — five-value bucket, dropped status/kind, pinned/stage/run_state added | ✅ done |
| 03 | SQLite index, reindex, list, status, config root | ✅ done |
| 04 | Sessions + memory + handoffs (multi-open cache, 5-section memory, fs-only handoffs) | ✅ done |
| — | Self-contained agent skill at `skills/octopus/` (SKILL.md + references/) | ✅ done |
| 11 | pipx distribution + `octopus diagnose` + CI + logging | ✅ done |
| 05 | Textual TUI — Focus + Board modes, pixel mascot, shared `octopus.actions` write layer | ✅ done |
| 08 | Claude Code + Codex plugin scaffold (6 commands, 3 agents, 2 hooks; install assistant deferred) | ✅ done |
| **06** | **Adapter framework** | 🟢 **next-up** |
| 07 | Obsidian symlink bridge | queued |
| 09 | Apple Reminders pull | queued |
| 12 | Lint cleanup (re-tighten ruff — debt deferred from #11) | queued |
| 18 | Mascot animation (tentacle wave + idle bob) | backlog |
| 19 | Task naming formula + kind/area schema exploration | backlog |

v1 ships when 06 + 07 are done. The protocol — `.octopus/` on disk — is the lock-in, not the Python.

---

## Honest positioning

### Octopus is for you if

- You live on the command line and run many projects at once.
- You want your tasks to **live next to your work**, not in a SaaS.
- You use Obsidian (or want to) and like plain-text-everything.
- You work with AI coding agents and want them to know where they are.
- You're allergic to losing your data in someone else's database.

### Octopus is *not* for you if

- You want a polished GUI app with native widgets. (We have a terminal TUI on the roadmap. It's a TUI.)
- You want team collaboration with permissions and comments. (Octopus is single-user. Git is your sync layer.)
- You need cloud sync built in. (No. Git, Syncthing, iCloud, Dropbox — pick one.)
- You want recurring tasks today. (Reserved for v2.)

---

## Credits & license

Built by Alessandro Smedile, 2026.

License: MIT. See [LICENSE](LICENSE) when v1 ships.

The mascot is a friendly orange octopus 🐙 because tasks have eight little arms reaching into every folder, and someone has to keep them straight.

---

<div align="center">

*The folder is the activity. The protocol is the product.*

</div>

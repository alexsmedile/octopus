---
status: queued
priority: low
owner: alex
updated: 2026-05-21
summary: "octopus serve — Textual web preview, FastAPI later if justified."
related:
  - 05-tui
  - 12-watcher-daemon
gates:
  - 05-tui
---

# Web viewer (v1.5)

## Goal

`octopus serve` exposes the TUI over HTTP via Textual's built-in `serve`. Zero new code for v1.5 — just plumbing. FastAPI dashboard is a separate v2 consideration if the Textual preview proves insufficient.

## To be expanded when activated.

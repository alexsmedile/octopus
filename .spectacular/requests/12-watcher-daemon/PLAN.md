---
status: queued
priority: low
owner: alex
updated: 2026-05-21
summary: "octopus watch — opt-in fsevents daemon for real-time index sync. Lands with web viewer."
related:
  - 13-viewer-web
gates:
  - 11-distribution-pipx
---

# Watcher daemon (v1.5)

## Goal

Background daemon using `watchdog` library for true real-time index sync. Off by default. The reason to build this is the web viewer wanting live data without polling.

## Scope summary

- `octopus watch start | stop | status`.
- PID at `~/.cache/octopus/watcher.pid`, logs at `~/.local/share/octopus/logs/watcher.log`.
- Subscribes only to configured roots, filters to `.octopus/**/*.md`.
- On change: single-file re-parse + upsert.

## To be expanded when activated.

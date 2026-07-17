---
status: done
priority: low
owner: alex
updated: 2026-07-16
summary: "octopus watch — opt-in fsevents daemon for real-time index sync. Shipped standalone ahead of the web viewer."
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

## Shipped (2026-07-16, `c67a323`)

Implemented as `octopus watch start|stop|status` managing a detached process. Prefers `watchdog` (native fsevents/inotify); falls back to mtime-diff polling when `watchdog` is unavailable or `[watcher] polling_fallback` is set. PID at `~/.cache/octopus/watcher.pid`, log at `~/.local/share/octopus/logs/watcher.log` per `SCHEMA-CONFIG.md` §5.2/5.3. `[watcher]` config block (`enabled`, `polling_fallback`) added to `SCHEMA-CONFIG.md`.

Landed standalone, ahead of `13-viewer-web` — not gated on it in practice, just related.

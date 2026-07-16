"""Background fsevents watcher daemon (v1.5, PRD §13.5, SCHEMA-CONFIG.md §5.2/5.3).

Opt-in, off by default. `octopus watch start|stop|status` manages a detached
process that reindexes on filesystem change instead of relying on the
CLI's per-read stale-check.
"""

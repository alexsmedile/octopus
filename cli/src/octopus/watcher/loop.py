"""The watch loop itself: reindex on filesystem change.

Prefers `watchdog` (native fsevents/inotify). Falls back to a plain mtime-diff
poll when `watchdog` is not installed, or when `[watcher] polling_fallback = true`
is set explicitly in config.

Debounces bursts of events (e.g. a git checkout touching many files at once)
into a single reindex, since `reindex_all` is not free to run per-file.
"""

from __future__ import annotations

import logging
import signal
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from octopus.db.connection import get_db
from octopus.db.reindex import reindex_all
from octopus.fs.discover import find_all_activities
from octopus.watcher.paths import log_path

_DEBOUNCE_SECONDS = 1.5
_POLL_INTERVAL_SECONDS = 5.0
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 5

_shutdown_requested = False


def _handle_shutdown(signum, frame) -> None:
    global _shutdown_requested
    _shutdown_requested = True


def _setup_watcher_logging() -> logging.Logger:
    """Configure a dedicated logger writing to watcher.log (SCHEMA-CONFIG.md §5.3).

    Distinct from octopus.core.logging's shared octopus.log — the watcher runs
    as a forked, detached process and needs its own handler regardless of what
    the parent CLI process already set up before forking.
    """
    logger = logging.getLogger("octopus.watcher")
    logger.handlers.clear()
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def _reindex(roots: list[Path]) -> None:
    log = logging.getLogger("octopus.watcher")
    conn = get_db()
    try:
        result = reindex_all(conn, roots, prune=True, accept_renames=True)
        log.info(
            "reindex activities=%d tasks=%d sessions=%d errors=%d",
            result.activities_seen, result.tasks_seen, result.sessions_seen,
            len(result.errors),
        )
    finally:
        conn.close()


def run_watch_loop(roots: list[Path], *, polling_fallback: bool = False) -> None:
    """Block, reindexing on filesystem change, until SIGTERM/SIGINT."""
    log = _setup_watcher_logging()
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    watchdog_available = False
    if not polling_fallback:
        try:
            import watchdog  # noqa: F401

            watchdog_available = True
        except ImportError:
            log.warning("watchdog not installed — falling back to polling")

    log.info(
        "watch loop start roots=%s mode=%s",
        [str(r) for r in roots],
        "fsevents" if watchdog_available else "polling",
    )
    _reindex(roots)  # initial sync so the index reflects state at start

    if watchdog_available:
        _run_fsevents(roots, log)
    else:
        _run_polling(roots, log)

    log.info("watch loop stopped")


def _run_fsevents(roots: list[Path], log) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    pending = {"dirty": False}

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.src_path.endswith(".md"):
                pending["dirty"] = True

    observer = Observer()
    handler = _Handler()
    for root in roots:
        if root.exists():
            observer.schedule(handler, str(root), recursive=True)
    observer.start()
    try:
        while not _shutdown_requested:
            time.sleep(_DEBOUNCE_SECONDS)
            if pending["dirty"]:
                pending["dirty"] = False
                try:
                    _reindex(roots)
                except Exception as exc:
                    log.error("reindex failed: %s", exc)
    finally:
        observer.stop()
        observer.join()


def _run_polling(roots: list[Path], log) -> None:
    last_mtimes: dict[Path, float] = _snapshot_mtimes(roots)
    while not _shutdown_requested:
        for _ in range(int(_POLL_INTERVAL_SECONDS * 10)):
            if _shutdown_requested:
                return
            time.sleep(0.1)
        current = _snapshot_mtimes(roots)
        if current != last_mtimes:
            last_mtimes = current
            try:
                _reindex(roots)
            except Exception as exc:
                log.error("reindex failed: %s", exc)


def _snapshot_mtimes(roots: list[Path]) -> dict[Path, float]:
    snapshot: dict[Path, float] = {}
    for activity_folder in find_all_activities(roots):
        for md_file in activity_folder.rglob("*.md"):
            try:
                snapshot[md_file] = md_file.stat().st_mtime
            except OSError:
                continue
    return snapshot

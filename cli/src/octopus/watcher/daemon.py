"""Process lifecycle for the watcher daemon: start/stop/status via PID file.

The daemon itself (`_run`) is a foreground loop; `start()` forks it into the
background with stdio redirected to the watcher log, per SCHEMA-CONFIG.md §5.2/5.3.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from octopus.watcher.paths import log_path, pid_path


@dataclass
class WatchStatus:
    running: bool
    pid: int | None = None


def _read_pid() -> int | None:
    path = pid_path()
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by someone else — treat as alive.
        return True
    return True


def status() -> WatchStatus:
    """Report whether a watcher daemon is currently running.

    Stale PID files (process no longer alive) are cleaned up as a side effect.
    """
    pid = _read_pid()
    if pid is None:
        return WatchStatus(running=False)
    if not _pid_alive(pid):
        pid_path().unlink(missing_ok=True)
        return WatchStatus(running=False)
    return WatchStatus(running=True, pid=pid)


def start(roots: list[Path], *, polling_fallback: bool = False) -> tuple[bool, str]:
    """Fork the watcher daemon into the background.

    Returns (started, message). `started=False` if already running.
    """
    existing = status()
    if existing.running:
        return False, f"watcher already running (pid {existing.pid})"

    pid_path().parent.mkdir(parents=True, exist_ok=True)
    log_path().parent.mkdir(parents=True, exist_ok=True)

    pid = os.fork()
    if pid > 0:
        # Parent: wait briefly for the child to write its PID file, then return.
        for _ in range(50):
            if pid_path().is_file():
                break
            time.sleep(0.02)
        return True, f"watcher started (pid {pid})"

    # Child: detach from the controlling terminal and become session leader.
    os.setsid()
    _daemonize_streams()
    pid_path().write_text(str(os.getpid()), encoding="utf-8")
    try:
        _run(roots, polling_fallback=polling_fallback)
    finally:
        pid_path().unlink(missing_ok=True)
        os._exit(0)


def stop() -> tuple[bool, str]:
    """Signal the running watcher daemon to shut down.

    Returns (stopped, message). `stopped=False` if not running.
    """
    current = status()
    if not current.running:
        return False, "watcher not running"
    os.kill(current.pid, signal.SIGTERM)
    for _ in range(50):
        if not _pid_alive(current.pid):
            break
        time.sleep(0.02)
    pid_path().unlink(missing_ok=True)
    return True, f"watcher stopped (pid {current.pid})"


def _daemonize_streams() -> None:
    """Redirect stdio to the watcher log so the parent terminal is freed."""
    log_path().parent.mkdir(parents=True, exist_ok=True)
    # Deliberately left open for the process lifetime — dup2'd onto stdio.
    devnull = open(os.devnull, "rb")  # noqa: SIM115
    logfile = open(log_path(), "a", buffering=1, encoding="utf-8")  # noqa: SIM115
    os.dup2(devnull.fileno(), sys.stdin.fileno())
    os.dup2(logfile.fileno(), sys.stdout.fileno())
    os.dup2(logfile.fileno(), sys.stderr.fileno())


def _run(roots: list[Path], *, polling_fallback: bool) -> None:
    from octopus.watcher.loop import run_watch_loop

    run_watch_loop(roots, polling_fallback=polling_fallback)

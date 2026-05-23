"""File-only logging for octopus.

Writes to `$XDG_DATA_HOME/octopus/logs/octopus.log` (or `~/.local/share/...`)
with rotation. Silent on stdout — CLI output continues via rich.console.

`setup_logging()` is idempotent — safe to call from every entry point.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 5
_LOGGER_NAME = "octopus"
_SETUP_DONE = False


def default_log_path() -> Path:
    """Return $XDG_DATA_HOME/octopus/logs/octopus.log (or ~/.local/share/...)."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return base / "octopus" / "logs" / "octopus.log"


def setup_logging(level: int | str = logging.INFO) -> logging.Logger:
    """Configure the `octopus` logger with a rotating file handler.

    Idempotent. Returns the configured logger.
    """
    global _SETUP_DONE
    logger = logging.getLogger(_LOGGER_NAME)
    if _SETUP_DONE:
        return logger

    log_path = default_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create the log dir, fall back to NullHandler — don't crash the CLI.
        logger.addHandler(logging.NullHandler())
        logger.setLevel(level)
        _SETUP_DONE = True
        return logger

    handler = RotatingFileHandler(
        log_path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False  # don't bubble to root → keeps stdout clean
    _SETUP_DONE = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a child logger under `octopus.<name>`. Call setup_logging first."""
    if name is None:
        return logging.getLogger(_LOGGER_NAME)
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")

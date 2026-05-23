"""Tests for octopus.core.logging."""

from __future__ import annotations

import logging
from pathlib import Path

import octopus.core.logging as oct_logging
from octopus.core.logging import default_log_path, get_logger, setup_logging


def _reset_setup_flag() -> None:
    """Force setup_logging to re-run (it's idempotent by design)."""
    oct_logging._SETUP_DONE = False
    logger = logging.getLogger("octopus")
    for h in list(logger.handlers):
        logger.removeHandler(h)


def test_default_log_path_respects_xdg(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_log_path() == tmp_path / "octopus" / "logs" / "octopus.log"


def test_default_log_path_falls_back_to_home(monkeypatch) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    expected_suffix = Path(".local") / "share" / "octopus" / "logs" / "octopus.log"
    assert default_log_path().as_posix().endswith(expected_suffix.as_posix())


def test_setup_logging_creates_file_and_writes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _reset_setup_flag()

    logger = setup_logging()
    logger.info("hello-from-test")
    # Force handler flush.
    for h in logger.handlers:
        h.flush()

    log_file = tmp_path / "octopus" / "logs" / "octopus.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello-from-test" in content
    assert "[INFO]" in content


def test_setup_logging_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _reset_setup_flag()

    logger1 = setup_logging()
    handler_count = len(logger1.handlers)
    logger2 = setup_logging()
    assert logger2 is logger1
    assert len(logger2.handlers) == handler_count  # no duplicate handlers


def test_get_logger_returns_child(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _reset_setup_flag()
    setup_logging()

    child = get_logger("reindex")
    assert child.name == "octopus.reindex"
    parent = get_logger()
    assert parent.name == "octopus"


def test_logger_does_not_propagate(monkeypatch, tmp_path: Path) -> None:
    """Logs should not leak to root → no stdout pollution."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    _reset_setup_flag()
    logger = setup_logging()
    assert logger.propagate is False

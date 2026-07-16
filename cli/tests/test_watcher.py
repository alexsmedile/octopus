"""Tests for the watcher daemon (v1.5, PRD §13.5, SCHEMA-CONFIG.md §5.2/5.3)."""

from __future__ import annotations

import os

import pytest

from octopus.watcher import daemon, paths


@pytest.fixture(autouse=True)
def _isolate_watcher_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    yield


def test_pid_path_and_log_path_respect_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert paths.pid_path() == tmp_path / "cache" / "watcher.pid"
    assert paths.log_path() == tmp_path / "data" / "octopus" / "logs" / "watcher.log"


def test_status_not_running_when_no_pid_file():
    result = daemon.status()
    assert result.running is False
    assert result.pid is None


def test_status_cleans_up_stale_pid_file(tmp_path):
    pid_file = paths.pid_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    # A PID that (almost certainly) doesn't correspond to a live process.
    pid_file.write_text("999999", encoding="utf-8")

    result = daemon.status()

    assert result.running is False
    assert not pid_file.exists()


def test_status_running_for_live_process(tmp_path):
    pid_file = paths.pid_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")

    result = daemon.status()

    assert result.running is True
    assert result.pid == os.getpid()


def test_stop_when_not_running():
    stopped, message = daemon.stop()
    assert stopped is False
    assert "not running" in message


# NOTE: start()/stop() fork a real background process (SCHEMA-CONFIG.md §5.2).
# That full lifecycle is exercised manually (see PR description) rather than
# here — os.fork() inside pytest's own stdio-capturing process is a known
# hazard (the child inherits pytest's capture fds and dup2 races against
# pytest's teardown), which makes it flaky in-suite despite working standalone.
# The deterministic pieces (PID file read/write/stale-cleanup, status/stop
# messaging) are covered above without forking.

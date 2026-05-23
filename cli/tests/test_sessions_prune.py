"""`session prune` closes sessions inactive longer than `days`."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import pytest

from octopus.config import load_config
from octopus.fs.scaffold import init_activity
from octopus.sessions import (
    end_session,
    list_sessions,
    prune_sessions,
    read_session,
    start_session,
)
from octopus.sessions.cache import get_active


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("OCTOPUS_CACHE_HOME", str(tmp_path / ".cache" / "octopus"))


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def _backdate(path, days_old):
    past = time.time() - days_old * 86400
    os.utime(path, (past, past))


def test_prune_skips_fresh_sessions(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    pruned = prune_sessions(folder, aid, days=14)
    assert pruned == []
    on_disk, _ = read_session(s.path)
    assert on_disk.is_open()


def test_prune_closes_stale_sessions(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    _backdate(s.path, 20)
    pruned = prune_sessions(folder, aid, days=14)
    assert len(pruned) == 1
    on_disk, body = read_session(s.path)
    assert on_disk.ended is not None
    assert on_disk.status == "dropped"
    assert "auto-closed" in body


def test_prune_dry_run_does_not_mutate(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    _backdate(s.path, 20)
    pruned = prune_sessions(folder, aid, days=14, dry_run=True)
    assert len(pruned) == 1
    on_disk, _ = read_session(s.path)
    assert on_disk.is_open()  # not actually closed
    assert get_active(aid) == s.filename


def test_prune_clears_active_pointer_if_was_active(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    _backdate(s.path, 30)
    prune_sessions(folder, aid, days=14)
    assert get_active(aid) is None


def test_prune_respects_days_arg(activity):
    folder, aid = activity
    s = start_session(folder, aid, title="t")
    _backdate(s.path, 10)
    # days=14 → not stale
    assert prune_sessions(folder, aid, days=14) == []
    # days=7 → stale
    assert len(prune_sessions(folder, aid, days=7)) == 1


def test_config_defaults_to_14_and_7(monkeypatch, tmp_path):
    """With no config file present, defaults are 14 / 7."""
    from octopus import config as cfgmod
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_PATH", cfg_dir / "config.toml")
    cfg = load_config()
    assert cfg.session_prune_days == 14
    assert cfg.session_stale_warn_days == 7


def test_config_overrides_via_toml(monkeypatch, tmp_path):
    """`[sessions]` block in config.toml overrides both knobs."""
    from octopus import config as cfgmod
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text(
        "[sessions]\nstale_warn_days = 3\nprune_days = 21\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_PATH", cfg_dir / "config.toml")
    cfg = load_config()
    assert cfg.session_stale_warn_days == 3
    assert cfg.session_prune_days == 21

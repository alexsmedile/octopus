"""`[ui.glyphs]` config resolution (G4, request 49-tui-glyph-parity).

Order: activity config.toml > system config.toml > built-in defaults.
The CLI `--glyphs` flag itself is the highest tier but lives in cli.py, not
config.py — it's tested by simply not calling load_config() when the flag
is absent (see test_glyphs_cli.py for the flag-level behavior)."""

from __future__ import annotations

from octopus.config import load_config


def test_glyphs_defaults(monkeypatch, tmp_path):
    """With no config file present, defaults are collapsed/4/True/arrow."""
    from octopus import config as cfgmod
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_PATH", cfg_dir / "config.toml")
    cfg = load_config()
    assert cfg.glyphs_style == "collapsed"
    assert cfg.glyphs_progress_stages == 4
    assert cfg.glyphs_use_color is True
    assert cfg.glyphs_session_marker == "arrow"


def test_glyphs_system_config_overrides_defaults(monkeypatch, tmp_path):
    """`[ui.glyphs]` in the system-wide config.toml overrides built-in defaults."""
    from octopus import config as cfgmod
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text(
        "[ui.glyphs]\nstyle = \"minimal\"\nprogress_stages = 2\nuse_color = false\nsession_marker = \"none\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_PATH", cfg_dir / "config.toml")
    cfg = load_config()
    assert cfg.glyphs_style == "minimal"
    assert cfg.glyphs_progress_stages == 2
    assert cfg.glyphs_use_color is False
    assert cfg.glyphs_session_marker == "none"


def test_glyphs_activity_config_overrides_system_config(monkeypatch, tmp_path):
    """Per-activity `.octopus/config.toml` wins over the system-wide config."""
    from octopus import config as cfgmod
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text(
        "[ui.glyphs]\nstyle = \"minimal\"\n", encoding="utf-8",
    )
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_PATH", cfg_dir / "config.toml")

    activity_dir = tmp_path / "activity" / ".octopus"
    activity_dir.mkdir(parents=True)
    (activity_dir / "config.toml").write_text(
        "[ui.glyphs]\nstyle = \"combined\"\n", encoding="utf-8",
    )
    cfg = load_config(activity_dir)
    assert cfg.glyphs_style == "combined"


def test_glyphs_invalid_style_falls_back_to_default(monkeypatch, tmp_path):
    """An unrecognized `style` value is ignored, not silently accepted."""
    from octopus import config as cfgmod
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text(
        "[ui.glyphs]\nstyle = \"bogus\"\nprogress_stages = 7\nsession_marker = \"bogus\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfgmod, "SYSTEM_CONFIG_PATH", cfg_dir / "config.toml")
    cfg = load_config()
    assert cfg.glyphs_style == "collapsed"
    assert cfg.glyphs_progress_stages == 4
    assert cfg.glyphs_session_marker == "arrow"

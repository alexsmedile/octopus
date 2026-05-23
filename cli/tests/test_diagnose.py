"""Tests for octopus.diagnose."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from octopus.diagnose import (
    _read_log_tail,
    _redact,
    collect_diagnostics,
    default_out_path,
    format_summary,
    write_zip,
)


def test_redact_replaces_home() -> None:
    home = str(Path.home())
    assert _redact(f"{home}/foo/bar") == "~/foo/bar"
    assert _redact("/tmp/no-home") == "/tmp/no-home"


def test_collect_returns_expected_keys(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    payload = collect_diagnostics()
    for k in (
        "octopus_version",
        "spec_version",
        "collected_at",
        "python",
        "platform",
        "paths",
        "config",
        "index",
    ):
        assert k in payload, f"missing key: {k}"
    assert payload["paths"]["home"] == "~"


def test_collect_redacts_home_in_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    payload = collect_diagnostics()
    home = str(Path.home())
    # JSON-serialize the whole payload and check no raw $HOME leaked.
    serialized = json.dumps(payload, default=str)
    # tmp_path is outside $HOME typically, so absence of $HOME is the real check.
    if home != "/":  # paranoia guard
        assert home not in serialized


def test_format_summary_renders(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    payload = collect_diagnostics()
    text = format_summary(payload)
    assert "octopus version" in text
    assert "python" in text
    assert "platform" in text


def test_write_zip_contains_both_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    payload = collect_diagnostics()
    out = tmp_path / "bundle.zip"
    write_zip(payload, out, log_tail=["line1", "line2"])
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "diagnose.json" in names
        assert "octopus.log.tail" in names
        data = json.loads(zf.read("diagnose.json"))
        assert data["octopus_version"] == payload["octopus_version"]
        tail = zf.read("octopus.log.tail").decode("utf-8")
        assert "line1" in tail and "line2" in tail


def test_write_zip_omits_tail_when_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OCTOPUS_CONFIG_HOME", str(tmp_path / "cfg"))
    payload = collect_diagnostics()
    out = tmp_path / "bundle-no-log.zip"
    write_zip(payload, out, log_tail=[])
    with zipfile.ZipFile(out) as zf:
        assert "diagnose.json" in zf.namelist()
        assert "octopus.log.tail" not in zf.namelist()


def test_read_log_tail_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _read_log_tail(tmp_path / "nope.log") == []


def test_read_log_tail_limits_lines_and_redacts(tmp_path: Path) -> None:
    log = tmp_path / "octopus.log"
    home = str(Path.home())
    lines = [f"line {i} at {home}/x" for i in range(700)]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tail = _read_log_tail(log, lines=500)
    assert len(tail) == 500
    assert tail[0].startswith("line 200 at ~/x")
    assert all(home not in t for t in tail)


def test_default_out_path_in_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    p = default_out_path()
    assert p.parent == tmp_path
    assert p.name.startswith("octopus-diagnose-")
    assert p.suffix == ".zip"

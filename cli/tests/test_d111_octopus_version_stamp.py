"""D111 — record the CLI version that last wrote a project folder.

`octopus_version` is stamped on every activity.md write (shared, committed) and
mirrored into config.local.toml (machine-local). Read precedence: config.local
wins, activity.md is the fallback, "" when absent.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import frontmatter

from octopus import __version__
from octopus.core.models import Activity
from octopus.fs.io import read_activity, write_activity, write_local_state
from octopus.fs.scaffold import init_activity


def _git_init(folder: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=folder, check=True)


def test_init_stamps_octopus_version_in_activity_md(tmp_path: Path) -> None:
    _git_init(tmp_path)
    init_activity(tmp_path, title="Demo", activity_type="skill", area="dev")
    activity_md = tmp_path / ".octopus" / "activity.md"
    meta = frontmatter.load(activity_md).metadata
    assert meta["octopus_version"] == __version__


def test_init_stamps_octopus_version_in_local_state(tmp_path: Path) -> None:
    _git_init(tmp_path)
    init_activity(tmp_path, title="Demo", activity_type="skill", area="dev")
    local = tmp_path / ".octopus" / "config.local.toml"
    data = tomllib.loads(local.read_text(encoding="utf-8"))
    assert data["octopus_version"] == __version__


def test_read_roundtrips_octopus_version(tmp_path: Path) -> None:
    _git_init(tmp_path)
    init_activity(tmp_path, title="Demo", activity_type="skill", area="dev")
    activity, _ = read_activity(tmp_path / ".octopus" / "activity.md")
    assert activity.octopus_version == __version__


def test_write_always_stamps_running_version_not_stale_field(tmp_path: Path) -> None:
    """A stale octopus_version carried on the Activity must be overwritten."""
    _git_init(tmp_path)
    init_activity(tmp_path, title="Demo", activity_type="skill", area="dev")
    activity_md = tmp_path / ".octopus" / "activity.md"
    activity, body = read_activity(activity_md)
    # Pretend the in-memory object carries an ancient version.
    activity.octopus_version = "0.0.1-OLD"
    write_activity(activity_md, activity, body)
    meta = frontmatter.load(activity_md).metadata
    assert meta["octopus_version"] == __version__  # stamped, not preserved


def test_local_state_octopus_version_wins_over_activity_md(tmp_path: Path) -> None:
    """config.local.toml is the machine-local truth; it wins on read."""
    octopus_dir = tmp_path / ".octopus"
    octopus_dir.mkdir(parents=True)
    # activity.md carries an older shared stamp...
    activity = Activity(
        id="x", title="X", created=__import__("datetime").date(2026, 1, 1),
        octopus_version="0.0.1-OLD",
    )
    write_activity(octopus_dir / "activity.md", activity, "")
    # ...overwrite the activity.md stamp by hand to simulate a clone written elsewhere.
    amd = octopus_dir / "activity.md"
    amd.write_text(amd.read_text().replace(__version__, "9.9.9-SHARED"), encoding="utf-8")
    # config.local stamps the local machine's version.
    write_local_state(octopus_dir, last_known_path=str(tmp_path))
    read_back, _ = read_activity(amd)
    assert read_back.octopus_version == __version__  # local wins over 9.9.9-SHARED


def test_absent_octopus_version_reads_empty(tmp_path: Path) -> None:
    """A pre-D111 activity.md with no stamp and no local state → empty string."""
    octopus_dir = tmp_path / ".octopus"
    octopus_dir.mkdir(parents=True)
    amd = octopus_dir / "activity.md"
    amd.write_text(
        "---\nid: x\ntitle: X\ncreated: '2026-01-01'\nspec_version: 1\n---\n",
        encoding="utf-8",
    )
    activity, _ = read_activity(amd)
    assert activity.octopus_version == ""


def test_octopus_version_not_swallowed_by_extra(tmp_path: Path) -> None:
    """octopus_version is a recognized field, never dumped into extra."""
    _git_init(tmp_path)
    init_activity(tmp_path, title="Demo", activity_type="skill", area="dev")
    activity, _ = read_activity(tmp_path / ".octopus" / "activity.md")
    assert "octopus_version" not in activity.extra

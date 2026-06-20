"""D110 definitive leak fix: init auto-gitignores, reindex self-heals.

Covers the two gaps that let `last_known_path` (a machine-local absolute path)
keep leaking into committed `activity.md`:
  A. `octopus init` must gitignore `.octopus/config.local.toml`.
  B. `octopus reindex` must strip a stale `last_known_path` line from an
     existing `activity.md` (self-heal) and gitignore the local file.
  C. `ensure_gitignored` helper: idempotent, repo-aware, creates .gitignore.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import frontmatter

from octopus.db.reindex import reindex_all
from octopus.fs.io import ensure_gitignored
from octopus.fs.scaffold import init_activity

IGNORE_LINE = ".octopus/config.local.toml"


def _git_init(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=folder, check=True)


def _read_lkp_in_file(activity_md: Path) -> bool:
    return "last_known_path" in frontmatter.load(activity_md).metadata


# ── Fix A: init auto-gitignores ──────────────────────────────────────


def test_init_in_git_repo_gitignores_config_local(tmp_path):
    repo = tmp_path / "proj"
    _git_init(repo)
    init_activity(repo, activity_type="code")

    gitignore = repo / ".gitignore"
    assert gitignore.is_file(), "init must create .gitignore in a git repo"
    assert IGNORE_LINE in gitignore.read_text()


def test_init_never_writes_last_known_path_to_activity_md(tmp_path):
    repo = tmp_path / "proj"
    _git_init(repo)
    init_activity(repo, activity_type="code")
    activity_md = repo / ".octopus" / "activity.md"
    assert not _read_lkp_in_file(activity_md)
    # …but the value IS preserved locally
    local = (repo / ".octopus" / "config.local.toml").read_text()
    assert "last_known_path" in local


def test_init_outside_git_repo_skips_gitignore(tmp_path):
    # No .git anywhere → no .gitignore created, but local state still written.
    folder = tmp_path / "loose"
    folder.mkdir()
    init_activity(folder, activity_type="code")
    assert not (folder / ".gitignore").exists()
    assert (folder / ".octopus" / "config.local.toml").is_file()


def test_init_appends_to_existing_gitignore_without_duplicating(tmp_path):
    repo = tmp_path / "proj"
    _git_init(repo)
    (repo / ".gitignore").write_text("node_modules/\n*.log\n")
    init_activity(repo, activity_type="code")
    content = (repo / ".gitignore").read_text()
    assert content.count(IGNORE_LINE) == 1
    assert "node_modules/" in content  # preserved


# ── Fix C: ensure_gitignored idempotency ─────────────────────────────


def test_ensure_gitignored_is_idempotent(tmp_path):
    repo = tmp_path / "proj"
    _git_init(repo)
    octo = repo / ".octopus"
    octo.mkdir()

    assert ensure_gitignored(repo) is True   # first call writes
    assert ensure_gitignored(repo) is False  # second call no-ops
    assert (repo / ".gitignore").read_text().count(IGNORE_LINE) == 1


def test_ensure_gitignored_returns_false_outside_repo(tmp_path):
    folder = tmp_path / "loose"
    folder.mkdir()
    assert ensure_gitignored(folder) is False
    assert not (folder / ".gitignore").exists()


# ── Fix B: reindex self-heals a pre-D110 activity.md ─────────────────


def _make_pre_d110_activity(repo: Path) -> Path:
    """init, then inject a stale last_known_path line as a pre-D110 file would have."""
    _git_init(repo)
    init_activity(repo, activity_type="code")
    octo = repo / ".octopus"
    activity_md = octo / "activity.md"
    # Simulate the legacy on-disk state: line present in activity.md, and remove
    # the local file + gitignore rule so this looks untouched-since-pre-D110.
    post = frontmatter.load(activity_md)
    post.metadata["last_known_path"] = str(repo)
    activity_md.write_text(frontmatter.dumps(post), encoding="utf-8")
    (octo / "config.local.toml").unlink(missing_ok=True)
    (repo / ".gitignore").unlink(missing_ok=True)
    return activity_md


def test_reindex_strips_stale_last_known_path(temp_db, tmp_path):
    repo = tmp_path / "root" / "legacy"
    activity_md = _make_pre_d110_activity(repo)
    assert _read_lkp_in_file(activity_md)  # precondition: leak present

    res = reindex_all(temp_db, [tmp_path / "root"])

    assert res.migrated_local_state == 1
    assert not _read_lkp_in_file(activity_md), "reindex must strip the line"
    # value relocated, not lost
    local = (repo / ".octopus" / "config.local.toml").read_text()
    assert str(repo) in local
    # gitignore repaired
    assert IGNORE_LINE in (repo / ".gitignore").read_text()


def test_reindex_self_heal_is_idempotent(temp_db, tmp_path):
    repo = tmp_path / "root" / "legacy"
    _make_pre_d110_activity(repo)

    first = reindex_all(temp_db, [tmp_path / "root"])
    assert first.migrated_local_state == 1
    # Second pass: nothing left to migrate.
    second = reindex_all(temp_db, [tmp_path / "root"])
    assert second.migrated_local_state == 0


def test_reindex_clean_activity_not_rewritten(temp_db, tmp_path):
    # A post-D110 activity (no line in file) must not be counted or touched.
    repo = tmp_path / "root" / "clean"
    _git_init(repo)
    init_activity(repo, activity_type="code")
    res = reindex_all(temp_db, [tmp_path / "root"])
    assert res.migrated_local_state == 0

"""Full reindex: idempotency, prune, sessions, missing roots."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from octopus.core.models import Task
from octopus.db.reindex import reindex_all
from octopus.fs.io import write_task
from octopus.fs.scaffold import init_activity


def _make_proj_with_tasks(root: Path, name: str, n_tasks: int = 3) -> None:
    folder = root / name
    folder.mkdir(parents=True)
    activity = init_activity(folder, activity_type="code")
    for i in range(n_tasks):
        slug = f"task-{i}"
        path = folder / ".octopus" / "tasks" / "backlog" / f"{slug}.md"
        t = Task(
            title=f"Task {i}",
            created=date(2026, 5, 1),
            bucket="backlog",
            slug=slug,
            path=path,
        )
        write_task(path, t, "")
    return activity


def test_reindex_empty_when_no_activities(temp_db, tmp_path):
    res = reindex_all(temp_db, [tmp_path])
    assert res.activities_seen == 0
    assert res.tasks_seen == 0
    assert res.errors == []


def test_reindex_populates_and_is_idempotent(temp_db, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _make_proj_with_tasks(root, "alpha", 3)
    _make_proj_with_tasks(root, "beta", 2)

    res = reindex_all(temp_db, [root])
    assert res.activities_seen == 2
    assert res.tasks_seen == 5

    rows = temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    assert rows == 5

    # Second run: same row counts (idempotent)
    res2 = reindex_all(temp_db, [root])
    assert res2.activities_seen == 2
    assert res2.tasks_seen == 5
    assert temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 5


def test_reindex_missing_root_reported(temp_db, tmp_path):
    ghost = tmp_path / "does-not-exist"
    res = reindex_all(temp_db, [ghost])
    assert ghost in res.missing_roots


def test_reindex_prune_removes_deleted_tasks(temp_db, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _make_proj_with_tasks(root, "alpha", 3)

    reindex_all(temp_db, [root])
    assert temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 3

    # Delete one task file
    victim = root / "alpha" / ".octopus" / "tasks" / "backlog" / "task-0.md"
    victim.unlink()

    # Reindex without prune: row stays
    reindex_all(temp_db, [root], prune=False)
    assert temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 3

    # Reindex with prune: row removed
    res = reindex_all(temp_db, [root], prune=True)
    assert res.pruned_tasks == 1
    assert temp_db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 2


def test_reindex_skips_trash(temp_db, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _make_proj_with_tasks(root, "alpha", 2)

    # Add a file in .trash/ — must be ignored
    trash = root / "alpha" / ".octopus" / "tasks" / ".trash"
    trash.mkdir()
    decoy = trash / "ghost.md"
    write_task(
        decoy,
        Task(title="Ghost", created=date(2026, 5, 1), bucket="backlog",
             slug="ghost", path=decoy),
        "",
    )

    res = reindex_all(temp_db, [root])
    assert res.tasks_seen == 2
    slugs = {r["slug"] for r in temp_db.execute("SELECT slug FROM tasks").fetchall()}
    assert "ghost" not in slugs


def test_reindex_picks_up_all_buckets(temp_db, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    folder = root / "alpha"
    folder.mkdir()
    init_activity(folder, activity_type="code")

    # One task per bucket
    for bucket in ("backlog", "next", "now"):
        path = folder / ".octopus" / "tasks" / bucket / f"in-{bucket}.md"
        write_task(
            path,
            Task(title=f"in {bucket}", created=date(2026, 5, 1), bucket=bucket,
                 slug=f"in-{bucket}", path=path),
            "",
        )

    res = reindex_all(temp_db, [root])
    assert res.tasks_seen == 3
    buckets = {r["bucket"] for r in temp_db.execute("SELECT bucket FROM tasks").fetchall()}
    assert buckets == {"backlog", "next", "now"}

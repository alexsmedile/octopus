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


# ── related_tasks propagation (D54) ───────────────────────────────────


def _make_activity_with_promoted_task(
    root: Path,
    *,
    name: str = "alpha",
    task_slug: str = "wire-thing",
    promoted_to: str | None = "spectacular:20-task-promotion",
    request_slug: str = "20-task-promotion",
) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    init_activity(folder, activity_type="code")
    # Task in done/ with promoted_to set
    path = folder / ".octopus" / "tasks" / "done" / f"{task_slug}.md"
    write_task(
        path,
        Task(
            title=task_slug,
            created=date(2026, 5, 1),
            bucket="done",
            slug=task_slug,
            path=path,
            start_date=date(2026, 5, 2),
            end_date=date(2026, 5, 3),
            promoted_to=promoted_to,
        ),
        "",
    )
    # Pre-existing PLAN.md to write related_tasks into
    plan_dir = folder / ".spectacular" / "requests" / request_slug
    plan_dir.mkdir(parents=True)
    (plan_dir / "PLAN.md").write_text("---\nstatus: backlog\n---\n# x\n")
    return folder


def test_reindex_writes_related_tasks_to_plan(temp_db, tmp_path):
    import frontmatter

    folder = _make_activity_with_promoted_task(tmp_path)
    res = reindex_all(temp_db, [tmp_path])
    assert res.related_tasks_propagated == 1
    plan = folder / ".spectacular" / "requests" / "20-task-promotion" / "PLAN.md"
    meta = frontmatter.load(plan).metadata
    assert meta["related_tasks"] == ["wire-thing"]


def test_reindex_removes_related_tasks_when_no_promoted(temp_db, tmp_path):
    """When no tasks reference a request, related_tasks must be default-omitted."""
    import frontmatter

    folder = _make_activity_with_promoted_task(
        tmp_path, promoted_to=None  # task has no promoted_to
    )
    plan = folder / ".spectacular" / "requests" / "20-task-promotion" / "PLAN.md"
    # Pre-seed with a stale related_tasks entry
    plan.write_text("---\nstatus: backlog\nrelated_tasks: [old-task]\n---\n# x\n")
    res = reindex_all(temp_db, [tmp_path])
    meta = frontmatter.load(plan).metadata
    assert "related_tasks" not in meta
    assert res.related_tasks_propagated == 1  # the rewrite happened


def test_reindex_idempotent_on_related_tasks(temp_db, tmp_path):
    """A second reindex with no changes should not rewrite the PLAN.md."""
    _make_activity_with_promoted_task(tmp_path)
    res1 = reindex_all(temp_db, [tmp_path])
    assert res1.related_tasks_propagated == 1
    res2 = reindex_all(temp_db, [tmp_path])
    assert res2.related_tasks_propagated == 0


def test_reindex_warns_on_malformed_promoted_to(temp_db, tmp_path):
    _make_activity_with_promoted_task(
        tmp_path, promoted_to="no-colon-here"
    )
    res = reindex_all(temp_db, [tmp_path])
    assert any("no-colon-here" in v for _, v in res.promoted_to_warnings)


def test_reindex_skips_archived_requests(temp_db, tmp_path):
    """Archived (`_archive/`) requests must not have their PLAN.md touched."""
    import frontmatter

    folder = _make_activity_with_promoted_task(tmp_path)
    src = folder / ".spectacular" / "requests" / "20-task-promotion"
    dst = folder / ".spectacular" / "requests" / "_archive" / "20-task-promotion"
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    res = reindex_all(temp_db, [tmp_path])
    assert res.related_tasks_propagated == 0
    meta = frontmatter.load(dst / "PLAN.md").metadata
    assert "related_tasks" not in meta


def test_reindex_non_spectacular_provider_is_noop(temp_db, tmp_path):
    """A `github:` promoted_to should NOT cause a spectacular regen."""
    import frontmatter

    folder = _make_activity_with_promoted_task(
        tmp_path, promoted_to="github:foo/bar#42"
    )
    plan = folder / ".spectacular" / "requests" / "20-task-promotion" / "PLAN.md"
    res = reindex_all(temp_db, [tmp_path])
    meta = frontmatter.load(plan).metadata
    assert "related_tasks" not in meta
    assert res.promoted_to_warnings == []


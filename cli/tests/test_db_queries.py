"""Read-shaped queries: list, status, loops, find_by_slug, empty-index."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from octopus.core.models import Task
from octopus.db.queries import (
    count_by_bucket,
    find_task_by_slug,
    get_activity_by_id_or_prefix,
    list_activities,
    loops,
    tasks_all,
    tasks_for_activity,
    total_row_counts,
)
from octopus.db.reindex import reindex_all
from octopus.fs.io import write_task
from octopus.fs.scaffold import init_activity


def _seed(root: Path) -> tuple[str, str]:
    """Create two activities and a few tasks across buckets. Returns (id_a, id_b)."""
    a_folder = root / "alpha"
    a_folder.mkdir(parents=True)
    a = init_activity(a_folder, activity_type="code")
    for bucket, slug, pinned in [
        ("backlog", "later", False),
        ("next", "soon", False),
        ("now", "doing", True),
        ("done", "shipped", False),
    ]:
        path = a_folder / ".octopus" / "tasks" / bucket / f"{slug}.md"
        t = Task(
            title=slug.title(),
            created=date(2026, 5, 1),
            bucket=bucket,
            slug=slug,
            path=path,
            pinned=True if pinned else None,
            start_date=date(2026, 5, 2) if bucket in {"now", "done"} else None,
            end_date=date(2026, 5, 3) if bucket == "done" else None,
        )
        write_task(path, t, "")

    b_folder = root / "beta"
    b_folder.mkdir(parents=True)
    b = init_activity(b_folder, activity_type="business")
    path = b_folder / ".octopus" / "tasks" / "next" / "pitch.md"
    write_task(
        path,
        Task(title="Pitch", created=date(2026, 5, 1), bucket="next",
             slug="pitch", path=path),
        "",
    )

    return a.id, b.id


def test_total_row_counts_empty(temp_db):
    counts = total_row_counts(temp_db)
    assert counts == {"activities": 0, "tasks": 0, "sessions": 0}


def test_list_activities_returns_seeded(temp_db, tmp_path):
    _seed(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = list_activities(temp_db)
    titles = sorted(r["title"] for r in rows)
    assert titles == ["alpha", "beta"]


def test_get_activity_by_prefix(temp_db, tmp_path):
    id_a, _ = _seed(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = get_activity_by_id_or_prefix(temp_db, "alpha")
    assert len(rows) == 1
    assert rows[0]["id"] == id_a


def test_tasks_for_activity_sorted_pinned_first(temp_db, tmp_path):
    id_a, _ = _seed(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_for_activity(temp_db, id_a)
    # `doing` is pinned → must be first
    assert rows[0]["slug"] == "doing"


def test_tasks_all_crosses_activities(temp_db, tmp_path):
    _seed(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_all(temp_db)
    slugs = {r["slug"] for r in rows}
    # All non-archived slugs from both activities
    assert {"later", "soon", "doing", "shipped", "pitch"} <= slugs


def test_loops_excludes_terminal(temp_db, tmp_path):
    _seed(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = loops(temp_db)
    slugs = {r["slug"] for r in rows}
    # `shipped` is bucket=done → must be excluded
    assert "shipped" not in slugs
    assert {"later", "soon", "doing", "pitch"} <= slugs


def test_count_by_bucket(temp_db, tmp_path):
    id_a, _ = _seed(tmp_path)
    reindex_all(temp_db, [tmp_path])
    counts = count_by_bucket(temp_db, id_a)
    assert counts == {"backlog": 1, "next": 1, "now": 1, "done": 1}


def test_find_task_by_slug_scoped(temp_db, tmp_path):
    id_a, id_b = _seed(tmp_path)
    reindex_all(temp_db, [tmp_path])
    # Global search
    rows = find_task_by_slug(temp_db, "pitch")
    assert len(rows) == 1
    assert rows[0]["activity_id"] == id_b
    # Scoped search
    rows = find_task_by_slug(temp_db, "pitch", activity_id=id_a)
    assert rows == []


# ── --kind / --promoted / --spec filters (D52) ────────────────────────


def _seed_with_kinds_and_promotion(root: Path) -> str:
    """Seed an activity with mixed kinds + a promoted task."""
    folder = root / "kinded"
    folder.mkdir(parents=True)
    a = init_activity(folder, activity_type="code")

    rows = [
        ("backlog", "fix-login", "bug", None),
        ("backlog", "add-tos-page", "feat", None),
        ("next", "polish-errs", "polish", None),
        ("done", "old-bug", "bug", None),
        ("done", "wire-bridge", "feat", "spectacular:20-task-promotion"),
    ]
    for bucket, slug, kind, promoted_to in rows:
        path = folder / ".octopus" / "tasks" / bucket / f"{slug}.md"
        t = Task(
            title=slug.replace("-", " ").title(),
            created=date(2026, 5, 1),
            bucket=bucket,
            slug=slug,
            path=path,
            kind=kind,
            promoted_to=promoted_to,
            start_date=date(2026, 5, 2) if bucket == "done" else None,
            end_date=date(2026, 5, 3) if bucket == "done" else None,
        )
        write_task(path, t, "")
    return a.id


def test_tasks_filter_by_single_kind(temp_db, tmp_path):
    aid = _seed_with_kinds_and_promotion(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_for_activity(temp_db, aid, kinds=["bug"])
    slugs = {r["slug"] for r in rows}
    # 'old-bug' is bucket=done → excluded by default (include_archived guard
    # doesn't drop it, but the default scope still includes done in queries —
    # this filter just narrows by kind, no scope changes).
    assert "fix-login" in slugs
    assert "old-bug" in slugs
    assert "polish-errs" not in slugs


def test_tasks_filter_by_multi_kind(temp_db, tmp_path):
    aid = _seed_with_kinds_and_promotion(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_for_activity(temp_db, aid, kinds=["feat", "polish"])
    slugs = {r["slug"] for r in rows}
    assert "add-tos-page" in slugs
    assert "polish-errs" in slugs
    assert "fix-login" not in slugs


def test_tasks_filter_promoted_only(temp_db, tmp_path):
    aid = _seed_with_kinds_and_promotion(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_for_activity(temp_db, aid, promoted=True)
    slugs = {r["slug"] for r in rows}
    assert slugs == {"wire-bridge"}


def test_tasks_filter_by_spec_slug(temp_db, tmp_path):
    aid = _seed_with_kinds_and_promotion(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_for_activity(temp_db, aid, spec="20-task-promotion")
    slugs = {r["slug"] for r in rows}
    assert slugs == {"wire-bridge"}


def test_tasks_filter_spec_unknown_returns_empty(temp_db, tmp_path):
    aid = _seed_with_kinds_and_promotion(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_for_activity(temp_db, aid, spec="999-nope")
    assert rows == []


def test_tasks_all_cross_activity_kind_filter(temp_db, tmp_path):
    _seed_with_kinds_and_promotion(tmp_path)
    reindex_all(temp_db, [tmp_path])
    rows = tasks_all(temp_db, kinds=["polish"])
    slugs = {r["slug"] for r in rows}
    assert slugs == {"polish-errs"}

"""Tests for octopus.actions.promote_task and the octopus.promotion helpers.

Covers D47–D51 + D54 — the full task → request promotion seam.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import frontmatter

from octopus import actions
from octopus.actions import ActionError
from octopus.config import Config, REGISTERED_PROVIDERS
from octopus.fs.io import read_task
from octopus.fs.scaffold import init_activity
from octopus.promotion import (
    PromotionError,
    apply_auto_number,
    derive_related_tasks,
    find_spectacular_request,
    next_request_number,
    parse_target,
    scaffold_request,
)


@pytest.fixture
def activity(tmp_path: Path) -> Path:
    init_activity(tmp_path, title="test", activity_type="other")
    return tmp_path


@pytest.fixture
def cfg() -> Config:
    return Config()  # v1 defaults: spectacular + chip "spec"


# ── parse_target ───────────────────────────────────────────────────────


def test_parse_target_explicit_provider_id(cfg: Config) -> None:
    t = parse_target("spectacular:20-task-promotion", task_slugs=["foo"], cfg=cfg)
    assert t.provider == "spectacular"
    assert t.identifier == "20-task-promotion"
    assert t.canonical == "spectacular:20-task-promotion"
    assert not t.create_new


def test_parse_target_chip_alias_resolved(cfg: Config) -> None:
    t = parse_target("spec:20-foo", task_slugs=["foo"], cfg=cfg)
    assert t.provider == "spectacular"
    assert t.canonical == "spectacular:20-foo"


def test_parse_target_bare_id_uses_default(cfg: Config) -> None:
    t = parse_target("20-foo", task_slugs=["foo"], cfg=cfg)
    assert t.canonical == "spectacular:20-foo"


def test_parse_target_provider_shorthand_single_task(cfg: Config) -> None:
    t = parse_target("spec", task_slugs=["wire-thing"], cfg=cfg)
    assert t.canonical == "spectacular:wire-thing"
    assert not t.explicit_slug


def test_parse_target_provider_shorthand_multi_task_rejected(cfg: Config) -> None:
    with pytest.raises(PromotionError, match="ambiguous"):
        parse_target("spec", task_slugs=["a", "b"], cfg=cfg)


def test_parse_target_create_new(cfg: Config) -> None:
    t = parse_target("spectacular:new", task_slugs=["foo"], cfg=cfg)
    assert t.create_new
    assert t.identifier == ""


def test_parse_target_unknown_provider(cfg: Config) -> None:
    with pytest.raises(PromotionError, match="unknown provider"):
        parse_target("notreal:foo", task_slugs=["x"], cfg=cfg)


def test_parse_target_empty_identifier(cfg: Config) -> None:
    with pytest.raises(PromotionError, match="empty identifier"):
        parse_target("spectacular:", task_slugs=["x"], cfg=cfg)


# ── find_spectacular_request / next_request_number / auto_number ──────


def test_find_request_live(activity: Path) -> None:
    (activity / ".spectacular" / "requests" / "20-foo").mkdir(parents=True)
    (activity / ".spectacular" / "requests" / "20-foo" / "PLAN.md").write_text("---\n---\n")
    assert find_spectacular_request(activity, "20-foo") is not None


def test_find_request_archived(activity: Path) -> None:
    arch = activity / ".spectacular" / "requests" / "_archive" / "19-old"
    arch.mkdir(parents=True)
    (arch / "PLAN.md").write_text("---\n---\n")
    found = find_spectacular_request(activity, "19-old")
    assert found is not None
    assert "_archive" in str(found)


def test_find_request_missing(activity: Path) -> None:
    assert find_spectacular_request(activity, "nope") is None


def test_next_request_number_empty(activity: Path) -> None:
    assert next_request_number(activity) == 1


def test_next_request_number_skips_used(activity: Path) -> None:
    for n in ("01-a", "02-b", "05-c"):
        (activity / ".spectacular" / "requests" / n).mkdir(parents=True)
    assert next_request_number(activity) == 3  # first gap


def test_apply_auto_number_already_numbered(activity: Path, cfg: Config) -> None:
    assert apply_auto_number("20-task-promotion", activity, cfg) == "20-task-promotion"


def test_apply_auto_number_prepends(activity: Path, cfg: Config) -> None:
    out = apply_auto_number("wire-thing", activity, cfg)
    assert out == "01-wire-thing"


def test_apply_auto_number_off(activity: Path) -> None:
    cfg = Config(spectacular_auto_number=False)
    assert apply_auto_number("wire-thing", activity, cfg) == "wire-thing"


# ── scaffold_request ───────────────────────────────────────────────────


def test_scaffold_request_creates_plan(activity: Path) -> None:
    plan_path = scaffold_request(
        activity, slug="20-foo", title="Foo title", promoted_from="wire-foo"
    )
    assert plan_path.exists()
    post = frontmatter.load(plan_path)
    assert post.metadata["promoted_from"] == "wire-foo"
    assert post.metadata["status"] == "backlog"
    assert "Foo title" in post.content


def test_scaffold_request_refuses_to_overwrite(activity: Path) -> None:
    (activity / ".spectacular" / "requests" / "20-foo").mkdir(parents=True)
    with pytest.raises(PromotionError):
        scaffold_request(activity, slug="20-foo", title="x", promoted_from="x")


# ── end-to-end: promote_task ──────────────────────────────────────────


def _capture(activity: Path, title: str) -> str:
    return actions.capture_task(activity, title).slug


def test_promote_single_task_scaffolds_new_request(activity: Path) -> None:
    slug = _capture(activity, "wire obsidian bridge")
    result = actions.promote_task(
        activity, [slug], to="spectacular:wire-obsidian-bridge"
    )
    assert result.scaffolded
    assert result.target == "spectacular:01-wire-obsidian-bridge"  # auto-numbered
    assert slug in result.promoted
    # Task file moved to done/
    task_path = activity / ".octopus" / "tasks" / "done" / f"{slug}.md"
    assert task_path.exists()
    task, body = read_task(task_path)
    assert task.bucket == "done"
    assert task.promoted_to == "spectacular:01-wire-obsidian-bridge"
    assert task.end_date is not None
    # Body is the stub
    assert "The request PLAN.md is the source of truth" in body
    # Request PLAN exists
    plan = activity / ".spectacular" / "requests" / "01-wire-obsidian-bridge" / "PLAN.md"
    assert plan.exists()


def test_promote_links_existing_request(activity: Path) -> None:
    # Pre-create the request
    (activity / ".spectacular" / "requests" / "20-task-promotion").mkdir(parents=True)
    plan = activity / ".spectacular" / "requests" / "20-task-promotion" / "PLAN.md"
    plan.write_text("---\nstatus: queued\n---\n")
    slug = _capture(activity, "wire foo")
    result = actions.promote_task(activity, [slug], to="spectacular:20-task-promotion")
    assert not result.scaffolded
    assert result.target == "spectacular:20-task-promotion"


def test_promote_shorthand_uses_task_slug(activity: Path) -> None:
    slug = _capture(activity, "polish error messages")
    result = actions.promote_task(activity, [slug], to="spec")  # provider-only shorthand
    # Auto-numbering applies because slug had no NN-
    assert result.target.startswith("spectacular:01-")
    assert "polish-error-messages" in result.target


def test_promote_multi_task_shared_target(activity: Path) -> None:
    a = _capture(activity, "wire obsidian bridge")
    b = _capture(activity, "fix obsidian frontmatter")
    result = actions.promote_task(
        activity, [a, b], to="spectacular:obsidian-bridge"
    )
    assert len(result.promoted) == 2
    assert result.scaffolded
    assert result.target == "spectacular:01-obsidian-bridge"


def test_promote_multi_with_provider_only_shorthand_rejected(activity: Path) -> None:
    a = _capture(activity, "wire a")
    b = _capture(activity, "wire b")
    with pytest.raises(ActionError, match="ambiguous"):
        actions.promote_task(activity, [a, b], to="spec")


def test_promote_already_promoted_rejects(activity: Path) -> None:
    slug = _capture(activity, "polish err")
    actions.promote_task(activity, [slug], to="spectacular:foo")
    with pytest.raises(ActionError, match="already promoted"):
        actions.promote_task(activity, [slug], to="spectacular:bar")


def test_promote_force_repoints(activity: Path) -> None:
    slug = _capture(activity, "polish err")
    actions.promote_task(activity, [slug], to="spectacular:foo")
    result = actions.promote_task(
        activity, [slug], to="spectacular:bar", force=True
    )
    assert slug in result.repointed
    task, body = read_task(activity / ".octopus" / "tasks" / "done" / f"{slug}.md")
    # Auto-numbering picks the next free integer; first promote got 01-foo,
    # so this scaffold becomes 02-bar.
    assert task.promoted_to == "spectacular:02-bar"
    # Body NOT re-rewritten — still points at first target (the first stub is preserved)
    assert "The request PLAN.md is the source of truth" in body


def test_promote_revert_moves_to_backlog_and_clears(activity: Path) -> None:
    slug = _capture(activity, "polish err")
    actions.promote_task(activity, [slug], to="spectacular:foo")
    result = actions.promote_task(activity, [slug], revert=True)
    assert slug in result.reverted
    # Task moved back to backlog/
    backlog_path = activity / ".octopus" / "tasks" / "backlog" / f"{slug}.md"
    assert backlog_path.exists()
    assert not (activity / ".octopus" / "tasks" / "done" / f"{slug}.md").exists()
    task, _ = read_task(backlog_path)
    assert task.promoted_to is None
    assert task.end_date is None
    assert task.bucket == "backlog"


def test_promote_revert_idempotent_on_unpromoted(activity: Path) -> None:
    slug = _capture(activity, "polish err")
    result = actions.promote_task(activity, [slug], revert=True)
    assert result.reverted == []  # nothing to clear, no-op


def test_promote_atomic_pre_flight_aborts_on_first_failure(activity: Path) -> None:
    a = _capture(activity, "task a")
    b = _capture(activity, "task b")
    # Pre-promote `a` so the multi-task batch should fail before any write.
    actions.promote_task(activity, [a], to="spectacular:first")
    with pytest.raises(ActionError, match="already promoted"):
        actions.promote_task(activity, [a, b], to="spectacular:second")
    # `b` must not have been touched.
    b_path = activity / ".octopus" / "tasks" / "backlog" / f"{b}.md"
    assert b_path.exists()
    task_b, _ = read_task(b_path)
    assert task_b.promoted_to is None
    assert task_b.bucket == "backlog"


def test_promote_new_requires_slug(activity: Path) -> None:
    slug = _capture(activity, "polish err")
    with pytest.raises(ActionError, match="requires --slug"):
        actions.promote_task(activity, [slug], to="spectacular:new")


def test_promote_new_with_explicit_slug(activity: Path) -> None:
    slug = _capture(activity, "polish err")
    result = actions.promote_task(
        activity, [slug], to="spectacular:new", explicit_slug="99-explicit"
    )
    assert result.scaffolded
    assert result.target == "spectacular:99-explicit"


# ── derive_related_tasks (pure helper) ────────────────────────────────


def test_derive_related_tasks_groups_by_spec_slug() -> None:
    entries = [
        "task-a\tspectacular:20-foo",
        "task-b\tspectacular:20-foo",
        "task-c\tspectacular:21-bar",
    ]
    out = derive_related_tasks(entries)
    assert out == {"20-foo": ["task-a", "task-b"], "21-bar": ["task-c"]}


def test_derive_related_tasks_skips_non_spectacular() -> None:
    entries = [
        "task-a\tgithub:foo/bar#1",
        "task-b\tspectacular:20-foo",
    ]
    out = derive_related_tasks(entries)
    assert out == {"20-foo": ["task-b"]}


def test_derive_related_tasks_skips_malformed() -> None:
    entries = ["task-a\tno-colon", "task-b\t", "task-c\tspectacular:"]
    out = derive_related_tasks(entries)
    assert out == {}


def test_derive_related_tasks_sorted_deduped() -> None:
    entries = [
        "task-z\tspectacular:foo",
        "task-a\tspectacular:foo",
        "task-a\tspectacular:foo",  # duplicate
    ]
    out = derive_related_tasks(entries)
    assert out == {"foo": ["task-a", "task-z"]}

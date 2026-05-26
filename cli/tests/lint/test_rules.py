"""Tests for every lint rule + the runner."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from octopus.lint import lint_activity
from octopus.lint.findings import Severity
from octopus.lint.runner import apply_fix

from .conftest import write_task_file

# ── slug-match ────────────────────────────────────────────────────────


def test_slug_match_clean(activity: Path):
    write_task_file(activity, "backlog", "do-the-thing", {"slug": "do-the-thing"})
    report = lint_activity(activity, rule_codes=["slug-match"])
    assert report.findings == []


def test_slug_match_detects_drift(activity: Path):
    write_task_file(activity, "backlog", "do-the-thing", {"slug": "wrong-slug-here"})
    report = lint_activity(activity, rule_codes=["slug-match"])
    assert len(report.findings) == 1
    f = report.findings[0]
    assert f.code == "slug-match"
    assert f.severity == Severity.ERROR
    assert f.auto_fixable
    assert f.fix_preview == {"slug": "do-the-thing"}


def test_slug_match_fix_repairs_field(activity: Path):
    write_task_file(activity, "backlog", "do-the-thing", {"slug": "wrong"})
    report = lint_activity(activity, rule_codes=["slug-match"])
    assert apply_fix(report.findings[0]) is True
    report2 = lint_activity(activity, rule_codes=["slug-match"])
    assert report2.findings == []


# ── slug-shape ────────────────────────────────────────────────────────


def test_slug_shape_clean(activity: Path):
    write_task_file(activity, "backlog", "good-slug", {"slug": "good-slug"})
    report = lint_activity(activity, rule_codes=["slug-shape"])
    assert report.findings == []


def test_slug_shape_detects_space(activity: Path):
    # Filename can't contain spaces, but slug field can be malformed.
    p = write_task_file(activity, "backlog", "ok", {"slug": "bad slug here"})
    assert p.exists()
    report = lint_activity(activity, rule_codes=["slug-shape"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.ERROR


# ── bucket-match ──────────────────────────────────────────────────────


def test_bucket_match_clean(activity: Path):
    write_task_file(activity, "now", "x", {"bucket": "now"})
    report = lint_activity(activity, rule_codes=["bucket-match"])
    assert report.findings == []


def test_bucket_match_detects_mismatch(activity: Path):
    # File in next/, but frontmatter claims backlog
    write_task_file(activity, "next", "x", {"bucket": "backlog"})
    report = lint_activity(activity, rule_codes=["bucket-match"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.ERROR
    assert report.findings[0].auto_fixable


def test_bucket_match_fix_rewrites_field(activity: Path):
    write_task_file(activity, "next", "x", {"bucket": "backlog"})
    report = lint_activity(activity, rule_codes=["bucket-match"])
    assert apply_fix(report.findings[0]) is True
    report2 = lint_activity(activity, rule_codes=["bucket-match"])
    assert report2.findings == []


# ── corrupt-frontmatter ───────────────────────────────────────────────


def test_corrupt_frontmatter_legacy_field(activity: Path):
    raw = (
        "---\n"
        "title: bad\n"
        "created: '2026-05-26'\n"
        "bucket: backlog\n"
        "status: open\n"  # legacy
        "---\n"
        "\n"
    )
    write_task_file(activity, "backlog", "legacy", raw=raw)
    report = lint_activity(activity, rule_codes=["corrupt-frontmatter"])
    assert len(report.findings) == 1
    assert "legacy field" in report.findings[0].message


def test_corrupt_frontmatter_unparseable(activity: Path):
    raw = "---\nthis: : is\n  not [ valid yaml\n---\n"
    write_task_file(activity, "backlog", "broken", raw=raw)
    report = lint_activity(activity, rule_codes=["corrupt-frontmatter"])
    # python-frontmatter is permissive — accept either a parse-error finding
    # or zero findings (it may have coerced the YAML into a degenerate dict).
    # Either way, the rule must not crash.
    for f in report.findings:
        assert f.code == "corrupt-frontmatter"
        assert f.severity == Severity.ERROR


# ── start-without-now ─────────────────────────────────────────────────


def test_start_without_now_clean_in_now(activity: Path):
    write_task_file(activity, "now", "x", {"bucket": "now", "start_date": "2026-05-20"})
    report = lint_activity(activity, rule_codes=["start-without-now"])
    assert report.findings == []


def test_start_without_now_detects_backlog(activity: Path):
    write_task_file(activity, "backlog", "x", {"bucket": "backlog", "start_date": "2026-05-20"})
    report = lint_activity(activity, rule_codes=["start-without-now"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.WARN


def test_start_without_now_ignores_done(activity: Path):
    write_task_file(activity, "done", "x", {
        "bucket": "done", "start_date": "2026-05-20", "end_date": "2026-05-21",
    })
    report = lint_activity(activity, rule_codes=["start-without-now"])
    assert report.findings == []


# ── dangling-blocker ──────────────────────────────────────────────────


def test_dangling_blocker_clean_internal_ref(activity: Path):
    write_task_file(activity, "backlog", "target", {})
    write_task_file(activity, "now", "src", {"blocked_by": "target"})
    report = lint_activity(activity, rule_codes=["dangling-blocker"])
    assert report.findings == []


def test_dangling_blocker_detects_missing(activity: Path):
    write_task_file(activity, "now", "src", {"blocked_by": "missing-slug"})
    report = lint_activity(activity, rule_codes=["dangling-blocker"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.WARN


def test_dangling_blocker_skips_free_text(activity: Path):
    # Free-text "needs review" should not be validated as a slug
    write_task_file(activity, "now", "src", {"blocked_by": "needs key schema review"})
    report = lint_activity(activity, rule_codes=["dangling-blocker"])
    assert report.findings == []


# ── stale-done ────────────────────────────────────────────────────────


def test_stale_done_clean_recent(activity: Path):
    write_task_file(activity, "done", "x", {
        "bucket": "done",
        "end_date": (date.today() - timedelta(days=5)).isoformat(),
    })
    report = lint_activity(activity, rule_codes=["stale-done"])
    assert report.findings == []


def test_stale_done_detects_old(activity: Path):
    write_task_file(activity, "done", "x", {
        "bucket": "done",
        "end_date": (date.today() - timedelta(days=60)).isoformat(),
    })
    report = lint_activity(activity, rule_codes=["stale-done"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.INFO
    assert report.findings[0].auto_fixable


def test_stale_done_fix_moves_file(activity: Path):
    end = date.today() - timedelta(days=60)
    p = write_task_file(activity, "done", "x", {
        "bucket": "done", "end_date": end.isoformat(),
    })
    report = lint_activity(activity, rule_codes=["stale-done"])
    assert apply_fix(report.findings[0]) is True
    assert not p.exists()
    archive = activity / "_archive" / f"tasks-{end.strftime('%Y-%m')}" / "x.md"
    assert archive.is_file()


# ── bucket-blocked ────────────────────────────────────────────────────


def test_bucket_blocked_info_in_now(activity: Path):
    write_task_file(activity, "now", "x", {"bucket": "now", "issue": "blocked"})
    report = lint_activity(activity, rule_codes=["bucket-blocked"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.INFO  # per D100


def test_bucket_blocked_info_in_next_waiting(activity: Path):
    write_task_file(activity, "next", "x", {"bucket": "next", "issue": "waiting"})
    report = lint_activity(activity, rule_codes=["bucket-blocked"])
    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.INFO


def test_bucket_blocked_silent_in_backlog(activity: Path):
    write_task_file(activity, "backlog", "x", {"bucket": "backlog", "issue": "blocked"})
    report = lint_activity(activity, rule_codes=["bucket-blocked"])
    assert report.findings == []


# ── runner / exit codes ───────────────────────────────────────────────


def test_exit_code_clean(activity: Path):
    write_task_file(activity, "backlog", "x")
    report = lint_activity(activity)
    assert report.exit_code() == 0


def test_exit_code_warn(activity: Path):
    write_task_file(activity, "backlog", "x", {"bucket": "backlog", "start_date": "2026-01-01"})
    report = lint_activity(activity)
    assert report.exit_code() == 1


def test_exit_code_error(activity: Path):
    write_task_file(activity, "backlog", "x", {"slug": "wrong"})
    report = lint_activity(activity)
    assert report.exit_code() == 2


def test_unknown_rule_raises():
    with pytest.raises(ValueError, match="unknown rule"):
        lint_activity(Path("/nonexistent"), rule_codes=["does-not-exist"])

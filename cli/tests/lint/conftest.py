"""Shared fixtures for lint tests.

Each test gets a minimal activity layout under tmp_path:

    <tmp>/<activity>/.octopus/activity.md
    <tmp>/<activity>/.octopus/tasks/<bucket>/<slug>.md
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _activity_md(title: str = "test") -> str:
    return (
        "---\n"
        "id: test-aaaa\n"
        "title: test\n"
        "type: other\n"
        "status: active\n"
        "spec_version: 1\n"
        "last_known_path: /tmp/test\n"
        "---\n"
    )


@pytest.fixture
def activity(tmp_path: Path) -> Path:
    """Build a minimal activity scaffold; return the activity root."""
    root = tmp_path / "act"
    octo = root / ".octopus"
    octo.mkdir(parents=True)
    (octo / "activity.md").write_text(_activity_md(), encoding="utf-8")
    tasks = octo / "tasks"
    tasks.mkdir()
    for b in ("now", "next", "backlog", "done", "dropped"):
        (tasks / b).mkdir()
    return root


def write_task_file(
    activity_root: Path,
    bucket: str,
    slug: str,
    frontmatter: dict | None = None,
    body: str = "",
    raw: str | None = None,
) -> Path:
    """Write a task file. If `raw` is given, write it verbatim (for corruption tests)."""
    path = activity_root / ".octopus" / "tasks" / bucket / f"{slug}.md"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    fm = dict(frontmatter or {})
    fm.setdefault("title", slug)
    fm.setdefault("created", "2026-05-26")
    fm.setdefault("bucket", bucket)
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, str) and not v.startswith("'"):
            lines.append(f"{k}: '{v}'" if k in {"created", "due", "start_date", "end_date"} else f"{k}: {v}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

"""Handoff I/O: read, write, default body, collision-suffixed filenames."""

from __future__ import annotations

from datetime import date

import pytest

from octopus.fs.scaffold import init_activity
from octopus.handoffs.io import (
    HandoffNotFoundError,
    default_body,
    generate_filename,
    handoffs_dir,
    list_handoffs,
    new_handoff,
    read_handoff,
    show_handoff,
    write_handoff,
)


@pytest.fixture
def activity(tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    a = init_activity(folder, activity_type="code")
    return folder, a.id


def test_generate_filename_basic():
    fn = generate_filename("pick up legacy auth work", when=date(2026, 5, 23))
    # slugify drops stopwords ("up") but keeps content words
    assert fn.startswith("2026-05-23-")
    assert "legacy" in fn
    assert "auth" in fn


def test_generate_filename_empty_title():
    fn = generate_filename("", when=date(2026, 5, 23))
    assert fn == "2026-05-23-handoff"


def test_generate_filename_collision():
    fn = generate_filename(
        "x",
        when=date(2026, 5, 23),
        existing=["2026-05-23-x", "2026-05-23-x-2"],
    )
    assert fn == "2026-05-23-x-3"


def test_default_body_includes_required_sections():
    b = default_body("My Handoff")
    assert "# My Handoff" in b
    assert "## TL;DR" in b
    assert "## What's done" in b
    assert "## What's next" in b
    assert "## Suggested next actions" in b
    assert "## Open questions" in b
    assert "## References" in b
    # Must include executable command hints — handoff is a router.
    assert "`octopus " in b


def test_new_handoff_creates_file(activity):
    folder, _ = activity
    h = new_handoff(folder, "Pick up here later")
    assert h.path is not None
    assert h.path.is_file()
    # slugify drops "up", "here" stopwords; keeps "pick", "later"
    assert "pick" in h.slug
    assert "later" in h.slug
    assert h.status == "open"
    assert h.from_actor == "human"
    assert h.priority == "medium"


def test_new_handoff_with_full_args(activity):
    folder, _ = activity
    h = new_handoff(
        folder,
        "Cross-team handoff",
        from_session="2026-05-23-some-session",
        from_actor="ai",
        to_actor="human",
        to_owner="alex",
        priority="high",
        summary="quick TL;DR",
        related_tasks=["task-1", "task-2"],
    )
    assert h.from_session == "2026-05-23-some-session"
    assert h.from_actor == "ai"
    assert h.to_actor == "human"
    assert h.to_owner == "alex"
    assert h.priority == "high"
    assert h.related_tasks == ["task-1", "task-2"]


def test_new_handoff_requires_title(activity):
    folder, _ = activity
    with pytest.raises(ValueError, match="title is required"):
        new_handoff(folder, "")
    with pytest.raises(ValueError, match="title is required"):
        new_handoff(folder, "   ")


def test_new_handoff_rejects_invalid_enum(activity):
    folder, _ = activity
    with pytest.raises(ValueError):
        new_handoff(folder, "bad", from_actor="alien")
    with pytest.raises(ValueError):
        new_handoff(folder, "bad", to_actor="alien")
    with pytest.raises(ValueError):
        new_handoff(folder, "bad", priority="yesterday")


def test_round_trip_preserves_body(activity):
    folder, _ = activity
    custom_body = "# Title\n\nCustom body — em-dash and `code`."
    h = new_handoff(folder, "rt", body=custom_body)
    h2, body2 = read_handoff(h.path)
    assert body2 == custom_body
    assert h2.title == "rt"


def test_round_trip_preserves_unknown_frontmatter(activity):
    folder, _ = activity
    h = new_handoff(folder, "unknown-fm")
    # Hand-inject a non-canonical field.
    p = h.path
    text = p.read_text(encoding="utf-8")
    text = text.replace("title:", "owner_external: someone\ntitle:")
    p.write_text(text, encoding="utf-8")

    h2, body2 = read_handoff(p)
    assert h2.extra.get("owner_external") == "someone"
    # Write back; unknown key should survive.
    write_handoff(p, h2, body2)
    after = p.read_text(encoding="utf-8")
    assert "owner_external: someone" in after


def test_default_omission_on_write(activity):
    folder, _ = activity
    h = new_handoff(folder, "defaults")
    text = h.path.read_text(encoding="utf-8")
    # Default priority/from_actor are required-or-default; from_actor must appear
    # (schema requires it), priority should be omitted when medium.
    assert "from_actor: human" in text
    assert "priority:" not in text
    # tags/related_tasks empty → omitted.
    assert "tags:" not in text
    assert "related_tasks:" not in text


def test_list_handoffs_empty(activity):
    folder, _ = activity
    assert list_handoffs(folder) == []


def test_list_handoffs_sorted_by_created(activity):
    folder, _ = activity
    new_handoff(folder, "a", when=date(2026, 5, 1))
    new_handoff(folder, "b", when=date(2026, 5, 3))
    new_handoff(folder, "c", when=date(2026, 5, 2))
    hs = list_handoffs(folder)
    assert [h.title for h in hs] == ["a", "c", "b"]


def test_list_handoffs_status_filter(activity):
    folder, _ = activity
    h1 = new_handoff(folder, "still-open")
    h2 = new_handoff(folder, "to-resolve")
    # Hand-edit h2 to resolved.
    h2.status = "resolved"
    h2.received_at = date(2026, 5, 23)
    h2.resolved_at = date(2026, 5, 23)
    _, body = read_handoff(h2.path)
    write_handoff(h2.path, h2, body)

    open_only = list_handoffs(folder, status="open")
    resolved_only = list_handoffs(folder, status="resolved")
    assert [h.slug for h in open_only] == [h1.slug]
    assert [h.slug for h in resolved_only] == [h2.slug]


def test_show_handoff_found(activity):
    folder, _ = activity
    h = new_handoff(folder, "look at me")
    h2 = show_handoff(folder, h.slug)
    assert h2.title == "look at me"


def test_show_handoff_missing_raises(activity):
    folder, _ = activity
    with pytest.raises(HandoffNotFoundError):
        show_handoff(folder, "no-such-slug")


def test_handoffs_dir_lazy(activity):
    folder, _ = activity
    # Directory should NOT exist until first write (scaffold is lazy).
    assert not handoffs_dir(folder).is_dir()
    new_handoff(folder, "first")
    assert handoffs_dir(folder).is_dir()


def test_new_handoff_collision_suffix(activity):
    folder, _ = activity
    h1 = new_handoff(folder, "same", when=date(2026, 5, 23))
    h2 = new_handoff(folder, "same", when=date(2026, 5, 23))
    assert h1.slug == "2026-05-23-same"
    assert h2.slug == "2026-05-23-same-2"


def test_validation_rejects_invalid_received_state(activity):
    folder, _ = activity
    h = new_handoff(folder, "v")
    # Inject illegal state: received_at set but status still open.
    h.received_at = date(2026, 5, 23)
    errors = h.validate()
    assert any("received_at requires status" in e for e in errors)

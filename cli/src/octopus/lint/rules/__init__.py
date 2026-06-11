"""Lint rule registrations. Importing this module registers every rule."""

from octopus.lint.rules import (
    bucket_blocked,  # noqa: F401
    bucket_match,  # noqa: F401
    corrupt_frontmatter,  # noqa: F401
    dangling_blocker,  # noqa: F401
    slug_match,  # noqa: F401
    slug_shape,  # noqa: F401
    stale_done,  # noqa: F401
    start_without_now,  # noqa: F401
    subtask_cross_activity,  # noqa: F401
    subtask_depth,  # noqa: F401
    subtask_orphan,  # noqa: F401
)

"""Session lifecycle: start / log / end / switch / prune / show / list.

Sessions are activity-scoped. The runtime "active session" pointer per
activity lives in `~/.cache/octopus/active-sessions.json` (cache wins
over frontmatter `active:` on mismatch).
"""

from octopus.sessions.cache import (
    cache_path,
    clear_active,
    get_active,
    load_active_map,
    set_active,
)
from octopus.sessions.io import (
    append_log_entry,
    generate_filename,
    list_sessions,
    read_session,
    sessions_dir,
    write_session,
)
from octopus.sessions.lifecycle import (
    NoActiveSessionError,
    end_session,
    log_session,
    prune_sessions,
    show_session,
    start_session,
    switch_session,
)

__all__ = [
    "NoActiveSessionError",
    "append_log_entry",
    "cache_path",
    "clear_active",
    "end_session",
    "generate_filename",
    "get_active",
    "list_sessions",
    "load_active_map",
    "log_session",
    "prune_sessions",
    "read_session",
    "sessions_dir",
    "set_active",
    "show_session",
    "start_session",
    "switch_session",
    "write_session",
]

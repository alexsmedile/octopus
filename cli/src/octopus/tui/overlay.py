"""TaskDetailOverlay — centered modal showing one task's full record.

Read-only. Shows title + bucket + axis chips + body + session log tail +
memory tail. Closed with Esc / left-arrow. Reused by Focus and (later) Board.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll  # Container used in error branches
from textual.screen import ModalScreen
from textual.widgets import Static

from octopus.fs.io import read_task
from octopus.fs.scaffold import BUCKET_FOLDERS, read_storage_mode
from octopus.sessions.io import list_sessions
from octopus.tui.icons import BLOCKED, DONE, DROPPED, NEXT, NOW, PINNED

_BUCKET_GLYPH = {
    "now": NOW,
    "next": NEXT,
    "done": DONE,
    "dropped": DROPPED,
    "backlog": "·",
}


def _find_task_file(octopus_dir: Path, storage_mode: str, slug: str) -> Path | None:
    """Locate tasks/<slug>.md across both flat and bucket-folder layouts.

    Mirrors `octopus.cli._find_task_file` — duplicated to keep tui/ free of
    cli.py imports (avoids circular wiring). Move to fs/io.py in group 5.
    """
    tasks_dir = octopus_dir / "tasks"
    if storage_mode == "folders":
        for bucket in BUCKET_FOLDERS:
            candidate = tasks_dir / bucket / f"{slug}.md"
            if candidate.is_file():
                return candidate
        return None
    candidate = tasks_dir / f"{slug}.md"
    return candidate if candidate.is_file() else None


def _render_chips(task: Any, bucket: str) -> Text:
    """Right-aligned chip row: bucket + pinned + blocked."""
    t = Text()
    glyph = _BUCKET_GLYPH.get(bucket, "·")
    bucket_color = {
        "now": "#F38BA8",
        "next": "#89DCEB",
        "done": "#A6E3A1",
        "dropped": "#8A8D9A",
        "backlog": "#8A8D9A",
    }.get(bucket, "#8A8D9A")
    t.append(f"{glyph} {bucket}", style=f"{bucket_color} bold")

    if getattr(task, "pinned", None):
        t.append("   ")
        t.append(f"{PINNED} pinned", style="#CBA6F7")

    if getattr(task, "run_state", None) == "blocked":
        t.append("   ")
        t.append(f"{BLOCKED} blocked", style="#FAB387")

    return t


def _render_sessions_tail(activity_root: Path, slug: str, *, limit: int = 5) -> Text:
    """Last N sessions that reference this task slug."""
    try:
        all_sessions = list_sessions(activity_root)
    except Exception as exc:
        return Text(f"(sessions unavailable: {exc})", style="#8A8D9A italic")

    matching = [
        s for s in all_sessions
        if slug in (getattr(s, "related_tasks", None) or [])
    ]
    if not matching:
        return Text("(no sessions yet)", style="#8A8D9A italic")

    tail = matching[-limit:]
    out = Text()
    for s in tail:
        when = s.started.strftime("%Y-%m-%d %H:%M")
        out.append(f"  {when}", style="#8A8D9A")
        out.append("  ")
        ended = "  open" if not getattr(s, "ended", None) else "  closed"
        out.append(ended, style="#89DCEB" if "open" in ended else "#8A8D9A")
        out.append("\n")
    return out


def _render_memory_tail(activity_root: Path, slug: str, *, limit: int = 5) -> Text:
    """Last N memory entries (text-only — the memory.md file structure)."""
    memory_md = activity_root / ".octopus" / "memory.md"
    if not memory_md.is_file():
        return Text("(no memory entries)", style="#8A8D9A italic")
    try:
        text = memory_md.read_text(encoding="utf-8")
    except Exception as exc:
        return Text(f"(memory unavailable: {exc})", style="#8A8D9A italic")

    # Pull the last `limit` non-empty lines that mention the slug. This is a
    # cheap heuristic — proper memory schema parsing is out of scope for the
    # overlay; we only want to show recent context.
    hits = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and slug in line
    ]
    if not hits:
        return Text("(no memory entries for this task)", style="#8A8D9A italic")
    out = Text()
    for line in hits[-limit:]:
        if len(line) > 90:
            line = line[:89] + "…"
        out.append(f"  {line}\n", style="#F5F5F7")
    return out


class TaskDetailOverlay(ModalScreen):
    """Centered modal showing one task. Esc / ← closes."""

    BINDINGS = [
        Binding("escape", "close", "close", show=True),
        Binding("left", "close", "back", show=False),
        Binding("q", "close", "close", show=False),
    ]

    def __init__(self, activity_root: Path, slug: str) -> None:
        super().__init__()
        self._activity_root = activity_root
        self._slug = slug

    def compose(self) -> ComposeResult:
        octopus_dir = self._activity_root / ".octopus"
        try:
            storage_mode = read_storage_mode(octopus_dir)
        except Exception:
            storage_mode = "flat"

        task_path = _find_task_file(octopus_dir, storage_mode, self._slug)

        if task_path is None:
            yield Container(
                Static(
                    f"[bold]Task not found:[/] {self._slug}",
                    classes="overlay-title",
                ),
                Static(
                    "  The task file could not be located in this activity.\n"
                    "  It may have been moved or the index may be stale.\n\n"
                    "  Press [bold]r[/] in Focus to reindex.",
                ),
                Static("Esc to close", classes="overlay-hint"),
                classes="overlay",
                id="overlay-root",
            )
            return

        try:
            task, body = read_task(task_path)
        except Exception as exc:
            yield Container(
                Static(
                    f"[bold]Could not read task:[/] {self._slug}",
                    classes="overlay-title",
                ),
                Static(f"  {exc}", classes="row--blocked"),
                Static("Esc to close", classes="overlay-hint"),
                classes="overlay",
                id="overlay-root",
            )
            return

        bucket = str(getattr(task, "bucket", "") or "")
        title = (task.title or "(untitled)").strip()
        body_text = (body or "").strip() or "(no body)"

        # Compose the header (title) + chips + body + tails
        chips = _render_chips(task, bucket)
        sessions_tail = _render_sessions_tail(self._activity_root, self._slug)
        memory_tail = _render_memory_tail(self._activity_root, self._slug)

        yield VerticalScroll(
            Static(title, classes="overlay-title"),
            Static(chips),
            Static(""),
            Static(Text(body_text, style="#F5F5F7")),
            Static(""),
            Static("[#8A8D9A]── sessions ──[/]"),
            Static(sessions_tail),
            Static("[#8A8D9A]── memory ──[/]"),
            Static(memory_tail),
            Static("Esc to close", classes="overlay-hint"),
            classes="overlay",
            id="overlay-root",
        )

    def action_close(self) -> None:
        self.dismiss(None)

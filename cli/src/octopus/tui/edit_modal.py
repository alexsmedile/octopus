"""In-app edit modal — opens task body in a Textual TextArea.

Bound to `e`. The `E` binding keeps the legacy `$EDITOR` (vim) flow.

Design:
- Body is focused by default.
- `↑` at the top of the body jumps focus into the frontmatter pane.
- `↓` at the bottom of the frontmatter brings focus back to the body.
- Border color tracks the task's bucket (now=pink, next=cyan, …).
- `Ctrl+S` saves. `Esc` on a dirty buffer asks before discarding.
- The on-disk file is split → edited → recombined so the YAML and body
  panes can be edited independently without one stomping the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from octopus.tui.icons import ACTIVITY

# Bucket → border color. Mirrors theme.tcss panel focus colors.
_BUCKET_COLORS: dict[str, str] = {
    "backlog": "#8A8D9A",
    "next": "#89DCEB",
    "now": "#F38BA8",
    "done": "#A6E3A1",
    "dropped": "#F38BA8",
}


@dataclass
class _Split:
    """Result of splitting a task file into its YAML and body parts."""

    has_frontmatter: bool
    frontmatter: str  # without the leading/trailing `---` fences
    body: str

    @classmethod
    def parse(cls, raw: str) -> "_Split":
        """Split a markdown file with optional YAML frontmatter.

        Recognizes the standard `---\\nYAML\\n---\\n…` form. If the file has no
        frontmatter, the whole content is treated as body.
        """
        if not raw.startswith("---\n"):
            return cls(has_frontmatter=False, frontmatter="", body=raw)
        rest = raw[4:]
        end = rest.find("\n---\n")
        if end < 0:
            # malformed — treat whole thing as body
            return cls(has_frontmatter=False, frontmatter="", body=raw)
        fm = rest[:end]
        body = rest[end + 5 :]  # skip "\n---\n"
        return cls(has_frontmatter=True, frontmatter=fm, body=body)

    def serialize(self) -> str:
        if not self.has_frontmatter:
            return self.body
        return f"---\n{self.frontmatter}\n---\n{self.body}"


class _ConfirmDiscard(ModalScreen[bool]):
    """Tiny confirm overlay for discarding unsaved changes."""

    BINDINGS = [
        Binding("y", "accept", "discard"),
        Binding("Y", "accept", "discard"),
        Binding("n", "decline", "keep"),
        Binding("N", "decline", "keep"),
        Binding("escape", "decline", "keep"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            "Discard unsaved changes?  (y / n)",
            id="confirm-discard",
            classes="overlay",
        )

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_decline(self) -> None:
        self.dismiss(False)


class EditModal(ModalScreen[bool]):
    """Modal task editor — body + frontmatter panes.

    Returns True if the file was saved, False otherwise.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "save", show=False, priority=True),
        Binding("escape", "close", "close", show=False, priority=True),
    ]

    def __init__(self, path: Path, slug: str, bucket: str) -> None:
        super().__init__()
        self._path = path
        self._slug = slug
        self._bucket = bucket
        self._original = path.read_text(encoding="utf-8")
        self._split = _Split.parse(self._original)
        self._dirty = False
        self._color = _BUCKET_COLORS.get(bucket, "#CBA6F7")

        self._fm_area = TextArea(self._split.frontmatter, id="edit-frontmatter")
        self._fm_area.show_line_numbers = False
        self._body_area = TextArea(self._split.body, id="edit-body")
        self._body_area.show_line_numbers = False
        self._dirty_static = Static("", id="edit-dirty")

    # ─── compose ──────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        title = Text()
        title.append(f"{ACTIVITY} ", style="#CBA6F7")
        title.append("edit · ", style="#F5F5F7")
        title.append(self._slug, style="bold #F5F5F7")
        right = Text(self._bucket, style=f"bold {self._color}")

        with Container(id="edit-modal", classes="overlay"):
            with Horizontal(id="edit-titlebar"):
                yield Static(title, id="edit-title")
                yield Static(right, id="edit-bucket")
            with Vertical(id="edit-panes"):
                yield Static("▾ frontmatter  (↑ from body to edit)", classes="edit-section")
                yield self._fm_area
                yield Static("▾ body", classes="edit-section")
                yield self._body_area
            with Horizontal(id="edit-footer"):
                yield Static(
                    "Ctrl+S save · Esc cancel · ↑ frontmatter",
                    id="edit-hint",
                )
                yield self._dirty_static

    # ─── lifecycle ────────────────────────────────────────────────────

    def on_mount(self) -> None:
        # Border color from the bucket. ModalScreen styles ride on #edit-modal.
        modal = self.query_one("#edit-modal")
        modal.styles.border = ("heavy", self._color)
        modal.styles.border_title_color = self._color
        modal.border_title = f"edit · {self._slug}"
        # Body focused by default.
        self._body_area.focus()

    def on_text_area_changed(self, _event: TextArea.Changed) -> None:
        new_fm = self._fm_area.text
        new_body = self._body_area.text
        is_dirty = (
            new_fm != self._split.frontmatter or new_body != self._split.body
        )
        if is_dirty != self._dirty:
            self._dirty = is_dirty
            self._dirty_static.update(
                Text("● modified", style=f"bold {self._color}") if is_dirty else Text("")
            )

    # ─── key handling — pane spill ────────────────────────────────────

    def on_key(self, event) -> None:
        """Up at top of body jumps to frontmatter; down at bottom of fm returns."""
        focused = self.focused
        if event.key == "up" and focused is self._body_area:
            if self._body_area.cursor_location[0] == 0 and self._split.has_frontmatter:
                self._fm_area.focus()
                # Land at the end of frontmatter for natural continuity.
                last_row = len(self._fm_area.text.splitlines())
                self._fm_area.cursor_location = (max(0, last_row - 1), 0)
                event.stop()
        elif event.key == "down" and focused is self._fm_area:
            last_row = len(self._fm_area.text.splitlines())
            if self._fm_area.cursor_location[0] >= max(0, last_row - 1):
                self._body_area.focus()
                self._body_area.cursor_location = (0, 0)
                event.stop()

    # ─── actions ──────────────────────────────────────────────────────

    def action_save(self) -> None:
        new_split = _Split(
            has_frontmatter=self._split.has_frontmatter,
            frontmatter=self._fm_area.text,
            body=self._body_area.text,
        )
        try:
            self._path.write_text(new_split.serialize(), encoding="utf-8")
        except Exception as exc:
            # Show in the dirty indicator slot — cheapest visible surface.
            self._dirty_static.update(Text(f"✗ save failed: {exc}", style="#F38BA8"))
            return
        self.dismiss(True)

    def action_close(self) -> None:
        if not self._dirty:
            self.dismiss(False)
            return

        def _on_confirm(discard: bool | None) -> None:
            if discard:
                self.dismiss(False)

        self.app.push_screen(_ConfirmDiscard(), _on_confirm)

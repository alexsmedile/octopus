"""In-app edit modal — opens task body in a Textual TextArea.

Bound to `e`. The `E` binding keeps the legacy `$EDITOR` (vim) flow.

Visual language matches the main view:
- Outer modal: lavender heavy border, panel-style background.
- Inner panes (frontmatter, body) use the `.panel` idiom — heavy
  `#2A2C36` resting border, bucket-color border on focus.
- Footer chip strip styled like `#keymap-bar`.

Layout flexes with terminal size — modal is 90% w × 90% h with sensible
minimums; inner panes use fr units so they reflow.

Editing model:
- Body is focused by default.
- `↑` at the top of the body jumps focus into the frontmatter pane.
- `↓` at the bottom of the frontmatter brings focus back to the body.
- `Alt+Left`/`Alt+Right` jump by word (macOS-native shortcut).
- `Alt+Backspace` deletes the previous word.
- `Ctrl+S` saves. `Esc` on a dirty buffer asks before discarding.

The on-disk file is split → edited → recombined so the YAML and body
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
from textual.widgets import ListItem, ListView, Static, TextArea

from octopus.tui.icons import ACTIVITY

# Bucket → border color. Mirrors theme.tcss panel focus colors.
_BUCKET_COLORS: dict[str, str] = {
    "backlog": "#8A8D9A",
    "next": "#89DCEB",
    "now": "#F38BA8",
    "done": "#A6E3A1",
    "dropped": "#F38BA8",
}

# Canonical Octopus task properties (from SCHEMA-TASK.md). Each entry:
#   (yaml_key, default_value_stub, one_line_description)
# Default value is a placeholder showing common syntax — not the actual default.
_TASK_PROPERTIES: list[tuple[str, str, str]] = [
    # identity (read-only — never inserted blindly)
    ("title", "", "task title (required)"),
    ("created", "YYYY-MM-DD", "creation date (required, ISO)"),
    # pipeline
    ("bucket", "backlog", "backlog | next | now | done | dropped"),
    ("stage", "", "free-form sub-stage within the activity"),
    # runtime
    ("run_state", "queued", "queued | running | finished | failed"),
    # attention
    ("pinned", "true", "marks task as pinned (omit when false)"),
    ("issue", "blocked", "blocked | waiting"),
    ("blocked_by", "", "required when issue=blocked"),
    ("waiting_for", "", "required when issue=waiting"),
    ("archived", "true", "hide from board/focus (omit when false)"),
    # dates
    ("due", "YYYY-MM-DD", "due date (ISO)"),
    ("scheduled", "YYYY-MM-DD", "scheduled date (ISO)"),
    ("start_date", "YYYY-MM-DD", "set by `octopus start`"),
    ("end_date", "YYYY-MM-DD", "set by `octopus finish`/`drop`"),
    # prioritization
    ("priority", "high", "low | high | urgent (absent = normal)"),
    ("energy", "mid", "low | mid | high"),
    # actors
    ("actor", "human", "human | ai | automation"),
    ("owner", "", "free-form owner / assignee"),
    # taxonomy
    ("kind", "feat", "feat | bug | spec | polish | test | chore"),
    ("tags", "[]", "list of strings"),
    # integrations
    ("external_refs", "{}", "{ reminders: <id>, github: <url> }"),
    ("import_date", "YYYY-MM-DD", "ISO date — set on import"),
    ("imported_from", "", "string — source of import"),
    ("promoted_to", "", "<provider>:<id> when promoted"),
]


@dataclass
class _Split:
    """Result of splitting a task file into its YAML and body parts."""

    has_frontmatter: bool
    frontmatter: str
    body: str

    @classmethod
    def parse(cls, raw: str) -> "_Split":
        if not raw.startswith("---\n"):
            return cls(has_frontmatter=False, frontmatter="", body=raw)
        rest = raw[4:]
        end = rest.find("\n---\n")
        if end < 0:
            return cls(has_frontmatter=False, frontmatter="", body=raw)
        fm = rest[:end]
        body = rest[end + 5 :]
        return cls(has_frontmatter=True, frontmatter=fm, body=body)

    def serialize(self) -> str:
        if not self.has_frontmatter:
            return self.body
        return f"---\n{self.frontmatter}\n---\n{self.body}"


class _OctopusTextArea(TextArea):
    """TextArea with macOS-native word navigation (alt+arrow).

    Stock Textual binds word-jump to ctrl+arrow; we want alt+arrow as
    well so it matches the terminal convention on macOS and the rest of
    the OS shortcuts.
    """

    BINDINGS = [
        Binding("alt+left", "cursor_word_left", "word left", show=False),
        Binding("alt+right", "cursor_word_right", "word right", show=False),
        Binding("alt+shift+left", "cursor_word_left(True)", "select word left", show=False),
        Binding("alt+shift+right", "cursor_word_right(True)", "select word right", show=False),
        Binding("alt+backspace", "delete_word_left", "delete word left", show=False),
    ]


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
            "Discard unsaved changes?   y / n",
            id="confirm-discard",
        )

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_decline(self) -> None:
        self.dismiss(False)


class EditModal(ModalScreen[bool]):
    """Modal task editor — frontmatter, body, and a properties cheat-sheet."""

    BINDINGS = [
        Binding("ctrl+s", "save", "save", show=False, priority=True),
        Binding("escape", "close", "close", show=False, priority=True),
        Binding("f2", "focus_properties", "properties", show=False, priority=True),
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

        self._fm_area = _OctopusTextArea(
            self._split.frontmatter,
            id="edit-frontmatter",
            classes="edit-pane",
        )
        self._fm_area.show_line_numbers = False
        self._body_area = _OctopusTextArea(
            self._split.body,
            id="edit-body",
            classes="edit-pane",
        )
        self._body_area.show_line_numbers = False
        self._fm_panel = Container(
            self._fm_area,
            id="edit-frontmatter-panel",
            classes="edit-panel",
        )
        self._body_panel = Container(
            self._body_area,
            id="edit-body-panel",
            classes="edit-panel",
        )
        self._dirty_static = Static("", id="edit-dirty")

        # Properties cheat-sheet — read-only list, Enter inserts the YAML
        # stub into the frontmatter pane at the cursor.
        items: list[ListItem] = []
        for key, stub, desc in _TASK_PROPERTIES:
            row = Text()
            row.append("  ", style="#0F1014")
            row.append(key, style="bold #CBA6F7")
            row.append("  ", style="#0F1014")
            row.append(desc, style="#8A8D9A")
            li = ListItem(Static(row))
            li.props_key = key  # type: ignore[attr-defined]
            li.props_stub = stub  # type: ignore[attr-defined]
            items.append(li)
        self._props_list = ListView(*items, id="edit-properties-list")
        self._props_panel = Container(
            self._props_list,
            id="edit-properties-panel",
            classes="edit-panel",
        )

    # ─── compose ──────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Container(id="edit-modal"):
            with Horizontal(id="edit-row"):
                with Vertical(id="edit-panes"):
                    yield self._fm_panel
                    yield self._body_panel
                yield self._props_panel
            with Horizontal(id="edit-footer"):
                yield Static(self._hint_text(), id="edit-hint")
                yield self._dirty_static

    def _hint_text(self) -> Text:
        out = Text()
        # chip-styled hints, same vocabulary as keymap_bar
        def chip(key: str, desc: str, color: str) -> None:
            out.append(f" {key} ", style=f"bold {color} on #16171E")
            out.append(" ", style="on #0F1014")
            out.append(desc, style="#8A8D9A on #0F1014")
            out.append("   ", style="on #0F1014")

        chip("^S", "save", "#86EFAC")
        chip("ESC", "cancel", "#3A3D48")
        chip("↑", "frontmatter", "#CBA6F7")
        chip("F2", "properties", "#CBA6F7")
        chip("⌥←→", "word", "#3A3D48")
        return out

    # ─── lifecycle ────────────────────────────────────────────────────

    def on_mount(self) -> None:
        modal = self.query_one("#edit-modal")
        modal.styles.border = ("heavy", "#CBA6F7")
        modal.styles.border_title_color = "#CBA6F7"
        modal.styles.border_subtitle_color = self._color
        modal.border_title = f"◇ edit · {self._slug}"
        modal.border_subtitle = self._bucket

        # Inner panel border colors set explicitly here so they track the
        # bucket on focus and the resting grey otherwise.
        self._fm_panel.border_title = "frontmatter"
        self._body_panel.border_title = "body"
        self._props_panel.border_title = "properties"
        self._props_panel.border_subtitle = "CR insert · F2 focus"

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
            if is_dirty:
                txt = Text()
                txt.append("●", style=f"bold {self._color}")
                txt.append(" modified", style="#8A8D9A")
                self._dirty_static.update(txt)
            else:
                self._dirty_static.update(Text(""))

    # ─── pane spill ───────────────────────────────────────────────────

    def on_key(self, event) -> None:
        focused = self.focused
        if event.key == "up" and focused is self._body_area:
            if self._body_area.cursor_location[0] == 0 and self._split.has_frontmatter:
                self._fm_area.focus()
                last_row = max(0, len(self._fm_area.text.splitlines()) - 1)
                self._fm_area.cursor_location = (last_row, 0)
                event.stop()
        elif event.key == "down" and focused is self._fm_area:
            last_row = max(0, len(self._fm_area.text.splitlines()) - 1)
            if self._fm_area.cursor_location[0] >= last_row:
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

    def action_focus_properties(self) -> None:
        """Move focus into the properties cheat-sheet."""
        try:
            self.set_focus(self._props_list)
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Insert the YAML stub for the highlighted property into frontmatter."""
        item = event.item
        if item is None or item.parent is not self._props_list:
            return
        key = getattr(item, "props_key", None)
        stub = getattr(item, "props_stub", "")
        if not key:
            return
        # Build the YAML line. Indentation matches Octopus convention: no leading spaces.
        line = f"{key}: {stub}" if stub else f"{key}: "

        # Ensure the file has a frontmatter block. If not, create one.
        if not self._split.has_frontmatter:
            self._split.has_frontmatter = True
            self._fm_area.text = line
        else:
            current = self._fm_area.text
            # Insert at cursor row. Defensive: append at end if cursor unknown.
            try:
                row, col = self._fm_area.cursor_location
                lines = current.splitlines()
                # Insert after the current row, or at end if past it.
                insert_at = min(row + 1, len(lines))
                lines.insert(insert_at, line)
                self._fm_area.text = "\n".join(lines)
                self._fm_area.cursor_location = (insert_at, len(line))
            except Exception:
                self._fm_area.text = current.rstrip("\n") + "\n" + line

        # Move focus back to the frontmatter area, ready to edit the stub.
        self._fm_area.focus()

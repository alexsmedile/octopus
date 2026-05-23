"""Toast — short-lived bottom-of-screen feedback line.

Used in early groups (3–4) to confirm a keystroke registered, even when its
mutation isn't wired yet. Replaced by real action feedback in group 5+.
"""

from __future__ import annotations

from textual.widgets import Static


class Toast(Static):
    def __init__(self) -> None:
        super().__init__("", id="toast")
        self._timer = None

    def flash(self, message: str, *, seconds: float = 1.6) -> None:
        self.update(message)
        self.add_class("--visible")
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
        self._timer = self.set_timer(seconds, self._hide)

    def _hide(self) -> None:
        self.remove_class("--visible")
        self._timer = None

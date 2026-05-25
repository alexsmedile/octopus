"""Animated mascot rendering + state machine — see `mascot_frames.py` for the
grid library and #31 PLAN.md for the locked spec.

The renderer (this module) turns 16×14 grids into half-block Pixels objects.
The state machine (also this module) decides which grid to render each tick:
default is Calm-A (independent body + blink channels), and `trigger(name)`
plays a one-shot animation from the registry, then returns to Calm-A.

The Textual widget that mounts this state machine lives in `header_bar.py`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache

from PIL import Image
from rich_pixels import Pixels

from octopus.tui.mascot_frames import (
    ANIMATIONS,
    BASE_REF,
    BLINK_COOLDOWN_MAX_MS,
    BLINK_COOLDOWN_MIN_MS,
    CALM_A_SEQUENCE,
    DOUBLE_BLINK_PHASES,
    DOUBLE_BLINK_PROB,
    POOL_FRAMES,
    SINGLE_BLINK_PHASES,
    AnimFrame,
    BlinkPhase,
    H,
    W,
    apply_blink,
)

# Palette colors (Catppuccin lavender + near-black + TUI bg).
MASCOT_COLOR = (203, 166, 247)   # #CBA6F7
EYE_COLOR = (26, 26, 26)         # #1A1A1A
BG_COLOR = (15, 16, 20)          # #0F1014

_PALETTE = {"L": MASCOT_COLOR, "E": EYE_COLOR, ".": BG_COLOR}


def _build_image(grid: str) -> Image.Image:
    """Convert a 16×14 grid string into a PIL Image."""
    img = Image.new("RGB", (W, H), BG_COLOR)
    pixels = img.load()
    for i, ch in enumerate(grid):
        x = i % W
        y = i // W
        pixels[x, y] = _PALETTE[ch]
    return img


@lru_cache(maxsize=128)
def render_grid(grid: str) -> Pixels:
    """Render any grid string as a half-block Pixels object.

    Cached — same grid string returns the same Pixels object (the animation
    state machine reuses these aggressively across blink/body combinations).
    """
    return Pixels.from_image(_build_image(grid))


# Backwards-compat: callers that previously imported `render_mascot()` keep
# working. Returns the static rest frame.
@lru_cache(maxsize=1)
def render_mascot() -> Pixels:
    """Static base mascot — same as the v1 static frame."""
    return render_grid(BASE_REF)


# ─── State machine ────────────────────────────────────────────────────


@dataclass
class _ActiveBlink:
    """Current blink phase being held."""

    phase: BlinkPhase
    ms_left: int


@dataclass
class MascotController:
    """State machine for the mascot's animation.

    Default state: Calm-A (body cycle + decoupled blink channel).
    On `trigger(name)`, plays the named animation one-shot, then returns to
    Calm-A. Triggers while not idle are ignored (no queueing).

    Pure Python — no Textual coupling. The widget calls `tick(delta_ms)` on
    every interval and then reads `current_grid()` to render.
    """

    # Public state
    state: str = "idle"     # "idle" | "capovolta" | "moonwalk-d6" | "moonwalk-e"

    # Calm-A body channel
    _calm_step_idx: int = 0
    _calm_step_elapsed_ms: int = 0

    # Calm-A blink channel
    _blink_queue: list[BlinkPhase] = field(default_factory=list)
    _blink_active: _ActiveBlink | None = None
    _blink_cooldown_ms: int = 2500   # initial cooldown

    # Non-idle animation channel
    _anim_frames: tuple[AnimFrame, ...] = ()
    _anim_frame_idx: int = 0
    _anim_frame_elapsed_ms: int = 0

    # Reproducibility for tests
    _rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        # Schedule the first blink with a randomized cooldown.
        self._blink_cooldown_ms = self._rng.randint(
            BLINK_COOLDOWN_MIN_MS, BLINK_COOLDOWN_MAX_MS
        )

    # ─── Public API ───

    def trigger(self, animation_name: str) -> bool:
        """Start a one-shot animation. Returns True if accepted, False if
        ignored (state was not idle).
        """
        if self.state != "idle":
            return False
        if animation_name not in ANIMATIONS:
            raise ValueError(f"unknown animation: {animation_name!r}")
        self.state = animation_name
        self._anim_frames = ANIMATIONS[animation_name]
        self._anim_frame_idx = 0
        self._anim_frame_elapsed_ms = 0
        return True

    def tick(self, delta_ms: int) -> None:
        """Advance time by delta_ms. Updates whichever channels are active."""
        if self.state == "idle":
            self._tick_calm(delta_ms)
        else:
            self._tick_anim(delta_ms)

    def current_grid(self) -> str:
        """Return the grid string that should be rendered right now."""
        if self.state == "idle":
            base_frame = POOL_FRAMES[CALM_A_SEQUENCE[self._calm_step_idx].pool_idx]
            return apply_blink(base_frame, self._current_blink_level())
        # Non-idle animation: the frame is already complete (blinks/tilts
        # baked in during frame construction).
        return self._anim_frames[self._anim_frame_idx].grid

    # ─── Internals ───

    def _current_blink_level(self) -> int:
        return self._blink_active.phase.level if self._blink_active else 0

    def _tick_calm(self, delta_ms: int) -> None:
        # Body channel
        self._calm_step_elapsed_ms += delta_ms
        step_ms = CALM_A_SEQUENCE[self._calm_step_idx].ms
        if self._calm_step_elapsed_ms >= step_ms:
            self._calm_step_elapsed_ms = 0
            self._calm_step_idx = (self._calm_step_idx + 1) % len(CALM_A_SEQUENCE)
        # Blink channel
        if self._blink_active is not None:
            self._blink_active.ms_left -= delta_ms
            if self._blink_active.ms_left <= 0:
                if self._blink_queue:
                    nxt = self._blink_queue.pop(0)
                    self._blink_active = _ActiveBlink(phase=nxt, ms_left=nxt.ms)
                else:
                    self._blink_active = None
                    self._blink_cooldown_ms = self._rng.randint(
                        BLINK_COOLDOWN_MIN_MS, BLINK_COOLDOWN_MAX_MS
                    )
        elif self._blink_queue:
            nxt = self._blink_queue.pop(0)
            self._blink_active = _ActiveBlink(phase=nxt, ms_left=nxt.ms)
        else:
            self._blink_cooldown_ms -= delta_ms
            if self._blink_cooldown_ms <= 0:
                self._start_blink()

    def _start_blink(self) -> None:
        if self._rng.random() < DOUBLE_BLINK_PROB:
            self._blink_queue = list(DOUBLE_BLINK_PHASES)
        else:
            self._blink_queue = list(SINGLE_BLINK_PHASES)

    def _tick_anim(self, delta_ms: int) -> None:
        self._anim_frame_elapsed_ms += delta_ms
        frame_ms = self._anim_frames[self._anim_frame_idx].ms
        if self._anim_frame_elapsed_ms >= frame_ms:
            self._anim_frame_elapsed_ms = 0
            self._anim_frame_idx += 1
            if self._anim_frame_idx >= len(self._anim_frames):
                # Animation done — return to idle.
                self.state = "idle"
                self._anim_frames = ()
                self._anim_frame_idx = 0


# ─── Tick interval used by the Textual widget ────────────────────────

# Pick a tick granularity that divides cleanly into all our timings.
# Calm-A holds: 1200ms. Blink phases: 100/140/180. D6 frames: 150/200.
# Capovolta frames: 100/150/200. E frames: 150/200.
# GCD ≈ 10ms, but Textual intervals < 50ms are wasteful. Use 50ms.
TICK_INTERVAL_S: float = 0.05
TICK_INTERVAL_MS: int = 50

"""Tests for the TUI mascot animation system — see #31 PLAN.md."""

from __future__ import annotations

import random

import pytest

from octopus.tui.mascot import MascotController
from octopus.tui.mascot_frames import (
    ANIMATIONS,
    BASE_REF,
    BLINK_COOLDOWN_MAX_MS,
    CAPOVOLTA_B_FRAMES,
    H,
    MOONWALK_D6_FRAMES,
    MOONWALK_E_FRAMES,
    POOL_FRAMES,
    W,
    apply_blink,
    shift_v,
)

# ─── Frame integrity ──────────────────────────────────────────────────


def _assert_valid_grid(grid: str) -> None:
    assert len(grid) == W * H, f"grid length {len(grid)} ≠ {W * H}"
    assert set(grid) <= set(".LE"), f"unexpected chars: {set(grid) - set('.LE')}"


def test_base_ref_valid():
    _assert_valid_grid(BASE_REF)


def test_pool_frames_valid():
    assert len(POOL_FRAMES) == 3
    for g in POOL_FRAMES:
        _assert_valid_grid(g)


def test_capovolta_frames_valid():
    assert len(CAPOVOLTA_B_FRAMES) == 6
    for f in CAPOVOLTA_B_FRAMES:
        _assert_valid_grid(f.grid)
        assert f.ms > 0


def test_moonwalk_d6_frames_valid():
    assert len(MOONWALK_D6_FRAMES) == 15
    for f in MOONWALK_D6_FRAMES:
        _assert_valid_grid(f.grid)
        assert f.ms > 0


def test_moonwalk_e_frames_valid():
    assert len(MOONWALK_E_FRAMES) == 9
    for f in MOONWALK_E_FRAMES:
        _assert_valid_grid(f.grid)
        assert f.ms > 0


def test_all_animations_settle_to_base_ref():
    """The last frame of every non-idle animation must be BASE_REF so the
    state machine can hand back to Calm-A without a visual jump."""
    for name, frames in ANIMATIONS.items():
        assert frames[-1].grid == BASE_REF, f"{name} doesn't end on BASE_REF"


# ─── apply_blink semantics (the bug fix from v9 → v10) ───────────────


def test_blink_level_0_is_passthrough():
    for g in POOL_FRAMES:
        assert apply_blink(g, 0) == g


def test_blink_level_1_blanks_top_eye_row():
    """Level 1 = lid drops from above → top eye row turns to body, bottom
    keeps the eye. The thin dark line shows at the bottom of the eye cell."""
    rest = POOL_FRAMES[0]
    blinked = apply_blink(rest, 1)
    # In BASE_REF, eye rows are 5 and 6. After level-1: row 5 has no E,
    # row 6 still has E.
    row5 = blinked[5 * W : 6 * W]
    row6 = blinked[6 * W : 7 * W]
    assert "E" not in row5
    assert "E" in row6


def test_blink_level_2_blanks_both_eye_rows():
    rest = POOL_FRAMES[0]
    blinked = apply_blink(rest, 2)
    row5 = blinked[5 * W : 6 * W]
    row6 = blinked[6 * W : 7 * W]
    assert "E" not in row5
    assert "E" not in row6


def test_blink_works_when_body_shifted_up():
    """Body=up shifts the eye rows from 5-6 to 4-5. Level-1 must blank row 4
    (the new top eye row), not the old row 5 (which is now an eye row but
    NOT the top). This was the v9 bug."""
    up = POOL_FRAMES[1]
    # Sanity: eyes should be on rows 4-5 in the up frame.
    rows = [up[y * W : (y + 1) * W] for y in range(H)]
    eye_rows = [y for y, r in enumerate(rows) if "E" in r]
    assert eye_rows == [4, 5], f"unexpected eye rows in POOL_UP: {eye_rows}"

    blinked = apply_blink(up, 1)
    row4 = blinked[4 * W : 5 * W]
    row5 = blinked[5 * W : 6 * W]
    assert "E" not in row4, "level-1 must blank the top eye row (row 4 when body=up)"
    assert "E" in row5, "level-1 must keep the bottom eye row intact (row 5 when body=up)"


def test_blink_works_when_body_shifted_down():
    """Body=down shifts eyes to rows 6-7. Level-1 blanks row 6, keeps row 7."""
    down = POOL_FRAMES[2]
    rows = [down[y * W : (y + 1) * W] for y in range(H)]
    eye_rows = [y for y, r in enumerate(rows) if "E" in r]
    assert eye_rows == [6, 7], f"unexpected eye rows in POOL_DOWN: {eye_rows}"

    blinked = apply_blink(down, 1)
    row6 = blinked[6 * W : 7 * W]
    row7 = blinked[7 * W : 8 * W]
    assert "E" not in row6
    assert "E" in row7


def test_blink_level_2_works_for_all_body_positions():
    for g in POOL_FRAMES:
        blinked = apply_blink(g, 2)
        assert "E" not in blinked


# ─── shift_v helper ──────────────────────────────────────────────────


def test_shift_v_up_moves_content_up():
    shifted = shift_v(BASE_REF, -1)
    # BASE_REF has body content starting on row 2. Shifted up by 1, it should
    # now start on row 1.
    row1 = shifted[1 * W : 2 * W]
    assert "L" in row1


def test_shift_v_down_moves_content_down():
    shifted = shift_v(BASE_REF, 1)
    # Body content originally on row 2 should now be on row 3.
    row3 = shifted[3 * W : 4 * W]
    assert "L" in row3


# ─── MascotController state machine ─────────────────────────────────


def _seeded_controller(seed: int = 42) -> MascotController:
    c = MascotController()
    c._rng = random.Random(seed)
    # Re-init the cooldown with seeded rng
    c._blink_cooldown_ms = c._rng.randint(2000, 4000)
    return c


def test_controller_starts_idle():
    c = MascotController()
    assert c.state == "idle"


def test_controller_initial_grid_is_calm():
    c = MascotController()
    # Should be BASE_REF (rest frame, no blink active)
    assert c.current_grid() == BASE_REF


def test_trigger_capovolta_changes_state():
    c = MascotController()
    accepted = c.trigger("capovolta")
    assert accepted is True
    assert c.state == "capovolta"


def test_trigger_unknown_raises():
    c = MascotController()
    with pytest.raises(ValueError):
        c.trigger("not-a-real-animation")


def test_trigger_during_animation_is_rejected():
    c = MascotController()
    c.trigger("capovolta")
    rejected = c.trigger("moonwalk-d6")
    assert rejected is False
    assert c.state == "capovolta"


def test_animation_returns_to_idle_after_completing():
    """Tick through capovolta's full duration; state should return to idle."""
    c = MascotController()
    c.trigger("capovolta")
    total_ms = sum(f.ms for f in CAPOVOLTA_B_FRAMES)
    # Tick a bit past the total to ensure we cross the boundary.
    for _ in range((total_ms + 200) // 50):
        c.tick(50)
    assert c.state == "idle"


def test_each_animation_completes():
    for name in ANIMATIONS:
        c = MascotController()
        c.trigger(name)
        total_ms = sum(f.ms for f in ANIMATIONS[name])
        for _ in range((total_ms + 200) // 50):
            c.tick(50)
        assert c.state == "idle", f"{name} did not return to idle"


def test_calm_body_cycles_through_pool():
    """Tick through one full calm cycle; the body should visit all 3 pool frames."""
    c = _seeded_controller()
    seen_pool_idx = set()
    for _ in range(120):  # 6s
        seen_pool_idx.add(c._calm_step_idx)
        c.tick(50)
    # All 4 sequence steps should have been visited.
    assert seen_pool_idx == {0, 1, 2, 3}


def test_calm_grid_changes_over_time():
    """The grid should not be static while in idle — body bob changes it."""
    c = _seeded_controller()
    grids = set()
    for _ in range(120):
        grids.add(c.current_grid())
        c.tick(50)
    # At minimum: rest, up, down (3 body positions). Possibly more if blinks fire.
    assert len(grids) >= 3


def test_blink_eventually_fires():
    """With a deterministic RNG, a blink should fire within the max cooldown."""
    c = _seeded_controller(seed=1)
    levels_seen = set()
    # Ample time for at least one blink at max cooldown.
    for _ in range((BLINK_COOLDOWN_MAX_MS + 1000) // 50):
        c.tick(50)
        levels_seen.add(c._current_blink_level())
    # We should see at least the half (1) state.
    assert 1 in levels_seen


def test_animation_frames_advance_through_each_position():
    """Capovolta has 6 distinct frames; ticking through should hit each."""
    c = MascotController()
    c.trigger("capovolta")
    seen_grids = set()
    for _ in range(30):  # 1.5s = more than capovolta's 900ms
        seen_grids.add(c.current_grid())
        c.tick(50)
    # 6 frames but some may not be unique — at least 4 distinct.
    assert len(seen_grids) >= 4

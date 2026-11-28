"""Unit tests for the 60 FPS MotionEngine, easing curves, and GlowCache."""

from __future__ import annotations

import math
import os

from neo_flood_fill.effects import (
    GlowCache,
    MotionEngine,
    clamp01,
    ease_in_out_sine,
    ease_out_back,
    ease_out_cubic,
    exp_lerp,
    lerp_rgb,
)
from neo_flood_fill.studio_state import StudioState


def test_easing_boundaries_and_monotonic_endpoints() -> None:
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0

    for fn in (ease_out_cubic, ease_out_back, ease_in_out_sine):
        assert math.isclose(fn(0.0), 0.0, abs_tol=1e-6)
        assert math.isclose(fn(1.0), 1.0, abs_tol=1e-6)

    # ease_out_back overshoots > 1.0 near t=0.7
    assert ease_out_back(0.7) > 1.0
    # ease_out_cubic decelerates cleanly within [0, 1]
    assert 0.8 < ease_out_cubic(0.5) < 1.0


def test_exp_lerp_and_lerp_rgb() -> None:
    val = 0.0
    for _ in range(60):
        val = exp_lerp(val, 100.0, speed=18.0, dt_sec=1.0 / 60.0)
    assert math.isclose(val, 100.0, abs_tol=0.1)

    assert lerp_rgb((0, 0, 0), (200, 100, 50), 0.5) == (100, 50, 25)
    assert lerp_rgb((10, 20, 30), (40, 50, 60), 0.0) == (10, 20, 30)
    assert lerp_rgb((10, 20, 30), (40, 50, 60), 1.0) == (40, 50, 60)


def test_motion_engine_cell_lifecycle_path_chain_and_sliding_pills() -> None:
    import pygame

    engine = MotionEngine()
    engine.trigger_cell(1, 2, (32, 201, 151), "fill")
    engine.trigger_cell(2, 2, (139, 92, 246), "path")
    engine.trigger_cell(2, 3, (139, 92, 246), "path")

    assert (1, 2) in engine.cell_anims
    assert engine.path_chain == [(2, 2), (2, 3)]
    assert 0.35 <= engine.cell_anims[(1, 2)].scale() <= 1.15

    # Sliding pill glides smoothly toward new target rect
    r1 = pygame.Rect(100, 10, 80, 26)
    r2 = pygame.Rect(200, 10, 90, 26)
    assert engine.sync_pill("mode", r1) == r1
    engine.sync_pill("mode", r2)
    for _ in range(45):
        engine.update(16.6, has_toast=True)
    assert engine.sync_pill("mode", r2) == r2
    assert engine.toast_vis > 0.95

    # Cell animations expire cleanly once age_ms >= duration_ms
    assert len(engine.cell_anims) == 0

    engine.clear_grid_effects()
    assert engine.path_chain == []


def test_motion_engine_caps_active_animations_and_glow_cache() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame

    pygame.init()
    try:
        engine = MotionEngine()
        for idx in range(450):
            engine.trigger_cell(idx // 30, idx % 30, (99, 102, 241), "visit")
        assert len(engine.cell_anims) <= 361

        cache = GlowCache(max_entries=4)
        for i in range(6):
            surf = cache.get(12 + i * 2, (100, 120, 240))
            assert surf.get_width() > 0
        assert len(cache._cache) <= 4
    finally:
        pygame.quit()


def test_studio_state_emits_visual_events_for_motion_engine() -> None:
    state = StudioState(grid_size_key="small", preset="multi_room")
    initial_events = state.pop_visual_events()
    assert any(ev[0] == "clear" for ev in initial_events)

    state.set_speed_index(5)
    assert state.start_flood_fill((1, 1)) is True
    state.update(16.0)
    fill_events = state.pop_visual_events()
    assert any(ev[0] == "fill" for ev in fill_events)

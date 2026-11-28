"""Unit tests for StudioState interactions and headless Pygame StudioRenderer."""

from __future__ import annotations

import os

import pytest

from neo_flood_fill.grid import (
    EMPTY,
    PALETTE_ENTRIES,
    WALL,
)
from neo_flood_fill.studio_state import (
    StudioState,
    bresenham_line,
)


def _drain_animation(state: StudioState, max_ticks: int = 500) -> None:
    """Advance ``state`` at max speed until the active animation finishes."""
    state.set_speed_index(len(state.run_history) * 0 + 5)  # Max speed
    for _ in range(max_ticks):
        if not state.is_running:
            break
        state.update(16.0)


def test_bresenham_line_horizontal_vertical_and_diagonal() -> None:
    assert bresenham_line((2, 1), (2, 5)) == [(2, 1), (2, 2), (2, 3), (2, 4), (2, 5)]
    assert bresenham_line((0, 0), (3, 3)) == [(0, 0), (1, 1), (2, 2), (3, 3)]
    assert bresenham_line((4, 2), (4, 2)) == [(4, 2)]


def test_multi_color_paint_bucket_flood_fill_independent_regions() -> None:
    state = StudioState(grid_size_key="small", preset="multi_room")
    mint_id = PALETTE_ENTRIES[0].color_id
    coral_id = PALETTE_ENTRIES[6].color_id
    purple_id = PALETTE_ENTRIES[4].color_id

    # Paint top-left room with Mint
    state.pick_palette_entry(mint_id)
    assert state.start_flood_fill((1, 1)) is True
    _drain_animation(state)
    assert state.status == "Done"
    assert state.grid.get_base(1, 1) == mint_id
    assert len(state.run_history) == 1

    # Find an untouched EMPTY cell in a sealed chamber and paint it Coral
    sealed_cell = None
    for r in range(state.grid.rows):
        for c in range(state.grid.cols):
            if state.grid.get_base(r, c) == EMPTY:
                sealed_cell = (r, c)
                break
        if sealed_cell is not None:
            break

    assert sealed_cell is not None, "Multi-room preset should contain a sealed chamber"
    state.pick_palette_entry(coral_id)
    assert state.start_flood_fill(sealed_cell) is True
    _drain_animation(state)
    assert state.grid.get_base(*sealed_cell) == coral_id
    # First room remained Mint
    assert state.grid.get_base(1, 1) == mint_id

    # Repaint first room from Mint -> Purple without affecting Coral chamber
    state.pick_palette_entry(purple_id)
    assert state.start_flood_fill((1, 1)) is True
    _drain_animation(state)
    assert state.grid.get_base(1, 1) == purple_id
    assert state.grid.get_base(*sealed_cell) == coral_id


def test_pathfinding_comparison_history_preserves_painted_base_colors() -> None:
    state = StudioState(grid_size_key="small", preset="multi_room")
    mint_id = PALETTE_ENTRIES[0].color_id

    # First paint a region in Flood Fill mode
    state.pick_palette_entry(mint_id)
    state.start_flood_fill((1, 1))
    _drain_animation(state)
    assert state.grid.get_base(1, 1) == mint_id

    # Switch to Pathfinding and run BFS then A* on the same map
    state.set_studio_mode("pathfinding")
    state.set_algorithm("bfs")
    assert state.start_pathfinding() is True
    _drain_animation(state)
    bfs_record = state.run_history[0]
    assert bfs_record.found is True

    state.set_algorithm("astar")
    assert state.start_pathfinding() is True
    _drain_animation(state)
    astar_record = state.run_history[0]
    assert astar_record.found is True
    assert astar_record.result_value == bfs_record.result_value
    assert astar_record.visited <= bfs_record.visited

    # Clearing pathfinding overlay keeps painted Mint region intact
    state.clear_search_overlay()
    assert state.grid.get_base(1, 1) == mint_id


def test_drag_wall_painting_right_click_erase_and_undo() -> None:
    state = StudioState(grid_size_key="small", preset="multi_room")
    state.reset_grid()
    state.set_tool("wall")

    state.begin_cell_interaction((3, 2), button=1)
    state.drag_cell_interaction((3, 7))
    state.end_cell_interaction()

    for c in range(2, 8):
        assert state.grid.get_base(3, c) == WALL

    # Undo removes the entire wall stroke cleanly
    assert state.undo() is True
    for c in range(2, 8):
        assert state.grid.get_base(3, c) == EMPTY

    # Draw again and right-click drag erase
    state.begin_cell_interaction((4, 2), button=1)
    state.drag_cell_interaction((4, 5))
    state.end_cell_interaction()
    assert state.grid.get_base(4, 4) == WALL

    state.begin_cell_interaction((4, 2), button=3)
    state.drag_cell_interaction((4, 5))
    state.end_cell_interaction()
    for c in range(2, 6):
        assert state.grid.get_base(4, c) == EMPTY


def test_pause_resume_and_single_step_playback() -> None:
    state = StudioState(grid_size_key="small", preset="maze")
    state.set_studio_mode("pathfinding")
    state.set_algorithm("bfs")
    state.set_speed_index(0)

    state.toggle_run_pause()  # Start running
    assert state.is_running is True

    state.toggle_run_pause()  # Pause
    assert state.is_paused is True

    assert state.step_once() is True
    assert state.is_paused is True

    state.toggle_run_pause()  # Resume
    assert state.is_running is True


def test_color_conflict_guard_blocks_collisions() -> None:
    state = StudioState(grid_size_key="small", preset="multi_room")
    coral_id = PALETTE_ENTRIES[6].color_id  # Coral
    blue_id = PALETTE_ENTRIES[2].color_id   # Blue

    # Assign Path to Coral
    state.set_color_target("path")
    assert state.pick_palette_entry(coral_id) is True

    # Attempting to set Wall to Coral must be rejected
    state.set_color_target("wall")
    assert state.pick_palette_entry(coral_id) is False
    assert "cannot share" in state.alert_message.lower()

    # Assign Start to Blue, then reject End == Blue
    state.set_color_target("start")
    assert state.pick_palette_entry(blue_id) is True
    state.set_color_target("end")
    assert state.pick_palette_entry(blue_id) is False

    state.reset_colors()
    assert state.active_color_target == "fill"


def test_headless_pygame_studio_renderer_and_events() -> None:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    import pygame
    from neo_flood_fill.visualizer import (
        StudioRenderer,
        WINDOW_HEIGHT,
        WINDOW_WIDTH,
    )

    pygame.init()
    try:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        state = StudioState(grid_size_key="medium", preset="multi_room")
        renderer = StudioRenderer(state)

        # Render Flood Fill mode, trigger a fill, render mid-animation & done
        renderer.render(screen)
        assert state.start_flood_fill((1, 1)) is True
        state.update(50.0)
        renderer.render(screen)
        _drain_animation(state)
        renderer.render(screen)

        # Switch to Pathfinding via TAB event, run A* via SPACE event
        assert renderer.handle_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_TAB})
        )
        assert state.studio_mode == "pathfinding"
        assert renderer.handle_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE})
        )
        _drain_animation(state)
        renderer.render(screen)

        # Verify pixel output is non-empty
        assert screen.get_size() == (WINDOW_WIDTH, WINDOW_HEIGHT)
        assert screen.get_at((200, 200))[:3] != (0, 0, 0)
    finally:
        pygame.quit()

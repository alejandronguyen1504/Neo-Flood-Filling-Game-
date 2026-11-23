"""Unit tests for the two-layer Grid model, pure helpers, and terrain generators."""

from __future__ import annotations

import pytest

from neo_flood_fill.algorithms import pathfind_bfs
from neo_flood_fill.grid import (
    EMPTY,
    FILLED,
    GRID_PRESETS,
    OVERLAY_END,
    OVERLAY_FRONTIER,
    OVERLAY_NONE,
    OVERLAY_PATH,
    OVERLAY_START,
    OVERLAY_VISITED,
    PALETTE_ENTRIES,
    PALETTE_START_ID,
    WALL,
    Grid,
    create_grid,
    format_grid,
    generate_maze,
    generate_multi_room,
    generate_random_obstacles,
    generate_spiral,
    get_cell,
    get_grid_size,
    is_valid_cell,
    set_cell,
)


def test_pure_grid_helpers_basic_and_bounds() -> None:
    g = create_grid(3, 4)
    assert get_grid_size(g) == (3, 4)
    assert is_valid_cell(g, 0, 0)
    assert is_valid_cell(g, 2, 3)
    assert not is_valid_cell(g, -1, 0)
    assert not is_valid_cell(g, 3, 0)
    assert not is_valid_cell(g, 0, 4)

    assert set_cell(g, 1, 2, WALL) is True
    assert set_cell(g, 9, 9, WALL) is False
    assert get_cell(g, 1, 2) == WALL
    assert get_cell(g, -1, 0) is None
    assert "1" in format_grid(g)


def test_pure_grid_helpers_empty_grids() -> None:
    assert get_grid_size([]) == (0, 0)
    assert not is_valid_cell([], 0, 0)
    assert not is_valid_cell([[]], 0, 0)
    assert get_cell([], 0, 0) is None
    assert set_cell([], 0, 0, WALL) is False

    with pytest.raises(ValueError):
        create_grid(-1, 3)


def test_grid_presets_and_validation() -> None:
    for name, expected_size in GRID_PRESETS.items():
        g = Grid.from_preset(name)
        assert (g.rows, g.cols) == expected_size

    with pytest.raises(ValueError):
        Grid.from_preset("nonexistent")

    with pytest.raises(ValueError):
        Grid(0, 5)


def test_two_layer_isolation_preserves_multi_color_regions() -> None:
    g = Grid(6, 6)
    color_a = PALETTE_ENTRIES[0].color_id
    color_b = PALETTE_ENTRIES[1].color_id

    g.set_base(0, 0, color_a)
    g.set_base(0, 1, color_b)
    g.set_base(1, 1, WALL)
    g.set_start(0, 0)
    g.set_end(5, 5)

    # Simulate pathfinding overlay on top of painted regions
    g.set_overlay(0, 1, OVERLAY_VISITED)
    g.set_overlay(2, 2, OVERLAY_FRONTIER)
    g.set_overlay(3, 3, OVERLAY_PATH)

    g.clear_search_overlay()

    # Search overlays cleared, endpoints & base colors completely intact
    assert g.get_overlay(0, 1) == OVERLAY_NONE
    assert g.get_overlay(2, 2) == OVERLAY_NONE
    assert g.get_overlay(3, 3) == OVERLAY_NONE
    assert g.get_overlay(0, 0) == OVERLAY_START
    assert g.get_overlay(5, 5) == OVERLAY_END
    assert g.get_base(0, 0) == color_a
    assert g.get_base(0, 1) == color_b
    assert g.get_base(1, 1) == WALL


def test_endpoint_collision_and_wall_interaction() -> None:
    g = Grid(5, 5)
    g.set_base(2, 2, WALL)
    assert g.set_start(2, 2, overwrite_wall=False) is False
    assert g.start is None

    assert g.set_start(2, 2, overwrite_wall=True) is True
    assert g.get_base(2, 2) == EMPTY
    assert g.start == (2, 2)

    # Moving end onto start clears start cleanly
    g.set_end(2, 2)
    assert g.end == (2, 2)
    assert g.start is None
    assert g.get_overlay(2, 2) == OVERLAY_END

    # Placing a wall on end clears end cleanly
    g.set_base(2, 2, WALL)
    assert g.end is None
    assert g.get_overlay(2, 2) == OVERLAY_NONE


def test_undo_snapshot_and_erase_cell() -> None:
    g = Grid(4, 4)
    g.set_start(0, 0)
    g.push_snapshot()

    g.set_base(1, 1, WALL)
    g.set_base(2, 2, PALETTE_START_ID)
    g.erase_cell(0, 0)
    assert g.start is None

    assert g.can_undo()
    assert g.undo() is True
    assert g.start == (0, 0)
    assert g.get_base(1, 1) == EMPTY
    assert g.get_base(2, 2) == EMPTY
    assert g.undo() is False


def test_clear_regions_keeps_walls_and_endpoints() -> None:
    g = Grid(4, 4)
    g.set_base(0, 1, WALL)
    g.set_base(1, 1, FILLED)
    g.set_base(2, 2, PALETTE_START_ID)
    g.set_start(0, 0)
    g.clear_regions()

    assert g.get_base(0, 1) == WALL
    assert g.get_base(1, 1) == EMPTY
    assert g.get_base(2, 2) == EMPTY
    assert g.start == (0, 0)


@pytest.mark.parametrize("rows,cols", [(11, 15), (12, 16), (21, 31)])
def test_maze_generator_is_deterministic_and_solvable(rows: int, cols: int) -> None:
    m1, s1, e1 = generate_maze(rows, cols, seed=123)
    m2, s2, e2 = generate_maze(rows, cols, seed=123)
    assert m1 == m2 and s1 == s2 and e1 == e2

    path, metrics = pathfind_bfs(m1, s1, e1, connectivity=4)
    assert metrics.found is True
    assert path[0] == s1 and path[-1] == e1


def test_multi_room_and_spiral_and_random_generators() -> None:
    mr, s_mr, e_mr = generate_multi_room(15, 21, seed=7)
    path_mr, metrics_mr = pathfind_bfs(mr, s_mr, e_mr, connectivity=4)
    assert metrics_mr.found is True
    assert path_mr[0] == s_mr and path_mr[-1] == e_mr

    sp, s_sp, e_sp = generate_spiral(15, 15)
    path_sp, metrics_sp = pathfind_bfs(sp, s_sp, e_sp, connectivity=4)
    assert metrics_sp.found is True
    assert path_sp[0] == s_sp and path_sp[-1] == e_sp

    rnd1, s1, e1 = generate_random_obstacles(12, 16, density=0.3, seed=99)
    rnd2, s2, e2 = generate_random_obstacles(12, 16, density=0.3, seed=99)
    assert rnd1 == rnd2
    assert rnd1[s1[0]][s1[1]] == EMPTY
    assert rnd1[e1[0]][e1[1]] == EMPTY

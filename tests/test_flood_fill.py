"""Comprehensive unit tests for all 4 Flood Fill algorithms (4-way and 8-way)."""

from __future__ import annotations

import copy
import sys

import pytest

from neo_flood_fill.algorithms import (
    Connectivity,
    FLOOD_FILL_ALGORITHMS,
    flood_fill_bfs,
    flood_fill_recursive,
)
from neo_flood_fill.grid import (
    EMPTY,
    FILLED,
    PALETTE_START_ID,
    WALL,
    Grid,
    create_grid,
    generate_multi_room,
    generate_random_obstacles,
    set_cell,
)

ALL_ALGO_KEYS = tuple(FLOOD_FILL_ALGORITHMS.keys())
ITERATIVE_ALGO_KEYS = ("iterative_dfs", "bfs", "scanline")


def make_base_grid() -> list[list[int]]:
    """5x5 test grid matching v1 Phase 1 baseline tests."""
    g = create_grid(5, 5, EMPTY)
    set_cell(g, 0, 1, WALL)
    set_cell(g, 1, 2, WALL)
    set_cell(g, 2, 2, FILLED)
    return g


@pytest.mark.parametrize("algo_key", ALL_ALGO_KEYS)
def test_basic_correctness_preserves_walls_and_prefilled(algo_key: str) -> None:
    _, fn, _ = FLOOD_FILL_ALGORITHMS[algo_key]
    red = 3
    g = make_base_grid()
    original = make_base_grid()

    metrics = fn(g, 1, 1, EMPTY, red, 4)

    for r in range(5):
        for c in range(5):
            if original[r][c] == EMPTY:
                assert g[r][c] == red
    assert g[0][1] == WALL
    assert g[1][2] == WALL
    assert g[2][2] == FILLED
    assert metrics.cells_filled == 22
    assert metrics.cells_visited == 22


@pytest.mark.parametrize("algo_key", ALL_ALGO_KEYS)
@pytest.mark.parametrize("connectivity", [4, 8])
def test_target_equals_fill_guard_prevents_infinite_loop(
    algo_key: str, connectivity: Connectivity
) -> None:
    """Regression test for v1 known bug: target_color == fill_color must be a safe no-op."""
    _, fn, steps_fn = FLOOD_FILL_ALGORITHMS[algo_key]
    g = make_base_grid()
    before = copy.deepcopy(g)

    metrics = fn(g, 1, 1, EMPTY, EMPTY, connectivity)
    assert g == before
    assert metrics.cells_filled == 0
    assert metrics.cells_visited == 0
    assert metrics.recursion_limit_hit is False

    # Step generator must also terminate cleanly in 1 event
    events = list(steps_fn(g, 1, 1, EMPTY, EMPTY, connectivity))
    assert len(events) == 1
    assert events[0].kind == "done"
    assert g == before


@pytest.mark.parametrize("algo_key", ALL_ALGO_KEYS)
def test_edge_cases_wall_oob_single_cell_and_empty_grid(algo_key: str) -> None:
    _, fn, _ = FLOOD_FILL_ALGORITHMS[algo_key]
    red = 3

    # Start on WALL -> no change
    g_wall = make_base_grid()
    orig = copy.deepcopy(g_wall)
    m_wall = fn(g_wall, 0, 1, EMPTY, red, 4)
    assert g_wall == orig and m_wall.cells_filled == 0

    # Out-of-bounds start -> no change
    m_oob = fn(g_wall, -1, 0, EMPTY, red, 4)
    assert g_wall == orig and m_oob.cells_filled == 0

    # Empty grid [] -> no crash
    m_empty = fn([], 0, 0, EMPTY, red, 4)
    assert m_empty.cells_filled == 0

    # 1x1 grid -> fills single cell
    g1 = [[EMPTY]]
    m1 = fn(g1, 0, 0, EMPTY, red, 4)
    assert g1 == [[red]] and m1.cells_filled == 1

    # Already filled with target absent -> no change
    g_full = [[red, red], [red, red]]
    m_full = fn(g_full, 0, 0, EMPTY, red, 4)
    assert g_full == [[red, red], [red, red]] and m_full.cells_filled == 0


@pytest.mark.parametrize("algo_key", ALL_ALGO_KEYS)
def test_connectivity_wall_barrier_l_corridor_and_corner(algo_key: str) -> None:
    _, fn, _ = FLOOD_FILL_ALGORITHMS[algo_key]
    red = 3

    # Vertical barrier splits 3x5 grid
    g_split = create_grid(3, 5, EMPTY)
    for r in range(3):
        set_cell(g_split, r, 2, WALL)
    fn(g_split, 0, 0, EMPTY, red, 4)
    assert all(g_split[r][c] == red for r in range(3) for c in range(2))
    assert all(g_split[r][c] == EMPTY for r in range(3) for c in range(3, 5))

    # L-shaped corridor
    g_l = [
        [EMPTY, EMPTY, EMPTY, WALL],
        [WALL, WALL, EMPTY, WALL],
        [WALL, WALL, EMPTY, EMPTY],
    ]
    fn(g_l, 0, 0, EMPTY, red, 4)
    for r, c in ((0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (2, 3)):
        assert g_l[r][c] == red
    for r, c in ((0, 3), (1, 0), (1, 1), (1, 3), (2, 0), (2, 1)):
        assert g_l[r][c] == WALL

    # Bottom-right corner start
    g_corner = create_grid(3, 3, EMPTY)
    fn(g_corner, 2, 2, EMPTY, red, 4)
    assert all(g_corner[r][c] == red for r in range(3) for c in range(3))


@pytest.mark.parametrize("algo_key", ALL_ALGO_KEYS)
def test_multicolor_region_and_auto_inferred_target(algo_key: str) -> None:
    _, fn, _ = FLOOD_FILL_ALGORITHMS[algo_key]
    blue, green, purple = 10, 11, 12

    g = [
        [EMPTY, EMPTY, WALL],
        [EMPTY, WALL, blue],
        [EMPTY, EMPTY, blue],
    ]
    # Replace only EMPTY with green
    fn(g, 0, 0, EMPTY, green, 4)
    assert g[0][0] == green and g[2][1] == green
    assert g[0][2] == WALL and g[1][1] == WALL
    assert g[1][2] == blue and g[2][2] == blue

    # Auto-infer target_color=None when repainting blue region to purple
    metrics = fn(g, 1, 2, None, purple, 4)
    assert g[1][2] == purple and g[2][2] == purple
    assert g[0][0] == green
    assert metrics.cells_filled == 2


@pytest.mark.parametrize("algo_key", ALL_ALGO_KEYS)
def test_four_way_vs_eight_way_diagonal_bridge(algo_key: str) -> None:
    """Cells touching only diagonally are disconnected in 4-way, connected in 8-way."""
    _, fn, _ = FLOOD_FILL_ALGORITHMS[algo_key]
    fill = PALETTE_START_ID

    diagonal_template = [
        [EMPTY, WALL, WALL],
        [WALL, EMPTY, WALL],
        [WALL, WALL, EMPTY],
    ]

    g4 = copy.deepcopy(diagonal_template)
    m4 = fn(g4, 0, 0, EMPTY, fill, 4)
    assert g4[0][0] == fill
    assert g4[1][1] == EMPTY
    assert g4[2][2] == EMPTY
    assert m4.cells_filled == 1

    g8 = copy.deepcopy(diagonal_template)
    m8 = fn(g8, 0, 0, EMPTY, fill, 8)
    assert g8[0][0] == fill
    assert g8[1][1] == fill
    assert g8[2][2] == fill
    assert m8.cells_filled == 3


@pytest.mark.parametrize("connectivity", [4, 8])
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_all_four_algorithms_and_generators_produce_identical_grids(
    connectivity: Connectivity, seed: int
) -> None:
    """Cross-check sync and step-generator equivalence across all 4 flood fill algorithms."""
    template, start, _ = generate_random_obstacles(15, 19, density=0.35, seed=seed)
    sr, sc = start
    fill = PALETTE_START_ID

    ref_grid = copy.deepcopy(template)
    ref_metrics = flood_fill_bfs(ref_grid, sr, sc, EMPTY, fill, connectivity)

    for algo_key, (_, sync_fn, steps_fn) in FLOOD_FILL_ALGORITHMS.items():
        # Synchronous version
        g_sync = copy.deepcopy(template)
        m_sync = sync_fn(g_sync, sr, sc, EMPTY, fill, connectivity)
        assert g_sync == ref_grid, f"{algo_key} sync diverged on seed={seed}, {connectivity}-way"
        assert m_sync.cells_filled == ref_metrics.cells_filled

        # Generator version
        g_gen = copy.deepcopy(template)
        fill_events = 0
        final_metrics = None
        for event in steps_fn(g_gen, sr, sc, EMPTY, fill, connectivity):
            if event.kind == "fill":
                fill_events += 1
            elif event.kind == "done":
                final_metrics = event.metrics
        assert g_gen == ref_grid, f"{algo_key} steps diverged on seed={seed}, {connectivity}-way"
        assert final_metrics is not None
        assert fill_events == ref_metrics.cells_filled
        assert final_metrics.cells_filled == ref_metrics.cells_filled


@pytest.mark.parametrize("algo_key", ITERATIVE_ALGO_KEYS)
def test_iterative_algorithms_handle_large_grid_without_recursion_error(
    algo_key: str,
) -> None:
    _, fn, _ = FLOOD_FILL_ALGORITHMS[algo_key]
    g = create_grid(60, 60, EMPTY)
    metrics = fn(g, 0, 0, EMPTY, PALETTE_START_ID, 4)
    assert metrics.cells_filled == 3600
    assert metrics.recursion_limit_hit is False
    assert all(g[r][c] == PALETTE_START_ID for r in range(60) for c in range(60))


def test_recursive_dfs_handles_recursion_limit_gracefully() -> None:
    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(150)
        g = create_grid(25, 25, EMPTY)
        metrics = flood_fill_recursive(g, 0, 0, EMPTY, PALETTE_START_ID, 4)
        assert metrics.recursion_limit_hit is True
        assert 0 < metrics.cells_filled < 625
    finally:
        sys.setrecursionlimit(old_limit)


def test_flood_fill_directly_on_two_layer_grid_object() -> None:
    matrix, start, end = generate_multi_room(13, 19, seed=11)
    grid = Grid(13, 19)
    grid.load_base(matrix, start=start, end=end)

    metrics = flood_fill_bfs(grid, start[0], start[1], EMPTY, PALETTE_START_ID, 4)
    assert metrics.cells_filled > 0
    assert grid.get_base(start[0], start[1]) == PALETTE_START_ID
    assert grid.start == start and grid.end == end

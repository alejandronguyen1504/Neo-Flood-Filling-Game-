"""Unit tests for BFS, DFS, and A* pathfinding (4-way and 8-way)."""

from __future__ import annotations

import math

import pytest

from neo_flood_fill.algorithms import (
    Connectivity,
    PATHFINDING_ALGORITHMS,
    SQRT2,
    pathfind_astar,
    pathfind_bfs,
    pathfind_dfs,
)
from neo_flood_fill.grid import (
    EMPTY,
    WALL,
    Grid,
    create_grid,
    generate_maze,
    generate_random_obstacles,
    generate_spiral,
    set_cell,
)

ALL_PATH_KEYS = tuple(PATHFINDING_ALGORITHMS.keys())


def _assert_valid_path(
    grid: list[list[int]],
    path: list[tuple[int, int]],
    start: tuple[int, int],
    end: tuple[int, int],
    connectivity: Connectivity,
) -> None:
    assert len(path) >= 1
    assert path[0] == start
    assert path[-1] == end
    for r, c in path:
        assert grid[r][c] != WALL
    for (r1, c1), (r2, c2) in zip(path, path[1:]):
        dr, dc = abs(r1 - r2), abs(c1 - c2)
        if connectivity == 4:
            assert dr + dc == 1
        else:
            assert max(dr, dc) == 1


@pytest.mark.parametrize("algo_key", ALL_PATH_KEYS)
@pytest.mark.parametrize("connectivity", [4, 8])
def test_pathfinding_edge_cases(algo_key: str, connectivity: Connectivity) -> None:
    _, fn, _ = PATHFINDING_ALGORITHMS[algo_key]
    g = create_grid(5, 5, EMPTY)
    set_cell(g, 0, 1, WALL)

    # Start == End
    path, m = fn(g, (2, 2), (2, 2), connectivity, WALL)
    assert m.found is True and path == [(2, 2)] and m.path_length == 1 and m.path_cost == 0.0

    # Start on wall
    path_w, m_w = fn(g, (0, 1), (4, 4), connectivity, WALL)
    assert m_w.found is False and path_w == []

    # End out of bounds
    path_oob, m_oob = fn(g, (0, 0), (9, 9), connectivity, WALL)
    assert m_oob.found is False and path_oob == []

    # Unreachable target separated by solid wall
    g_blocked = create_grid(5, 5, EMPTY)
    for r in range(5):
        set_cell(g_blocked, r, 2, WALL)
    path_no, m_no = fn(g_blocked, (0, 0), (4, 4), connectivity, WALL)
    assert m_no.found is False and path_no == []


@pytest.mark.parametrize("seed", [3, 17, 42])
def test_bfs_and_astar_agree_on_optimal_4way_shortest_path(seed: int) -> None:
    maze, start, end = generate_maze(17, 23, seed=seed)

    path_bfs, m_bfs = pathfind_bfs(maze, start, end, connectivity=4)
    path_astar, m_astar = pathfind_astar(maze, start, end, connectivity=4)
    path_dfs, m_dfs = pathfind_dfs(maze, start, end, connectivity=4)

    assert m_bfs.found and m_astar.found and m_dfs.found
    _assert_valid_path(maze, path_bfs, start, end, 4)
    _assert_valid_path(maze, path_astar, start, end, 4)
    _assert_valid_path(maze, path_dfs, start, end, 4)

    # Both BFS and A* must find identical optimal path length
    assert len(path_bfs) == len(path_astar)
    assert math.isclose(m_bfs.path_cost, m_astar.path_cost)
    # DFS path is always >= optimal length
    assert len(path_dfs) >= len(path_bfs)


def test_astar_explores_fewer_or_equal_cells_than_bfs_on_open_grid() -> None:
    g = create_grid(20, 20, EMPTY)
    start, end = (1, 1), (18, 18)

    path_bfs, m_bfs = pathfind_bfs(g, start, end, connectivity=4)
    path_astar, m_astar = pathfind_astar(g, start, end, connectivity=4)

    assert m_bfs.found and m_astar.found
    assert len(path_bfs) == len(path_astar) == 35
    assert m_astar.cells_visited < m_bfs.cells_visited


def test_astar_8way_octile_optimality() -> None:
    g = create_grid(10, 10, EMPTY)
    start, end = (0, 0), (5, 8)

    path_astar, m_astar = pathfind_astar(g, start, end, connectivity=8)
    _assert_valid_path(g, path_astar, start, end, 8)

    # Optimal 8-way cost from (0,0) to (5,8): 5 diagonal steps + 3 straight steps
    expected_cost = 5 * SQRT2 + 3.0
    assert math.isclose(m_astar.path_cost, expected_cost, rel_tol=1e-9)
    assert m_astar.path_length == 9  # 8 edges + 1


def test_dfs_demonstrates_non_optimal_path_on_open_grid() -> None:
    g = create_grid(8, 8, EMPTY)
    start, end = (0, 0), (0, 7)

    path_bfs, _ = pathfind_bfs(g, start, end, connectivity=4)
    path_dfs, m_dfs = pathfind_dfs(g, start, end, connectivity=4)

    assert m_dfs.found
    _assert_valid_path(g, path_dfs, start, end, 4)
    assert len(path_bfs) == 8
    assert len(path_dfs) > len(path_bfs)


@pytest.mark.parametrize("algo_key", ALL_PATH_KEYS)
@pytest.mark.parametrize("connectivity", [4, 8])
def test_pathfinding_sync_matches_steps_generator(
    algo_key: str, connectivity: Connectivity
) -> None:
    _, sync_fn, steps_fn = PATHFINDING_ALGORITHMS[algo_key]
    g, start, end = generate_random_obstacles(12, 14, density=0.22, seed=5)
    grid_obj = Grid(12, 14)
    grid_obj.load_base(g, start=start, end=end)

    sync_path, sync_metrics = sync_fn(grid_obj, start, end, connectivity, WALL)

    gen_path: list[tuple[int, int]] = []
    gen_metrics = None
    for ev in steps_fn(grid_obj, start, end, connectivity, WALL):
        if ev.kind == "path" and ev.row is not None and ev.col is not None:
            gen_path.append((ev.row, ev.col))
        elif ev.kind in ("done", "no_path"):
            gen_metrics = ev.metrics

    assert gen_metrics is not None
    assert gen_path == sync_path
    assert gen_metrics.found == sync_metrics.found
    assert gen_metrics.cells_visited == sync_metrics.cells_visited


def test_pathfinding_on_spiral_corridor() -> None:
    spiral, start, end = generate_spiral(15, 15)
    path_bfs, m_bfs = pathfind_bfs(spiral, start, end, connectivity=4)
    path_astar, m_astar = pathfind_astar(spiral, start, end, connectivity=4)

    assert m_bfs.found and m_astar.found
    assert len(path_bfs) == len(path_astar)
    _assert_valid_path(spiral, path_astar, start, end, 4)

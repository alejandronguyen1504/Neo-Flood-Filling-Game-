"""Scientific complexity verification tests for Flood Fill & Pathfinding benchmarks."""

from __future__ import annotations

from neo_flood_fill.benchmarks import (
    benchmark_flood_fill,
    benchmark_pathfinding,
    compute_scaling_ratios,
)


def test_flood_fill_time_complexity_scales_linearly_on_open_grids() -> None:
    """When N quadruples (20x20 -> 40x40 -> 80x80), O(N) runtime scales ~4x, well below O(N^2) ~16x."""
    results = benchmark_flood_fill(
        sizes=(20, 40, 80),
        terrains=("open",),
        algorithms=("bfs", "scanline", "iterative_dfs"),
        repeats=3,
    )

    for algo_key in ("bfs", "scanline", "iterative_dfs"):
        algo_res = [r for r in results if r.algorithm_key == algo_key]
        ratios = compute_scaling_ratios(algo_res)
        assert len(ratios) == 2
        for label, cell_ratio, time_ratio in ratios:
            assert cell_ratio == 4.0
            # Strict O(N) bound: significantly below O(N^2) = 16x
            assert time_ratio < 10.0, (
                f"{algo_key} scaled super-linearly on {label}: {time_ratio:.2f}x"
            )


def test_algorithmic_space_complexity_dfs_on_vs_bfs_sqrt_n_vs_scanline() -> None:
    """Verify real algorithmic space growth:
    - Recursive DFS call-stack depth grows as O(N) (~N on open n x n grid).
    - BFS peak queue length on an open n x n grid is O(n) = O(sqrt(N)), strictly << DFS depth.
    - Scanline peak span stack stays tiny (O(1) on fully open rectangles).
    """
    sizes = (6, 10, 15, 20)
    results = benchmark_flood_fill(
        sizes=sizes,
        terrains=("open",),
        algorithms=("recursive_dfs", "bfs", "scanline"),
        repeats=1,
    )

    rec = [r for r in results if r.algorithm_key == "recursive_dfs"]
    bfs = [r for r in results if r.algorithm_key == "bfs"]
    scan = [r for r in results if r.algorithm_key == "scanline"]

    # Monotonic growth for Recursive DFS stack depth & BFS frontier
    rec_depths = [r.peak_recursion_depth for r in rec]
    bfs_peaks = [r.peak_frontier for r in bfs]
    assert all(a < b for a, b in zip(rec_depths, rec_depths[1:]))
    assert all(a < b for a, b in zip(bfs_peaks, bfs_peaks[1:]))

    for n, r_rec, r_bfs, r_scan in zip(sizes, rec, bfs, scan):
        n_cells = n * n
        assert 0 < r_rec.peak_recursion_depth <= n_cells
        assert 0 < r_bfs.peak_frontier <= 2 * n
        # Key CS takeaway: BFS frontier O(sqrt(N)) is strictly smaller than DFS O(N)
        assert r_bfs.peak_frontier < r_rec.peak_recursion_depth
        # Scanline stores at most a handful of row seeds on an open grid
        assert r_scan.peak_frontier <= r_bfs.peak_frontier


def test_benchmark_pathfinding_across_terrains() -> None:
    results = benchmark_pathfinding(
        sizes=(15,),
        terrains=("open", "maze", "spiral"),
        algorithms=("astar", "bfs", "dfs"),
        repeats=2,
    )
    assert len(results) == 9
    assert all(r.found for r in results)

    # On open grid, A* must visit fewer cells than BFS while matching optimal length
    open_astar = next(
        r for r in results if r.terrain == "open" and r.algorithm_key == "astar"
    )
    open_bfs = next(
        r for r in results if r.terrain == "open" and r.algorithm_key == "bfs"
    )
    assert open_astar.path_length == open_bfs.path_length
    assert open_astar.cells_visited < open_bfs.cells_visited

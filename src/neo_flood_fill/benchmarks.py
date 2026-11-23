"""Scientific runtime, algorithmic space, and heap benchmarks for Flood Fill & Pathfinding.

Note on CPython memory measurement
----------------------------------
``tracemalloc`` records Python *heap* allocations (such as ``deque`` blocks and
coordinate tuples), whereas CPython 3.11+ stores interpreter call frames in a
contiguous per-thread frame stack rather than per-call heap allocations. As a
result, comparing ``tracemalloc`` alone makes Recursive DFS appear artificially
smaller than BFS.

To measure space complexity rigorously, this module reports **both**:
1. Algorithmic space metrics: ``peak_recursion_depth`` (call-stack depth, O(N)
   for Recursive DFS) and ``peak_frontier`` (queue/stack peak length — O(sqrt(N))
   on open square grids for BFS and even smaller for Scanline spans).
2. CPython heap peak (``heap_peak_kb`` via ``tracemalloc``), measured on a
   separate pass so tracing overhead never contaminates wall-clock timings.
"""

from __future__ import annotations

import copy
import statistics
import sys
import tracemalloc
from dataclasses import dataclass
from typing import Literal, Sequence

from .algorithms import (
    Connectivity,
    FLOOD_FILL_ALGORITHMS,
    PATHFINDING_ALGORITHMS,
)
from .grid import (
    Coord,
    EMPTY,
    PALETTE_START_ID,
    create_grid,
    generate_maze,
    generate_spiral,
)

Terrain = Literal["open", "maze", "spiral"]


@dataclass(frozen=True)
class FloodFillBenchmarkResult:
    """Measured runtime and space metrics for one Flood Fill benchmark case."""

    algorithm_key: str
    algorithm: str
    terrain: str
    connectivity: int
    rows: int
    cols: int
    total_cells: int
    cells_filled: int
    median_ms: float
    peak_frontier: int
    peak_recursion_depth: int
    heap_peak_kb: float
    recursion_limit_hit: bool


@dataclass(frozen=True)
class PathfindingBenchmarkResult:
    """Measured runtime and search efficiency for one Pathfinding benchmark case."""

    algorithm_key: str
    algorithm: str
    terrain: str
    connectivity: int
    rows: int
    cols: int
    found: bool
    cells_visited: int
    peak_frontier: int
    path_length: int
    path_cost: float
    median_ms: float


def build_terrain_grid(
    terrain: Terrain,
    size: int,
    seed: int = 42,
) -> tuple[list[list[int]], Coord, Coord]:
    """Construct a reproducible ``size x size`` terrain grid and ``(start, end)``."""
    if terrain == "open":
        grid = create_grid(size, size, EMPTY)
        return grid, (0, 0), (size - 1, size - 1)
    if terrain == "maze":
        # Ensure odd dimensions >= 5 for crisp recursive-backtracking corridors
        odd_size = size if size % 2 == 1 else size + 1
        return generate_maze(odd_size, odd_size, seed=seed)
    if terrain == "spiral":
        odd_size = size if size % 2 == 1 else size + 1
        return generate_spiral(odd_size, odd_size)
    raise ValueError(f"Unknown terrain '{terrain}'. Expected 'open', 'maze', or 'spiral'.")


def benchmark_flood_fill(
    sizes: Sequence[int] = (15, 25, 35, 50),
    terrains: Sequence[Terrain] = ("open",),
    algorithms: Sequence[str] = ("recursive_dfs", "iterative_dfs", "bfs", "scanline"),
    connectivity: Connectivity = 4,
    repeats: int = 3,
    recursion_limit: int | None = 100_000,
    seed: int = 42,
) -> list[FloodFillBenchmarkResult]:
    """Run controlled Flood Fill benchmarks across grid sizes, terrains, and algorithms."""
    results: list[FloodFillBenchmarkResult] = []
    old_limit = sys.getrecursionlimit()

    try:
        if recursion_limit is not None and recursion_limit > old_limit:
            sys.setrecursionlimit(recursion_limit)

        for terrain in terrains:
            for size in sizes:
                template, start, _ = build_terrain_grid(terrain, size, seed=seed)
                rows, cols = len(template), len(template[0])
                sr, sc = start

                for algo_key in algorithms:
                    if algo_key not in FLOOD_FILL_ALGORITHMS:
                        raise ValueError(f"Unknown flood fill algorithm key: {algo_key!r}")
                    display_name, fn, _ = FLOOD_FILL_ALGORITHMS[algo_key]

                    timings: list[float] = []
                    last_metrics = None
                    for _ in range(max(1, repeats)):
                        work_grid = copy.deepcopy(template)
                        last_metrics = fn(
                            work_grid,
                            sr,
                            sc,
                            EMPTY,
                            PALETTE_START_ID,
                            connectivity,
                        )
                        timings.append(last_metrics.elapsed_ms)

                    # Separate pass for heap measurement so tracemalloc doesn't skew timing
                    heap_grid = copy.deepcopy(template)
                    tracemalloc.start()
                    fn(heap_grid, sr, sc, EMPTY, PALETTE_START_ID, connectivity)
                    _, peak_bytes = tracemalloc.get_traced_memory()
                    tracemalloc.stop()

                    assert last_metrics is not None
                    results.append(
                        FloodFillBenchmarkResult(
                            algorithm_key=algo_key,
                            algorithm=display_name,
                            terrain=terrain,
                            connectivity=connectivity,
                            rows=rows,
                            cols=cols,
                            total_cells=rows * cols,
                            cells_filled=last_metrics.cells_filled,
                            median_ms=statistics.median(timings),
                            peak_frontier=last_metrics.peak_frontier,
                            peak_recursion_depth=last_metrics.peak_recursion_depth,
                            heap_peak_kb=peak_bytes / 1024.0,
                            recursion_limit_hit=last_metrics.recursion_limit_hit,
                        )
                    )
    finally:
        sys.setrecursionlimit(old_limit)

    return results


def benchmark_pathfinding(
    sizes: Sequence[int] = (15, 25, 35),
    terrains: Sequence[Terrain] = ("open", "maze", "spiral"),
    algorithms: Sequence[str] = ("astar", "bfs", "dfs"),
    connectivity: Connectivity = 4,
    repeats: int = 3,
    seed: int = 42,
) -> list[PathfindingBenchmarkResult]:
    """Run controlled Pathfinding benchmarks across sizes, terrains, and algorithms."""
    results: list[PathfindingBenchmarkResult] = []

    for terrain in terrains:
        for size in sizes:
            template, start, end = build_terrain_grid(terrain, size, seed=seed)
            rows, cols = len(template), len(template[0])

            for algo_key in algorithms:
                if algo_key not in PATHFINDING_ALGORITHMS:
                    raise ValueError(f"Unknown pathfinding algorithm key: {algo_key!r}")
                display_name, fn, _ = PATHFINDING_ALGORITHMS[algo_key]

                timings: list[float] = []
                last_metrics = None
                for _ in range(max(1, repeats)):
                    _, last_metrics = fn(template, start, end, connectivity, 1)
                    timings.append(last_metrics.elapsed_ms)

                assert last_metrics is not None
                results.append(
                    PathfindingBenchmarkResult(
                        algorithm_key=algo_key,
                        algorithm=display_name,
                        terrain=terrain,
                        connectivity=connectivity,
                        rows=rows,
                        cols=cols,
                        found=last_metrics.found,
                        cells_visited=last_metrics.cells_visited,
                        peak_frontier=last_metrics.peak_frontier,
                        path_length=last_metrics.path_length,
                        path_cost=last_metrics.path_cost,
                        median_ms=statistics.median(timings),
                    )
                )

    return results


def compute_scaling_ratios(
    results: Sequence[FloodFillBenchmarkResult],
) -> list[tuple[str, float, float]]:
    """Compute consecutive ``(label, cell_ratio, time_ratio)`` scaling pairs.

    For an O(N) algorithm, ``time_ratio`` scales approximately proportionally
    with ``cell_ratio`` (as opposed to ``cell_ratio ** 2`` for O(N^2)).
    """
    ordered = sorted(results, key=lambda r: r.total_cells)
    ratios: list[tuple[str, float, float]] = []
    for prev, curr in zip(ordered, ordered[1:]):
        label = f"{prev.rows}x{prev.cols} -> {curr.rows}x{curr.cols}"
        cell_ratio = (
            curr.cells_filled / prev.cells_filled if prev.cells_filled > 0 else 0.0
        )
        time_ratio = curr.median_ms / prev.median_ms if prev.median_ms > 0 else float("inf")
        ratios.append((label, cell_ratio, time_ratio))
    return ratios

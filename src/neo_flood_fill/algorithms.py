"""Flood Fill and Pathfinding algorithms (synchronous + step-by-step generators).

Flood Fill variants (all support 4-way and 8-way connectivity):
    - Recursive DFS (with ``target_color == fill_color`` guard and safe RecursionError handling)
    - Iterative DFS (explicit stack, no recursion limit)
    - Queue-based BFS (wavefront expansion, O(sqrt(N)) frontier on open square grids)
    - Scanline Flood Fill (horizontal span seeding, minimal frontier overhead)

Pathfinding variants (all support 4-way and 8-way connectivity):
    - Breadth-First Search (BFS — guaranteed shortest unweighted path)
    - Depth-First Search (DFS — non-optimal contrast baseline)
    - A* Search (Manhattan heuristic for 4-way; Octile heuristic with sqrt(2) diagonal cost for 8-way)
"""

from __future__ import annotations

import heapq
import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterator, Literal, Sequence

from .grid import Coord, Grid, WALL, is_valid_cell

Connectivity = Literal[4, 8]
StepKind = Literal["frontier", "visit", "fill", "path", "done", "no_path"]

SQRT2: float = math.sqrt(2.0)

DIRECTIONS_4: tuple[tuple[int, int], ...] = (
    (-1, 0),  # up
    (1, 0),   # down
    (0, -1),  # left
    (0, 1),   # right
)

DIRECTIONS_8: tuple[tuple[int, int], ...] = (
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
    (-1, -1),
    (-1, 1),
    (1, -1),
    (1, 1),
)


def get_directions(connectivity: int) -> tuple[tuple[int, int], ...]:
    """Return neighbor offset tuples for 4-way or 8-way connectivity."""
    if connectivity == 4:
        return DIRECTIONS_4
    if connectivity == 8:
        return DIRECTIONS_8
    raise ValueError(f"Unsupported connectivity {connectivity!r}. Expected 4 or 8.")


@dataclass
class AlgorithmMetrics:
    """Execution metrics captured during a flood fill or pathfinding run."""

    algorithm: str
    connectivity: int = 4
    cells_visited: int = 0
    cells_filled: int = 0
    peak_frontier: int = 0
    peak_recursion_depth: int = 0
    path_length: int = 0
    path_cost: float = 0.0
    elapsed_ms: float = 0.0
    found: bool = True
    recursion_limit_hit: bool = False


@dataclass(frozen=True)
class StepEvent:
    """Atomic animation event yielded by ``*_steps`` algorithm generators."""

    kind: StepKind
    row: int | None = None
    col: int | None = None
    color: int | None = None
    metrics: AlgorithmMetrics | None = None


def _extract_matrix(grid_or_matrix: Grid | list[list[int]]) -> list[list[int]]:
    """Return the underlying 2D mutable base matrix from a ``Grid`` or raw list."""
    if isinstance(grid_or_matrix, Grid):
        return grid_or_matrix.base
    return grid_or_matrix


def _prepare_flood_fill(
    matrix: list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
) -> tuple[bool, int]:
    """Validate flood-fill preconditions and resolve ``target_color``.

    Returns ``(should_run, resolved_target_color)``.
    Guards against out-of-bounds start, non-matching target, and the classic
    ``target_color == fill_color`` infinite-loop trap.
    """
    if not is_valid_cell(matrix, row, col):
        return False, -1
    resolved_target = matrix[row][col] if target_color is None else target_color
    if resolved_target == fill_color:
        return False, resolved_target
    if matrix[row][col] != resolved_target:
        return False, resolved_target
    return True, resolved_target


# ===========================================================================
# FLOOD FILL — 1. RECURSIVE DFS
# ===========================================================================


def flood_fill_recursive(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> AlgorithmMetrics:
    """Recursive DFS flood fill with safe ``target == fill`` and ``RecursionError`` handling."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(algorithm="Recursive DFS", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return metrics

    def _dfs(r: int, c: int, depth: int) -> None:
        if not is_valid_cell(matrix, r, c) or matrix[r][c] != resolved_target:
            return
        if depth > metrics.peak_recursion_depth:
            metrics.peak_recursion_depth = depth
        matrix[r][c] = fill_color
        metrics.cells_visited += 1
        metrics.cells_filled += 1
        for dr, dc in directions:
            _dfs(r + dr, c + dc, depth + 1)

    try:
        _dfs(row, col, 1)
    except RecursionError:
        metrics.recursion_limit_hit = True

    metrics.peak_frontier = metrics.peak_recursion_depth
    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return metrics


def flood_fill_recursive_steps(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> Iterator[StepEvent]:
    """Step-by-step generator for Recursive DFS flood fill."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(algorithm="Recursive DFS", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("done", metrics=metrics)
        return

    def _dfs_gen(r: int, c: int, depth: int) -> Iterator[StepEvent]:
        if not is_valid_cell(matrix, r, c) or matrix[r][c] != resolved_target:
            return
        if depth > metrics.peak_recursion_depth:
            metrics.peak_recursion_depth = depth
        matrix[r][c] = fill_color
        metrics.cells_visited += 1
        metrics.cells_filled += 1
        yield StepEvent("fill", r, c, color=fill_color)
        for dr, dc in directions:
            yield from _dfs_gen(r + dr, c + dc, depth + 1)

    try:
        yield from _dfs_gen(row, col, 1)
    except RecursionError:
        metrics.recursion_limit_hit = True

    metrics.peak_frontier = metrics.peak_recursion_depth
    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    yield StepEvent("done", metrics=metrics)


# ===========================================================================
# FLOOD FILL — 2. ITERATIVE DFS
# ===========================================================================


def flood_fill_iterative_dfs(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> AlgorithmMetrics:
    """Iterative stack-based DFS flood fill (immune to Python recursion limits)."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(algorithm="Iterative DFS", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return metrics

    stack: list[Coord] = [(row, col)]
    metrics.peak_frontier = 1

    while stack:
        r, c = stack.pop()
        if matrix[r][c] != resolved_target:
            continue
        matrix[r][c] = fill_color
        metrics.cells_visited += 1
        metrics.cells_filled += 1

        # Push in reverse order so popped order matches DIRECTIONS ordering
        for dr, dc in reversed(directions):
            nr, nc = r + dr, c + dc
            if is_valid_cell(matrix, nr, nc) and matrix[nr][nc] == resolved_target:
                stack.append((nr, nc))
        if len(stack) > metrics.peak_frontier:
            metrics.peak_frontier = len(stack)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return metrics


def flood_fill_iterative_dfs_steps(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> Iterator[StepEvent]:
    """Step-by-step generator for Iterative DFS flood fill."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(algorithm="Iterative DFS", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("done", metrics=metrics)
        return

    stack: list[Coord] = [(row, col)]
    metrics.peak_frontier = 1

    while stack:
        r, c = stack.pop()
        if matrix[r][c] != resolved_target:
            continue
        matrix[r][c] = fill_color
        metrics.cells_visited += 1
        metrics.cells_filled += 1
        yield StepEvent("fill", r, c, color=fill_color)

        for dr, dc in reversed(directions):
            nr, nc = r + dr, c + dc
            if is_valid_cell(matrix, nr, nc) and matrix[nr][nc] == resolved_target:
                stack.append((nr, nc))
        if len(stack) > metrics.peak_frontier:
            metrics.peak_frontier = len(stack)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    yield StepEvent("done", metrics=metrics)


# ===========================================================================
# FLOOD FILL — 3. QUEUE-BASED BFS
# ===========================================================================


def flood_fill_bfs(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> AlgorithmMetrics:
    """Queue-based BFS flood fill expanding layer by layer."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(algorithm="Queue BFS", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return metrics

    queue: deque[Coord] = deque([(row, col)])
    matrix[row][col] = fill_color
    metrics.cells_visited = 1
    metrics.cells_filled = 1
    metrics.peak_frontier = 1

    while queue:
        r, c = queue.popleft()
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if is_valid_cell(matrix, nr, nc) and matrix[nr][nc] == resolved_target:
                matrix[nr][nc] = fill_color
                queue.append((nr, nc))
                metrics.cells_visited += 1
                metrics.cells_filled += 1
                if len(queue) > metrics.peak_frontier:
                    metrics.peak_frontier = len(queue)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return metrics


def flood_fill_bfs_steps(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> Iterator[StepEvent]:
    """Step-by-step generator for Queue-based BFS flood fill."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(algorithm="Queue BFS", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("done", metrics=metrics)
        return

    queue: deque[Coord] = deque([(row, col)])
    matrix[row][col] = fill_color
    metrics.cells_visited = 1
    metrics.cells_filled = 1
    metrics.peak_frontier = 1
    yield StepEvent("fill", row, col, color=fill_color)

    while queue:
        r, c = queue.popleft()
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if is_valid_cell(matrix, nr, nc) and matrix[nr][nc] == resolved_target:
                matrix[nr][nc] = fill_color
                queue.append((nr, nc))
                metrics.cells_visited += 1
                metrics.cells_filled += 1
                if len(queue) > metrics.peak_frontier:
                    metrics.peak_frontier = len(queue)
                yield StepEvent("fill", nr, nc, color=fill_color)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    yield StepEvent("done", metrics=metrics)


# ===========================================================================
# FLOOD FILL — 4. SCANLINE FLOOD FILL
# ===========================================================================


def _enqueue_adjacent_spans(
    matrix: list[list[int]],
    adj_row: int,
    scan_left: int,
    scan_right: int,
    target_color: int,
    stack: list[Coord],
) -> None:
    """Push one seed coordinate per contiguous target-colored run on ``adj_row``."""
    in_span = False
    row_data = matrix[adj_row]
    for col in range(scan_left, scan_right + 1):
        if row_data[col] == target_color:
            if not in_span:
                stack.append((adj_row, col))
                in_span = True
        else:
            in_span = False


def flood_fill_scanline(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> AlgorithmMetrics:
    """Scanline (span) flood fill supporting both 4-way and 8-way connectivity.

    Fills maximal horizontal runs in one sweep and seeds only one coordinate
    per adjacent contiguous run, drastically reducing frontier size.
    """
    matrix = _extract_matrix(grid)
    get_directions(connectivity)  # validate connectivity
    metrics = AlgorithmMetrics(algorithm="Scanline", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return metrics

    rows = len(matrix)
    cols = len(matrix[0])
    diag_pad = 1 if connectivity == 8 else 0

    stack: list[Coord] = [(row, col)]
    metrics.peak_frontier = 1

    while stack:
        r, c = stack.pop()
        row_data = matrix[r]
        if row_data[c] != resolved_target:
            continue

        left = c
        while left > 0 and row_data[left - 1] == resolved_target:
            left -= 1

        right = c
        while right + 1 < cols and row_data[right + 1] == resolved_target:
            right += 1

        for x in range(left, right + 1):
            row_data[x] = fill_color
        span_len = right - left + 1
        metrics.cells_visited += span_len
        metrics.cells_filled += span_len

        scan_left = max(0, left - diag_pad)
        scan_right = min(cols - 1, right + diag_pad)

        if r > 0:
            _enqueue_adjacent_spans(
                matrix, r - 1, scan_left, scan_right, resolved_target, stack
            )
        if r + 1 < rows:
            _enqueue_adjacent_spans(
                matrix, r + 1, scan_left, scan_right, resolved_target, stack
            )

        if len(stack) > metrics.peak_frontier:
            metrics.peak_frontier = len(stack)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return metrics


def flood_fill_scanline_steps(
    grid: Grid | list[list[int]],
    row: int,
    col: int,
    target_color: int | None,
    fill_color: int,
    connectivity: Connectivity = 4,
) -> Iterator[StepEvent]:
    """Step-by-step generator for Scanline flood fill."""
    matrix = _extract_matrix(grid)
    get_directions(connectivity)
    metrics = AlgorithmMetrics(algorithm="Scanline", connectivity=connectivity)

    t0 = time.perf_counter()
    should_run, resolved_target = _prepare_flood_fill(
        matrix, row, col, target_color, fill_color
    )
    if not should_run:
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("done", metrics=metrics)
        return

    rows = len(matrix)
    cols = len(matrix[0])
    diag_pad = 1 if connectivity == 8 else 0

    stack: list[Coord] = [(row, col)]
    metrics.peak_frontier = 1

    while stack:
        r, c = stack.pop()
        row_data = matrix[r]
        if row_data[c] != resolved_target:
            continue

        left = c
        while left > 0 and row_data[left - 1] == resolved_target:
            left -= 1

        right = c
        while right + 1 < cols and row_data[right + 1] == resolved_target:
            right += 1

        for x in range(left, right + 1):
            row_data[x] = fill_color
            metrics.cells_visited += 1
            metrics.cells_filled += 1
            yield StepEvent("fill", r, x, color=fill_color)

        scan_left = max(0, left - diag_pad)
        scan_right = min(cols - 1, right + diag_pad)

        if r > 0:
            _enqueue_adjacent_spans(
                matrix, r - 1, scan_left, scan_right, resolved_target, stack
            )
        if r + 1 < rows:
            _enqueue_adjacent_spans(
                matrix, r + 1, scan_left, scan_right, resolved_target, stack
            )

        if len(stack) > metrics.peak_frontier:
            metrics.peak_frontier = len(stack)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    yield StepEvent("done", metrics=metrics)


# ===========================================================================
# PATHFINDING HELPERS
# ===========================================================================


def _reconstruct_path(
    parent: dict[Coord, Coord | None],
    end: Coord,
) -> list[Coord]:
    """Reconstruct path from start to ``end`` using ``parent`` pointers."""
    path: list[Coord] = []
    cur: Coord | None = end
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def _compute_path_cost(path: Sequence[Coord]) -> float:
    """Compute geometric path cost (1.0 orthogonal, sqrt(2) diagonal)."""
    if len(path) <= 1:
        return 0.0
    total = 0.0
    for (r1, c1), (r2, c2) in zip(path, path[1:]):
        total += SQRT2 if (r1 != r2 and c1 != c2) else 1.0
    return total


def _heuristic(a: Coord, b: Coord, connectivity: Connectivity) -> float:
    """Admissible heuristic: Manhattan for 4-way, Octile for 8-way."""
    dr = abs(a[0] - b[0])
    dc = abs(a[1] - b[1])
    if connectivity == 4:
        return float(dr + dc)
    return float(dr + dc) + (SQRT2 - 2.0) * float(min(dr, dc))


def _validate_pathfinding(
    matrix: list[list[int]],
    start: Coord,
    end: Coord,
    wall_value: int,
) -> bool:
    """Return True if ``start`` and ``end`` are in bounds and passable."""
    if not is_valid_cell(matrix, start[0], start[1]):
        return False
    if not is_valid_cell(matrix, end[0], end[1]):
        return False
    if matrix[start[0]][start[1]] == wall_value:
        return False
    if matrix[end[0]][end[1]] == wall_value:
        return False
    return True


# ===========================================================================
# PATHFINDING — 1. BFS (SHORTEST UNWEIGHTED PATH)
# ===========================================================================


def pathfind_bfs_steps(
    grid: Grid | list[list[int]],
    start: Coord,
    end: Coord,
    connectivity: Connectivity = 4,
    wall_value: int = WALL,
) -> Iterator[StepEvent]:
    """Step-by-step generator for BFS shortest-path search."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(
        algorithm="BFS", connectivity=connectivity, found=False
    )
    t0 = time.perf_counter()

    if not _validate_pathfinding(matrix, start, end, wall_value):
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("no_path", metrics=metrics)
        return

    if start == end:
        metrics.found = True
        metrics.cells_visited = 1
        metrics.peak_frontier = 1
        metrics.path_length = 1
        metrics.path_cost = 0.0
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("path", start[0], start[1])
        yield StepEvent("done", metrics=metrics)
        return

    queue: deque[Coord] = deque([start])
    visited: set[Coord] = {start}
    parent: dict[Coord, Coord | None] = {start: None}
    metrics.peak_frontier = 1

    while queue:
        cur = queue.popleft()
        metrics.cells_visited += 1
        if cur != start and cur != end:
            yield StepEvent("visit", cur[0], cur[1])

        if cur == end:
            path = _reconstruct_path(parent, end)
            metrics.found = True
            metrics.path_length = len(path)
            metrics.path_cost = _compute_path_cost(path)
            metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
            for pr, pc in path:
                yield StepEvent("path", pr, pc)
            yield StepEvent("done", metrics=metrics)
            return

        r, c = cur
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            nxt = (nr, nc)
            if (
                is_valid_cell(matrix, nr, nc)
                and matrix[nr][nc] != wall_value
                and nxt not in visited
            ):
                visited.add(nxt)
                parent[nxt] = cur
                queue.append(nxt)
                if len(queue) > metrics.peak_frontier:
                    metrics.peak_frontier = len(queue)
                if nxt != end:
                    yield StepEvent("frontier", nr, nc)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    yield StepEvent("no_path", metrics=metrics)


def pathfind_bfs(
    grid: Grid | list[list[int]],
    start: Coord,
    end: Coord,
    connectivity: Connectivity = 4,
    wall_value: int = WALL,
) -> tuple[list[Coord], AlgorithmMetrics]:
    """Run BFS pathfinding synchronously and return ``(path, metrics)``."""
    path: list[Coord] = []
    final_metrics = AlgorithmMetrics(
        algorithm="BFS", connectivity=connectivity, found=False
    )
    for event in pathfind_bfs_steps(grid, start, end, connectivity, wall_value):
        if event.kind == "path" and event.row is not None and event.col is not None:
            path.append((event.row, event.col))
        elif event.kind in ("done", "no_path") and event.metrics is not None:
            final_metrics = event.metrics
    return path, final_metrics


# ===========================================================================
# PATHFINDING — 2. ITERATIVE DFS (NON-OPTIMAL CONTRAST BASELINE)
# ===========================================================================


def pathfind_dfs_steps(
    grid: Grid | list[list[int]],
    start: Coord,
    end: Coord,
    connectivity: Connectivity = 4,
    wall_value: int = WALL,
) -> Iterator[StepEvent]:
    """Step-by-step generator for iterative DFS pathfinding (does not guarantee shortest path)."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(
        algorithm="DFS", connectivity=connectivity, found=False
    )
    t0 = time.perf_counter()

    if not _validate_pathfinding(matrix, start, end, wall_value):
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("no_path", metrics=metrics)
        return

    if start == end:
        metrics.found = True
        metrics.cells_visited = 1
        metrics.peak_frontier = 1
        metrics.path_length = 1
        metrics.path_cost = 0.0
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("path", start[0], start[1])
        yield StepEvent("done", metrics=metrics)
        return

    stack: list[Coord] = [start]
    visited: set[Coord] = set()
    parent: dict[Coord, Coord | None] = {start: None}
    metrics.peak_frontier = 1

    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        metrics.cells_visited += 1
        if cur != start and cur != end:
            yield StepEvent("visit", cur[0], cur[1])

        if cur == end:
            path = _reconstruct_path(parent, end)
            metrics.found = True
            metrics.path_length = len(path)
            metrics.path_cost = _compute_path_cost(path)
            metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
            for pr, pc in path:
                yield StepEvent("path", pr, pc)
            yield StepEvent("done", metrics=metrics)
            return

        r, c = cur
        for dr, dc in reversed(directions):
            nr, nc = r + dr, c + dc
            nxt = (nr, nc)
            if (
                is_valid_cell(matrix, nr, nc)
                and matrix[nr][nc] != wall_value
                and nxt not in visited
            ):
                parent[nxt] = cur
                stack.append(nxt)
                if len(stack) > metrics.peak_frontier:
                    metrics.peak_frontier = len(stack)
                if nxt != end:
                    yield StepEvent("frontier", nr, nc)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    yield StepEvent("no_path", metrics=metrics)


def pathfind_dfs(
    grid: Grid | list[list[int]],
    start: Coord,
    end: Coord,
    connectivity: Connectivity = 4,
    wall_value: int = WALL,
) -> tuple[list[Coord], AlgorithmMetrics]:
    """Run iterative DFS pathfinding synchronously and return ``(path, metrics)``."""
    path: list[Coord] = []
    final_metrics = AlgorithmMetrics(
        algorithm="DFS", connectivity=connectivity, found=False
    )
    for event in pathfind_dfs_steps(grid, start, end, connectivity, wall_value):
        if event.kind == "path" and event.row is not None and event.col is not None:
            path.append((event.row, event.col))
        elif event.kind in ("done", "no_path") and event.metrics is not None:
            final_metrics = event.metrics
    return path, final_metrics


# ===========================================================================
# PATHFINDING — 3. A* SEARCH (MANHATTAN 4-WAY / OCTILE 8-WAY)
# ===========================================================================


def pathfind_astar_steps(
    grid: Grid | list[list[int]],
    start: Coord,
    end: Coord,
    connectivity: Connectivity = 4,
    wall_value: int = WALL,
) -> Iterator[StepEvent]:
    """Step-by-step generator for A* shortest-path search."""
    matrix = _extract_matrix(grid)
    directions = get_directions(connectivity)
    metrics = AlgorithmMetrics(
        algorithm="A*", connectivity=connectivity, found=False
    )
    t0 = time.perf_counter()

    if not _validate_pathfinding(matrix, start, end, wall_value):
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("no_path", metrics=metrics)
        return

    if start == end:
        metrics.found = True
        metrics.cells_visited = 1
        metrics.peak_frontier = 1
        metrics.path_length = 1
        metrics.path_cost = 0.0
        metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        yield StepEvent("path", start[0], start[1])
        yield StepEvent("done", metrics=metrics)
        return

    counter = 0
    open_heap: list[tuple[float, float, int, Coord]] = [
        (_heuristic(start, end, connectivity), 0.0, counter, start)
    ]
    g_score: dict[Coord, float] = {start: 0.0}
    parent: dict[Coord, Coord | None] = {start: None}
    closed: set[Coord] = set()
    metrics.peak_frontier = 1

    while open_heap:
        _, _, _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        closed.add(cur)
        metrics.cells_visited += 1
        if cur != start and cur != end:
            yield StepEvent("visit", cur[0], cur[1])

        if cur == end:
            path = _reconstruct_path(parent, end)
            metrics.found = True
            metrics.path_length = len(path)
            metrics.path_cost = g_score[end]
            metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
            for pr, pc in path:
                yield StepEvent("path", pr, pc)
            yield StepEvent("done", metrics=metrics)
            return

        r, c = cur
        cur_g = g_score[cur]
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            nxt = (nr, nc)
            if (
                not is_valid_cell(matrix, nr, nc)
                or matrix[nr][nc] == wall_value
                or nxt in closed
            ):
                continue

            step_cost = SQRT2 if (dr != 0 and dc != 0) else 1.0
            tentative_g = cur_g + step_cost
            if tentative_g < g_score.get(nxt, math.inf):
                g_score[nxt] = tentative_g
                parent[nxt] = cur
                h = _heuristic(nxt, end, connectivity)
                counter += 1
                # Tie-break on smaller h so A* expands straight toward the goal
                heapq.heappush(open_heap, (tentative_g + h, h, counter, nxt))
                if len(open_heap) > metrics.peak_frontier:
                    metrics.peak_frontier = len(open_heap)
                if nxt != end:
                    yield StepEvent("frontier", nr, nc)

    metrics.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    yield StepEvent("no_path", metrics=metrics)


def pathfind_astar(
    grid: Grid | list[list[int]],
    start: Coord,
    end: Coord,
    connectivity: Connectivity = 4,
    wall_value: int = WALL,
) -> tuple[list[Coord], AlgorithmMetrics]:
    """Run A* pathfinding synchronously and return ``(path, metrics)``."""
    path: list[Coord] = []
    final_metrics = AlgorithmMetrics(
        algorithm="A*", connectivity=connectivity, found=False
    )
    for event in pathfind_astar_steps(grid, start, end, connectivity, wall_value):
        if event.kind == "path" and event.row is not None and event.col is not None:
            path.append((event.row, event.col))
        elif event.kind in ("done", "no_path") and event.metrics is not None:
            final_metrics = event.metrics
    return path, final_metrics


# ===========================================================================
# UNIFIED REGISTRIES
# ===========================================================================

FloodFillFn = Callable[
    [Grid | list[list[int]], int, int, int | None, int, Connectivity],
    AlgorithmMetrics,
]
FloodFillStepsFn = Callable[
    [Grid | list[list[int]], int, int, int | None, int, Connectivity],
    Iterator[StepEvent],
]
PathfindFn = Callable[
    [Grid | list[list[int]], Coord, Coord, Connectivity, int],
    tuple[list[Coord], AlgorithmMetrics],
]
PathfindStepsFn = Callable[
    [Grid | list[list[int]], Coord, Coord, Connectivity, int],
    Iterator[StepEvent],
]

FLOOD_FILL_ALGORITHMS: dict[str, tuple[str, FloodFillFn, FloodFillStepsFn]] = {
    "bfs": ("Queue BFS", flood_fill_bfs, flood_fill_bfs_steps),
    "scanline": ("Scanline", flood_fill_scanline, flood_fill_scanline_steps),
    "iterative_dfs": ("Iterative DFS", flood_fill_iterative_dfs, flood_fill_iterative_dfs_steps),
    "recursive_dfs": ("Recursive DFS", flood_fill_recursive, flood_fill_recursive_steps),
}

PATHFINDING_ALGORITHMS: dict[str, tuple[str, PathfindFn, PathfindStepsFn]] = {
    "astar": ("A* Search", pathfind_astar, pathfind_astar_steps),
    "bfs": ("BFS", pathfind_bfs, pathfind_bfs_steps),
    "dfs": ("DFS", pathfind_dfs, pathfind_dfs_steps),
}

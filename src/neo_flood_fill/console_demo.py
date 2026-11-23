"""Console step-by-step simulation for Flood Fill and Shortest Path algorithms."""

from __future__ import annotations

import argparse
import time

from .algorithms import (
    AlgorithmMetrics,
    Connectivity,
    FLOOD_FILL_ALGORITHMS,
    PATHFINDING_ALGORITHMS,
)
from .grid import (
    Coord,
    EMPTY,
    PALETTE_START_ID,
    WALL,
    create_grid,
    format_grid,
    get_cell,
    set_cell,
)

CONSOLE_SYMBOLS: dict[int, str] = {
    EMPTY: ".",
    WALL: "#",
    PALETTE_START_ID: "~",
    98: "v",  # visited
    99: "*",  # path
    96: "S",  # start
    97: "E",  # end
}


def prompt_index(label: str, max_value: int) -> int:
    """Prompt the user for a 1-based row/column index and return its 0-based value."""
    while True:
        raw = input(f"Enter {label} (1..{max_value}): ").strip()
        if not raw:
            print(f"{label.capitalize()} cannot be empty.")
        elif not raw.isdigit():
            print(f"Invalid number for {label}.")
        elif not (1 <= int(raw) <= max_value):
            print(f"{label.capitalize()} must be between 1 and {max_value}.")
        else:
            return int(raw) - 1


def prompt_valid_cell(
    grid: list[list[int]],
    role: str,
    disallowed: Coord | None = None,
) -> Coord:
    """Interactively prompt for a non-wall coordinate inside ``grid``."""
    rows, cols = len(grid), len(grid[0])
    print(format_grid(grid, CONSOLE_SYMBOLS))
    print(f"Legend: . = Empty, # = Wall | Grid: {rows}x{cols}")

    while True:
        print(f"--- Select {role.upper()} point ---")
        r = prompt_index("row", rows)
        c = prompt_index("column", cols)
        if get_cell(grid, r, c) == WALL:
            print("Cannot select a WALL cell. Please choose another cell.")
        elif disallowed is not None and (r, c) == disallowed:
            print("End cell cannot be the same as Start cell.")
        else:
            return r, c


def build_sample_console_grid() -> list[list[int]]:
    """Build a classic 6x7 demonstration grid with walls."""
    grid = create_grid(6, 7, EMPTY)
    for r, c in ((0, 1), (1, 1), (1, 2), (2, 4), (3, 4), (4, 2)):
        set_cell(grid, r, c, WALL)
    return grid


def run_console_flood_fill(
    grid: list[list[int]],
    start: Coord,
    algorithm: str = "bfs",
    connectivity: Connectivity = 4,
    delay: float = 0.05,
    max_frames: int | None = None,
) -> AlgorithmMetrics:
    """Animate Flood Fill step-by-step in the console."""
    if algorithm not in FLOOD_FILL_ALGORITHMS:
        raise ValueError(
            f"Unknown flood fill algorithm '{algorithm}'. Choose from {list(FLOOD_FILL_ALGORITHMS)}."
        )

    display_name, _, steps_fn = FLOOD_FILL_ALGORITHMS[algorithm]
    sr, sc = start
    print(f"\n=== Console Flood Fill: {display_name} ({connectivity}-way) ===")
    print(f"Start: {start}\n")

    frames = 0
    final_metrics = AlgorithmMetrics(algorithm=display_name, connectivity=connectivity)
    for event in steps_fn(grid, sr, sc, None, PALETTE_START_ID, connectivity):
        if event.kind == "fill":
            frames += 1
            if max_frames is None or frames <= max_frames:
                print(f"Step {frames}: filled ({event.row}, {event.col})")
                print(format_grid(grid, CONSOLE_SYMBOLS))
                print()
                if delay > 0:
                    time.sleep(delay)
        elif event.kind == "done" and event.metrics is not None:
            final_metrics = event.metrics

    print(
        f"Done! Filled {final_metrics.cells_filled} cells | "
        f"Peak frontier: {final_metrics.peak_frontier} | "
        f"Time: {final_metrics.elapsed_ms:.3f} ms"
    )
    return final_metrics


def run_console_pathfinding(
    grid: list[list[int]],
    start: Coord,
    end: Coord,
    algorithm: str = "bfs",
    connectivity: Connectivity = 4,
    delay: float = 0.05,
    max_frames: int | None = None,
) -> AlgorithmMetrics:
    """Animate Pathfinding exploration and shortest-path trace in the console."""
    if algorithm not in PATHFINDING_ALGORITHMS:
        raise ValueError(
            f"Unknown pathfinding algorithm '{algorithm}'. Choose from {list(PATHFINDING_ALGORITHMS)}."
        )

    display_name, _, steps_fn = PATHFINDING_ALGORITHMS[algorithm]
    canvas = [row[:] for row in grid]
    canvas[start[0]][start[1]] = 96
    canvas[end[0]][end[1]] = 97

    print(f"\n=== Console Pathfinding: {display_name} ({connectivity}-way) ===")
    print(f"Start: {start} -> End: {end}\n")

    frames = 0
    final_metrics = AlgorithmMetrics(
        algorithm=display_name, connectivity=connectivity, found=False
    )
    for event in steps_fn(grid, start, end, connectivity, WALL):
        if event.kind == "visit" and event.row is not None and event.col is not None:
            canvas[event.row][event.col] = 98
            frames += 1
            if max_frames is None or frames <= max_frames:
                print(f"Explore step {frames}: ({event.row}, {event.col})")
                print(format_grid(canvas, CONSOLE_SYMBOLS))
                print()
                if delay > 0:
                    time.sleep(delay)
        elif event.kind == "path" and event.row is not None and event.col is not None:
            if (event.row, event.col) not in (start, end):
                canvas[event.row][event.col] = 99
        elif event.kind in ("done", "no_path") and event.metrics is not None:
            final_metrics = event.metrics

    print("Final grid:")
    print(format_grid(canvas, CONSOLE_SYMBOLS))
    if final_metrics.found:
        print(
            f"\nPath found! Length: {final_metrics.path_length} cells | "
            f"Cost: {final_metrics.path_cost:.2f} | "
            f"Visited: {final_metrics.cells_visited} | "
            f"Time: {final_metrics.elapsed_ms:.3f} ms"
        )
    else:
        print("\nNo path found!")
    return final_metrics


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for console-based Flood Fill & Pathfinding demonstrations."""
    parser = argparse.ArgumentParser(
        description="Console step-by-step demo for Neo Flood Fill algorithms."
    )
    parser.add_argument(
        "--mode",
        choices=("fill", "path"),
        default="path",
        help="Run Flood Fill ('fill') or Pathfinding ('path') demo.",
    )
    parser.add_argument(
        "--algo",
        default="bfs",
        help="Algorithm key: bfs, scanline, iterative_dfs, recursive_dfs (fill) or astar, bfs, dfs (path).",
    )
    parser.add_argument(
        "--connectivity",
        type=int,
        choices=(4, 8),
        default=4,
        help="Neighbor connectivity: 4 or 8.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        help="Delay in seconds between printed animation frames (0 for instant).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for custom 1-based start/end coordinates in the terminal.",
    )
    args = parser.parse_args(argv)

    grid = build_sample_console_grid()
    if args.interactive:
        start = prompt_valid_cell(grid, "start")
        end = (
            prompt_valid_cell(grid, "end", disallowed=start)
            if args.mode == "path"
            else (0, 0)
        )
    else:
        start = (0, 0)
        end = (5, 6)

    connectivity: Connectivity = 8 if args.connectivity == 8 else 4
    if args.mode == "fill":
        run_console_flood_fill(grid, start, args.algo, connectivity, delay=args.delay)
    else:
        run_console_pathfinding(
            grid, start, end, args.algo, connectivity, delay=args.delay
        )


if __name__ == "__main__":
    main()

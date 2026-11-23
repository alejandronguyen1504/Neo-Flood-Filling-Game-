"""Two-layer grid data model, palette definitions, and map/maze generators."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Sequence

# Base layer cell constants
EMPTY: int = 0
WALL: int = 1
FILLED: int = 2  # Preserved for backward compatibility with v1 code/tests
PALETTE_START_ID: int = 10

# Overlay layer constants (transient search & pathfinding markers)
OVERLAY_NONE: int = 0
OVERLAY_START: int = 1
OVERLAY_END: int = 2
OVERLAY_FRONTIER: int = 3
OVERLAY_VISITED: int = 4
OVERLAY_PATH: int = 5

# Standard studio grid presets (odd sizes for Medium/Large support clean mazes)
GRID_PRESETS: dict[str, tuple[int, int]] = {
    "small": (12, 16),
    "medium": (21, 31),
    "large": (31, 47),
}

RGBColor = tuple[int, int, int]
Coord = tuple[int, int]


@dataclass(frozen=True)
class PaletteEntry:
    """Single selectable region color for Paint Bucket flood fill."""

    color_id: int
    name: str
    rgb: RGBColor


PALETTE_ENTRIES: tuple[PaletteEntry, ...] = (
    PaletteEntry(10, "Mint", (32, 201, 151)),
    PaletteEntry(11, "Cyan", (6, 182, 212)),
    PaletteEntry(12, "Blue", (59, 130, 246)),
    PaletteEntry(13, "Indigo", (99, 102, 241)),
    PaletteEntry(14, "Purple", (168, 85, 247)),
    PaletteEntry(15, "Pink", (236, 72, 153)),
    PaletteEntry(16, "Coral", (244, 63, 94)),
    PaletteEntry(17, "Orange", (249, 115, 22)),
    PaletteEntry(18, "Amber", (245, 158, 11)),
    PaletteEntry(19, "Lime", (132, 204, 22)),
    PaletteEntry(20, "Teal", (20, 184, 166)),
    PaletteEntry(21, "Slate", (148, 163, 184)),
)

PALETTE_BY_ID: dict[int, PaletteEntry] = {
    entry.color_id: entry for entry in PALETTE_ENTRIES
}


# ---------------------------------------------------------------------------
# Pure 2D list helpers (used by algorithms, tests, and educational notebook)
# ---------------------------------------------------------------------------


def create_grid(rows: int, cols: int, default_value: int = EMPTY) -> list[list[int]]:
    """Create a 2D integer grid of size ``rows x cols`` initialized to ``default_value``."""
    if rows < 0 or cols < 0:
        raise ValueError("Grid dimensions must be non-negative.")
    return [[default_value for _ in range(cols)] for _ in range(rows)]


def get_grid_size(grid: Sequence[Sequence[int]]) -> tuple[int, int]:
    """Return ``(rows, cols)`` dimensions of a 2D grid, or ``(0, 0)`` if empty."""
    if not grid:
        return 0, 0
    return len(grid), len(grid[0])


def is_valid_cell(grid: Sequence[Sequence[int]], row: int, col: int) -> bool:
    """Return True if ``(row, col)`` lies within the bounds of ``grid``."""
    if not grid or not grid[0]:
        return False
    return 0 <= row < len(grid) and 0 <= col < len(grid[0])


def get_cell(grid: Sequence[Sequence[int]], row: int, col: int) -> int | None:
    """Safely read ``grid[row][col]`` or return ``None`` if out of bounds."""
    if is_valid_cell(grid, row, col):
        return grid[row][col]
    return None


def set_cell(grid: list[list[int]], row: int, col: int, value: int) -> bool:
    """Safely write ``value`` to ``grid[row][col]``; return True if updated."""
    if is_valid_cell(grid, row, col):
        grid[row][col] = value
        return True
    return False


def format_grid(
    grid: Sequence[Sequence[int]],
    symbol_map: dict[int, str] | None = None,
) -> str:
    """Render a 2D grid as a readable multiline string."""
    lines: list[str] = []
    for row in grid:
        if symbol_map is None:
            lines.append(" ".join(str(cell) for cell in row))
        else:
            lines.append(" ".join(symbol_map.get(cell, str(cell)) for cell in row))
    return "\n".join(lines)


def print_grid(
    grid: Sequence[Sequence[int]],
    symbol_map: dict[int, str] | None = None,
) -> None:
    """Print a 2D grid to stdout."""
    print(format_grid(grid, symbol_map=symbol_map))


# ---------------------------------------------------------------------------
# Two-layer Grid model
# ---------------------------------------------------------------------------


class Grid:
    """Two-layer grid separating permanent terrain/region colors from search overlays.

    Layers
    ------
    base:
        Stores ``EMPTY``, ``WALL``, ``FILLED``, or multi-color palette IDs
        (``PALETTE_START_ID`` and above) so multiple enclosed regions can hold
        independent colors simultaneously.
    overlay:
        Stores transient pathfinding visualization states (``OVERLAY_START``,
        ``OVERLAY_END``, ``OVERLAY_FRONTIER``, ``OVERLAY_VISITED``,
        ``OVERLAY_PATH``). Clearing search overlays never destroys painted
        regions or walls in ``base``.
    """

    def __init__(self, rows: int, cols: int, max_undo: int = 50) -> None:
        if rows <= 0 or cols <= 0:
            raise ValueError("Grid rows and cols must be positive integers.")
        self.rows: int = rows
        self.cols: int = cols
        self.max_undo: int = max_undo
        self.base: list[list[int]] = create_grid(rows, cols, EMPTY)
        self.overlay: list[list[int]] = create_grid(rows, cols, OVERLAY_NONE)
        self.start: Coord | None = None
        self.end: Coord | None = None
        self._undo_stack: list[tuple[list[list[int]], Coord | None, Coord | None]] = []

    @classmethod
    def from_preset(cls, preset_name: str) -> Grid:
        """Create a new ``Grid`` sized according to ``GRID_PRESETS``."""
        key = preset_name.lower()
        if key not in GRID_PRESETS:
            raise ValueError(
                f"Unknown grid preset '{preset_name}'. Choose from {list(GRID_PRESETS)}."
            )
        rows, cols = GRID_PRESETS[key]
        return cls(rows, cols)

    def is_valid(self, row: int, col: int) -> bool:
        """Return True if ``(row, col)`` is inside grid bounds."""
        return 0 <= row < self.rows and 0 <= col < self.cols

    def get_base(self, row: int, col: int) -> int | None:
        """Read a cell from the base layer, or None if out of bounds."""
        if self.is_valid(row, col):
            return self.base[row][col]
        return None

    def set_base(self, row: int, col: int, value: int) -> bool:
        """Write ``value`` to the base layer.

        Placing a ``WALL`` on top of ``start`` or ``end`` clears that endpoint
        to guarantee start/end never reside on impassable walls.
        """
        if not self.is_valid(row, col):
            return False
        self.base[row][col] = value
        if value == WALL:
            if self.start == (row, col):
                self.start = None
                self.overlay[row][col] = OVERLAY_NONE
            if self.end == (row, col):
                self.end = None
                self.overlay[row][col] = OVERLAY_NONE
        return True

    def get_overlay(self, row: int, col: int) -> int | None:
        """Read a cell from the overlay layer, or None if out of bounds."""
        if self.is_valid(row, col):
            return self.overlay[row][col]
        return None

    def set_overlay(self, row: int, col: int, value: int) -> bool:
        """Write ``value`` to the overlay layer."""
        if not self.is_valid(row, col):
            return False
        self.overlay[row][col] = value
        return True

    def set_start(self, row: int, col: int, *, overwrite_wall: bool = True) -> bool:
        """Set the pathfinding start cell, updating overlay markers cleanly."""
        if not self.is_valid(row, col):
            return False
        if self.base[row][col] == WALL:
            if not overwrite_wall:
                return False
            self.base[row][col] = EMPTY

        if self.start is not None:
            old_r, old_c = self.start
            if self.overlay[old_r][old_c] == OVERLAY_START:
                self.overlay[old_r][old_c] = OVERLAY_NONE

        if self.end == (row, col):
            self.end = None

        self.start = (row, col)
        self.overlay[row][col] = OVERLAY_START
        return True

    def set_end(self, row: int, col: int, *, overwrite_wall: bool = True) -> bool:
        """Set the pathfinding end cell, updating overlay markers cleanly."""
        if not self.is_valid(row, col):
            return False
        if self.base[row][col] == WALL:
            if not overwrite_wall:
                return False
            self.base[row][col] = EMPTY

        if self.end is not None:
            old_r, old_c = self.end
            if self.overlay[old_r][old_c] == OVERLAY_END:
                self.overlay[old_r][old_c] = OVERLAY_NONE

        if self.start == (row, col):
            self.start = None

        self.end = (row, col)
        self.overlay[row][col] = OVERLAY_END
        return True

    def erase_cell(self, row: int, col: int) -> bool:
        """Reset a cell to ``EMPTY`` and clear any overlay marker on it."""
        if not self.is_valid(row, col):
            return False
        self.base[row][col] = EMPTY
        self.overlay[row][col] = OVERLAY_NONE
        if self.start == (row, col):
            self.start = None
        if self.end == (row, col):
            self.end = None
        return True

    def clear_search_overlay(self) -> None:
        """Remove transient frontier/visited/path overlays while preserving base & endpoints."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.overlay[r][c] in (
                    OVERLAY_FRONTIER,
                    OVERLAY_VISITED,
                    OVERLAY_PATH,
                ):
                    self.overlay[r][c] = OVERLAY_NONE
        if self.start is not None:
            sr, sc = self.start
            self.overlay[sr][sc] = OVERLAY_START
        if self.end is not None:
            er, ec = self.end
            self.overlay[er][ec] = OVERLAY_END

    def clear_regions(self) -> None:
        """Clear all painted regions back to ``EMPTY`` while keeping walls and endpoints."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.base[r][c] != WALL:
                    self.base[r][c] = EMPTY

    def clear_all(self) -> None:
        """Reset both base and overlay layers completely."""
        self.base = create_grid(self.rows, self.cols, EMPTY)
        self.overlay = create_grid(self.rows, self.cols, OVERLAY_NONE)
        self.start = None
        self.end = None

    def load_base(
        self,
        matrix: Sequence[Sequence[int]],
        start: Coord | None = None,
        end: Coord | None = None,
    ) -> None:
        """Replace grid contents with ``matrix`` and optional ``start``/``end`` points."""
        rows, cols = get_grid_size(matrix)
        if rows <= 0 or cols <= 0:
            raise ValueError("Cannot load an empty matrix into Grid.")
        self.rows = rows
        self.cols = cols
        self.base = [list(row) for row in matrix]
        self.overlay = create_grid(rows, cols, OVERLAY_NONE)
        self.start = None
        self.end = None
        if start is not None:
            self.set_start(start[0], start[1], overwrite_wall=True)
        if end is not None:
            self.set_end(end[0], end[1], overwrite_wall=True)

    def push_snapshot(self) -> None:
        """Save current base state and endpoints onto the undo stack."""
        snapshot = (copy.deepcopy(self.base), self.start, self.end)
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self.max_undo:
            self._undo_stack.pop(0)

    def can_undo(self) -> bool:
        """Return True if at least one undo snapshot is available."""
        return len(self._undo_stack) > 0

    def undo(self) -> bool:
        """Restore the most recent snapshot from the undo stack."""
        if not self._undo_stack:
            return False
        base_copy, start, end = self._undo_stack.pop()
        self.rows = len(base_copy)
        self.cols = len(base_copy[0])
        self.base = base_copy
        self.overlay = create_grid(self.rows, self.cols, OVERLAY_NONE)
        self.start = None
        self.end = None
        if start is not None:
            self.set_start(start[0], start[1], overwrite_wall=True)
        if end is not None:
            self.set_end(end[0], end[1], overwrite_wall=True)
        return True

    def clone(self) -> Grid:
        """Return a deep copy of this ``Grid`` (excluding undo history)."""
        cloned = Grid(self.rows, self.cols, max_undo=self.max_undo)
        cloned.base = copy.deepcopy(self.base)
        cloned.overlay = copy.deepcopy(self.overlay)
        cloned.start = self.start
        cloned.end = self.end
        return cloned


# ---------------------------------------------------------------------------
# Deterministic / seedable map & terrain generators
# ---------------------------------------------------------------------------


def generate_maze(
    rows: int,
    cols: int,
    seed: int | None = None,
) -> tuple[list[list[int]], Coord, Coord]:
    """Generate a solvable maze using iterative Recursive Backtracking.

    Returns ``(base_grid, start, end)`` with guaranteed connectivity between
    ``start`` and ``end``.
    """
    if rows < 3 or cols < 3:
        grid = create_grid(max(1, rows), max(1, cols), EMPTY)
        return grid, (0, 0), (max(0, rows - 1), max(0, cols - 1))

    rng = random.Random(seed)
    grid = create_grid(rows, cols, WALL)

    start: Coord = (1, 1)
    grid[1][1] = EMPTY
    stack: list[Coord] = [start]

    while stack:
        r, c = stack[-1]
        candidates: list[tuple[int, int, int, int]] = []
        for dr, dc in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            nr, nc = r + dr, c + dc
            if 1 <= nr < rows - 1 and 1 <= nc < cols - 1 and grid[nr][nc] == WALL:
                candidates.append((nr, nc, r + dr // 2, c + dc // 2))

        if candidates:
            nr, nc, wall_r, wall_c = rng.choice(candidates)
            grid[wall_r][wall_c] = EMPTY
            grid[nr][nc] = EMPTY
            stack.append((nr, nc))
        else:
            stack.pop()

    # Choose the bottom-right-most carved odd cell as end
    end_r = rows - 2 if (rows - 2) % 2 == 1 else rows - 3
    end_c = cols - 2 if (cols - 2) % 2 == 1 else cols - 3
    end_r = max(1, end_r)
    end_c = max(1, end_c)
    grid[end_r][end_c] = EMPTY

    return grid, start, (end_r, end_c)


def generate_multi_room(
    rows: int,
    cols: int,
    seed: int | None = None,
) -> tuple[list[list[int]], Coord, Coord]:
    """Generate a multi-chamber layout ideal for demonstrating multi-color Flood Fill.

    Creates enclosed rooms (perfect for Paint Bucket testing) alongside a
    navigable corridor connecting ``start`` and ``end``.
    """
    rng = random.Random(seed)
    grid = create_grid(rows, cols, EMPTY)

    # Outer border walls
    for r in range(rows):
        grid[r][0] = WALL
        grid[r][cols - 1] = WALL
    for c in range(cols):
        grid[0][c] = WALL
        grid[rows - 1][c] = WALL

    if rows >= 7 and cols >= 9:
        mid_r = rows // 2
        c1 = cols // 3
        c2 = (2 * cols) // 3

        # Horizontal divider
        for c in range(1, cols - 1):
            grid[mid_r][c] = WALL
        # Vertical dividers
        for r in range(1, rows - 1):
            grid[r][c1] = WALL
            grid[r][c2] = WALL

        # Open doorways along a path from top-left to bottom-right while
        # keeping 2 side chambers completely sealed for independent flood-fill coloring
        door_top_mid = max(1, min(mid_r - 1, rng.randint(1, max(1, mid_r - 1))))
        door_mid_col = max(c1 + 1, min(c2 - 1, rng.randint(c1 + 1, max(c1 + 1, c2 - 1))))
        door_bot_right = max(mid_r + 1, min(rows - 2, rng.randint(mid_r + 1, max(mid_r + 1, rows - 2))))

        grid[door_top_mid][c1] = EMPTY
        grid[mid_r][door_mid_col] = EMPTY
        grid[door_bot_right][c2] = EMPTY

    start = (min(1, rows - 1), min(1, cols - 1))
    end = (max(0, rows - 2), max(0, cols - 2))
    grid[start[0]][start[1]] = EMPTY
    grid[end[0]][end[1]] = EMPTY
    return grid, start, end


def generate_random_obstacles(
    rows: int,
    cols: int,
    density: float = 0.28,
    seed: int | None = None,
) -> tuple[list[list[int]], Coord, Coord]:
    """Generate a grid with random wall obstacles at the given ``density``."""
    rng = random.Random(seed)
    clamped_density = max(0.0, min(0.85, density))
    grid = create_grid(rows, cols, EMPTY)

    start = (min(1, rows - 1), min(1, cols - 1))
    end = (max(0, rows - 2), max(0, cols - 2))

    for r in range(rows):
        for c in range(cols):
            if (r, c) in (start, end):
                continue
            if rng.random() < clamped_density:
                grid[r][c] = WALL

    return grid, start, end


def generate_spiral(rows: int, cols: int) -> tuple[list[list[int]], Coord, Coord]:
    """Generate a tight inward spiral corridor (stress test for DFS depth & heuristics)."""
    grid = create_grid(rows, cols, WALL)
    if rows < 3 or cols < 3:
        grid = create_grid(max(1, rows), max(1, cols), EMPTY)
        return grid, (0, 0), (max(0, rows - 1), max(0, cols - 1))

    top, bottom = 0, rows - 1
    left, right = 0, cols - 1
    carved: list[Coord] = []

    while top <= bottom and left <= right:
        # Carve right along top
        for c in range(left, right + 1):
            grid[top][c] = EMPTY
            carved.append((top, c))
        # Carve down along right
        for r in range(top + 1, bottom + 1):
            grid[r][right] = EMPTY
            carved.append((r, right))
        if bottom - top >= 2 and right - left >= 2:
            # Carve left along bottom
            for c in range(right - 1, left - 1, -1):
                grid[bottom][c] = EMPTY
                carved.append((bottom, c))
            # Carve up along left, leaving 1 wall row below previous top
            for r in range(bottom - 1, top + 1, -1):
                grid[r][left] = EMPTY
                carved.append((r, left))
            # Bridge inward to the next spiral ring
            if left + 1 <= right - 2 and top + 2 <= bottom - 2:
                grid[top + 2][left + 1] = EMPTY
                carved.append((top + 2, left + 1))

        top += 2
        bottom -= 2
        left += 2
        right -= 2

    start = carved[0] if carved else (0, 0)
    end = carved[-1] if carved else (rows - 1, cols - 1)
    return grid, start, end

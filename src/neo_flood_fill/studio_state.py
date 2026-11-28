"""Pure-Python state controller for the Interactive Algorithm Studio.

Separating interaction logic, animation playback, color conflict validation,
and run-history tracking from Pygame rendering keeps the studio cleanly
architected and thoroughly unit-testable without a display server.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator, Literal

from .algorithms import (
    AlgorithmMetrics,
    Connectivity,
    FLOOD_FILL_ALGORITHMS,
    PATHFINDING_ALGORITHMS,
    StepEvent,
)
from .grid import (
    Coord,
    EMPTY,
    GRID_PRESETS,
    OVERLAY_END,
    OVERLAY_FRONTIER,
    OVERLAY_PATH,
    OVERLAY_START,
    OVERLAY_VISITED,
    PALETTE_BY_ID,
    PALETTE_ENTRIES,
    PALETTE_START_ID,
    RGBColor,
    WALL,
    Grid,
    generate_maze,
    generate_multi_room,
    generate_random_obstacles,
    generate_spiral,
)

StudioMode = Literal["flood_fill", "pathfinding"]
ToolMode = Literal["wall", "fill", "erase", "start", "end"]
ThemeTarget = Literal["fill", "wall", "path", "visited", "start", "end"]
PresetName = Literal["multi_room", "maze", "obstacles", "spiral"]
PlaybackStatus = Literal["Ready", "Running", "Paused", "Done", "No Path", "Limit Hit"]

DEFAULT_THEME_COLORS: dict[str, RGBColor] = {
    "empty": (241, 245, 249),
    "wall": (24, 30, 42),
    "start": (34, 197, 94),
    "end": (239, 68, 68),
    "frontier": (56, 189, 248),
    "visited": (99, 102, 241),
    "path": (250, 204, 21),
}

# Speed levels: (label, steps_per_tick, tick_interval_ms)
SPEED_LEVELS: tuple[tuple[str, int, float], ...] = (
    ("0.5x", 1, 70.0),
    ("1x", 1, 28.0),
    ("2x", 2, 16.0),
    ("5x", 6, 12.0),
    ("15x", 20, 10.0),
    ("Max", 120, 0.0),
)


@dataclass(frozen=True)
class RunRecord:
    """Compact summary stored in the Recent Runs comparison table."""

    mode: StudioMode
    algorithm: str
    connectivity: int
    visited: int
    peak_frontier: int
    result_value: str  # e.g., "42 len" for pathfinding or "185 fill" for flood fill
    compute_ms: float
    found: bool


def bresenham_line(a: Coord, b: Coord) -> list[Coord]:
    """Return all grid coordinates along the discrete segment from ``a`` to ``b``."""
    r0, c0 = a
    r1, c1 = b
    points: list[Coord] = []
    dr = abs(r1 - r0)
    dc = abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dr - dc

    r, c = r0, c0
    while True:
        points.append((r, c))
        if r == r1 and c == c1:
            break
        e2 = 2 * err
        if e2 > -dc:
            err -= dc
            r += sr
        if e2 < dr:
            err += dr
            c += sc
    return points


class StudioState:
    """Complete interactive state machine for Neo Flood Fill Algorithm Studio."""

    def __init__(self, grid_size_key: str = "medium", preset: PresetName = "multi_room") -> None:
        self.grid_size_key: str = grid_size_key if grid_size_key in GRID_PRESETS else "medium"
        self.grid: Grid = Grid.from_preset(self.grid_size_key)

        self.studio_mode: StudioMode = "flood_fill"
        self.tool: ToolMode = "fill"
        self.connectivity: Connectivity = 4

        self.flood_algo: str = "bfs"
        self.path_algo: str = "astar"

        # Color picker state
        self.selected_fill_color_id: int = PALETTE_START_ID  # Mint
        self.active_color_target: ThemeTarget = "fill"
        self.theme_colors: dict[str, RGBColor] = dict(DEFAULT_THEME_COLORS)

        # Playback state
        self.speed_index: int = 2  # "2x" default: smooth & snappy
        self.status: PlaybackStatus = "Ready"
        self._generator: Iterator[StepEvent] | None = None
        self._active_run_mode: StudioMode | None = None
        self._active_run_algo_label: str = ""
        self._accum_ms: float = 0.0
        self._compute_ms: float = 0.0

        # Live metrics & recent run history
        self.live_visited: int = 0
        self.live_filled: int = 0
        self.live_peak: int = 0
        self.live_path_length: int = 0
        self.live_path_cost: float = 0.0
        self.live_compute_ms: float = 0.0
        self.run_history: list[RunRecord] = []

        # UI toast/alert feedback
        self.alert_message: str = ""
        self.alert_level: Literal["info", "warn", "error"] = "info"
        self.alert_timer_ms: float = 0.0

        # Drag painting state
        self._dragging_tool: ToolMode | None = None
        self._last_drag_cell: Coord | None = None
        self._preset_counter: int = 1

        self.load_preset(preset, record_undo=False)
        self.set_alert(
            "Click any enclosed room to Flood Fill, or switch to Pathfinding (TAB).",
            level="info",
            duration_ms=4500.0,
        )

    # ------------------------------------------------------------------
    # Properties & helpers
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self.status == "Running" and self._generator is not None

    @property
    def is_paused(self) -> bool:
        return self.status == "Paused" and self._generator is not None

    @property
    def has_active_animation(self) -> bool:
        return self._generator is not None

    @property
    def active_algo_key(self) -> str:
        return self.flood_algo if self.studio_mode == "flood_fill" else self.path_algo

    @property
    def active_algo_label(self) -> str:
        if self.studio_mode == "flood_fill":
            return FLOOD_FILL_ALGORITHMS[self.flood_algo][0]
        return PATHFINDING_ALGORITHMS[self.path_algo][0]

    @property
    def speed_label(self) -> str:
        return SPEED_LEVELS[self.speed_index][0]

    def set_alert(
        self,
        message: str,
        level: Literal["info", "warn", "error"] = "info",
        duration_ms: float = 3200.0,
    ) -> None:
        self.alert_message = message
        self.alert_level = level
        self.alert_timer_ms = duration_ms

    def clear_alert(self) -> None:
        self.alert_message = ""
        self.alert_timer_ms = 0.0

    # ------------------------------------------------------------------
    # Mode, algorithm, connectivity & speed controls
    # ------------------------------------------------------------------

    def set_studio_mode(self, mode: StudioMode) -> None:
        if mode == self.studio_mode:
            return
        self.stop_animation()
        self.studio_mode = mode
        if mode == "flood_fill":
            self.tool = "fill"
            self.active_color_target = "fill"
            self.set_alert("Flood Fill mode: pick a swatch and click any region.", "info")
        else:
            self.tool = "wall"
            self.set_alert("Pathfinding mode: press SPACE or click Run to search.", "info")

    def toggle_studio_mode(self) -> None:
        self.set_studio_mode("pathfinding" if self.studio_mode == "flood_fill" else "flood_fill")

    def set_tool(self, tool: ToolMode) -> None:
        self.tool = tool
        if tool == "fill" and self.studio_mode != "flood_fill":
            self.stop_animation()
            self.studio_mode = "flood_fill"
            self.active_color_target = "fill"

    def set_algorithm(self, algo_key: str) -> None:
        self.stop_animation()
        if self.studio_mode == "flood_fill":
            if algo_key in FLOOD_FILL_ALGORITHMS:
                self.flood_algo = algo_key
        else:
            if algo_key in PATHFINDING_ALGORITHMS:
                self.path_algo = algo_key

    def set_connectivity(self, connectivity: Connectivity) -> None:
        if connectivity in (4, 8):
            self.stop_animation()
            self.connectivity = connectivity

    def set_speed_index(self, index: int) -> None:
        self.speed_index = max(0, min(len(SPEED_LEVELS) - 1, index))

    def adjust_speed(self, delta: int) -> None:
        self.set_speed_index(self.speed_index + delta)

    # ------------------------------------------------------------------
    # Color picker & conflict guard
    # ------------------------------------------------------------------

    def set_color_target(self, target: ThemeTarget) -> None:
        self.active_color_target = target

    def check_color_conflict(self, target: ThemeTarget, rgb: RGBColor) -> str | None:
        """Return a warning message if assigning ``rgb`` to ``target`` causes poor contrast."""
        if target == "fill":
            if rgb == self.theme_colors["wall"]:
                return "Fill color matches Wall color — choose a distinct swatch."
            return None

        if target == "wall":
            if rgb == self.theme_colors["path"]:
                return "Wall and Path cannot share the same color."
            if rgb == self.theme_colors["empty"]:
                return "Wall cannot match Empty cell background."
        elif target == "path":
            if rgb == self.theme_colors["wall"]:
                return "Path and Wall cannot share the same color."
            if rgb == self.theme_colors["visited"]:
                return "Path and Visited should remain distinct colors."
        elif target == "visited":
            if rgb == self.theme_colors["path"]:
                return "Visited and Path cannot share the same color."
            if rgb == self.theme_colors["wall"]:
                return "Visited and Wall cannot share the same color."
        elif target == "start":
            if rgb == self.theme_colors["end"]:
                return "Start and End markers cannot share the same color."
        elif target == "end":
            if rgb == self.theme_colors["start"]:
                return "End and Start markers cannot share the same color."
        return None

    def pick_palette_entry(self, color_id: int) -> bool:
        """Apply a clicked palette swatch to either the Paint Bucket or active theme target."""
        if color_id not in PALETTE_BY_ID:
            return False
        entry = PALETTE_BY_ID[color_id]
        conflict = self.check_color_conflict(self.active_color_target, entry.rgb)
        if conflict is not None:
            self.set_alert(conflict, level="warn", duration_ms=3500.0)
            return False

        if self.active_color_target == "fill":
            self.selected_fill_color_id = color_id
            if self.studio_mode == "flood_fill":
                self.tool = "fill"
        else:
            self.theme_colors[self.active_color_target] = entry.rgb
        self.clear_alert()
        return True

    def reset_colors(self) -> None:
        self.theme_colors = dict(DEFAULT_THEME_COLORS)
        self.selected_fill_color_id = PALETTE_START_ID
        self.active_color_target = "fill"
        self.set_alert("Colors reset to studio defaults.", "info", duration_ms=2200.0)

    # ------------------------------------------------------------------
    # Grid sizing, presets, clear & undo
    # ------------------------------------------------------------------

    def set_grid_size(self, size_key: str) -> None:
        if size_key not in GRID_PRESETS or size_key == self.grid_size_key:
            return
        self.stop_animation()
        self.grid_size_key = size_key
        self.grid = Grid.from_preset(size_key)
        self.run_history.clear()
        self.load_preset("multi_room", record_undo=False)
        self.set_alert(
            f"Grid resized to {self.grid.rows}x{self.grid.cols}.",
            "info",
            duration_ms=2200.0,
        )

    def load_preset(self, preset: PresetName, *, record_undo: bool = True) -> None:
        self.stop_animation()
        if record_undo:
            self.grid.push_snapshot()

        self._preset_counter += 1
        seed = self._preset_counter * 17
        rows, cols = self.grid.rows, self.grid.cols

        if preset == "maze":
            matrix, start, end = generate_maze(rows, cols, seed=seed)
        elif preset == "multi_room":
            matrix, start, end = generate_multi_room(rows, cols, seed=seed)
        elif preset == "obstacles":
            matrix, start, end = generate_random_obstacles(rows, cols, density=0.28, seed=seed)
        elif preset == "spiral":
            matrix, start, end = generate_spiral(rows, cols)
        else:
            return

        self.grid.load_base(matrix, start=start, end=end)
        self.run_history.clear()
        self._reset_live_metrics()
        self.status = "Ready"

    def clear_search_overlay(self) -> None:
        self.stop_animation()
        self.grid.clear_search_overlay()
        self._reset_live_metrics()
        self.status = "Ready"

    def clear_regions(self) -> None:
        self.stop_animation()
        self.grid.push_snapshot()
        self.grid.clear_regions()
        self._reset_live_metrics()
        self.status = "Ready"

    def reset_grid(self) -> None:
        self.stop_animation()
        self.grid.push_snapshot()
        self.grid.clear_all()
        self.grid.set_start(1, 1)
        self.grid.set_end(self.grid.rows - 2, self.grid.cols - 2)
        self.run_history.clear()
        self._reset_live_metrics()
        self.status = "Ready"
        self.set_alert("Grid cleared.", "info", duration_ms=1800.0)

    def undo(self) -> bool:
        self.stop_animation()
        if self.grid.undo():
            self._reset_live_metrics()
            self.status = "Ready"
            self.set_alert("Undid last change.", "info", duration_ms=1600.0)
            return True
        self.set_alert("Nothing to undo.", "warn", duration_ms=1600.0)
        return False

    # ------------------------------------------------------------------
    # Mouse painting & Flood Fill click triggering
    # ------------------------------------------------------------------

    def begin_cell_interaction(self, cell: Coord, button: int = 1) -> None:
        """Handle mouse press on a grid cell (left button uses active tool, right button erases)."""
        if self.is_running:
            return
        r, c = cell
        if not self.grid.is_valid(r, c):
            return

        effective_tool: ToolMode = "erase" if button == 3 else self.tool

        if effective_tool == "fill":
            self.start_flood_fill(cell)
            return

        self.grid.push_snapshot()
        if effective_tool in ("wall", "erase"):
            self._dragging_tool = effective_tool
            self._last_drag_cell = cell
            self._apply_paint_cell(cell, effective_tool)
        elif effective_tool == "start":
            self.grid.clear_search_overlay()
            self.grid.set_start(r, c, overwrite_wall=True)
            self.status = "Ready"
        elif effective_tool == "end":
            self.grid.clear_search_overlay()
            self.grid.set_end(r, c, overwrite_wall=True)
            self.status = "Ready"

    def drag_cell_interaction(self, cell: Coord) -> None:
        """Handle continuous drag painting with Bresenham interpolation."""
        if self._dragging_tool is None or self.is_running:
            return
        if not self.grid.is_valid(cell[0], cell[1]):
            return
        if self._last_drag_cell is None:
            points = [cell]
        else:
            points = bresenham_line(self._last_drag_cell, cell)
        for pt in points:
            self._apply_paint_cell(pt, self._dragging_tool)
        self._last_drag_cell = cell

    def end_cell_interaction(self) -> None:
        self._dragging_tool = None
        self._last_drag_cell = None

    def _apply_paint_cell(self, cell: Coord, tool: ToolMode) -> None:
        r, c = cell
        if not self.grid.is_valid(r, c):
            return
        if tool == "wall":
            if self.grid.start != (r, c) and self.grid.end != (r, c):
                self.grid.set_base(r, c, WALL)
        elif tool == "erase":
            self.grid.erase_cell(r, c)

    # ------------------------------------------------------------------
    # Animation launch, pause, step, and tick
    # ------------------------------------------------------------------

    def start_flood_fill(self, start_cell: Coord) -> bool:
        """Start an animated multi-color Region Flood Fill from ``start_cell``."""
        r, c = start_cell
        if not self.grid.is_valid(r, c):
            return False

        target = self.grid.get_base(r, c)
        if target == WALL:
            self.set_alert("Cannot flood fill a WALL cell. Click an open or colored region.", "warn")
            return False
        if target == self.selected_fill_color_id:
            self.set_alert("Region already uses this color — pick a different swatch.", "info")
            return False

        self.stop_animation()
        self.grid.push_snapshot()
        self._reset_live_metrics()

        label, _, steps_fn = FLOOD_FILL_ALGORITHMS[self.flood_algo]
        self._generator = steps_fn(
            self.grid,
            r,
            c,
            target,
            self.selected_fill_color_id,
            self.connectivity,
        )
        self._active_run_mode = "flood_fill"
        self._active_run_algo_label = label
        self.status = "Running"
        self._accum_ms = 0.0
        self._compute_ms = 0.0
        self.clear_alert()
        return True

    def start_pathfinding(self) -> bool:
        """Start an animated BFS / DFS / A* pathfinding run from Start to End."""
        if self.grid.start is None or self.grid.end is None:
            self.set_alert("Set both Start (S) and End (D) cells before running Pathfinding.", "warn")
            return False

        self.stop_animation()
        self.grid.clear_search_overlay()
        self._reset_live_metrics()

        label, _, steps_fn = PATHFINDING_ALGORITHMS[self.path_algo]
        self._generator = steps_fn(
            self.grid,
            self.grid.start,
            self.grid.end,
            self.connectivity,
            WALL,
        )
        self._active_run_mode = "pathfinding"
        self._active_run_algo_label = label
        self.status = "Running"
        self._accum_ms = 0.0
        self._compute_ms = 0.0
        self.clear_alert()
        return True

    def toggle_run_pause(self) -> None:
        """SPACE action: pause/resume active animation, or start a new run."""
        if self.is_running:
            self.status = "Paused"
            return
        if self.is_paused:
            self.status = "Running"
            return

        if self.studio_mode == "pathfinding":
            self.start_pathfinding()
        else:
            # In Flood Fill mode, SPACE triggers a fill at Start (if valid) or prompts user
            if self.grid.start is not None and self.grid.get_base(*self.grid.start) != WALL:
                if not self.start_flood_fill(self.grid.start):
                    self.set_alert(
                        "Pick a new swatch or click any enclosed region to Flood Fill.",
                        "info",
                    )
            else:
                self.set_alert("Click any enclosed region on the grid to start Flood Fill.", "info")

    def step_once(self) -> bool:
        """Advance a single animation event (pauses if running; starts pathfinding if idle)."""
        if self._generator is None:
            if self.studio_mode == "pathfinding":
                if not self.start_pathfinding():
                    return False
                self.status = "Paused"
            else:
                self.set_alert("Click a region first, then pause (SPACE) to single-step.", "info")
                return False

        if self.status == "Running":
            self.status = "Paused"
        return self._consume_one_event()

    def stop_animation(self) -> None:
        self._generator = None
        self._active_run_mode = None
        self._accum_ms = 0.0
        if self.status in ("Running", "Paused"):
            self.status = "Ready"

    def update(self, dt_ms: float) -> None:
        """Advance toast timer and animation steps according to the active speed setting."""
        if self.alert_timer_ms > 0.0:
            self.alert_timer_ms = max(0.0, self.alert_timer_ms - dt_ms)
            if self.alert_timer_ms == 0.0:
                self.alert_message = ""

        if not self.is_running or self._generator is None:
            return

        _, steps_per_tick, interval_ms = SPEED_LEVELS[self.speed_index]
        if interval_ms <= 0.0:
            for _ in range(steps_per_tick):
                if not self._consume_one_event():
                    break
            return

        self._accum_ms += dt_ms
        while self._accum_ms >= interval_ms and self.is_running:
            self._accum_ms -= interval_ms
            for _ in range(steps_per_tick):
                if not self._consume_one_event():
                    break

    def _consume_one_event(self) -> bool:
        if self._generator is None:
            return False

        t0 = time.perf_counter()
        try:
            event = next(self._generator)
        except StopIteration:
            self._generator = None
            if self.status in ("Running", "Paused"):
                self.status = "Done"
            return False
        finally:
            self._compute_ms += (time.perf_counter() - t0) * 1000.0
            self.live_compute_ms = self._compute_ms

        if event.kind == "fill":
            self.live_visited += 1
            self.live_filled += 1
        elif event.kind == "frontier" and event.row is not None and event.col is not None:
            if self.grid.get_overlay(event.row, event.col) not in (OVERLAY_START, OVERLAY_END):
                self.grid.set_overlay(event.row, event.col, OVERLAY_FRONTIER)
        elif event.kind == "visit" and event.row is not None and event.col is not None:
            self.live_visited += 1
            if self.grid.get_overlay(event.row, event.col) not in (OVERLAY_START, OVERLAY_END):
                self.grid.set_overlay(event.row, event.col, OVERLAY_VISITED)
        elif event.kind == "path" and event.row is not None and event.col is not None:
            self.live_path_length += 1
            if self.grid.get_overlay(event.row, event.col) not in (OVERLAY_START, OVERLAY_END):
                self.grid.set_overlay(event.row, event.col, OVERLAY_PATH)
        elif event.kind in ("done", "no_path"):
            self._finalize_run(event.kind, event.metrics)
            return False

        return True

    def _finalize_run(self, kind: str, metrics: AlgorithmMetrics | None) -> None:
        mode = self._active_run_mode or self.studio_mode
        label = self._active_run_algo_label or self.active_algo_label
        self._generator = None
        self._active_run_mode = None

        if metrics is not None:
            self.live_visited = metrics.cells_visited
            self.live_filled = metrics.cells_filled
            self.live_peak = (
                metrics.peak_recursion_depth
                if metrics.peak_recursion_depth > 0
                else metrics.peak_frontier
            )
            self.live_path_length = metrics.path_length
            self.live_path_cost = metrics.path_cost

            if kind == "no_path" or not metrics.found:
                self.status = "No Path"
                self.set_alert(
                    f"No path found with {label} ({self.connectivity}-way).",
                    level="warn",
                    duration_ms=4000.0,
                )
            elif metrics.recursion_limit_hit:
                self.status = "Limit Hit"
                self.set_alert(
                    "Recursive DFS hit Python's recursion limit! Try BFS, Scanline, or Iterative DFS.",
                    level="error",
                    duration_ms=5000.0,
                )
            else:
                self.status = "Done"

            result_str = (
                f"{metrics.cells_filled} fill"
                if mode == "flood_fill"
                else (f"{metrics.path_length} len" if metrics.found else "No path")
            )
            self.run_history.insert(
                0,
                RunRecord(
                    mode=mode,
                    algorithm=label,
                    connectivity=metrics.connectivity,
                    visited=metrics.cells_visited,
                    peak_frontier=self.live_peak,
                    result_value=result_str,
                    compute_ms=self.live_compute_ms,
                    found=metrics.found and not metrics.recursion_limit_hit,
                ),
            )
            if len(self.run_history) > 4:
                self.run_history.pop()
        else:
            self.status = "No Path" if kind == "no_path" else "Done"

    def _reset_live_metrics(self) -> None:
        self.live_visited = 0
        self.live_filled = 0
        self.live_peak = 0
        self.live_path_length = 0
        self.live_path_cost = 0.0
        self.live_compute_ms = 0.0
        self._compute_ms = 0.0


def palette_id_list() -> list[int]:
    """Return ordered palette color IDs for UI swatch rendering."""
    return [entry.color_id for entry in PALETTE_ENTRIES]

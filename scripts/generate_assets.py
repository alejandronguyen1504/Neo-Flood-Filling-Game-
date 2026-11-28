"""Generate README showcase assets: animated GIFs, Studio screenshots, and benchmark charts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("MPLBACKEND", "Agg")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib.pyplot as plt
import pygame
from PIL import Image

from neo_flood_fill.benchmarks import benchmark_flood_fill, benchmark_pathfinding
from neo_flood_fill.grid import EMPTY, PALETTE_ENTRIES
from neo_flood_fill.studio_state import StudioState
from neo_flood_fill.visualizer import StudioRenderer, WINDOW_HEIGHT, WINDOW_WIDTH

ASSETS_DIR = ROOT / "docs" / "assets"


def _surface_to_pil(surface: pygame.Surface, scale: tuple[int, int] | None = None) -> Image.Image:
    raw = pygame.image.tobytes(surface, "RGB")
    img = Image.frombytes("RGB", surface.get_size(), raw)
    if scale is not None:
        img = img.resize(scale, Image.Resampling.LANCZOS)
    return img


def _save_gif(frames: list[Image.Image], path: Path, duration_ms: int = 55) -> None:
    if not frames:
        return
    # Quantize with adaptive palette for crisp UI colors & compact file size
    quantized = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f in frames]
    durations = [duration_ms] * len(quantized)
    durations[-1] = 1400  # Pause on final completed frame
    quantized[0].save(
        path,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )


def generate_studio_visuals() -> None:
    """Capture crisp 1200x720 screenshots and smooth animated GIFs of the Studio."""
    pygame.init()
    try:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        gif_size = (800, 480)

        # ------------------------------------------------------------------
        # 1. Flood Fill Studio GIF + Screenshot (Multi-Room Paint Bucket)
        # ------------------------------------------------------------------
        state = StudioState(grid_size_key="medium", preset="multi_room")
        renderer = StudioRenderer(state)
        state.clear_alert()
        state.set_speed_index(4)  # 15x smooth sweep

        ff_frames: list[Image.Image] = []
        renderer.render(screen)
        ff_frames.append(_surface_to_pil(screen, gif_size))

        # Room 1 with Queue BFS (Mint)
        state.set_algorithm("bfs")
        state.pick_palette_entry(PALETTE_ENTRIES[0].color_id)  # Mint
        state.start_flood_fill((1, 1))
        step = 0
        while state.is_running:
            state.update(14.0)
            step += 1
            if step % 2 == 0 or not state.is_running:
                renderer.render(screen)
                ff_frames.append(_surface_to_pil(screen, gif_size))

        # Find two sealed rooms and paint with Coral (Scanline) and Purple (Iterative DFS)
        sealed_targets: list[tuple[int, int]] = []
        seen_regions = 0
        for r in range(1, state.grid.rows - 1):
            for c in range(1, state.grid.cols - 1):
                if state.grid.get_base(r, c) == EMPTY:
                    sealed_targets.append((r, c))
                    break
            if len(sealed_targets) >= 1:
                break

        # Fill sealed room with Coral using Scanline
        if sealed_targets:
            state.set_algorithm("scanline")
            state.pick_palette_entry(PALETTE_ENTRIES[6].color_id)  # Coral
            state.start_flood_fill(sealed_targets[0])
            while state.is_running:
                state.update(14.0)
                renderer.render(screen)
                ff_frames.append(_surface_to_pil(screen, gif_size))

        # Find second sealed room (bottom-left) and fill with Purple using Iterative DFS
        for r in range(state.grid.rows - 2, 0, -1):
            for c in range(1, state.grid.cols - 1):
                if state.grid.get_base(r, c) == EMPTY:
                    state.set_algorithm("iterative_dfs")
                    state.pick_palette_entry(PALETTE_ENTRIES[4].color_id)  # Purple
                    state.start_flood_fill((r, c))
                    step = 0
                    while state.is_running:
                        state.update(14.0)
                        step += 1
                        if step % 2 == 0 or not state.is_running:
                            renderer.render(screen)
                            ff_frames.append(_surface_to_pil(screen, gif_size))
                    seen_regions += 1
                    break
            if seen_regions:
                break

        renderer.hover_cell = (5, 8)
        renderer.render(screen)
        pygame.image.save(screen, str(ASSETS_DIR / "studio_flood_fill.png"))
        _save_gif(ff_frames, ASSETS_DIR / "demo_flood_fill.gif", duration_ms=65)

        # ------------------------------------------------------------------
        # 2. Pathfinding Studio GIF + Screenshot (Maze: BFS then A* comparison)
        # ------------------------------------------------------------------
        pf_state = StudioState(grid_size_key="medium", preset="maze")
        pf_renderer = StudioRenderer(pf_state)
        pf_state.clear_alert()
        pf_state.set_studio_mode("pathfinding")
        pf_state.clear_alert()
        pf_state.set_speed_index(4)

        pf_frames: list[Image.Image] = []
        pf_renderer.render(screen)
        pf_frames.append(_surface_to_pil(screen, gif_size))

        # Run BFS first (records in Recent Runs table)
        pf_state.set_algorithm("bfs")
        pf_state.start_pathfinding()
        step = 0
        while pf_state.is_running:
            pf_state.update(14.0)
            step += 1
            if step % 2 == 0 or not pf_state.is_running:
                pf_renderer.render(screen)
                pf_frames.append(_surface_to_pil(screen, gif_size))

        # Hold BFS completed frame briefly
        for _ in range(6):
            pf_frames.append(pf_frames[-1])

        # Switch to A* Search on the exact same maze and run
        pf_state.set_algorithm("astar")
        pf_state.start_pathfinding()
        step = 0
        while pf_state.is_running:
            pf_state.update(14.0)
            step += 1
            if step % 2 == 0 or not pf_state.is_running:
                pf_renderer.render(screen)
                pf_frames.append(_surface_to_pil(screen, gif_size))

        pf_renderer.hover_cell = (10, 15)
        pf_renderer.render(screen)
        pygame.image.save(screen, str(ASSETS_DIR / "studio_pathfinding.png"))
        _save_gif(pf_frames, ASSETS_DIR / "demo_pathfinding.gif", duration_ms=60)
    finally:
        pygame.quit()


def generate_benchmark_charts() -> None:
    """Run controlled benchmarks and export high-DPI matplotlib comparison figures."""
    plt.rcParams.update(
        {
            "figure.facecolor": "#0d111a",
            "axes.facecolor": "#161b27",
            "axes.edgecolor": "#2e384d",
            "axes.labelcolor": "#e2e8f0",
            "xtick.color": "#94a3b8",
            "ytick.color": "#94a3b8",
            "text.color": "#f1f5f9",
            "grid.color": "#263044",
            "grid.linestyle": "--",
            "grid.alpha": 0.6,
            "legend.facecolor": "#1d2434",
            "legend.edgecolor": "#2e384d",
        }
    )

    algo_styles = {
        "recursive_dfs": ("Recursive DFS", "#f43f5e", "o"),
        "iterative_dfs": ("Iterative DFS", "#f97316", "s"),
        "bfs": ("Queue BFS", "#38bdf8", "^"),
        "scanline": ("Scanline", "#20c997", "D"),
    }

    # 1. Flood Fill Benchmark Chart (Open Grid scaling + Multi-Terrain Peak Space)
    sizes = (15, 25, 35, 50, 65)
    open_results = benchmark_flood_fill(
        sizes=sizes,
        terrains=("open",),
        algorithms=("recursive_dfs", "iterative_dfs", "bfs", "scanline"),
        repeats=5,
    )
    terrain_results = benchmark_flood_fill(
        sizes=(35,),
        terrains=("open", "maze", "spiral"),
        algorithms=("recursive_dfs", "iterative_dfs", "bfs", "scanline"),
        repeats=3,
    )

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6), dpi=160)
    fig.suptitle(
        "Flood Fill Benchmarks — Time O(N) & Algorithmic Space Comparison",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    # Panel A: Open Grid Runtime vs N
    ax = axes[0]
    for key, (label, color, marker) in algo_styles.items():
        subset = [r for r in open_results if r.algorithm_key == key]
        xs = [r.total_cells for r in subset]
        ys = [r.median_ms for r in subset]
        ax.plot(xs, ys, label=label, color=color, marker=marker, linewidth=2.0)
    ax.set_title("Open Grid Runtime vs N", fontsize=11, fontweight="bold")
    ax.set_xlabel("Grid Size N (cells)")
    ax.set_ylabel("Median Runtime (ms)")
    ax.grid(True)
    ax.legend(fontsize=8.5)

    # Panel B: Open Grid Peak Frontier / Stack Depth vs N
    ax = axes[1]
    for key, (label, color, marker) in algo_styles.items():
        subset = [r for r in open_results if r.algorithm_key == key]
        xs = [r.total_cells for r in subset]
        ys = [
            r.peak_recursion_depth if key == "recursive_dfs" else r.peak_frontier
            for r in subset
        ]
        ax.plot(xs, ys, label=label, color=color, marker=marker, linewidth=2.0)
    ax.set_title("Peak Stack / Frontier vs N (Open Grid)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Grid Size N (cells)")
    ax.set_ylabel("Peak Entries (log scale)")
    ax.set_yscale("log")
    ax.grid(True)
    ax.legend(fontsize=8.5)

    # Panel C: Runtime Across Terrains (35x35)
    ax = axes[2]
    terrains = ("open", "maze", "spiral")
    x_positions = list(range(len(terrains)))
    bar_width = 0.19
    for idx, (key, (label, color, _)) in enumerate(algo_styles.items()):
        vals = [
            next(
                r.median_ms
                for r in terrain_results
                if r.terrain == t and r.algorithm_key == key
            )
            for t in terrains
        ]
        offsets = [x + (idx - 1.5) * bar_width for x in x_positions]
        ax.bar(offsets, vals, width=bar_width, label=label, color=color)
    ax.set_title("Runtime Across Terrains (35x35)", fontsize=11, fontweight="bold")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(["Open Grid", "Maze", "Spiral"])
    ax.set_ylabel("Median Runtime (ms)")
    ax.grid(True, axis="y")
    ax.legend(fontsize=8.5)

    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(ASSETS_DIR / "benchmark_flood_fill.png", dpi=160)
    plt.close(fig)

    # 2. Pathfinding Benchmark Chart (A* vs BFS vs DFS across Open / Maze / Spiral)
    pf_results = benchmark_pathfinding(
        sizes=(31,),
        terrains=("open", "maze", "spiral"),
        algorithms=("astar", "bfs", "dfs"),
        connectivity=4,
        repeats=5,
    )
    pf_styles = {
        "astar": ("A* (Manhattan)", "#20c997"),
        "bfs": ("BFS", "#38bdf8"),
        "dfs": ("DFS", "#f43f5e"),
    }

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), dpi=160)
    fig.suptitle(
        "Pathfinding Benchmarks (31x31, 4-Way) — A* vs BFS vs DFS",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    x_positions = list(range(len(terrains)))
    bar_width = 0.24

    # Panel A: Cells Visited
    ax = axes[0]
    for idx, (key, (label, color)) in enumerate(pf_styles.items()):
        vals = [
            next(
                r.cells_visited
                for r in pf_results
                if r.terrain == t and r.algorithm_key == key
            )
            for t in terrains
        ]
        offsets = [x + (idx - 1) * bar_width for x in x_positions]
        bars = ax.bar(offsets, vals, width=bar_width, label=label, color=color)
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                v + 8,
                str(v),
                ha="center",
                va="bottom",
                fontsize=8,
                color="#cbd5e1",
            )
    ax.set_title("Cells Explored (Lower = More Efficient)", fontsize=11, fontweight="bold")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(["Open Grid", "Maze", "Spiral"])
    ax.set_ylabel("Cells Visited")
    ax.grid(True, axis="y")
    ax.legend(fontsize=9)

    # Panel B: Path Length Found
    ax = axes[1]
    for idx, (key, (label, color)) in enumerate(pf_styles.items()):
        vals = [
            next(
                r.path_length
                for r in pf_results
                if r.terrain == t and r.algorithm_key == key
            )
            for t in terrains
        ]
        offsets = [x + (idx - 1) * bar_width for x in x_positions]
        bars = ax.bar(offsets, vals, width=bar_width, label=label, color=color)
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                v + 6,
                str(v),
                ha="center",
                va="bottom",
                fontsize=8,
                color="#cbd5e1",
            )
    ax.set_title("Path Length Found (A* & BFS = Optimal)", fontsize=11, fontweight="bold")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(["Open Grid", "Maze", "Spiral"])
    ax.set_ylabel("Cells in Path")
    ax.grid(True, axis="y")
    ax.legend(fontsize=9)

    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(ASSETS_DIR / "benchmark_pathfinding.png", dpi=160)
    plt.close(fig)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating Studio screenshots and animated GIFs...")
    generate_studio_visuals()
    print("Generating matplotlib benchmark charts...")
    generate_benchmark_charts()
    print(f"All showcase assets saved to: {ASSETS_DIR}")


if __name__ == "__main__":
    main()

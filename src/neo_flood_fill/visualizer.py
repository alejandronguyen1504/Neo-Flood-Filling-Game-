"""Async Pygame visualizer (Phase 1 minimal shell; upgraded to full Studio in Phase 2)."""

from __future__ import annotations

import asyncio

import pygame

from .grid import (
    EMPTY,
    OVERLAY_END,
    OVERLAY_FRONTIER,
    OVERLAY_NONE,
    OVERLAY_PATH,
    OVERLAY_START,
    OVERLAY_VISITED,
    PALETTE_BY_ID,
    WALL,
    Grid,
    generate_multi_room,
)

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 720
FPS = 60

BG_COLOR = (18, 22, 31)
GRID_LINE_COLOR = (45, 53, 68)
EMPTY_COLOR = (241, 245, 249)
WALL_COLOR = (23, 27, 36)
OVERLAY_COLORS = {
    OVERLAY_START: (34, 197, 94),
    OVERLAY_END: (239, 68, 68),
    OVERLAY_FRONTIER: (56, 189, 248),
    OVERLAY_VISITED: (99, 102, 241),
    OVERLAY_PATH: (250, 204, 21),
}


async def run_studio(
    preset: str = "medium",
    max_frames: int | None = None,
) -> None:
    """Launch the async Pygame visualizer loop (Desktop + pygbag WebAssembly compatible)."""
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Neo Flood Fill — Algorithm Studio")
    clock = pygame.time.Clock()

    grid = Grid.from_preset(preset)
    matrix, start, end = generate_multi_room(grid.rows, grid.cols, seed=42)
    grid.load_base(matrix, start=start, end=end)

    running = True
    frames = 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill(BG_COLOR)
        cell_size = min(
            (WINDOW_WIDTH - 340) // grid.cols,
            (WINDOW_HEIGHT - 80) // grid.rows,
        )
        offset_x = 24
        offset_y = 40

        for r in range(grid.rows):
            for c in range(grid.cols):
                base_val = grid.base[r][c]
                overlay_val = grid.overlay[r][c]
                if overlay_val != OVERLAY_NONE:
                    color = OVERLAY_COLORS.get(overlay_val, EMPTY_COLOR)
                elif base_val == WALL:
                    color = WALL_COLOR
                elif base_val == EMPTY:
                    color = EMPTY_COLOR
                elif base_val in PALETTE_BY_ID:
                    color = PALETTE_BY_ID[base_val].rgb
                else:
                    color = (148, 163, 184)

                rect = pygame.Rect(
                    offset_x + c * cell_size,
                    offset_y + r * cell_size,
                    max(1, cell_size - 1),
                    max(1, cell_size - 1),
                )
                pygame.draw.rect(screen, color, rect)

        pygame.display.flip()
        clock.tick(FPS)
        await asyncio.sleep(0)

        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False

    pygame.quit()

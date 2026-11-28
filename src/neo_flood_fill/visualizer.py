"""Interactive Pygame Algorithm Studio (Desktop + pygbag WebAssembly compatible).

Window layout: 1200x720 (16:9) dark-mode studio featuring:
- Top bar: mode switch (Flood Fill / Pathfinding), 4/8-way connectivity, grid size presets
- Main canvas: two-layer grid renderer with drag-to-paint, hover highlight, and toast alerts
- Bottom bar: 12-color Paint Bucket palette + theme customizer with color-conflict guard
- Right sidebar: tools, algorithm selector, playback & speed slider, map presets, live HUD,
  and a Recent Runs comparison table
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Callable

import pygame

from .algorithms import FLOOD_FILL_ALGORITHMS, PATHFINDING_ALGORITHMS
from .grid import (
    Coord,
    EMPTY,
    OVERLAY_END,
    OVERLAY_FRONTIER,
    OVERLAY_NONE,
    OVERLAY_PATH,
    OVERLAY_START,
    OVERLAY_VISITED,
    PALETTE_BY_ID,
    PALETTE_ENTRIES,
    RGBColor,
    WALL,
)
from .studio_state import (
    PresetName,
    SPEED_LEVELS,
    StudioState,
    ThemeTarget,
    ToolMode,
)

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 720
FPS = 60

# Dark-mode Studio theme palette
BG_COLOR = (13, 17, 26)
SURFACE_COLOR = (22, 27, 39)
SURFACE_ALT = (29, 36, 52)
HEADER_COLOR = (18, 23, 35)
BORDER_SUBTLE = (46, 56, 77)
BORDER_ACTIVE = (56, 189, 248)
BUTTON_BG = (33, 41, 59)
BUTTON_HOVER = (46, 58, 82)
BUTTON_ACTIVE = (37, 99, 235)
BUTTON_PRIMARY = (16, 185, 129)
BUTTON_PRIMARY_HOVER = (20, 204, 143)
BUTTON_DANGER = (127, 29, 29)
TEXT_PRIMARY = (241, 245, 249)
TEXT_SECONDARY = (148, 163, 184)
TEXT_MUTED = (100, 116, 139)
ACCENT_CYAN = (56, 189, 248)
ACCENT_AMBER = (251, 191, 36)
ACCENT_ROSE = (244, 63, 94)
ACCENT_GREEN = (34, 197, 94)

CANVAS_CARD = pygame.Rect(16, 58, 824, 554)
CANVAS_INNER = pygame.Rect(24, 66, 808, 538)
PALETTE_CARD = pygame.Rect(16, 622, 824, 86)
SIDEBAR_CARD = pygame.Rect(852, 58, 334, 650)


@dataclass
class UIButton:
    """Clickable rectangular button tracked per frame."""

    rect: pygame.Rect
    label: str
    action: Callable[[], None]
    active: bool = False
    accent: RGBColor | None = None
    subtle: bool = False


def _is_wasm() -> bool:
    return sys.platform == "emscripten"


def _blend_rgb(base: RGBColor, tint: RGBColor, alpha: float) -> RGBColor:
    inv = 1.0 - alpha
    return (
        int(base[0] * inv + tint[0] * alpha),
        int(base[1] * inv + tint[1] * alpha),
        int(base[2] * inv + tint[2] * alpha),
    )


def _load_ui_font(size: int, bold: bool = False) -> pygame.font.Font:
    if _is_wasm():
        return pygame.font.Font(None, size + 4)
    try:
        return pygame.font.SysFont(
            "inter,segoeui,sfprotext,helveticaneue,dejavusans,arial",
            size,
            bold=bold,
        )
    except Exception:
        return pygame.font.Font(None, size + 4)


def _load_mono_font(size: int, bold: bool = False) -> pygame.font.Font:
    if _is_wasm():
        return pygame.font.Font(None, size + 3)
    try:
        return pygame.font.SysFont(
            "jetbrainsmono,menlo,consolas,dejavusansmono,couriernew",
            size,
            bold=bold,
        )
    except Exception:
        return pygame.font.Font(None, size + 3)


class StudioRenderer:
    """Renders the 1200x720 Studio UI and routes mouse/keyboard events to ``StudioState``."""

    def __init__(self, state: StudioState) -> None:
        self.state = state
        self.font_brand = _load_ui_font(18, bold=True)
        self.font_section = _load_ui_font(11, bold=True)
        self.font_btn = _load_ui_font(13, bold=True)
        self.font_small = _load_ui_font(12, bold=False)
        self.font_tiny = _load_ui_font(11, bold=False)
        self.font_metric = _load_mono_font(15, bold=True)
        self.font_table = _load_mono_font(11, bold=False)
        self.font_glyph = _load_ui_font(13, bold=True)

        self.buttons: list[UIButton] = []
        self.swatch_rects: list[tuple[pygame.Rect, int]] = []
        self.slider_track: pygame.Rect = pygame.Rect(928, 298, 166, 10)
        self.dragging_slider: bool = False
        self.hover_cell: Coord | None = None
        self.alert_rect: pygame.Rect | None = None

    # ------------------------------------------------------------------
    # Grid geometry
    # ------------------------------------------------------------------

    def grid_geometry(self) -> tuple[int, int, int, int, int]:
        """Return ``(origin_x, origin_y, cell_size, total_w, total_h)``."""
        rows, cols = self.state.grid.rows, self.state.grid.cols
        cell_size = max(6, min(CANVAS_INNER.width // cols, CANVAS_INNER.height // rows))
        total_w = cols * cell_size
        total_h = rows * cell_size
        origin_x = CANVAS_INNER.x + (CANVAS_INNER.width - total_w) // 2
        origin_y = CANVAS_INNER.y + (CANVAS_INNER.height - total_h) // 2
        return origin_x, origin_y, cell_size, total_w, total_h

    def pos_to_cell(self, pos: tuple[int, int]) -> Coord | None:
        ox, oy, cell_size, total_w, total_h = self.grid_geometry()
        mx, my = pos
        if mx < ox or mx >= ox + total_w or my < oy or my >= oy + total_h:
            return None
        col = (mx - ox) // cell_size
        row = (my - oy) // cell_size
        if self.state.grid.is_valid(row, col):
            return int(row), int(col)
        return None

    # ------------------------------------------------------------------
    # Dynamic button layout builder
    # ------------------------------------------------------------------

    def _build_controls(self) -> None:
        s = self.state
        self.buttons = []
        self.swatch_rects = []

        # --- Top Header Controls ---
        self.buttons.append(
            UIButton(
                pygame.Rect(272, 10, 100, 30),
                "Flood Fill",
                lambda: s.set_studio_mode("flood_fill"),
                active=s.studio_mode == "flood_fill",
            )
        )
        self.buttons.append(
            UIButton(
                pygame.Rect(376, 10, 106, 30),
                "Pathfinding",
                lambda: s.set_studio_mode("pathfinding"),
                active=s.studio_mode == "pathfinding",
            )
        )
        self.buttons.append(
            UIButton(
                pygame.Rect(502, 10, 58, 30),
                "4-Way",
                lambda: s.set_connectivity(4),
                active=s.connectivity == 4,
            )
        )
        self.buttons.append(
            UIButton(
                pygame.Rect(564, 10, 58, 30),
                "8-Way",
                lambda: s.set_connectivity(8),
                active=s.connectivity == 8,
            )
        )
        for idx, (size_key, lbl) in enumerate(
            (("small", "12x16"), ("medium", "21x31"), ("large", "31x47"))
        ):
            self.buttons.append(
                UIButton(
                    pygame.Rect(644 + idx * 64, 10, 60, 30),
                    lbl,
                    lambda k=size_key: s.set_grid_size(k),
                    active=s.grid_size_key == size_key,
                )
            )

        # --- Bottom Palette & Theme Target Controls ---
        targets: tuple[tuple[ThemeTarget, str, int], ...] = (
            ("fill", "Fill", 50),
            ("wall", "Wall", 50),
            ("path", "Path", 52),
            ("visited", "Visit", 54),
            ("start", "Start", 54),
            ("end", "End", 48),
        )
        tx = 408
        for target_key, target_label, tw in targets:
            self.buttons.append(
                UIButton(
                    pygame.Rect(tx, 628, tw, 24),
                    target_label,
                    lambda t=target_key: s.set_color_target(t),
                    active=s.active_color_target == target_key,
                )
            )
            tx += tw + 5
        self.buttons.append(
            UIButton(
                pygame.Rect(tx + 4, 628, 72, 24),
                "Reset (C)",
                s.reset_colors,
                subtle=True,
            )
        )

        sx = 28
        sy = 664
        for entry in PALETTE_ENTRIES:
            self.swatch_rects.append((pygame.Rect(sx, sy, 32, 32), entry.color_id))
            sx += 40

        # --- Right Sidebar: Tools (3x2) ---
        sx0 = 866
        tool_specs: list[tuple[ToolMode | None, str, Callable[[], None]]] = [
            ("wall", "W  Wall", lambda: s.set_tool("wall")),
            ("fill", "F  Fill", lambda: s.set_tool("fill")),
            ("erase", "E  Erase", lambda: s.set_tool("erase")),
            ("start", "S  Start", lambda: s.set_tool("start")),
            ("end", "D  End", lambda: s.set_tool("end")),
            (None, "Z  Undo", lambda: s.undo()),
        ]
        for idx, (tool_key, label, action) in enumerate(tool_specs):
            row = idx // 3
            col = idx % 3
            rect = pygame.Rect(sx0 + col * 104, 86 + row * 34, 98, 28)
            self.buttons.append(
                UIButton(
                    rect,
                    label,
                    action,
                    active=(tool_key is not None and s.tool == tool_key),
                    subtle=(tool_key is None),
                )
            )

        # --- Right Sidebar: Algorithm Selector ---
        if s.studio_mode == "flood_fill":
            algo_items = list(FLOOD_FILL_ALGORITHMS.items())
            for idx, (key, (display_name, _, _)) in enumerate(algo_items):
                row = idx // 2
                col = idx % 2
                rect = pygame.Rect(sx0 + col * 156, 174 + row * 30, 150, 26)
                self.buttons.append(
                    UIButton(
                        rect,
                        display_name,
                        lambda k=key: s.set_algorithm(k),
                        active=(s.flood_algo == key),
                    )
                )
        else:
            algo_items = list(PATHFINDING_ALGORITHMS.items())
            for idx, (key, (display_name, _, _)) in enumerate(algo_items):
                rect = pygame.Rect(sx0 + idx * 104, 174, 98, 28)
                self.buttons.append(
                    UIButton(
                        rect,
                        display_name,
                        lambda k=key: s.set_algorithm(k),
                        active=(s.path_algo == key),
                    )
                )

        # --- Right Sidebar: Playback & Speed ---
        run_label = "Pause" if s.is_running else ("Resume" if s.is_paused else "Run")
        self.buttons.append(
            UIButton(
                pygame.Rect(sx0, 254, 114, 30),
                run_label,
                s.toggle_run_pause,
                accent=ACCENT_AMBER if s.is_running else BUTTON_PRIMARY,
            )
        )
        self.buttons.append(
            UIButton(
                pygame.Rect(sx0 + 120, 254, 74, 30),
                "Step",
                lambda: s.step_once(),
            )
        )
        clear_label = "Clear Fill" if s.studio_mode == "flood_fill" else "Clear Path"
        clear_action = s.clear_regions if s.studio_mode == "flood_fill" else s.clear_search_overlay
        self.buttons.append(
            UIButton(
                pygame.Rect(sx0 + 200, 254, 106, 30),
                clear_label,
                clear_action,
                subtle=True,
            )
        )

        # Speed [-] and [+] buttons flanking slider track
        self.buttons.append(
            UIButton(pygame.Rect(sx0 + 62, 291, 24, 24), "-", lambda: s.adjust_speed(-1))
        )
        self.slider_track = pygame.Rect(sx0 + 94, 298, 178, 10)
        self.buttons.append(
            UIButton(pygame.Rect(sx0 + 280, 291, 26, 24), "+", lambda: s.adjust_speed(1))
        )

        # --- Right Sidebar: Map Presets ---
        presets_row1: tuple[tuple[PresetName, str], ...] = (
            ("multi_room", "Multi-Room"),
            ("maze", "Maze"),
            ("obstacles", "Obstacles"),
        )
        for idx, (pkey, plabel) in enumerate(presets_row1):
            self.buttons.append(
                UIButton(
                    pygame.Rect(sx0 + idx * 104, 352, 98, 26),
                    plabel,
                    lambda p=pkey: s.load_preset(p),
                )
            )
        self.buttons.append(
            UIButton(
                pygame.Rect(sx0, 384, 150, 26),
                "Spiral",
                lambda: s.load_preset("spiral"),
            )
        )
        self.buttons.append(
            UIButton(
                pygame.Rect(sx0 + 156, 384, 150, 26),
                "Reset Grid (R)",
                s.reset_grid,
                accent=BUTTON_DANGER,
            )
        )

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process one Pygame event; return False if the user requested quit."""
        s = self.state

        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            return self._handle_keydown(event.key)

        if event.type == pygame.MOUSEMOTION:
            self.hover_cell = self.pos_to_cell(event.pos)
            if self.dragging_slider:
                self._update_slider_from_x(event.pos[0])
            elif self.hover_cell is not None:
                s.drag_cell_interaction(self.hover_cell)
            return True

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging_slider = False
            s.end_cell_interaction()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            if event.button == 1:
                # Dismiss alert banner if clicked
                if self.alert_rect is not None and self.alert_rect.collidepoint(pos):
                    s.clear_alert()
                    return True

                # Slider track click/drag
                hit_slider = self.slider_track.inflate(8, 14)
                if hit_slider.collidepoint(pos):
                    self.dragging_slider = True
                    self._update_slider_from_x(pos[0])
                    return True

                # UI buttons
                for btn in self.buttons:
                    if btn.rect.collidepoint(pos):
                        btn.action()
                        return True

                # Palette swatches
                for rect, color_id in self.swatch_rects:
                    if rect.collidepoint(pos):
                        s.pick_palette_entry(color_id)
                        return True

            # Canvas cell interaction (left click uses tool; right click erases)
            if event.button in (1, 3):
                cell = self.pos_to_cell(pos)
                if cell is not None:
                    s.begin_cell_interaction(cell, button=event.button)

        return True

    def _handle_keydown(self, key: int) -> bool:
        s = self.state
        if key == pygame.K_ESCAPE:
            if _is_wasm():
                s.stop_animation()
                return True
            return False
        if key == pygame.K_SPACE:
            s.toggle_run_pause()
        elif key == pygame.K_PERIOD:
            s.step_once()
        elif key == pygame.K_TAB:
            s.toggle_studio_mode()
        elif key == pygame.K_w:
            s.set_tool("wall")
        elif key == pygame.K_f:
            s.set_tool("fill")
        elif key == pygame.K_e:
            s.set_tool("erase")
        elif key == pygame.K_s:
            s.set_tool("start")
        elif key == pygame.K_d:
            s.set_tool("end")
        elif key == pygame.K_z:
            s.undo()
        elif key == pygame.K_x:
            if s.studio_mode == "flood_fill":
                s.clear_regions()
            else:
                s.clear_search_overlay()
        elif key == pygame.K_r:
            s.reset_grid()
        elif key == pygame.K_c:
            s.reset_colors()
        elif key == pygame.K_k:
            s.set_connectivity(8 if s.connectivity == 4 else 4)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            s.adjust_speed(-1)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            s.adjust_speed(1)
        return True

    def _update_slider_from_x(self, mouse_x: int) -> None:
        rel = (mouse_x - self.slider_track.x) / max(1, self.slider_track.width)
        clamped = max(0.0, min(1.0, rel))
        idx = int(round(clamped * (len(SPEED_LEVELS) - 1)))
        self.state.set_speed_index(idx)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface) -> None:
        self._build_controls()
        mouse_pos = pygame.mouse.get_pos()

        screen.fill(BG_COLOR)
        self._draw_header(screen)
        self._draw_canvas(screen)
        self._draw_palette_bar(screen, mouse_pos)
        self._draw_sidebar(screen)

        # Draw all registered buttons cleanly
        for btn in self.buttons:
            self._draw_button(screen, btn, btn.rect.collidepoint(mouse_pos))

        # Draw speed slider on top of sidebar
        self._draw_speed_slider(screen)

        # Draw toast alert banner on top of canvas if active
        self._draw_alert_banner(screen)

    def _draw_header(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, HEADER_COLOR, (0, 0, WINDOW_WIDTH, 50))
        pygame.draw.line(screen, BORDER_SUBTLE, (0, 49), (WINDOW_WIDTH, 49), 1)

        title = self.font_brand.render("NEO FLOOD FILL", True, TEXT_PRIMARY)
        screen.blit(title, (18, 14))

        badge_rect = pygame.Rect(178, 14, 72, 22)
        pygame.draw.rect(screen, (20, 44, 66), badge_rect, border_radius=11)
        pygame.draw.rect(screen, ACCENT_CYAN, badge_rect, 1, border_radius=11)
        badge_txt = self.font_section.render("STUDIO", True, ACCENT_CYAN)
        screen.blit(badge_txt, badge_txt.get_rect(center=badge_rect.center))

        hint = self.font_tiny.render(
            "SPACE Run/Pause  |  . Step  |  TAB Mode  |  K 4/8-Way  |  R-Click Erase",
            True,
            TEXT_MUTED,
        )
        screen.blit(hint, (SIDEBAR_CARD.right - hint.get_width(), 18))

    def _draw_canvas(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, SURFACE_COLOR, CANVAS_CARD, border_radius=10)
        pygame.draw.rect(screen, BORDER_SUBTLE, CANVAS_CARD, 1, border_radius=10)

        s = self.state
        grid = s.grid
        ox, oy, cell_size, total_w, total_h = self.grid_geometry()

        # Subtle grid frame backdrop
        frame_rect = pygame.Rect(ox - 2, oy - 2, total_w + 4, total_h + 4)
        pygame.draw.rect(screen, (36, 44, 62), frame_rect, border_radius=4)

        gap = 1 if cell_size >= 14 else 0
        radius = 3 if cell_size >= 22 else (2 if cell_size >= 14 else 0)

        empty_rgb = s.theme_colors["empty"]
        wall_rgb = s.theme_colors["wall"]
        start_rgb = s.theme_colors["start"]
        end_rgb = s.theme_colors["end"]
        frontier_rgb = s.theme_colors["frontier"]
        visited_rgb = s.theme_colors["visited"]
        path_rgb = s.theme_colors["path"]

        for r in range(grid.rows):
            cy = oy + r * cell_size
            base_row = grid.base[r]
            over_row = grid.overlay[r]
            for c in range(grid.cols):
                cx = ox + c * cell_size
                bval = base_row[c]
                oval = over_row[c]

                if bval == WALL:
                    color = wall_rgb
                elif bval == EMPTY:
                    color = empty_rgb
                elif bval in PALETTE_BY_ID:
                    color = PALETTE_BY_ID[bval].rgb
                else:
                    color = (148, 163, 184)

                # Blend transient search overlay over base layer
                if oval == OVERLAY_FRONTIER:
                    color = _blend_rgb(color, frontier_rgb, 0.72)
                elif oval == OVERLAY_VISITED:
                    color = _blend_rgb(color, visited_rgb, 0.62)
                elif oval == OVERLAY_PATH:
                    color = path_rgb
                elif oval == OVERLAY_START:
                    color = start_rgb
                elif oval == OVERLAY_END:
                    color = end_rgb

                rect = pygame.Rect(cx, cy, cell_size - gap, cell_size - gap)
                pygame.draw.rect(screen, color, rect, border_radius=radius)

                if oval == OVERLAY_START and cell_size >= 16:
                    glyph = self.font_glyph.render("S", True, (10, 20, 14))
                    screen.blit(glyph, glyph.get_rect(center=rect.center))
                elif oval == OVERLAY_END and cell_size >= 16:
                    glyph = self.font_glyph.render("E", True, (255, 255, 255))
                    screen.blit(glyph, glyph.get_rect(center=rect.center))

        # Hover cell outline + coordinate readout
        if self.hover_cell is not None:
            hr, hc = self.hover_cell
            hrect = pygame.Rect(
                ox + hc * cell_size,
                oy + hr * cell_size,
                cell_size - gap,
                cell_size - gap,
            )
            pygame.draw.rect(screen, ACCENT_CYAN, hrect, 2, border_radius=radius)

            coord_label = self.font_table.render(
                f"({hr}, {hc})  tool:{s.tool}", True, TEXT_PRIMARY
            )
            chip_w = coord_label.get_width() + 14
            chip = pygame.Rect(
                CANVAS_CARD.right - chip_w - 10,
                CANVAS_CARD.bottom - 26,
                chip_w,
                20,
            )
            pygame.draw.rect(screen, (15, 23, 42), chip, border_radius=6)
            pygame.draw.rect(screen, BORDER_SUBTLE, chip, 1, border_radius=6)
            screen.blit(coord_label, coord_label.get_rect(center=chip.center))

    def _draw_palette_bar(
        self, screen: pygame.Surface, mouse_pos: tuple[int, int]
    ) -> None:
        s = self.state
        pygame.draw.rect(screen, SURFACE_COLOR, PALETTE_CARD, border_radius=10)
        pygame.draw.rect(screen, BORDER_SUBTLE, PALETTE_CARD, 1, border_radius=10)

        title = self.font_section.render("COLOR PICKER", True, TEXT_SECONDARY)
        screen.blit(title, (28, 633))

        # Show what target is currently being edited
        if s.active_color_target == "fill":
            entry = PALETTE_BY_ID[s.selected_fill_color_id]
            active_rgb = entry.rgb
            active_text = f"Paint Bucket: {entry.name}"
        else:
            active_rgb = s.theme_colors[s.active_color_target]
            active_text = f"Theme Target: {s.active_color_target.title()}"

        preview = pygame.Rect(132, 631, 18, 18)
        pygame.draw.rect(screen, active_rgb, preview, border_radius=4)
        pygame.draw.rect(screen, TEXT_PRIMARY, preview, 1, border_radius=4)
        edit_lbl = self.font_small.render(active_text, True, TEXT_PRIMARY)
        screen.blit(edit_lbl, (158, 632))

        # Swatches
        hovered_name: str | None = None
        for rect, color_id in self.swatch_rects:
            entry = PALETTE_BY_ID[color_id]
            is_selected = (
                s.active_color_target == "fill" and color_id == s.selected_fill_color_id
            ) or (
                s.active_color_target != "fill"
                and s.theme_colors[s.active_color_target] == entry.rgb
            )
            is_hovered = rect.collidepoint(mouse_pos)
            if is_hovered:
                hovered_name = entry.name

            pygame.draw.rect(screen, entry.rgb, rect, border_radius=6)
            if is_selected:
                pygame.draw.rect(screen, TEXT_PRIMARY, rect.inflate(4, 4), 2, border_radius=8)
            elif is_hovered:
                pygame.draw.rect(screen, ACCENT_CYAN, rect.inflate(2, 2), 2, border_radius=7)
            else:
                pygame.draw.rect(screen, BORDER_SUBTLE, rect, 1, border_radius=6)

        info_msg = (
            f"Swatch: {hovered_name}"
            if hovered_name
            else "Click a swatch to paint regions or recolor theme targets"
        )
        info_surf = self.font_tiny.render(info_msg, True, TEXT_SECONDARY)
        screen.blit(info_surf, (518, 673))

    def _draw_sidebar(self, screen: pygame.Surface) -> None:
        s = self.state
        pygame.draw.rect(screen, SURFACE_COLOR, SIDEBAR_CARD, border_radius=10)
        pygame.draw.rect(screen, BORDER_SUBTLE, SIDEBAR_CARD, 1, border_radius=10)

        sx0 = 866

        # Section headers
        screen.blit(self.font_section.render("TOOLS", True, TEXT_SECONDARY), (sx0, 68))

        algo_header = (
            "FLOOD FILL ALGORITHM"
            if s.studio_mode == "flood_fill"
            else "PATHFINDING ALGORITHM"
        )
        screen.blit(self.font_section.render(algo_header, True, TEXT_SECONDARY), (sx0, 156))

        if s.studio_mode == "pathfinding":
            heur = (
                "Heuristic: Manhattan (4-way)"
                if s.connectivity == 4
                else "Heuristic: Octile sqrt(2) (8-way)"
            )
            if s.path_algo == "bfs":
                heur = "Unweighted shortest path (FIFO queue)"
            elif s.path_algo == "dfs":
                heur = "Depth-first exploration (non-optimal)"
            screen.blit(self.font_tiny.render(heur, True, TEXT_MUTED), (sx0, 208))

        screen.blit(self.font_section.render("PLAYBACK & SPEED", True, TEXT_SECONDARY), (sx0, 236))
        screen.blit(
            self.font_small.render(f"Spd {s.speed_label}", True, TEXT_PRIMARY),
            (sx0, 295),
        )

        screen.blit(self.font_section.render("MAP PRESETS", True, TEXT_SECONDARY), (sx0, 334))

        # --- Live Metrics Section ---
        screen.blit(self.font_section.render("LIVE METRICS", True, TEXT_SECONDARY), (sx0, 420))
        status_colors = {
            "Ready": TEXT_SECONDARY,
            "Running": ACCENT_CYAN,
            "Paused": ACCENT_AMBER,
            "Done": ACCENT_GREEN,
            "No Path": ACCENT_AMBER,
            "Limit Hit": ACCENT_ROSE,
        }
        st_color = status_colors.get(s.status, TEXT_SECONDARY)
        st_surf = self.font_section.render(s.status.upper(), True, st_color)
        screen.blit(st_surf, (SIDEBAR_CARD.right - st_surf.get_width() - 16, 420))

        # 2x2 Metric Cards
        peak_title = "STACK DEPTH" if (s.studio_mode == "flood_fill" and s.flood_algo == "recursive_dfs") else "PEAK FRONTIER"
        if s.studio_mode == "flood_fill":
            c3_title = "CONNECTIVITY"
            c3_val = f"{s.connectivity}-Way"
        else:
            c3_title = "PATH LEN / COST"
            c3_val = (
                f"{s.live_path_length} / {s.live_path_cost:.1f}"
                if s.live_path_length > 0
                else "--"
            )

        cards = [
            ("VISITED / FILLED", f"{s.live_visited}" if s.studio_mode == "pathfinding" else f"{s.live_filled}"),
            (peak_title, f"{s.live_peak}"),
            (c3_title, c3_val),
            ("COMPUTE TIME", f"{s.live_compute_ms:.2f} ms"),
        ]
        for idx, (label, val) in enumerate(cards):
            row = idx // 2
            col = idx % 2
            crect = pygame.Rect(sx0 + col * 156, 440 + row * 46, 150, 40)
            pygame.draw.rect(screen, SURFACE_ALT, crect, border_radius=7)
            pygame.draw.rect(screen, BORDER_SUBTLE, crect, 1, border_radius=7)
            screen.blit(self.font_tiny.render(label, True, TEXT_MUTED), (crect.x + 8, crect.y + 4))
            screen.blit(self.font_metric.render(val, True, TEXT_PRIMARY), (crect.x + 8, crect.y + 18))

        # --- Recent Runs Comparison Table ---
        screen.blit(
            self.font_section.render("RECENT RUNS (COMPARE)", True, TEXT_SECONDARY),
            (sx0, 540),
        )
        table_rect = pygame.Rect(sx0, 558, 306, 136)
        pygame.draw.rect(screen, SURFACE_ALT, table_rect, border_radius=7)
        pygame.draw.rect(screen, BORDER_SUBTLE, table_rect, 1, border_radius=7)

        header_line = f"{'ALGO':<11} {'VIS':>5} {'PEAK':>4}  {'RESULT':>8}"
        screen.blit(
            self.font_table.render(header_line, True, ACCENT_CYAN),
            (table_rect.x + 10, table_rect.y + 8),
        )
        pygame.draw.line(
            screen,
            BORDER_SUBTLE,
            (table_rect.x + 8, table_rect.y + 25),
            (table_rect.right - 8, table_rect.y + 25),
            1,
        )

        if not s.run_history:
            empty_msg = self.font_tiny.render(
                "Run algorithms on the same map to compare.",
                True,
                TEXT_MUTED,
            )
            screen.blit(empty_msg, (table_rect.x + 12, table_rect.y + 40))
        else:
            for idx, rec in enumerate(s.run_history):
                short_algo = rec.algorithm.replace(" Search", "").replace("Queue ", "").replace("Iterative ", "It.").replace("Recursive ", "Rec.")
                algo_tag = f"{short_algo[:8]} {rec.connectivity}w"
                row_str = f"{algo_tag:<11} {rec.visited:>5} {rec.peak_frontier:>4}  {rec.result_value:>8}"
                row_color = TEXT_PRIMARY if idx == 0 else TEXT_SECONDARY
                screen.blit(
                    self.font_table.render(row_str, True, row_color),
                    (table_rect.x + 10, table_rect.y + 32 + idx * 24),
                )

    def _draw_speed_slider(self, screen: pygame.Surface) -> None:
        track = self.slider_track
        ratio = self.state.speed_index / max(1, len(SPEED_LEVELS) - 1)
        fill_w = int(track.width * ratio)

        pygame.draw.rect(screen, SURFACE_ALT, track, border_radius=5)
        if fill_w > 0:
            pygame.draw.rect(
                screen,
                ACCENT_CYAN,
                pygame.Rect(track.x, track.y, fill_w, track.height),
                border_radius=5,
            )
        pygame.draw.rect(screen, BORDER_SUBTLE, track, 1, border_radius=5)

        knob_x = track.x + fill_w
        knob_y = track.centery
        pygame.draw.circle(screen, TEXT_PRIMARY, (knob_x, knob_y), 8)
        pygame.draw.circle(screen, BUTTON_ACTIVE, (knob_x, knob_y), 4)

    def _draw_button(
        self, screen: pygame.Surface, btn: UIButton, hovered: bool
    ) -> None:
        if btn.accent is not None:
            bg = (
                tuple(min(255, c + 16) for c in btn.accent)
                if hovered
                else btn.accent
            )
            border = TEXT_PRIMARY if hovered else btn.accent
            txt_color = (12, 18, 28) if btn.accent in (BUTTON_PRIMARY, ACCENT_AMBER) else TEXT_PRIMARY
        elif btn.active:
            bg = BUTTON_ACTIVE
            border = BORDER_ACTIVE
            txt_color = TEXT_PRIMARY
        elif btn.subtle:
            bg = BUTTON_HOVER if hovered else SURFACE_ALT
            border = BORDER_ACTIVE if hovered else BORDER_SUBTLE
            txt_color = TEXT_PRIMARY if hovered else TEXT_SECONDARY
        else:
            bg = BUTTON_HOVER if hovered else BUTTON_BG
            border = BORDER_ACTIVE if hovered else BORDER_SUBTLE
            txt_color = TEXT_PRIMARY

        pygame.draw.rect(screen, bg, btn.rect, border_radius=6)
        pygame.draw.rect(screen, border, btn.rect, 1, border_radius=6)
        surf = self.font_btn.render(btn.label, True, txt_color)
        screen.blit(surf, surf.get_rect(center=btn.rect.center))

    def _draw_alert_banner(self, screen: pygame.Surface) -> None:
        msg = self.state.alert_message
        if not msg:
            self.alert_rect = None
            return

        if self.state.alert_level == "error":
            bg, border, fg = (69, 18, 30), ACCENT_ROSE, (255, 220, 226)
        elif self.state.alert_level == "warn":
            bg, border, fg = (66, 46, 16), ACCENT_AMBER, (254, 240, 199)
        else:
            bg, border, fg = (18, 39, 58), ACCENT_CYAN, (224, 242, 254)

        txt = self.font_small.render(msg, True, fg)
        bw = min(CANVAS_CARD.width - 36, txt.get_width() + 28)
        brect = pygame.Rect(
            CANVAS_CARD.centerx - bw // 2,
            CANVAS_CARD.y + 12,
            bw,
            30,
        )
        self.alert_rect = brect
        pygame.draw.rect(screen, bg, brect, border_radius=8)
        pygame.draw.rect(screen, border, brect, 1, border_radius=8)
        screen.blit(txt, txt.get_rect(center=brect.center))


async def run_studio(
    preset: PresetName = "multi_room",
    grid_size: str = "medium",
    max_frames: int | None = None,
) -> StudioState:
    """Launch the async Pygame Algorithm Studio (Desktop + pygbag WebAssembly)."""
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Neo Flood Fill — Interactive Algorithm Studio")
    clock = pygame.time.Clock()

    state = StudioState(grid_size_key=grid_size, preset=preset)
    renderer = StudioRenderer(state)

    running = True
    frames = 0
    while running:
        dt_ms = float(clock.tick(FPS))

        for event in pygame.event.get():
            if not renderer.handle_event(event):
                running = False
                break

        state.update(dt_ms)
        renderer.render(screen)
        pygame.display.flip()

        # Cooperative yield required by pygbag / WebAssembly event loop
        await asyncio.sleep(0)

        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False

    pygame.quit()
    return state

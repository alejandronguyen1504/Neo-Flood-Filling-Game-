"""Prior Labs–inspired Minimalist Monochrome Interactive Algorithm Studio.

Design Language ("Alabaster Paper x Obsidian Stage")
----------------------------------------------------
- Outer Studio Shell: warm alabaster (#F7F8FA) with subtle architectural dot-grid,
  pure white (#FFFFFF) cards, 1px hairline borders (#E2E5EC), and deep ink (#0B0E17)
  pill-shaped controls with 60 FPS gliding indicators and hover color interpolation.
- Main Algorithm Stage: deep obsidian (#080A10) showcase framing crisp architectural
  light-stone walls (#E4E8F2), vibrant Paint Bucket regions, radial cell-pop glow
  ripples, and a luminous Prior Labs violet-and-white shortest-path beam.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Callable

import pygame

from .algorithms import FLOOD_FILL_ALGORITHMS, PATHFINDING_ALGORITHMS
from .effects import (
    AnimKind,
    MotionEngine,
    draw_aa_circle,
    lerp_rgb,
)
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

# --- Editorial Alabaster & Ink Chrome Palette ---
APP_BG: RGBColor = (247, 248, 250)
DOT_GRID_COLOR: RGBColor = (222, 226, 236)
HEADER_BG: RGBColor = (255, 255, 255)
CARD_BG: RGBColor = (255, 255, 255)
CARD_SUBTLE: RGBColor = (244, 246, 250)
PILL_TRACK_BG: RGBColor = (238, 241, 247)
SHADOW_OUTER: RGBColor = (236, 239, 246)
SHADOW_INNER: RGBColor = (228, 232, 241)

HAIRLINE: RGBColor = (225, 229, 238)
HAIRLINE_HOVER: RGBColor = (176, 185, 204)

INK_PRIMARY: RGBColor = (11, 14, 23)
INK_MIDNIGHT: RGBColor = (17, 21, 58)  # Signature Prior Labs CTA midnight ink
INK_SECONDARY: RGBColor = (86, 96, 116)
INK_MUTED: RGBColor = (138, 148, 168)
WHITE: RGBColor = (255, 255, 255)

BTN_GHOST_BG: RGBColor = (255, 255, 255)
BTN_GHOST_HOVER: RGBColor = (241, 244, 250)
BTN_SUBTLE_BG: RGBColor = (246, 247, 251)

STATUS_RUN: RGBColor = (99, 102, 241)
STATUS_PAUSE: RGBColor = (217, 119, 6)
STATUS_DONE: RGBColor = (16, 185, 129)
STATUS_ERROR: RGBColor = (225, 29, 72)

# --- Centerpiece Obsidian Stage Palette ---
STAGE_BG: RGBColor = (8, 10, 16)
STAGE_GRID_BG: RGBColor = (24, 29, 42)
STAGE_RIM: RGBColor = (38, 45, 64)
WALL_HIGHLIGHT: RGBColor = (248, 250, 252)

BEAM_OUTER_RGBA = (124, 58, 237, 68)
BEAM_MID_RGBA = (167, 139, 250, 155)
BEAM_CORE_RGBA = (255, 255, 255, 238)

CANVAS_CARD = pygame.Rect(16, 60, 824, 550)
CANVAS_INNER = pygame.Rect(28, 72, 800, 526)
PALETTE_CARD = pygame.Rect(16, 620, 824, 86)
SIDEBAR_CARD = pygame.Rect(852, 60, 332, 646)


@dataclass
class UIButton:
    """Interactive pill/card button tracked per frame."""

    btn_id: str
    rect: pygame.Rect
    label: str
    action: Callable[[], None]
    active: bool = False
    variant: str = "ghost"  # "segment", "ghost", "primary", "amber", "danger_ghost"
    radius: int = 8


def _is_wasm() -> bool:
    return sys.platform == "emscripten"


def _load_ui_font(size: int, bold: bool = False) -> pygame.font.Font:
    if _is_wasm():
        return pygame.font.Font(None, size + 4)
    try:
        return pygame.font.SysFont(
            "inter,sfprotext,helveticaneue,segoeui,dejavusans,arial",
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
            "jetbrainsmono,sfmono,menlo,consolas,dejavusansmono,couriernew",
            size,
            bold=bold,
        )
    except Exception:
        return pygame.font.Font(None, size + 3)


def _build_dot_backdrop() -> pygame.Surface:
    """Pre-bake the subtle Prior Labs architectural dot-matrix background once."""
    surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    surf.fill(APP_BG)
    spacing = 18
    for y in range(60, WINDOW_HEIGHT, spacing):
        for x in range(12, WINDOW_WIDTH, spacing):
            surf.set_at((x, y), DOT_GRID_COLOR)
    return surf


def _draw_elevated_card(
    screen: pygame.Surface,
    rect: pygame.Rect,
    bg: RGBColor = CARD_BG,
    border: RGBColor = HAIRLINE,
    radius: int = 12,
) -> None:
    """Draw a crisp card with subtle 2-layer ambient shadow and 1px hairline border."""
    pygame.draw.rect(screen, SHADOW_OUTER, rect.move(0, 3), border_radius=radius + 1)
    pygame.draw.rect(screen, SHADOW_INNER, rect.move(0, 1), border_radius=radius)
    pygame.draw.rect(screen, bg, rect, border_radius=radius)
    pygame.draw.rect(screen, border, rect, 1, border_radius=radius)


class StudioRenderer:
    """Renders the 1200x720 Monochrome Research Studio with 60 FPS motion effects."""

    def __init__(self, state: StudioState) -> None:
        self.state = state
        self.motion = MotionEngine()

        self.font_brand = _load_ui_font(16, bold=True)
        self.font_section = _load_ui_font(10, bold=True)
        self.font_btn = _load_ui_font(12, bold=True)
        self.font_small = _load_ui_font(12, bold=False)
        self.font_tiny = _load_ui_font(11, bold=False)
        self.font_metric = _load_mono_font(15, bold=True)
        self.font_table = _load_mono_font(11, bold=False)
        self.font_glyph = _load_ui_font(12, bold=True)

        self._backdrop = _build_dot_backdrop()
        self._beam_surface = pygame.Surface(
            (CANVAS_CARD.width, CANVAS_CARD.height), pygame.SRCALPHA
        )

        self.buttons: list[UIButton] = []
        self.segment_tracks: list[tuple[str, pygame.Rect, pygame.Rect]] = []
        self.swatch_rects: list[tuple[pygame.Rect, int]] = []
        self.slider_track: pygame.Rect = pygame.Rect(946, 300, 174, 6)
        self.dragging_slider: bool = False
        self.hover_cell: Coord | None = None
        self.alert_rect: pygame.Rect | None = None
        self._last_dt_sec: float = 1.0 / 60.0

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
    # Sync visual events from StudioState into MotionEngine
    # ------------------------------------------------------------------

    def _sync_motion_events(self, dt_ms: float) -> None:
        s = self.state
        for kind, row, col, color_id in s.pop_visual_events():
            if kind == "clear":
                self.motion.clear_grid_effects()
                continue
            if row < 0 or col < 0:
                continue

            if kind == "fill":
                cid = color_id if color_id is not None else s.selected_fill_color_id
                rgb = PALETTE_BY_ID[cid].rgb if cid in PALETTE_BY_ID else (148, 163, 184)
                self.motion.trigger_cell(row, col, rgb, "fill")
            elif kind == "frontier":
                self.motion.trigger_cell(row, col, s.theme_colors["frontier"], "frontier")
            elif kind == "visit":
                self.motion.trigger_cell(row, col, s.theme_colors["visited"], "visit")
            elif kind == "path":
                self.motion.trigger_cell(row, col, s.theme_colors["path"], "path")
            elif kind == "paint":
                rgb = s.theme_colors["wall"] if color_id == WALL else (90, 100, 125)
                anim_kind: AnimKind = "paint"
                self.motion.trigger_cell(row, col, rgb, anim_kind)

        self.motion.update(dt_ms, has_toast=bool(s.alert_message))
        self._last_dt_sec = max(0.001, min(dt_ms, 80.0) / 1000.0)

    # ------------------------------------------------------------------
    # Dynamic control layout builder
    # ------------------------------------------------------------------

    def _build_controls(self) -> None:
        s = self.state
        self.buttons = []
        self.segment_tracks = []
        self.swatch_rects = []

        # --- Top Header Segmented Pill Groups ---
        mode_track = pygame.Rect(268, 9, 210, 32)
        m_ff = pygame.Rect(271, 12, 100, 26)
        m_pf = pygame.Rect(373, 12, 102, 26)
        self.segment_tracks.append(
            ("mode", mode_track, m_ff if s.studio_mode == "flood_fill" else m_pf)
        )
        self.buttons.append(
            UIButton(
                "mode_ff",
                m_ff,
                "Flood Fill",
                lambda: s.set_studio_mode("flood_fill"),
                active=s.studio_mode == "flood_fill",
                variant="segment",
                radius=13,
            )
        )
        self.buttons.append(
            UIButton(
                "mode_pf",
                m_pf,
                "Pathfinding",
                lambda: s.set_studio_mode("pathfinding"),
                active=s.studio_mode == "pathfinding",
                variant="segment",
                radius=13,
            )
        )

        conn_track = pygame.Rect(492, 9, 126, 32)
        c_4 = pygame.Rect(495, 12, 58, 26)
        c_8 = pygame.Rect(555, 12, 60, 26)
        self.segment_tracks.append(
            ("conn", conn_track, c_4 if s.connectivity == 4 else c_8)
        )
        self.buttons.append(
            UIButton(
                "conn_4",
                c_4,
                "4-Way",
                lambda: s.set_connectivity(4),
                active=s.connectivity == 4,
                variant="segment",
                radius=13,
            )
        )
        self.buttons.append(
            UIButton(
                "conn_8",
                c_8,
                "8-Way",
                lambda: s.set_connectivity(8),
                active=s.connectivity == 8,
                variant="segment",
                radius=13,
            )
        )

        size_track = pygame.Rect(632, 9, 192, 32)
        active_size_rect = pygame.Rect(635, 12, 60, 26)
        for idx, (size_key, lbl) in enumerate(
            (("small", "12x16"), ("medium", "21x31"), ("large", "31x47"))
        ):
            srect = pygame.Rect(635 + idx * 63, 12, 60, 26)
            if s.grid_size_key == size_key:
                active_size_rect = srect
            self.buttons.append(
                UIButton(
                    f"size_{size_key}",
                    srect,
                    lbl,
                    lambda k=size_key: s.set_grid_size(k),
                    active=s.grid_size_key == size_key,
                    variant="segment",
                    radius=13,
                )
            )
        self.segment_tracks.append(("size", size_track, active_size_rect))

        # --- Bottom Palette & Theme Target Pills ---
        targets: tuple[tuple[ThemeTarget, str, int], ...] = (
            ("fill", "Fill", 48),
            ("wall", "Wall", 48),
            ("path", "Path", 50),
            ("visited", "Visit", 52),
            ("start", "Start", 52),
            ("end", "End", 46),
        )
        tx = 414
        for target_key, target_label, tw in targets:
            self.buttons.append(
                UIButton(
                    f"tgt_{target_key}",
                    pygame.Rect(tx, 628, tw, 24),
                    target_label,
                    lambda t=target_key: s.set_color_target(t),
                    active=s.active_color_target == target_key,
                    radius=12,
                )
            )
            tx += tw + 5
        self.buttons.append(
            UIButton(
                "reset_colors",
                pygame.Rect(tx + 4, 628, 72, 24),
                "Reset (C)",
                s.reset_colors,
                radius=12,
            )
        )

        sx = 30
        sy = 663
        for entry in PALETTE_ENTRIES:
            self.swatch_rects.append((pygame.Rect(sx, sy, 30, 30), entry.color_id))
            sx += 39

        # --- Right Sidebar Controls (x: 868..1168, width = 300) ---
        sx0 = 868

        # 1. Tools (3x2 pills)
        tool_specs: list[tuple[str, ToolMode | None, str, Callable[[], None]]] = [
            ("tool_wall", "wall", "W  Wall", lambda: s.set_tool("wall")),
            ("tool_fill", "fill", "F  Fill", lambda: s.set_tool("fill")),
            ("tool_erase", "erase", "E  Erase", lambda: s.set_tool("erase")),
            ("tool_start", "start", "S  Start", lambda: s.set_tool("start")),
            ("tool_end", "end", "D  End", lambda: s.set_tool("end")),
            ("tool_undo", None, "Z  Undo", lambda: s.undo()),
        ]
        for idx, (bid, tool_key, label, action) in enumerate(tool_specs):
            row = idx // 3
            col = idx % 3
            rect = pygame.Rect(sx0 + col * 102, 86 + row * 33, 96, 27)
            self.buttons.append(
                UIButton(
                    bid,
                    rect,
                    label,
                    action,
                    active=(tool_key is not None and s.tool == tool_key),
                    radius=13,
                )
            )

        # 2. Algorithm Selector
        if s.studio_mode == "flood_fill":
            algo_items = list(FLOOD_FILL_ALGORITHMS.items())
            for idx, (key, (display_name, _, _)) in enumerate(algo_items):
                row = idx // 2
                col = idx % 2
                rect = pygame.Rect(sx0 + col * 153, 174 + row * 30, 147, 26)
                self.buttons.append(
                    UIButton(
                        f"algo_ff_{key}",
                        rect,
                        display_name,
                        lambda k=key: s.set_algorithm(k),
                        active=(s.flood_algo == key),
                        radius=13,
                    )
                )
        else:
            algo_items = list(PATHFINDING_ALGORITHMS.items())
            for idx, (key, (display_name, _, _)) in enumerate(algo_items):
                rect = pygame.Rect(sx0 + idx * 102, 174, 96, 28)
                self.buttons.append(
                    UIButton(
                        f"algo_pf_{key}",
                        rect,
                        display_name,
                        lambda k=key: s.set_algorithm(k),
                        active=(s.path_algo == key),
                        radius=14,
                    )
                )

        # 3. Playback & Speed
        if s.is_running:
            run_label, run_variant = "Pause ||", "amber"
        elif s.is_paused:
            run_label, run_variant = "Resume ->", "primary"
        else:
            run_label, run_variant = "Run ->", "primary"

        self.buttons.append(
            UIButton(
                "btn_run",
                pygame.Rect(sx0, 254, 114, 30),
                run_label,
                s.toggle_run_pause,
                variant=run_variant,
                radius=15,
            )
        )
        self.buttons.append(
            UIButton(
                "btn_step",
                pygame.Rect(sx0 + 120, 254, 72, 30),
                "Step",
                lambda: s.step_once(),
                radius=15,
            )
        )
        clear_label = "Clear Fill" if s.studio_mode == "flood_fill" else "Clear Path"
        clear_action = s.clear_regions if s.studio_mode == "flood_fill" else s.clear_search_overlay
        self.buttons.append(
            UIButton(
                "btn_clear",
                pygame.Rect(sx0 + 198, 254, 102, 30),
                clear_label,
                clear_action,
                radius=15,
            )
        )

        self.buttons.append(
            UIButton(
                "spd_down",
                pygame.Rect(sx0 + 62, 292, 24, 22),
                "-",
                lambda: s.adjust_speed(-1),
                radius=11,
            )
        )
        self.slider_track = pygame.Rect(sx0 + 95, 300, 172, 6)
        self.buttons.append(
            UIButton(
                "spd_up",
                pygame.Rect(sx0 + 276, 292, 24, 22),
                "+",
                lambda: s.adjust_speed(1),
                radius=11,
            )
        )

        # 4. Map Presets
        presets_row1: tuple[tuple[PresetName, str], ...] = (
            ("multi_room", "Multi-Room"),
            ("maze", "Maze"),
            ("obstacles", "Obstacles"),
        )
        for idx, (pkey, plabel) in enumerate(presets_row1):
            self.buttons.append(
                UIButton(
                    f"preset_{pkey}",
                    pygame.Rect(sx0 + idx * 102, 352, 96, 26),
                    plabel,
                    lambda p=pkey: s.load_preset(p),
                    radius=13,
                )
            )
        self.buttons.append(
            UIButton(
                "preset_spiral",
                pygame.Rect(sx0, 384, 147, 26),
                "Spiral",
                lambda: s.load_preset("spiral"),
                radius=13,
            )
        )
        self.buttons.append(
            UIButton(
                "preset_reset",
                pygame.Rect(sx0 + 153, 384, 147, 26),
                "Reset Grid (R)",
                s.reset_grid,
                variant="danger_ghost",
                radius=13,
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
                if self.alert_rect is not None and self.alert_rect.collidepoint(pos):
                    s.clear_alert()
                    return True

                if self.slider_track.inflate(10, 16).collidepoint(pos):
                    self.dragging_slider = True
                    self._update_slider_from_x(pos[0])
                    return True

                for btn in self.buttons:
                    if btn.rect.collidepoint(pos):
                        btn.action()
                        return True

                for rect, color_id in self.swatch_rects:
                    if rect.inflate(4, 4).collidepoint(pos):
                        s.pick_palette_entry(color_id)
                        return True

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
    # Master render pipeline
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface, dt_ms: float = 16.6) -> None:
        self._sync_motion_events(dt_ms)
        self._build_controls()
        mouse_pos = pygame.mouse.get_pos()

        # 1. Alabaster architectural dot-matrix backdrop
        screen.blit(self._backdrop, (0, 0))

        # 2. Top editorial header + segmented pill tracks
        self._draw_header(screen)

        # 3. Obsidian showcase canvas + animated cells + luminous path beam
        self._draw_stage(screen)

        # 4. Minimalist white palette bar & right sidebar
        self._draw_palette_bar(screen, mouse_pos)
        self._draw_sidebar(screen)

        # 5. Segmented pill tracks & gliding ink indicators
        for group_id, track_rect, active_rect in self.segment_tracks:
            pygame.draw.rect(screen, PILL_TRACK_BG, track_rect, border_radius=16)
            pygame.draw.rect(screen, HAIRLINE, track_rect, 1, border_radius=16)
            glide_rect = self.motion.sync_pill(group_id, active_rect)
            pygame.draw.rect(screen, INK_PRIMARY, glide_rect, border_radius=13)

        # 6. All buttons with smooth hover color interpolation
        for btn in self.buttons:
            h_weight = self.motion.update_hover(
                btn.btn_id, btn.rect.collidepoint(mouse_pos), self._last_dt_sec
            )
            self._draw_button(screen, btn, h_weight)

        # 7. Speed slider
        self._draw_speed_slider(screen)

        # 8. Smooth slide-and-fade toast banner
        self._draw_alert_banner(screen)

    def _draw_header(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, HEADER_BG, (0, 0, WINDOW_WIDTH, 50))
        pygame.draw.line(screen, HAIRLINE, (0, 49), (WINDOW_WIDTH, 49), 1)

        # Minimalist geometric Prior Labs-style striped emblem
        mark = pygame.Rect(18, 15, 20, 20)
        pygame.draw.rect(screen, INK_MIDNIGHT, mark, border_radius=4)
        for stripe_y in (18, 22, 26, 30):
            pygame.draw.line(screen, WHITE, (21, stripe_y), (34, stripe_y), 1)

        title = self.font_brand.render("NEO FLOOD FILL", True, INK_PRIMARY)
        screen.blit(title, (46, 16))

        badge_rect = pygame.Rect(190, 14, 64, 21)
        pygame.draw.rect(screen, CARD_SUBTLE, badge_rect, border_radius=11)
        pygame.draw.rect(screen, HAIRLINE_HOVER, badge_rect, 1, border_radius=11)
        badge_txt = self.font_section.render("STUDIO", True, INK_MIDNIGHT)
        screen.blit(badge_txt, badge_txt.get_rect(center=badge_rect.center))

        hint = self.font_tiny.render(
            "SPACE Run   . Step   TAB Mode   K 4/8w   R-Click Erase",
            True,
            INK_MUTED,
        )
        screen.blit(hint, (SIDEBAR_CARD.right - hint.get_width(), 19))

    def _draw_stage(self, screen: pygame.Surface) -> None:
        # Soft elevation shadow + deep Obsidian Showcase Frame
        pygame.draw.rect(
            screen, (218, 223, 235), CANVAS_CARD.move(0, 4), border_radius=15
        )
        pygame.draw.rect(
            screen, (229, 233, 242), CANVAS_CARD.move(0, 2), border_radius=14
        )
        pygame.draw.rect(screen, STAGE_BG, CANVAS_CARD, border_radius=14)
        pygame.draw.rect(screen, STAGE_RIM, CANVAS_CARD, 1, border_radius=14)

        s = self.state
        grid = s.grid
        ox, oy, cell_size, total_w, total_h = self.grid_geometry()

        # Crisp 1px inner grid frame
        frame_rect = pygame.Rect(ox - 2, oy - 2, total_w + 4, total_h + 4)
        pygame.draw.rect(screen, STAGE_GRID_BG, frame_rect, border_radius=5)
        pygame.draw.rect(screen, (34, 41, 59), frame_rect, 1, border_radius=5)

        gap = 1 if cell_size >= 13 else 0
        draw_size = max(1, cell_size - gap)
        radius = 4 if cell_size >= 22 else (2 if cell_size >= 14 else 0)

        empty_rgb = s.theme_colors["empty"]
        wall_rgb = s.theme_colors["wall"]
        start_rgb = s.theme_colors["start"]
        end_rgb = s.theme_colors["end"]
        frontier_rgb = s.theme_colors["frontier"]
        visited_rgb = s.theme_colors["visited"]
        path_rgb = s.theme_colors["path"]

        pulse = self.motion.pulse_phase(1900.0)
        glow_overlays: list[tuple[pygame.Surface, tuple[int, int]]] = []

        for r in range(grid.rows):
            cy = oy + r * cell_size
            base_row = grid.base[r]
            over_row = grid.overlay[r]
            for c in range(grid.cols):
                cx = ox + c * cell_size
                bval = base_row[c]
                oval = over_row[c]

                # Base background slot so scaled pop-in cells reveal obsidian slot beneath
                slot_rect = pygame.Rect(cx, cy, draw_size, draw_size)
                if bval == WALL:
                    color = wall_rgb
                elif bval == EMPTY:
                    color = empty_rgb
                elif bval in PALETTE_BY_ID:
                    color = PALETTE_BY_ID[bval].rgb
                else:
                    color = (148, 163, 184)

                if oval == OVERLAY_FRONTIER:
                    color = lerp_rgb(color, frontier_rgb, 0.85)
                elif oval == OVERLAY_VISITED:
                    color = lerp_rgb(color, visited_rgb, 0.56)
                elif oval == OVERLAY_PATH:
                    color = lerp_rgb(color, path_rgb, 0.78)
                elif oval == OVERLAY_START:
                    color = start_rgb
                elif oval == OVERLAY_END:
                    color = end_rgb

                anim = self.motion.cell_anims.get((r, c))
                if anim is not None and oval not in (OVERLAY_START, OVERLAY_END):
                    pygame.draw.rect(screen, empty_rgb, slot_rect, border_radius=radius)
                    scale = anim.scale()
                    scaled_w = max(2, min(draw_size + 2, int(round(draw_size * scale))))
                    anim_rect = pygame.Rect(0, 0, scaled_w, scaled_w)
                    anim_rect.center = slot_rect.center
                    pygame.draw.rect(screen, color, anim_rect, border_radius=radius)

                    g_strength = anim.glow_strength()
                    if g_strength > 0.08 and cell_size >= 12:
                        glow_r = max(8, int(cell_size * 0.95))
                        stamp = self.motion.glow_cache.get(glow_r, anim.color)
                        stamp_copy = stamp.copy()
                        stamp_copy.set_alpha(int(190 * g_strength))
                        glow_overlays.append(
                            (
                                stamp_copy,
                                (
                                    slot_rect.centerx - stamp_copy.get_width() // 2,
                                    slot_rect.centery - stamp_copy.get_height() // 2,
                                ),
                            )
                        )
                else:
                    pygame.draw.rect(screen, color, slot_rect, border_radius=radius)
                    if bval == WALL and oval == OVERLAY_NONE and cell_size >= 16:
                        # Subtle top architectural bevel on light stone walls
                        pygame.draw.line(
                            screen,
                            WALL_HIGHLIGHT,
                            (slot_rect.x + 2, slot_rect.y + 1),
                            (slot_rect.right - 3, slot_rect.y + 1),
                            1,
                        )

                # Ambient beacon halo + crisp S/E badge
                if oval in (OVERLAY_START, OVERLAY_END):
                    beacon_rgb = start_rgb if oval == OVERLAY_START else end_rgb
                    halo_r = max(10, int(cell_size * (0.85 + 0.22 * pulse)))
                    halo = self.motion.glow_cache.get(halo_r, beacon_rgb)
                    halo_pos = (
                        slot_rect.centerx - halo.get_width() // 2,
                        slot_rect.centery - halo.get_height() // 2,
                    )
                    glow_overlays.append((halo, halo_pos))
                    if cell_size >= 15:
                        glyph_char = "S" if oval == OVERLAY_START else "E"
                        glyph = self.font_glyph.render(glyph_char, True, WHITE)
                        screen.blit(glyph, glyph.get_rect(center=slot_rect.center))

        # Blit radial cell-pop & beacon halos
        for glow_surf, gpos in glow_overlays:
            screen.blit(glow_surf, gpos)

        # Render Prior Labs Luminous Shortest-Path Beam on top of cells
        self._draw_luminous_path_beam(screen, ox, oy, cell_size, draw_size)

        # Crisp minimal crosshair focus ring on hovered cell
        if self.hover_cell is not None:
            hr, hc = self.hover_cell
            hrect = pygame.Rect(
                ox + hc * cell_size,
                oy + hr * cell_size,
                draw_size,
                draw_size,
            )
            pygame.draw.rect(screen, WHITE, hrect.inflate(2, 2), 2, border_radius=radius + 1)

            coord_label = self.font_table.render(
                f"({hr}, {hc})  {s.tool.upper()}", True, WHITE
            )
            chip_w = coord_label.get_width() + 16
            chip = pygame.Rect(
                CANVAS_CARD.right - chip_w - 12,
                CANVAS_CARD.bottom - 28,
                chip_w,
                20,
            )
            pygame.draw.rect(screen, (18, 23, 36), chip, border_radius=10)
            pygame.draw.rect(screen, (62, 74, 102), chip, 1, border_radius=10)
            screen.blit(coord_label, coord_label.get_rect(center=chip.center))

    def _draw_luminous_path_beam(
        self,
        screen: pygame.Surface,
        ox: int,
        oy: int,
        cell_size: int,
        draw_size: int,
    ) -> None:
        chain = self.motion.path_chain
        if len(chain) < 2:
            return

        self._beam_surface.fill((0, 0, 0, 0))
        pts: list[tuple[int, int]] = [
            (
                ox + c * cell_size + draw_size // 2 - CANVAS_CARD.x,
                oy + r * cell_size + draw_size // 2 - CANVAS_CARD.y,
            )
            for r, c in chain
        ]

        w_outer = max(6, int(cell_size * 0.62))
        w_mid = max(4, int(cell_size * 0.34))
        w_core = max(2, cell_size // 7)

        pygame.draw.lines(self._beam_surface, BEAM_OUTER_RGBA, False, pts, w_outer)
        pygame.draw.lines(self._beam_surface, BEAM_MID_RGBA, False, pts, w_mid)
        pygame.draw.lines(self._beam_surface, BEAM_CORE_RGBA, False, pts, w_core)

        # Smooth rounded joints along beam turns
        for px, py in pts:
            pygame.draw.circle(self._beam_surface, BEAM_MID_RGBA, (px, py), max(2, w_mid // 2))
            pygame.draw.circle(self._beam_surface, BEAM_CORE_RGBA, (px, py), max(1, w_core // 2))

        # Animated energy spark gliding continuously from Start -> End
        seg_count = len(pts) - 1
        spark_pos = (self.motion.clock_ms / 42.0) % max(1, seg_count)
        seg_idx = min(seg_count - 1, int(spark_pos))
        frac = spark_pos - seg_idx
        x1, y1 = pts[seg_idx]
        x2, y2 = pts[seg_idx + 1]
        sx = int(x1 + (x2 - x1) * frac)
        sy = int(y1 + (y2 - y1) * frac)
        pygame.draw.circle(self._beam_surface, (196, 181, 253, 150), (sx, sy), max(5, cell_size // 3))
        pygame.draw.circle(self._beam_surface, (255, 255, 255, 255), (sx, sy), max(2, cell_size // 6))

        screen.blit(self._beam_surface, CANVAS_CARD.topleft)

    def _draw_palette_bar(
        self, screen: pygame.Surface, mouse_pos: tuple[int, int]
    ) -> None:
        s = self.state
        _draw_elevated_card(screen, PALETTE_CARD, radius=12)

        title = self.font_section.render("PALETTE", True, INK_MUTED)
        screen.blit(title, (30, 634))

        if s.active_color_target == "fill":
            entry = PALETTE_BY_ID[s.selected_fill_color_id]
            active_rgb = entry.rgb
            active_text = f"Bucket · {entry.name}"
        else:
            active_rgb = s.theme_colors[s.active_color_target]
            active_text = f"Theme · {s.active_color_target.title()}"

        preview = pygame.Rect(98, 631, 16, 16)
        pygame.draw.rect(screen, active_rgb, preview, border_radius=5)
        pygame.draw.rect(screen, INK_PRIMARY, preview, 1, border_radius=5)
        edit_lbl = self.font_small.render(active_text, True, INK_PRIMARY)
        screen.blit(edit_lbl, (122, 631))

        hovered_name: str | None = None
        for rect, color_id in self.swatch_rects:
            entry = PALETTE_BY_ID[color_id]
            is_selected = (
                s.active_color_target == "fill" and color_id == s.selected_fill_color_id
            ) or (
                s.active_color_target != "fill"
                and s.theme_colors[s.active_color_target] == entry.rgb
            )
            is_hovered = rect.inflate(4, 4).collidepoint(mouse_pos)
            if is_hovered:
                hovered_name = entry.name

            h_w = self.motion.update_hover(f"sw_{color_id}", is_hovered, self._last_dt_sec)
            lift = int(round(2.0 * h_w))
            draw_rect = rect.move(0, -lift)

            pygame.draw.rect(screen, entry.rgb, draw_rect, border_radius=8)
            pygame.draw.rect(screen, (0, 0, 0, 25), draw_rect, 1, border_radius=8)
            if is_selected:
                ring = draw_rect.inflate(6, 6)
                pygame.draw.rect(screen, INK_PRIMARY, ring, 2, border_radius=10)
            elif h_w > 0.1:
                ring = draw_rect.inflate(4, 4)
                pygame.draw.rect(
                    screen,
                    lerp_rgb(HAIRLINE, INK_PRIMARY, h_w),
                    ring,
                    1,
                    border_radius=9,
                )

        info_msg = (
            f"Swatch: {hovered_name}"
            if hovered_name
            else "Select a region tone or customize stage colors"
        )
        info_surf = self.font_tiny.render(info_msg, True, INK_MUTED)
        screen.blit(info_surf, (510, 672))

    def _draw_sidebar(self, screen: pygame.Surface) -> None:
        s = self.state
        _draw_elevated_card(screen, SIDEBAR_CARD, radius=12)
        sx0 = 868

        screen.blit(self.font_section.render("TOOLS", True, INK_MUTED), (sx0, 69))

        algo_header = (
            "FLOOD FILL ENGINE"
            if s.studio_mode == "flood_fill"
            else "PATHFINDING ENGINE"
        )
        screen.blit(self.font_section.render(algo_header, True, INK_MUTED), (sx0, 157))

        if s.studio_mode == "pathfinding":
            if s.path_algo == "astar":
                heur = (
                    "Admissible Manhattan (4-way)"
                    if s.connectivity == 4
                    else "Admissible Octile sqrt(2) (8-way)"
                )
            elif s.path_algo == "bfs":
                heur = "FIFO wavefront · guaranteed shortest hops"
            else:
                heur = "LIFO stack · non-optimal contrast baseline"
            screen.blit(self.font_tiny.render(heur, True, INK_MUTED), (sx0 + 2, 208))

        screen.blit(self.font_section.render("PLAYBACK & SPEED", True, INK_MUTED), (sx0, 237))
        screen.blit(
            self.font_small.render(f"{s.speed_label}", True, INK_PRIMARY),
            (sx0 + 2, 295),
        )

        screen.blit(self.font_section.render("STAGE PRESETS", True, INK_MUTED), (sx0, 335))

        # Hairline divider before telemetry
        pygame.draw.line(screen, HAIRLINE, (sx0, 418), (sx0 + 300, 418), 1)

        # --- Live Telemetry Section ---
        screen.blit(self.font_section.render("TELEMETRY", True, INK_MUTED), (sx0, 425))

        status_palette = {
            "Ready": (INK_SECONDARY, PILL_TRACK_BG),
            "Running": (STATUS_RUN, (238, 242, 255)),
            "Paused": (STATUS_PAUSE, (254, 243, 199)),
            "Done": (STATUS_DONE, (209, 250, 229)),
            "No Path": (STATUS_PAUSE, (254, 243, 199)),
            "Limit Hit": (STATUS_ERROR, (255, 228, 230)),
        }
        st_fg, st_bg = status_palette.get(s.status, (INK_SECONDARY, PILL_TRACK_BG))
        st_surf = self.font_section.render(s.status.upper(), True, st_fg)
        st_pill = pygame.Rect(
            sx0 + 300 - (st_surf.get_width() + 16),
            422,
            st_surf.get_width() + 16,
            18,
        )
        pygame.draw.rect(screen, st_bg, st_pill, border_radius=9)
        screen.blit(st_surf, st_surf.get_rect(center=st_pill.center))

        # Smooth rolling counters
        raw_vis = float(s.live_visited if s.studio_mode == "pathfinding" else s.live_filled)
        disp_vis = int(round(self.motion.smooth_metric("vis", raw_vis, self._last_dt_sec)))
        disp_peak = int(
            round(self.motion.smooth_metric("peak", float(s.live_peak), self._last_dt_sec))
        )

        peak_title = (
            "STACK DEPTH"
            if (s.studio_mode == "flood_fill" and s.flood_algo == "recursive_dfs")
            else "PEAK FRONTIER"
        )
        if s.studio_mode == "flood_fill":
            c3_title = "CONNECTIVITY"
            c3_val = f"{s.connectivity}-Way"
        else:
            c3_title = "PATH / COST"
            c3_val = (
                f"{s.live_path_length} / {s.live_path_cost:.1f}"
                if s.live_path_length > 0
                else "--"
            )

        cards = [
            ("VISITED" if s.studio_mode == "pathfinding" else "CELLS FILLED", f"{disp_vis}"),
            (peak_title, f"{disp_peak}"),
            (c3_title, c3_val),
            ("COMPUTE TIME", f"{s.live_compute_ms:.2f} ms"),
        ]
        for idx, (label, val) in enumerate(cards):
            row = idx // 2
            col = idx % 2
            crect = pygame.Rect(sx0 + col * 153, 444 + row * 45, 147, 39)
            pygame.draw.rect(screen, CARD_SUBTLE, crect, border_radius=8)
            pygame.draw.rect(screen, HAIRLINE, crect, 1, border_radius=8)
            screen.blit(self.font_section.render(label, True, INK_MUTED), (crect.x + 9, crect.y + 5))
            screen.blit(self.font_metric.render(val, True, INK_PRIMARY), (crect.x + 9, crect.y + 18))

        # --- Minimalist Monochrome Recent Runs Table ---
        screen.blit(
            self.font_section.render("RECENT RUNS", True, INK_MUTED),
            (sx0, 542),
        )
        table_rect = pygame.Rect(sx0, 559, 300, 134)
        pygame.draw.rect(screen, CARD_SUBTLE, table_rect, border_radius=8)
        pygame.draw.rect(screen, HAIRLINE, table_rect, 1, border_radius=8)

        header_line = f"{'ALGO':<11} {'VIS':>5} {'PEAK':>4}  {'RESULT':>8}"
        screen.blit(
            self.font_table.render(header_line, True, INK_SECONDARY),
            (table_rect.x + 10, table_rect.y + 8),
        )
        pygame.draw.line(
            screen,
            HAIRLINE,
            (table_rect.x + 8, table_rect.y + 25),
            (table_rect.right - 8, table_rect.y + 25),
            1,
        )

        if not s.run_history:
            empty_msg = self.font_tiny.render(
                "Execute runs on the same map to compare.",
                True,
                INK_MUTED,
            )
            screen.blit(empty_msg, (table_rect.x + 12, table_rect.y + 42))
        else:
            for idx, rec in enumerate(s.run_history):
                short_algo = (
                    rec.algorithm.replace(" Search", "")
                    .replace("Queue ", "")
                    .replace("Iterative ", "It.")
                    .replace("Recursive ", "Rec.")
                )
                algo_tag = f"{short_algo[:8]} {rec.connectivity}w"
                row_str = f"{algo_tag:<11} {rec.visited:>5} {rec.peak_frontier:>4}  {rec.result_value:>8}"
                ry = table_rect.y + 31 + idx * 24
                if idx == 0:
                    hi = pygame.Rect(table_rect.x + 4, ry - 2, table_rect.width - 8, 20)
                    pygame.draw.rect(screen, WHITE, hi, border_radius=5)
                    pygame.draw.rect(screen, HAIRLINE, hi, 1, border_radius=5)
                row_color = INK_PRIMARY if idx == 0 else INK_SECONDARY
                screen.blit(
                    self.font_table.render(row_str, True, row_color),
                    (table_rect.x + 10, ry + 1),
                )

    def _draw_speed_slider(self, screen: pygame.Surface) -> None:
        track = self.slider_track
        ratio = self.state.speed_index / max(1, len(SPEED_LEVELS) - 1)
        fill_w = int(track.width * ratio)

        pygame.draw.rect(screen, PILL_TRACK_BG, track, border_radius=3)
        if fill_w > 0:
            pygame.draw.rect(
                screen,
                INK_PRIMARY,
                pygame.Rect(track.x, track.y, fill_w, track.height),
                border_radius=3,
            )

        knob_x = track.x + fill_w
        knob_y = track.centery
        draw_aa_circle(screen, (knob_x, knob_y), 7, INK_PRIMARY)
        draw_aa_circle(screen, (knob_x, knob_y), 3, WHITE)

    def _draw_button(
        self, screen: pygame.Surface, btn: UIButton, hover_t: float
    ) -> None:
        if btn.variant == "segment":
            # Background is already drawn by the gliding ink pill!
            txt_color = (
                WHITE
                if btn.active
                else lerp_rgb(INK_SECONDARY, INK_PRIMARY, hover_t)
            )
            surf = self.font_btn.render(btn.label, True, txt_color)
            screen.blit(surf, surf.get_rect(center=btn.rect.center))
            return

        if btn.variant == "primary":
            bg = lerp_rgb(INK_MIDNIGHT, (35, 43, 108), hover_t)
            border = bg
            txt_color = WHITE
        elif btn.variant == "amber":
            bg = lerp_rgb(STATUS_PAUSE, (234, 138, 20), hover_t)
            border = bg
            txt_color = WHITE
        elif btn.variant == "danger_ghost":
            bg = lerp_rgb(BTN_SUBTLE_BG, (255, 241, 242), hover_t)
            border = lerp_rgb(HAIRLINE, (244, 63, 94), hover_t)
            txt_color = lerp_rgb(INK_SECONDARY, STATUS_ERROR, hover_t)
        elif btn.active:
            bg = INK_PRIMARY
            border = INK_PRIMARY
            txt_color = WHITE
        else:
            bg = lerp_rgb(BTN_GHOST_BG, BTN_GHOST_HOVER, hover_t)
            border = lerp_rgb(HAIRLINE, HAIRLINE_HOVER, hover_t)
            txt_color = lerp_rgb(INK_SECONDARY, INK_PRIMARY, hover_t)

        pygame.draw.rect(screen, bg, btn.rect, border_radius=btn.radius)
        pygame.draw.rect(screen, border, btn.rect, 1, border_radius=btn.radius)
        surf = self.font_btn.render(btn.label, True, txt_color)
        screen.blit(surf, surf.get_rect(center=btn.rect.center))

    def _draw_alert_banner(self, screen: pygame.Surface) -> None:
        msg = self.state.alert_message
        vis = self.motion.toast_vis
        if not msg and vis < 0.05:
            self.alert_rect = None
            return
        if not msg:
            return

        if self.state.alert_level == "error":
            accent, fg = STATUS_ERROR, WHITE
        elif self.state.alert_level == "warn":
            accent, fg = (251, 191, 36), WHITE
        else:
            accent, fg = (167, 139, 250), WHITE

        txt = self.font_small.render(msg, True, fg)
        bw = min(CANVAS_CARD.width - 40, txt.get_width() + 34)
        slide_offset = int(round((1.0 - vis) * -8.0))
        brect = pygame.Rect(
            CANVAS_CARD.centerx - bw // 2,
            CANVAS_CARD.y + 14 + slide_offset,
            bw,
            30,
        )
        self.alert_rect = brect

        pygame.draw.rect(screen, (17, 21, 34), brect, border_radius=15)
        pygame.draw.rect(screen, accent, brect, 1, border_radius=15)
        dot_pos = (brect.x + 13, brect.centery)
        draw_aa_circle(screen, dot_pos, 3, accent)
        screen.blit(txt, (brect.x + 23, brect.centery - txt.get_height() // 2))


async def run_studio(
    preset: PresetName = "multi_room",
    grid_size: str = "medium",
    max_frames: int | None = None,
) -> StudioState:
    """Launch the async Pygame Algorithm Studio (Desktop + pygbag WebAssembly)."""
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Neo Flood Fill — Minimalist Research Studio")
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
        renderer.render(screen, dt_ms=dt_ms)
        pygame.display.flip()

        await asyncio.sleep(0)

        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False

    pygame.quit()
    return state

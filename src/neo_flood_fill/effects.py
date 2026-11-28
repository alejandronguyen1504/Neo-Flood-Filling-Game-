"""60 FPS motion, easing, sliding-pill, and luminous glow engine (Desktop + WASM safe).

Pure Python + Pygame primitives with O(active_animations) frame cost so idle frames
consume ~0 ms and WebAssembly bundles remain ~35 KB with zero external dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pygame

try:
    from pygame import gfxdraw as _gfxdraw
except Exception:  # pragma: no cover - fallback if gfxdraw unavailable
    _gfxdraw = None

RGBColor = tuple[int, int, int]
Coord = tuple[int, int]
AnimKind = Literal["fill", "frontier", "visit", "path", "paint"]


# ---------------------------------------------------------------------------
# Mathematical easing & interpolation functions
# ---------------------------------------------------------------------------


def clamp01(value: float) -> float:
    """Clamp ``value`` into the closed interval ``[0.0, 1.0]``."""
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def ease_out_cubic(t: float) -> float:
    """Smooth deceleration curve ``1 - (1 - t)^3``."""
    u = 1.0 - clamp01(t)
    return 1.0 - u * u * u


def ease_out_back(t: float, overshoot: float = 1.28) -> float:
    """Subtle spring-overshoot curve for tactile cell pop-in."""
    x = clamp01(t) - 1.0
    return 1.0 + (overshoot + 1.0) * (x * x * x) + overshoot * (x * x)


def ease_in_out_sine(t: float) -> float:
    """Gentle sinusoidal curve used for ambient beacon breathing."""
    return 0.5 * (1.0 - math.cos(math.pi * clamp01(t)))


def exp_lerp(current: float, target: float, speed: float, dt_sec: float) -> float:
    """Framerate-independent exponential smoothing toward ``target``."""
    if dt_sec <= 0.0:
        return current
    factor = 1.0 - math.exp(-speed * min(dt_sec, 0.1))
    res = current + (target - current) * factor
    return target if abs(target - res) < 0.05 else res


def lerp_rgb(a: RGBColor, b: RGBColor, t: float) -> RGBColor:
    """Linearly interpolate between two RGB colors."""
    k = clamp01(t)
    inv = 1.0 - k
    return (
        int(a[0] * inv + b[0] * k),
        int(a[1] * inv + b[1] * k),
        int(a[2] * inv + b[2] * k),
    )


# ---------------------------------------------------------------------------
# Anti-aliased drawing & cached glow stamps
# ---------------------------------------------------------------------------


def draw_aa_circle(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    color: RGBColor,
) -> None:
    """Draw an anti-aliased filled circle using ``gfxdraw`` when available."""
    if radius <= 0:
        return
    cx, cy = center
    if _gfxdraw is not None:
        _gfxdraw.aacircle(surface, cx, cy, radius, color)
        _gfxdraw.filled_circle(surface, cx, cy, radius, color)
    else:
        pygame.draw.circle(surface, color, center, radius)


class GlowCache:
    """Caches small radial alpha glow surfaces keyed by ``(radius, rgb)``."""

    def __init__(self, max_entries: int = 96) -> None:
        self.max_entries = max_entries
        self._cache: dict[tuple[int, RGBColor], pygame.Surface] = {}

    def get(self, radius: int, color: RGBColor) -> pygame.Surface:
        quantized_r = max(4, min(64, (radius // 2) * 2))
        key = (quantized_r, color)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if len(self._cache) >= self.max_entries:
            self._cache.clear()

        diameter = quantized_r * 2
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        steps = 6
        for i in range(steps, 0, -1):
            frac = i / steps
            r_step = max(1, int(quantized_r * frac))
            alpha = int(58 * ((1.0 - frac + (1.0 / steps)) ** 1.8))
            pygame.draw.circle(
                surf,
                (color[0], color[1], color[2], alpha),
                (quantized_r, quantized_r),
                r_step,
            )
        self._cache[key] = surf
        return surf


# ---------------------------------------------------------------------------
# Active cell pop/ripple & UI sliding-pill trackers
# ---------------------------------------------------------------------------


@dataclass
class CellAnim:
    """Per-cell pop and luminous halo state."""

    kind: AnimKind
    color: RGBColor
    age_ms: float = 0.0
    duration_ms: float = 200.0

    @property
    def progress(self) -> float:
        return clamp01(self.age_ms / max(1.0, self.duration_ms))

    def scale(self) -> float:
        p = self.progress
        if self.kind in ("path", "paint"):
            return 0.42 + 0.58 * ease_out_back(p, overshoot=1.25)
        return 0.36 + 0.64 * ease_out_cubic(p)

    def glow_strength(self) -> float:
        return (1.0 - self.progress) ** 1.6


@dataclass
class SlidingPill:
    """Smoothly glides a highlight pill between segmented-control targets."""

    x: float
    y: float
    w: float
    h: float
    target_x: float
    target_y: float
    target_w: float
    target_h: float

    def set_target(self, rect: pygame.Rect) -> None:
        self.target_x = float(rect.x)
        self.target_y = float(rect.y)
        self.target_w = float(rect.width)
        self.target_h = float(rect.height)

    def update(self, dt_sec: float, speed: float = 20.0) -> None:
        self.x = exp_lerp(self.x, self.target_x, speed, dt_sec)
        self.y = exp_lerp(self.y, self.target_y, speed, dt_sec)
        self.w = exp_lerp(self.w, self.target_w, speed, dt_sec)
        self.h = exp_lerp(self.h, self.target_h, speed, dt_sec)

    def current_rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(round(self.x)),
            int(round(self.y)),
            max(1, int(round(self.w))),
            max(1, int(round(self.h))),
        )


class MotionEngine:
    """Central 60 FPS animation coordinator for grid cells, path beam, and UI chrome."""

    def __init__(self) -> None:
        self.cell_anims: dict[Coord, CellAnim] = {}
        self.path_chain: list[Coord] = []
        self.pills: dict[str, SlidingPill] = {}
        self.hover_weights: dict[str, float] = {}
        self.metric_display: dict[str, float] = {}
        self.toast_vis: float = 0.0
        self.clock_ms: float = 0.0
        self.glow_cache = GlowCache()

    def clear_grid_effects(self) -> None:
        """Clear transient cell pop animations and luminous path beam."""
        self.cell_anims.clear()
        self.path_chain.clear()

    def clear_path_beam(self) -> None:
        """Clear only the shortest-path beam chain."""
        self.path_chain.clear()

    def trigger_cell(
        self,
        row: int,
        col: int,
        color: RGBColor,
        kind: AnimKind = "fill",
    ) -> None:
        """Spawn or refresh a smooth cell pop + glow ripple at ``(row, col)``."""
        durations: dict[AnimKind, float] = {
            "frontier": 165.0,
            "visit": 195.0,
            "fill": 225.0,
            "path": 270.0,
            "paint": 150.0,
        }
        # Cap simultaneous active animations on ultra-fast Max speed sweeps
        if len(self.cell_anims) > 360 and (row, col) not in self.cell_anims:
            # Drop oldest entry (dict preserves insertion order in Python 3.7+)
            oldest_key = next(iter(self.cell_anims))
            del self.cell_anims[oldest_key]

        self.cell_anims[(row, col)] = CellAnim(
            kind=kind,
            color=color,
            age_ms=0.0,
            duration_ms=durations.get(kind, 200.0),
        )
        if kind == "path":
            if not self.path_chain or self.path_chain[-1] != (row, col):
                self.path_chain.append((row, col))

    def sync_pill(self, group_id: str, active_rect: pygame.Rect) -> pygame.Rect:
        """Register or update the target rect for a segmented-control sliding pill."""
        pill = self.pills.get(group_id)
        if pill is None:
            pill = SlidingPill(
                float(active_rect.x),
                float(active_rect.y),
                float(active_rect.width),
                float(active_rect.height),
                float(active_rect.x),
                float(active_rect.y),
                float(active_rect.width),
                float(active_rect.height),
            )
            self.pills[group_id] = pill
        else:
            pill.set_target(active_rect)
        return pill.current_rect()

    def update_hover(self, item_id: str, is_hovered: bool, dt_sec: float) -> float:
        """Smoothly advance hover weight ``[0.0, 1.0]`` for a button or swatch."""
        cur = self.hover_weights.get(item_id, 0.0)
        target = 1.0 if is_hovered else 0.0
        nxt = exp_lerp(cur, target, 18.0, dt_sec)
        if nxt < 0.005 and not is_hovered:
            self.hover_weights.pop(item_id, None)
            return 0.0
        self.hover_weights[item_id] = nxt
        return nxt

    def smooth_metric(self, key: str, target_value: float, dt_sec: float) -> float:
        """Smoothly roll numeric HUD counters toward ``target_value``."""
        cur = self.metric_display.get(key, target_value)
        if target_value == 0.0:
            self.metric_display[key] = 0.0
            return 0.0
        nxt = exp_lerp(cur, target_value, 22.0, dt_sec)
        self.metric_display[key] = nxt
        return nxt

    def pulse_phase(self, period_ms: float = 1800.0) -> float:
        """Return a smooth ``[0.0, 1.0]`` breathing oscillation."""
        raw = (self.clock_ms % period_ms) / period_ms
        return 0.5 * (1.0 - math.cos(2.0 * math.pi * raw))

    def update(self, dt_ms: float, has_toast: bool = False) -> None:
        """Advance all active animations by ``dt_ms`` milliseconds."""
        clamped_dt = max(0.0, min(dt_ms, 80.0))
        dt_sec = clamped_dt / 1000.0
        self.clock_ms += clamped_dt

        # Advance & prune finished cell animations
        expired: list[Coord] = []
        for coord, anim in self.cell_anims.items():
            anim.age_ms += clamped_dt
            if anim.age_ms >= anim.duration_ms:
                expired.append(coord)
        for coord in expired:
            del self.cell_anims[coord]

        # Advance sliding pills
        for pill in self.pills.values():
            pill.update(dt_sec)

        # Advance toast visibility
        toast_target = 1.0 if has_toast else 0.0
        self.toast_vis = exp_lerp(self.toast_vis, toast_target, 16.0, dt_sec)

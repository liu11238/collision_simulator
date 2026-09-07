"""Deterministic presentation motion; never integrates physical state."""
from dataclasses import dataclass
import math

import pygame

from config import ACCENT_2, ACCENT_3, MUTED, TEXT
from core.fonts import FONT_SMALL, FONT_TINY
from render.primitives import draw_arrow, draw_text, rounded_rect
from utils import clamp, format_sig3


def smooth(progress):
    progress = clamp(progress, 0.0, 1.0)
    return progress * progress * (3.0 - 2.0 * progress)


def stage_progress(elapsed, duration, stage):
    return smooth((elapsed - stage * duration) / duration)


def focus_strength(elapsed, total_duration):
    progress = clamp(elapsed / total_duration, 0.0, 1.0)
    if progress < 0.24:
        return smooth(progress / 0.24)
    if progress > 0.76:
        return smooth((1.0 - progress) / 0.24)
    return 1.0


@dataclass(frozen=True)
class SceneCamera:
    origin: tuple[float, float]
    scale: float
    zoom: float

    def point(self, x, y):
        return (round(self.origin[0] + x * self.scale),
                round(self.origin[1] + y * self.scale))


def fitted_camera(viewport, origin, scale, focus, bounds, zoom, padding):
    """Zoom around contact, then pan enough to keep subjects and labels visible.

    Bounds use world coordinates with y pointing down. Padding reserves screen
    pixels for the pivot, sphere radius, arrows and labels. A single scale is
    used for both geometry and radii, preserving tangency throughout the zoom.
    """
    view = pygame.Rect(viewport)
    left, top, right, bottom = bounds
    pad_l, pad_t, pad_r, pad_b = padding
    room_w = view.w - pad_l - pad_r
    room_h = view.h - pad_t - pad_b
    zoom = min(zoom, room_w / max((right - left) * scale, 1e-9),
               room_h / max((bottom - top) * scale, 1e-9))
    zoom = max(1.0, zoom)
    effective = scale * zoom
    x = origin[0] + focus[0] * (scale - effective)
    y = origin[1] + focus[1] * (scale - effective)
    x = clamp(x, view.left + pad_l - left * effective,
              view.right - pad_r - right * effective)
    y = clamp(y, view.top + pad_t - top * effective,
              view.bottom - pad_b - bottom * effective)
    return SceneCamera((x, y), effective, zoom)


def flow_dots(surface, start, end, elapsed, color, count=3, radius=3):
    """Continuously move markers along a direction already shown by an arrow."""
    if math.dist(start, end) < 4:
        return
    for i in range(count):
        p = (elapsed * 0.8 + i / count) % 1.0
        point = (round(start[0] + (end[0] - start[0]) * p),
                 round(start[1] + (end[1] - start[1]) * p))
        pygame.draw.circle(surface, color, point, radius + 2)
        pygame.draw.circle(surface, (240, 250, 255), point, radius)


def orbit_focus(surface, center, radius, elapsed, color):
    """Moving open arcs mark the objects currently being explained."""
    angle = elapsed * 1.8
    box = pygame.Rect(0, 0, 2 * radius, 2 * radius)
    box.center = center
    for offset in (0, math.pi):
        pygame.draw.arc(surface, color, box, angle + offset,
                        angle + offset + math.pi * 0.65, 2)


def draw_scene_explanation(surface, scene, elapsed, duration, centers, radii,
                            impulses, energy_before, energy_after, running=True):
    """Motion tied to the active concept, including elastic / zero-transfer cases."""
    stage = min(2, int(elapsed / duration))
    progress = stage_progress(elapsed, duration, stage)
    colors = (ACCENT_2, ACCENT_3)
    scene = pygame.Rect(scene)
    badge = pygame.Rect(scene.x + 16, scene.y + 10, 298, 61)
    rounded_rect(surface, badge, (23, 36, 34), 9, 1, (64, 87, 76))
    captions = ('速度变化 · 箭头逐步变为碰后速度',
                '冲量传递 · 两者受到反向接触冲量',
                '能量分配 · 光点追踪动能去向')
    draw_text(surface, captions[stage], (badge.x + 10, badge.y + 5), FONT_TINY, TEXT,
              max_width=badge.w - 20)
    status = '物理暂停，讲解正在播放' if running else '讲解已暂停'
    draw_text(surface, status, (badge.x + 10, badge.y + 28), FONT_TINY, MUTED)
    track = pygame.Rect(badge.x + 10, badge.bottom - 7, badge.w - 20, 3)
    pygame.draw.rect(surface, (46, 64, 56), track)
    p = clamp(elapsed / (duration * 3), 0, 1)
    pygame.draw.rect(surface, ACCENT_3, (track.x, track.y, round(track.w * p), 3))
    for center, radius, color in zip(centers, radii, colors):
        orbit_focus(surface, center, radius + 7, elapsed, color)

    if stage == 1:
        y = min(c[1] - r for c, r in zip(centers, radii)) - 19
        for center, impulse, color in zip(centers, impulses, colors):
            sign = 1 if impulse >= 0 else -1
            start = (center[0], y)
            end = (round(center[0] + sign * 85 * progress), y)
            if abs(impulse) > 1e-9:
                draw_arrow(surface, start, end, color, 3)
                flow_dots(surface, start, end, elapsed, color, radius=2)
            draw_text(surface, f'J={format_sig3(impulse * progress)} N·s',
                      (end[0] + sign * 8, y - 12), FONT_SMALL, color,
                      anchor='topleft' if sign > 0 else 'topright')
    elif stage == 2:
        delta = energy_after[1] - energy_before[1]
        if abs(delta) > 1e-9:
            first, last = (0, 1) if delta > 0 else (1, 0)
            start = (centers[first][0], centers[first][1] - radii[first] - 10)
            end = (centers[last][0], centers[last][1] - radii[last] - 10)
            crest = min(start[1], end[1]) - 32

            def point(t):
                u = 1 - t
                return (round(u*u*start[0] + 2*u*t*(start[0]+end[0])*.5 + t*t*end[0]),
                        round(u*u*start[1] + 2*u*t*crest + t*t*end[1]))

            pygame.draw.lines(surface, (70, 100, 115), False,
                              [point(i / 24) for i in range(25)], 2)
            for i in range(4):
                pos = point((elapsed * .7 + i / 4) % 1)
                pygame.draw.circle(surface, colors[last], pos, 4)
                pygame.draw.circle(surface, (245, 250, 255), pos, 2)
        loss = max(0.0, sum(energy_before) - sum(energy_after))
        if loss > max(1e-9, sum(energy_before) * 1e-9):
            contact = ((centers[0][0] + centers[1][0]) // 2,
                       (centers[0][1] + centers[1][1]) // 2)
            orbit_focus(surface, contact, max(radii) + 18, -elapsed, (209, 149, 123))

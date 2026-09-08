"""Deterministic, stateless impact visuals for replay frames."""

from __future__ import annotations

import theme

import math

import pygame

from config import ACCENT_2, RED

IMPACT_BLUE = theme.color((91, 181, 255))
IMPACT_BLUE_SOFT = theme.color((145, 218, 255))


def draw_impact_fx(surface, point, intensity, strength=1.0):
    """Draw an impact ring and directional sparks without mutable state.

    The same frame always produces the same pixels: there is no random source,
    particle list, or clock access here.  ``intensity`` is expected in 0..1.
    """
    intensity = max(0.0, min(1.0, float(intensity)))
    if intensity <= 1e-6:
        return
    x, y = int(point[0]), int(point[1])
    visual_strength = min(2.2, math.sqrt(max(0.5, strength)))
    radius = max(8, int(14 + 24 * intensity * visual_strength))
    alpha = int(210 * intensity)
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*IMPACT_BLUE, alpha), (x, y), radius, 2)
    pygame.draw.circle(layer, (*IMPACT_BLUE_SOFT, max(0, alpha // 2)), (x, y),
                       max(3, radius // 3), 1)
    for index in range(12):
        angle = index * math.tau / 12.0 + 0.13
        inner = radius * 0.72
        outer = radius * (1.0 + 0.32 * ((index % 3) / 2.0))
        start = (int(x + math.cos(angle) * inner),
                 int(y + math.sin(angle) * inner))
        end = (int(x + math.cos(angle) * outer),
               int(y + math.sin(angle) * outer))
        pygame.draw.line(layer, (*IMPACT_BLUE_SOFT, alpha), start, end, 2)
    surface.blit(layer, (0, 0))


def draw_friction_heat_fx(surface, point, heat, scale=1.0):
    """根据累计摩擦热绘制确定性的转轴热晕。

    这是能量账本的视觉提示，不模拟额外粒子；同一 ``heat`` 和 ``scale``
    永远使用相同的固定 10 条射线和圆环，因此回放 seek 可重复绘制。
    """
    heat = max(0.0, float(heat))
    intensity = 1.0 - math.exp(-heat / 0.35)
    if intensity <= 1e-6:
        return
    x, y = int(point[0]), int(point[1])
    radius = max(7, int((9.0 + 26.0 * intensity) * max(0.5, scale)))
    alpha = int(125 * intensity)
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*theme.RED, max(18, alpha // 3)), (x, y), radius + 4, 2)
    pygame.draw.circle(layer, (*theme.ACCENT_2, alpha), (x, y), max(3, radius // 3), 1)
    for index in range(10):
        angle = index * math.tau / 10.0 + 0.2
        inner = radius * 0.62
        outer = radius * (0.88 + 0.10 * (index % 2))
        pygame.draw.line(
            layer,
            (*theme.RED, max(12, alpha - 22)),
            (int(x + math.cos(angle) * inner), int(y + math.sin(angle) * inner)),
            (int(x + math.cos(angle) * outer), int(y + math.sin(angle) * outer)),
            2,
        )
    surface.blit(layer, (0, 0))

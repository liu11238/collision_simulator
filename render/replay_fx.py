"""Deterministic, stateless impact visuals for replay frames."""

from __future__ import annotations

import math

import pygame

from config import ACCENT_2, ACCENT_3


def draw_impact_fx(surface, point, intensity, strength=1.0):
    """Draw an impact ring and directional sparks without mutable state.

    The same frame always produces the same pixels: there is no random source,
    particle list, or clock access here.  ``intensity`` is expected in 0..1.
    """
    intensity = max(0.0, min(1.0, float(intensity)))
    if intensity <= 1e-6:
        return
    x, y = int(point[0]), int(point[1])
    radius = max(8, int(12 + 26 * intensity * max(0.5, strength)))
    alpha = int(210 * intensity)
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*ACCENT_2, alpha), (x, y), radius, 2)
    pygame.draw.circle(layer, (*ACCENT_3, max(0, alpha // 2)), (x, y),
                       max(3, radius // 3), 1)
    for index in range(12):
        angle = index * math.tau / 12.0 + 0.13
        inner = radius * 0.72
        outer = radius * (1.0 + 0.32 * ((index % 3) / 2.0))
        start = (int(x + math.cos(angle) * inner),
                 int(y + math.sin(angle) * inner))
        end = (int(x + math.cos(angle) * outer),
               int(y + math.sin(angle) * outer))
        pygame.draw.line(layer, (*ACCENT_2, alpha), start, end, 2)
    surface.blit(layer, (0, 0))

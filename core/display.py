"""pygame 窗口、时钟和共享绘图图层。"""

from __future__ import annotations

import pygame

from config import HEIGHT, SIM_H, WIDTH

pygame.init()
pygame.display.set_caption("弹性碰撞仿真器")
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# 可复用透明层
particle_surf = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
trail_surf_1 = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
trail_surf_2 = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
glow_surf = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
flash_surf = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()

from render.primitives import create_static_background  # noqa: E402

STATIC_BG = create_static_background()

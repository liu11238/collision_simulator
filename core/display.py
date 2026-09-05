"""pygame 窗口、时钟和共享绘图图层。

窗口以 ``pygame.RESIZABLE`` 打开；窗口尺寸变化时 :func:`resize_display`
负责按新几何重建窗口表面和可复用图层（绝不拉伸旧位图），并同步更新
静态背景。所有消费者必须通过 ``display.<名称>`` 动态访问这些对象，
而不是 ``from core.display import screen`` 的值绑定。
"""

from __future__ import annotations

import pygame

from config import (DEFAULT_HEIGHT, DEFAULT_WIDTH, LAYOUT, MIN_HEIGHT,
                    MIN_WIDTH)

pygame.init()
pygame.display.set_caption("弹性碰撞仿真器")
screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT),
                                 pygame.RESIZABLE)
clock = pygame.time.Clock()


def _build_layers(width: int, sim_h: int):
    size = (max(1, width), max(1, sim_h))
    return tuple(
        pygame.Surface(size, pygame.SRCALPHA).convert_alpha() for _ in range(5)
    )


particle_surf, trail_surf_1, trail_surf_2, glow_surf, flash_surf = _build_layers(
    DEFAULT_WIDTH, LAYOUT.sim_h)

from render.primitives import create_static_background  # noqa: E402

STATIC_BG = create_static_background(DEFAULT_WIDTH, LAYOUT.sim_h)


def begin_frame():
    """清空整帧并铺满顶栏/场景背景，避免动态文字残影和黑边。"""
    screen.fill((6, 10, 22))
    screen.blit(STATIC_BG, (0, 0))


def resize_display(width: int, height: int):
    """把窗口调整到 ``(width, height)`` 并重建全部共享图层。

    返回新的屏幕表面。调用方需先通过 ``LAYOUT.apply(width, height)``
    更新布局几何，再调用本函数。
    """
    global screen, STATIC_BG, particle_surf, trail_surf_1, trail_surf_2
    global glow_surf, flash_surf

    width = max(MIN_WIDTH, int(width))
    height = max(MIN_HEIGHT, int(height))
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)

    sim_h = LAYOUT.sim_h
    (particle_surf, trail_surf_1, trail_surf_2,
     glow_surf, flash_surf) = _build_layers(width, sim_h)
    STATIC_BG = create_static_background(width, sim_h)
    return screen

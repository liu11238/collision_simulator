"""能量账本的确定性 pygame 绘制器。"""

from __future__ import annotations

import pygame

from config import ACCENT, ACCENT_2, ACCENT_3, MUTED, RED, TEXT
from core.fonts import FONT_SMALL, FONT_TINY
from render.primitives import draw_arrow, draw_text, rounded_rect
from utils import clamp, format_sig3

from .energy_node import energy_nodes
from .energy_state import EnergyState


def draw_energy_flow(surface, rect, account, title="能量账本"):
    """绘制节点式能量流和账本残差。

    ``account`` 可为 ``EnergyState`` 或旧版字典；绘制顺序和所有几何均为
    固定值，所以回放 seek 和无头绘制不会引入随机差异。
    """
    state = EnergyState.from_account(account)
    rect = pygame.Rect(rect)
    rounded_rect(surface, rect, (10, 16, 32), 14, 1, (55, 72, 115))
    draw_text(surface, title, (rect.x + 14, rect.y + 8), FONT_SMALL, TEXT)

    nodes = energy_nodes(state)
    inner = pygame.Rect(rect.x + 14, rect.y + 31, rect.w - 28, max(1, rect.h - 52))
    positions = {
        node.key: (
            inner.x + int(inner.w * node.position[0]),
            inner.y + int(inner.h * node.position[1]),
        )
        for node in nodes
    }

    source = positions["mechanical"]
    collision = positions["collision_loss"]
    heat = positions["friction_heat"]
    draw_arrow(surface, (source[0], source[1] + 27),
               (collision[0] - 54, collision[1]), ACCENT_2, 2)
    draw_arrow(surface, (collision[0], collision[1] + 25),
               (heat[0], heat[1] - 25), ACCENT_3, 2)

    def draw_node(key, position):
        node = next(item for item in nodes if item.key == key)
        node_rect = pygame.Rect(0, 0, 128, 40)
        node_rect.center = (int(position[0]), int(position[1]))
        rounded_rect(surface, node_rect, (24, 35, 62), 9, 1, node.color)
        draw_text(surface, node.label, (node_rect.centerx, node_rect.y + 6),
                  FONT_TINY, node.color, anchor="midtop")
        draw_text(surface, f"{format_sig3(node.value)} J",
                  (node_rect.centerx, node_rect.bottom - 6), FONT_TINY, TEXT,
                  anchor="midbottom")

    draw_text(surface, "碰前", (inner.centerx, inner.y - 2), FONT_TINY, MUTED, anchor="midbottom")
    draw_node("mechanical", source)
    draw_node("collision_loss", collision)
    draw_node("friction_heat", heat)
    draw_text(surface, "碰撞", (collision[0] - 74, collision[1] - 22), FONT_TINY, ACCENT_2)

    residual_color = ACCENT_3 if abs(state.residual) < 1e-6 else RED
    draw_text(surface, f"残差 = {format_sig3(state.residual)} J",
              (rect.x + 14, rect.bottom - 14), FONT_TINY, residual_color)
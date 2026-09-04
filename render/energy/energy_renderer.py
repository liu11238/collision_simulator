"""能量账本的确定性 pygame 绘制器。"""

from __future__ import annotations

import pygame

from config import ACCENT, ACCENT_2, ACCENT_3, MUTED, RED, TEXT
from core.fonts import FONT_SMALL, FONT_TINY
from render.primitives import draw_text, rounded_rect
from utils import clamp, format_sig3

from .energy_node import energy_nodes
from .energy_state import EnergyState


def draw_energy_flow(surface, rect, account, title="能量账本"):
    """绘制机械能、碰撞耗散、摩擦热和账本残差。

    ``account`` 可为 ``EnergyState`` 或旧版字典；绘制顺序和所有几何均为
    固定值，所以回放 seek 和无头绘制不会引入随机差异。
    """
    state = EnergyState.from_account(account)
    rect = pygame.Rect(rect)
    rounded_rect(surface, rect, (10, 16, 32), 14, 1, (55, 72, 115))
    draw_text(surface, title, (rect.x + 14, rect.y + 8), FONT_SMALL, TEXT)

    denominator = max(state.initial, state.mechanical, 1e-12)
    bar_x = rect.x + 14
    bar_w = rect.w - 28
    y = rect.y + 31
    for node in energy_nodes(state):
        draw_text(surface, node.label, (bar_x, y), FONT_TINY, MUTED)
        draw_text(surface, f"{format_sig3(node.value)} J",
                  (rect.right - 14, y), FONT_TINY, TEXT, anchor="topright")
        y += 13
        pygame.draw.rect(surface, (27, 38, 66), (bar_x, y, bar_w, 6), border_radius=3)
        width = int(bar_w * clamp(node.value / denominator, 0.0, 1.0))
        if width and node.value > 1e-12:
            pygame.draw.rect(surface, node.color, (bar_x, y, width, 6), border_radius=3)
        y += 12

    residual_color = ACCENT_3 if abs(state.residual) < 1e-6 else RED
    draw_text(surface, f"残差 = {format_sig3(state.residual)} J",
              (bar_x, rect.bottom - 13), FONT_TINY, residual_color)
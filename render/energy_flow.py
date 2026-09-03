"""能量账本的轻量 pygame 绘制组件。"""

from __future__ import annotations

import pygame

from config import ACCENT, ACCENT_2, ACCENT_3, MUTED, PANEL_2, RED, TEXT
from core.fonts import FONT_SMALL, FONT_TINY
from render.primitives import draw_text, rounded_rect
from utils import clamp, format_sig3


def draw_energy_flow(surface, rect, account, title="能量账本"):
    """绘制当前能量、碰撞损失和阻尼耗散的分解。

    ``account`` 由模型的 ``energy_breakdown`` 提供，单位统一为焦耳。
    该函数不修改账户，便于无头测试和视觉回归调用。
    """
    rect = pygame.Rect(rect)
    rounded_rect(surface, rect, (10, 16, 32), 14, 1, (55, 72, 115))
    draw_text(surface, title, (rect.x + 14, rect.y + 10), FONT_SMALL, TEXT)

    total = max(account.get("initial", 0.0), 1e-12)
    rows = (
        ("当前机械能", account.get("mechanical", 0.0), ACCENT),
        ("碰撞瞬时损失", account.get("collision", 0.0), ACCENT_2),
        ("转轴阻尼耗散", account.get("damping", 0.0), ACCENT_3),
    )
    y = rect.y + 38
    bar_x = rect.x + 14
    bar_w = rect.w - 28
    for label, value, color in rows:
        value = max(0.0, value)
        draw_text(surface, label, (bar_x, y), FONT_TINY, MUTED)
        draw_text(surface, f"{format_sig3(value)} J", (rect.right - 14, y),
                  FONT_TINY, TEXT, anchor="topright")
        y += 17
        pygame.draw.rect(surface, (27, 38, 66), (bar_x, y, bar_w, 7), border_radius=3)
        width = int(bar_w * clamp(value / total, 0.0, 1.0))
        if width:
            pygame.draw.rect(surface, color, (bar_x, y, width, 7), border_radius=3)
        y += 13

    residual = account.get("residual", 0.0)
    residual_color = ACCENT_3 if abs(residual) < 1e-6 else RED
    draw_text(surface, f"账本误差 = {format_sig3(residual)} J",
              (bar_x, rect.bottom - 19), FONT_TINY, residual_color)

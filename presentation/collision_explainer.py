"""碰撞瞬间的可冻结讲解流程。"""

from __future__ import annotations

import math

import pygame

from config import ACCENT, ACCENT_2, ACCENT_3, MUTED, RED, TEXT
from core.fonts import FONT_BIG, FONT_SMALL, FONT_TINY
from render.primitives import draw_arrow, draw_text, rounded_rect
from utils import clamp, format_sig3


class CollisionExplainer:
    """按速度、动量、能量三个阶段展示一份碰撞快照。

    该对象只维护演示时间，不触碰模型的物理状态，因此模型可以在
    ``impact_explain`` 阶段严格冻结。
    """

    PHASES = ("velocity", "momentum", "energy")
    PHASE_DURATION = 1.55

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.elapsed = 0.0
        self.total_duration = self.PHASE_DURATION * len(self.PHASES)

    @property
    def complete(self):
        return self.elapsed >= self.total_duration

    @property
    def phase_index(self):
        return min(len(self.PHASES) - 1,
                   int(self.elapsed / self.PHASE_DURATION))

    @property
    def phase(self):
        return self.PHASES[self.phase_index]

    @property
    def phase_progress(self):
        return clamp(
            (self.elapsed - self.phase_index * self.PHASE_DURATION)
            / self.PHASE_DURATION, 0.0, 1.0
        )

    def update(self, dt):
        self.elapsed = min(self.total_duration, self.elapsed + max(0.0, dt))
        return self.complete

    def skip(self):
        self.elapsed = self.total_duration

    def focus_strength(self):
        """镜头缩放强度，先拉近再回落，避免切换时突兀。"""
        p = clamp(self.elapsed / self.total_duration, 0.0, 1.0)
        return math.sin(math.pi * p)

    def _draw_velocity(self, surface, rect):
        s = self.snapshot
        y = rect.y + 84
        left = rect.x + 55
        right = rect.right - 55
        scale = 8.0 + 20.0 * self.phase_progress
        draw_text(surface, "碰撞点相对速度", (rect.x + 20, rect.y + 54), FONT_SMALL, MUTED)
        draw_arrow(surface, (left, y), (left + s.contact_before * scale, y), ACCENT_2, 4)
        draw_arrow(surface, (right, y + 32), (right + s.v_after * scale, y + 32), ACCENT_3, 4)
        draw_text(surface, f"碰前 杆点速率 = {format_sig3(s.contact_before)} m/s",
                  (left, y - 25), FONT_TINY, TEXT)
        draw_text(surface, f"碰后 小球速率 = {format_sig3(s.v_after)} m/s",
                  (right, y + 39), FONT_TINY, TEXT, anchor="topright")
        draw_text(surface, f"v_rel' = -e v_rel = {format_sig3(s.relative_after)} m/s",
                  (rect.centerx, rect.bottom - 20), FONT_SMALL, ACCENT_3, anchor="center")

    def _draw_momentum(self, surface, rect):
        s = self.snapshot
        draw_text(surface, "关于转轴的角动量交换", (rect.x + 20, rect.y + 54), FONT_SMALL, MUTED)
        rows = (("碰前总角动量", s.total_L_before), ("碰后总角动量", s.total_L_after))
        max_value = max(abs(s.total_L_before), abs(s.total_L_after), 1e-9)
        y = rect.y + 82
        for label, value in rows:
            draw_text(surface, label, (rect.x + 20, y), FONT_TINY, TEXT)
            bar_w = rect.w - 205
            bar = int(bar_w * clamp(abs(value) / max_value, 0.0, 1.0)
                      * self.phase_progress)
            pygame.draw.rect(surface, (30, 43, 72), (rect.x + 170, y + 3, bar_w, 9), border_radius=4)
            pygame.draw.rect(surface, ACCENT if value >= 0 else RED,
                             (rect.x + 170, y + 3, bar, 9), border_radius=4)
            draw_text(surface, f"{format_sig3(value)} kg*m^2/s",
                      (rect.right - 20, y), FONT_TINY, ACCENT_3, anchor="topright")
            y += 29
        draw_text(surface, "转轴外力矩冲量不计入绕转轴的碰撞角动量",
                  (rect.x + 20, rect.bottom - 20), FONT_SMALL, ACCENT_2)

    def _draw_energy(self, surface, rect):
        s = self.snapshot
        draw_text(surface, "恢复系数决定的能量去向", (rect.x + 20, rect.y + 54), FONT_SMALL, MUTED)
        values = (("碰前动能", s.ke_before, ACCENT),
                  ("碰后动能", s.ke_after, ACCENT_3),
                  ("碰撞损失", s.collision_energy_loss, ACCENT_2))
        max_value = max(s.ke_before, 1e-9)
        y = rect.y + 82
        for label, value, color in values:
            draw_text(surface, label, (rect.x + 20, y), FONT_TINY, TEXT)
            bar_w = rect.w - 205
            width = int(bar_w * clamp(value / max_value, 0.0, 1.0)
                        * self.phase_progress)
            pygame.draw.rect(surface, (30, 43, 72), (rect.x + 170, y + 3, bar_w, 9), border_radius=4)
            pygame.draw.rect(surface, color, (rect.x + 170, y + 3, width, 9), border_radius=4)
            draw_text(surface, f"{format_sig3(value)} J", (rect.right - 20, y),
                      FONT_TINY, color, anchor="topright")
            y += 29
        draw_text(surface, "后续运动中的阻尼耗散将由能量账本继续累计",
                  (rect.x + 20, rect.bottom - 20), FONT_SMALL, ACCENT_3)

    def draw(self, surface, rect):
        """将当前讲解阶段绘制在场景上。"""
        rect = pygame.Rect(rect)
        rounded_rect(surface, rect, (8, 13, 29), 16, 2, (100, 145, 220))
        draw_text(surface, "碰撞讲解", (rect.x + 18, rect.y + 12), FONT_BIG, TEXT)
        draw_text(surface, "Space 跳过本次讲解", (rect.right - 18, rect.y + 18),
                  FONT_SMALL, ACCENT_2, anchor="topright")
        labels = ("① 速度", "② 动量", "③ 能量")
        for index, label in enumerate(labels):
            color = ACCENT_3 if index == self.phase_index else MUTED
            draw_text(surface, label, (rect.x + 205 + index * 105, rect.y + 20), FONT_SMALL, color)
        pygame.draw.rect(surface, (30, 43, 72), (rect.x + 18, rect.y + 43, rect.w - 36, 4), border_radius=2)
        progress_w = int((rect.w - 36) * clamp(self.elapsed / self.total_duration, 0.0, 1.0))
        pygame.draw.rect(surface, ACCENT_3,
                         (rect.x + 18, rect.y + 43, progress_w, 4), border_radius=2)

        if self.phase == "velocity":
            self._draw_velocity(surface, rect)
        elif self.phase == "momentum":
            self._draw_momentum(surface, rect)
        else:
            self._draw_energy(surface, rect)

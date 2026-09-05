"""紧凑、响应式的能量账本绘制器。"""
from __future__ import annotations

import pygame

from config import ACCENT_2, ACCENT_3, LAYOUT, MUTED, RED, TEXT
from core.fonts import font
from render.primitives import draw_text
from render.text import clipped, format_measurement
from .energy_state import EnergyState

ROD_ENERGY = (255, 204, 78)
BALL_ENERGY = (75, 211, 255)
POTENTIAL_ENERGY = (145, 125, 255)
COLLISION_LOSS = (255, 143, 72)
FRICTION_HEAT = (255, 92, 110)


def _segments(state):
    return (("杆动能", state.rod_kinetic, ROD_ENERGY),
            ("球动能", state.ball_kinetic, BALL_ENERGY),
            ("势能", state.potential, POTENTIAL_ENERGY),
            ("碰撞耗散", state.collision_loss, COLLISION_LOSS),
            ("摩擦热", state.friction_heat, FRICTION_HEAT))


def draw_energy_ledger(surface, rect, account, snapshot=None, title=None):
    """绘制能量组成、总账本和闭合残差。"""
    state = EnergyState.from_account(account)
    rect = pygame.Rect(rect)
    metrics = LAYOUT.metrics
    body = font(metrics.tiny_font_size)
    strong = font(metrics.small_font_size, True)
    line_h = body.get_height() + 3
    tolerance = max(1e-9, abs(state.initial) * 1e-8)
    residual_color = (ACCENT_3 if abs(state.residual) <= tolerance else
                      ACCENT_2 if abs(state.residual) <= tolerance * 10 else RED)

    with clipped(surface, rect):
        y = rect.y
        draw_text(surface, f"初始能量  {format_measurement(state.initial)} J",
                  (rect.x, y), strong, TEXT, max_width=rect.w)
        y += strong.get_height() + 7
        bar = pygame.Rect(rect.x, y, rect.w, 16)
        pygame.draw.rect(surface, (30, 42, 70), bar, border_radius=6)
        scale = max(abs(state.initial), 1e-12)
        cursor = bar.x
        for _, value, color in _segments(state):
            if value <= 0:
                continue
            width = max(2, int(bar.w * value / scale))
            width = min(width, bar.right - cursor)
            if width > 0:
                pygame.draw.rect(surface, color, (cursor, bar.y, width, bar.h),
                                 border_radius=4)
                cursor += width
        y = bar.bottom + 7
        label_w = max(64, int(rect.w * 0.34))
        value_w = max(58, int(rect.w * 0.25))
        meter_x = rect.x + label_w
        meter_w = max(20, rect.w - label_w - value_w - 6)
        for label, value, color in _segments(state):
            if y + line_h > rect.bottom - line_h * 2:
                break
            draw_text(surface, label, (rect.x, y), body, color,
                      max_width=label_w - 4)
            meter = pygame.Rect(meter_x, y + 4, meter_w, 7)
            pygame.draw.rect(surface, (31, 43, 70), meter, border_radius=3)
            fill = int(meter.w * max(0.0, value) / scale)
            if value > 0 and fill == 0:
                fill = 2
            if fill:
                pygame.draw.rect(surface, color,
                                 (meter.x, meter.y, min(fill, meter.w), meter.h),
                                 border_radius=3)
            draw_text(surface, f"{format_measurement(value)} J", (rect.right, y),
                      body, TEXT, anchor="topright", max_width=value_w)
            y += line_h
        if snapshot is not None and y + line_h <= rect.bottom - line_h:
            draw_text(surface,
                      f"碰前→碰后  {format_measurement(snapshot.ke_before)} → "
                      f"{format_measurement(snapshot.ke_after)} J",
                      (rect.x, y), body, MUTED, max_width=rect.w)
        draw_text(surface,
                  f"残差 {format_measurement(state.residual)} J  "
                  f"{'✓ 闭合' if abs(state.residual) <= tolerance else '⚠ 检查'}",
                  (rect.x, rect.bottom - line_h), body, residual_color,
                  max_width=rect.w)


def draw_energy_flow(surface, rect, account, title="能量账本"):
    """兼容旧入口。"""
    draw_energy_ledger(surface, rect, account, title=title)

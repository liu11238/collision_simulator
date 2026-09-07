"""Compact, responsive collision explanation shared by both models."""
import pygame

from config import ACCENT_2, ACCENT_3, MUTED, TEXT
from core.fonts import FONT_SMALL, FONT_TINY
from render.primitives import draw_arrow, draw_text
from utils import format_sig3


def draw_impact_panel(surface, rect, elapsed, duration, rows, momentum, energy):
    rect = pygame.Rect(rect)
    stage = min(2, int(elapsed / duration))
    labels = ('1  速度变化', '2  冲量与守恒', '3  能量去向')
    width = (rect.w - 12) // 3
    for i, label in enumerate(labels):
        cell = pygame.Rect(rect.x + i * (width + 6), rect.y, width, 25)
        pygame.draw.rect(surface, (28, 43, 67), cell, border_radius=6)
        draw_text(surface, label, cell.center, FONT_TINY,
                  ACCENT_3 if i == stage else MUTED, anchor='center', max_width=width - 8)
    def line(text, y, color=MUTED):
        draw_text(surface, text, (rect.x + 4, y), FONT_TINY, color, max_width=rect.w - 8)
    line('碰撞瞬间放大示意 · 物理时间冻结 · Space 跳过', rect.y + 31)
    if stage == 0:
        line('读取方式：碰前 → 碰后；箭头表示速度方向和大小', rect.y + 53)
        scale = max(1.0, *(abs(v) for _, a, b in rows for v in (a, b)))
        row_h = max(45, min(62, (rect.h - 105) // 2))
        for i, (name, before, after) in enumerate(rows):
            y = rect.y + 77 + i * row_h
            color = ACCENT_2 if i == 0 else ACCENT_3
            line(f'{name}   {format_sig3(before)} → {format_sig3(after)} m/s', y, color)
            for j, value in enumerate((before, after)):
                x = rect.x + int(rect.w * (0.26 if j == 0 else 0.74))
                reach = value / scale * rect.w * 0.17
                if abs(value) < 1e-8:
                    draw_text(surface, '静止', (x, y + 23), FONT_TINY, color, anchor='center')
                else:
                    draw_arrow(surface, (x, y + 25), (int(x + reach), y + 25), color, 3)
        line('左列：碰前     右列：碰后（不是位置轨迹）', rect.bottom - 18)
    else:
        lines = momentum if stage == 1 else energy
        spacing = max(23, min(34, (rect.h - 78) // max(1, len(lines))))
        for i, text in enumerate(lines):
            line(text, rect.y + 62 + i * spacing, TEXT if i == 0 else MUTED)

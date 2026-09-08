import theme
"""Animated collision comparisons with stable endpoints and a visible clock."""
import pygame

from config import ACCENT_2, ACCENT_3, LAYOUT, MUTED, TEXT
from core.fonts import font
from presentation.impact_motion import flow_dots, stage_progress
from render.primitives import draw_arrow, draw_text
from render.text import clipped
from utils import clamp, format_sig3

LOSS_COLOR = theme.color((255, 143, 72))
COLORS = (theme.ACCENT_2, theme.ACCENT_3, LOSS_COLOR)


def draw_impact_panel(surface, rect, elapsed, duration, rows, *, impulses,
                      momenta, conserved, energy_parts, active=True, running=True):
    """Interpolate snapshot endpoints without changing the physical model."""
    rect = pygame.Rect(rect)
    stage = min(2, max(0, int(elapsed / duration))) if active else 0
    progress = stage_progress(elapsed, duration, stage) if active else 1.0
    tiny = font(LAYOUT.metrics.tiny_font_size)
    line_h = tiny.get_height()
    width = (rect.w - 12) // 3

    def text(value, x, y, color=theme.MUTED, anchor='topleft', max_width=None):
        return draw_text(surface, value, (round(x), round(y)), tiny, color,
                         anchor=anchor, max_width=max_width or rect.w - 8)

    with clipped(surface, rect):
        for i, label in enumerate(('1  速度变化', '2  冲量与守恒', '3  能量去向')):
            cell = pygame.Rect(rect.x + i * (width + 6), rect.y, width, 25)
            color = theme.ACCENT_3 if i == stage else theme.MUTED
            pygame.draw.rect(surface, theme.color((32, 43, 41)), cell, border_radius=6)
            text(label, *cell.center, color, 'center', width - 8)
        if active:
            status = '讲解播放中' if running else '讲解已暂停'
            remaining = max(0.0, 3 * duration - elapsed)
            text(f'{status} · 剩余 {remaining:.1f}s · Space 跳过', rect.x + 4, rect.y + 33)
            bar = pygame.Rect(rect.x + 4, rect.y + 27, rect.w - 8, 3)
            pygame.draw.rect(surface, theme.color((37, 50, 48)), bar)
            filled = round(bar.w * clamp(elapsed / (3 * duration), 0, 1))
            pygame.draw.rect(surface, theme.ACCENT_3, (bar.x, bar.y, filled, bar.h))
        else:
            text('碰撞结果 · R 重置后可重新播放讲解', rect.x + 4, rect.y + 33)

        top = rect.y + 60
        footer_y = rect.bottom - line_h - 2
        if stage == 0:
            text('碰前参考 → 当前示意（箭头：方向 / 大小）', rect.x + 4, top)
            row_h = (footer_y - top - line_h - 6) // 2
            scale = max(1.0, *(abs(v) for _, a, b in rows for v in (a, b)))
            for i, (name, before, after) in enumerate(rows):
                y = top + line_h + 5 + i * row_h
                color = COLORS[i]
                current = before + (after - before) * progress
                text(f'{name}  {format_sig3(before)} → {format_sig3(after)} m/s',
                     rect.x + 4, y, color)
                for col, value in enumerate((before, current)):
                    x = rect.x + rect.w * (0.25 if col == 0 else 0.75)
                    ay = y + line_h + (row_h - line_h) * 0.45
                    end = (round(x + value / scale * rect.w * .18), round(ay))
                    start = (round(x), round(ay))
                    pygame.draw.line(surface, theme.color((46, 63, 60)),
                                     (round(x), round(ay - 5)), (round(x), round(ay + 5)))
                    if abs(value) < 1e-6:
                        text('静止', x, ay, color, 'center')
                    else:
                        draw_arrow(surface, start, end, color, 3)
                        if col == 1 and active:
                            flow_dots(surface, start, end, elapsed, color, count=2, radius=2)
            text('物理时间暂停；右列箭头逐步变为碰后速度' if active else
                 '左列为碰前，右列为碰后', rect.x + 4, footer_y)
        elif stage == 1:
            text('等大反向接触冲量，改变两者的运动', rect.x + 4, top, theme.TEXT)
            arrow_y = top + line_h + 40
            extent = rect.w * .20 * progress
            for i, impulse in enumerate(impulses):
                x = rect.x + rect.w * (.25 if i == 0 else .75)
                sign = 1 if impulse >= 0 else -1
                start, end = (round(x), arrow_y), (round(x + sign * extent), arrow_y)
                text(f'J={format_sig3(impulse * progress)} N·s', x,
                     arrow_y - 14, COLORS[i], 'midbottom', width + 30)
                if abs(impulse) > 1e-9:
                    draw_arrow(surface, start, end, COLORS[i], 3)
                    flow_dots(surface, start, end, elapsed, COLORS[i], radius=2)
            bar_top = arrow_y + 14
            row_h = (footer_y - bar_top - 4) // 2
            scale = max(1e-9, *(abs(v) for _, a, b in momenta for v in (a, b)))
            for i, (label, before, after) in enumerate(momenta):
                value = before + (after - before) * progress
                y = bar_top + i * row_h
                text(label, rect.x + 4, y, COLORS[i], max_width=rect.w * .40)
                text(format_sig3(value), rect.right - 4, y, COLORS[i], 'topright')
                x0, half_w = rect.x + rect.w * .66, rect.w * .17
                by = round(y + line_h + 3)
                pygame.draw.line(surface, theme.color((41, 55, 53)), (round(x0-half_w), by),
                                 (round(x0+half_w), by), 5)
                pygame.draw.line(surface, COLORS[i], (round(x0), by),
                                 (round(x0 + value / scale * half_w), by), 5)
                pygame.draw.line(surface, theme.MUTED, (round(x0), by-5), (round(x0), by+5))
            label, before, after, unit = conserved
            text(f'{label}守恒：{format_sig3(before)} → {format_sig3(after)} {unit}',
                 rect.x + 4, footer_y, theme.ACCENT_3)
        else:
            total = sum(part[1] for part in energy_parts)
            text('动能重新分配；橙色表示碰撞耗散', rect.x + 4, top, theme.TEXT)
            row_h = (footer_y - top - line_h - 6) // 3
            for i, (label, before, after) in enumerate(energy_parts):
                value = max(0.0, before + (after - before) * progress)
                if value < max(1e-9, total * 1e-9):
                    value = 0.0
                y = top + line_h + 5 + i * row_h
                text(label, rect.x + 4, y, COLORS[i])
                text(f'{format_sig3(value)} J', rect.right - 4, y, COLORS[i], 'topright')
                bar = pygame.Rect(rect.x + 4, y + line_h + 2, rect.w - 8, 7)
                pygame.draw.rect(surface, theme.color((37, 50, 48)), bar, border_radius=3)
                filled = round(bar.w * clamp(value / max(total, 1e-9), 0, 1))
                if filled > 0:
                    pygame.draw.rect(surface, COLORS[i], (bar.x, bar.y, filled, bar.h), border_radius=3)
                    flow_dots(surface, (bar.x, bar.centery), (bar.x + filled, bar.centery),
                              elapsed, COLORS[i], count=2, radius=2)
            loss = energy_parts[-1][2]
            text('完全弹性：动能总量不变，碰撞耗散为 0' if loss <= max(1e-9, total * 1e-9)
                 else f'动能 + 耗散 = {format_sig3(total)} J（总量保持闭合）',
                 rect.x + 4, footer_y, theme.ACCENT_3)

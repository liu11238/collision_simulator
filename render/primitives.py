"""通用 pygame 绘制原语和静态背景。"""

from __future__ import annotations

import math
import random

import pygame

from config import BG_BOTTOM, BG_MID, BG_TOP, SIM_H, TEXT, WIDTH
from core.fonts import FONT
from utils import clamp, lerp, lerp_color

def draw_text(surface, text, pos, font=FONT, color=TEXT, anchor="topleft"):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(img, rect)

    return rect


def draw_spaced_text(surface, text, pos, font=FONT, color=TEXT,
                     spacing=0, anchor="topleft"):
    """逐字绘制文本，并在相邻字符之间加入指定的横向间距。"""
    text = str(text)
    if not text:
        rect = pygame.Rect(0, 0, 0, font.get_height())
        setattr(rect, anchor, pos)

        return rect

    glyphs = [font.render(char, True, color) for char in text]
    total_width = sum(glyph.get_width() for glyph in glyphs)
    total_width += max(0, len(glyphs) - 1) * spacing
    total_height = max(font.get_height(), *(glyph.get_height() for glyph in glyphs))


    rect = pygame.Rect(0, 0, total_width, total_height)
    setattr(rect, anchor, pos)

    x = rect.x
    for index, glyph in enumerate(glyphs):
        y = rect.y + (total_height - glyph.get_height()) // 2
        surface.blit(glyph, (x, y))

        x += glyph.get_width()
        if index < len(glyphs) - 1:
            x += spacing
    return rect

def rounded_rect(surface, rect, color, radius=14, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surface, border_color, rect, width=border, border_radius=radius)



def draw_gradient_3(surface, rect, c_top, c_mid, c_bot):
    x, y, w, h = rect
    half = h // 2
    for i in range(half):
        c = lerp_color(c_top, c_mid, i / max(1, half - 1))
        pygame.draw.line(surface, c, (x, y + i), (x + w, y + i))
    for i in range(h - half):
        c = lerp_color(c_mid, c_bot, i / max(1, h - half - 1))

        pygame.draw.line(surface, c, (x, y + half + i), (x + w, y + half + i))


def draw_horizontal_gradient_line(surface, x, y, w, c1, c2, height=1):
    width = max(0, int(w))
    for i in range(width):
        c = lerp_color(c1, c2, i / max(1, width - 1))
        pygame.draw.line(surface, c, (x + i, y), (x + i, y + height - 1))


def draw_arrow(surface, start, end, color, width=3):
    pygame.draw.line(surface, color, start, end, width)
    dx = end[0] - start[0]

    dy = end[1] - start[1]
    ang = math.atan2(dy, dx)
    size = 12
    left = (
        end[0] - size * math.cos(ang - 0.45),
        end[1] - size * math.sin(ang - 0.45),
    )
    right = (
        end[0] - size * math.cos(ang + 0.45),
        end[1] - size * math.sin(ang + 0.45),
    )

    pygame.draw.polygon(surface, color, [end, left, right])

def create_static_background():
    bg = pygame.Surface((WIDTH, SIM_H)).convert()
    draw_gradient_3(bg, (0, 0, WIDTH, SIM_H), BG_TOP, BG_MID, BG_BOTTOM)

    stars = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
    rng = random.Random(42)

    for _ in range(130):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, SIM_H - 1)
        a = rng.randint(35, 135)
        r = rng.randint(1, 2)
        pygame.draw.circle(stars, (200, 215, 255, a), (x, y), r)
    bg.blit(stars, (0, 0))


    soft = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
    for r, a in [(280, 12), (195, 18), (120, 26), (65, 36)]:
        pygame.draw.circle(soft, (70, 130, 255, a), (1010, 110), r)
    for r, a in [(170, 10), (95, 16)]:
        pygame.draw.circle(soft, (255, 125, 90, a), (180, SIM_H - 85), r)
    bg.blit(soft, (0, 0))

    grid = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()

    for x in range(0, WIDTH, 50):
        pygame.draw.line(grid, (255, 255, 255, 8), (x, 0), (x, SIM_H))
    for y in range(0, SIM_H, 50):
        pygame.draw.line(grid, (255, 255, 255, 7), (0, y), (WIDTH, y))
    for x in range(0, WIDTH, 100):
        pygame.draw.line(grid, (255, 255, 255, 14), (x, 0), (x, SIM_H))
    for y in range(0, SIM_H, 100):
        pygame.draw.line(grid, (255, 255, 255, 12), (0, y), (WIDTH, y))
    bg.blit(grid, (0, 0))

    return bg

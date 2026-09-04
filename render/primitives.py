"""通用 pygame 绘制原语和静态背景。"""

from __future__ import annotations

import math
import random
from collections import OrderedDict

import pygame

from config import BG_BOTTOM, BG_MID, BG_TOP, TEXT
from core.fonts import FONT
from render.text import fit_text
from utils import clamp, lerp, lerp_color


_CACHE_LIMIT = 2048
_TEXT_CACHE = OrderedDict()
_SPACED_TEXT_CACHE = OrderedDict()
_GRADIENT_CACHE = OrderedDict()


def _cache_put(cache, key, value):
    cache[key] = value
    cache.move_to_end(key)
    if len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)
    return value


def _cached_text_image(text, font, color):
    key = (id(font), str(text), tuple(color))
    image = _TEXT_CACHE.get(key)
    if image is None:
        image = font.render(str(text), True, color)
        return _cache_put(_TEXT_CACHE, key, image)

    _TEXT_CACHE.move_to_end(key)
    return image


def draw_text(surface, text, pos, font=FONT, color=TEXT, anchor="topleft",
              max_width=None, overflow="ellipsis"):
    """绘制文本；提供 ``max_width`` 时先做宽度适配再绘制。

    overflow: ``clip`` 硬截断；``ellipsis`` 省略号；``shrink`` 缩字号。
    返回实际绘制的矩形。
    """
    text = str(text)
    if max_width is not None:
        text, font = fit_text(text, font, max_width, overflow)
    img = _cached_text_image(text, font, color)
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

    spacing_key = (id(font), text, tuple(color), spacing)
    image = _SPACED_TEXT_CACHE.get(spacing_key)
    if image is None:
        glyphs = [_cached_text_image(char, font, color) for char in text]
        total_width = sum(glyph.get_width() for glyph in glyphs)
        total_width += max(0, len(glyphs) - 1) * spacing
        total_height = max(font.get_height(), *(glyph.get_height() for glyph in glyphs))

        image = pygame.Surface((total_width, total_height), pygame.SRCALPHA)
        x = 0
        for index, glyph in enumerate(glyphs):
            y = (total_height - glyph.get_height()) // 2
            image.blit(glyph, (x, y))

            x += glyph.get_width()
            if index < len(glyphs) - 1:
                x += spacing
        _cache_put(_SPACED_TEXT_CACHE, spacing_key, image)
    else:
        _SPACED_TEXT_CACHE.move_to_end(spacing_key)

    rect = image.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(image, rect)
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
    height = int(height)
    if width <= 0 or height <= 0:
        return

    key = (width, height, tuple(c1), tuple(c2))
    image = _GRADIENT_CACHE.get(key)
    if image is None:
        image = pygame.Surface((width, height))
        for i in range(width):
            c = lerp_color(c1, c2, i / max(1, width - 1))
            pygame.draw.line(image, c, (i, 0), (i, height - 1))
        _cache_put(_GRADIENT_CACHE, key, image)
    else:
        _GRADIENT_CACHE.move_to_end(key)

    surface.blit(image, (int(x), int(y)))


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


def create_static_background(width: int, height: int):
    """按指定场景尺寸生成星空渐变背景；窗口缩放时整体重建而非拉伸。"""
    width = max(1, int(width))
    height = max(1, int(height))
    sx = width / 1280.0
    bg = pygame.Surface((width, height)).convert()
    draw_gradient_3(bg, (0, 0, width, height), BG_TOP, BG_MID, BG_BOTTOM)

    stars = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()
    rng = random.Random(42)

    for _ in range(130):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        a = rng.randint(35, 135)
        r = rng.randint(1, 2)
        pygame.draw.circle(stars, (200, 215, 255, a), (x, y), r)
    bg.blit(stars, (0, 0))


    soft = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()
    for r, a in [(280, 12), (195, 18), (120, 26), (65, 36)]:
        pygame.draw.circle(soft, (70, 130, 255, a), (int(1010 * sx), int(110 * height / 720)), r)
    for r, a in [(170, 10), (95, 16)]:
        pygame.draw.circle(soft, (255, 125, 90, a), (int(180 * sx), height - int(85 * height / 720)), r)
    bg.blit(soft, (0, 0))

    grid = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()

    for x in range(0, width, 50):
        pygame.draw.line(grid, (255, 255, 255, 8), (x, 0), (x, height))
    for y in range(0, height, 50):
        pygame.draw.line(grid, (255, 255, 255, 7), (0, y), (width, y))
    for x in range(0, width, 100):
        pygame.draw.line(grid, (255, 255, 255, 14), (x, 0), (x, height))
    for y in range(0, height, 100):
        pygame.draw.line(grid, (255, 255, 255, 12), (0, y), (width, y))
    bg.blit(grid, (0, 0))

    return bg

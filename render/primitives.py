"""通用 pygame 绘制原语和静态背景。"""

from __future__ import annotations

import math
from collections import OrderedDict
from functools import lru_cache

import pygame

from config import BG_BOTTOM, BG_MID, BG_TOP, TEXT
from core.fonts import FONT, render_text
from render.text import fit_text
from utils import clamp, lerp, lerp_color


_CACHE_LIMIT = 2048
_SPACED_TEXT_CACHE = OrderedDict()
_GRADIENT_CACHE = OrderedDict()


def _cache_put(cache, key, value):
    cache[key] = value
    cache.move_to_end(key)
    if len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)
    return value


def _cached_text_image(text, font, color):
    """渲染文本表面；缺字形回退与 LRU 缓存委托给 core.fonts.render_text。"""
    return render_text(text, font, color)


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
    """Cached quiet drafting surface; sparse marks leave the experiment legible."""
    from config import LAYOUT
    bg = pygame.Surface((max(1, width), max(1, height))).convert()
    draw_gradient_3(bg, (0, 0, width, height), BG_TOP, BG_MID, BG_BOTTOM)
    scene = pygame.Rect(LAYOUT.scene).inflate(-2, -12)
    haze = pygame.Surface((width, height), pygame.SRCALPHA)
    for radius, alpha in ((300, 8), (210, 10), (125, 12)):
        pygame.draw.circle(haze, (130, 191, 168, alpha),
                           (scene.left + scene.w // 3, scene.centery), radius)
    for radius, alpha in ((230, 6), (140, 9)):
        pygame.draw.circle(haze, (205, 153, 123, alpha),
                           (scene.right - scene.w // 5, scene.top + 70), radius)
    bg.blit(haze, (0, 0))
    for x in range(scene.left + 20, scene.right - 16, 32):
        for y in range(scene.top + 20, scene.bottom - 12, 32):
            pygame.draw.circle(bg, (40, 55, 53), (x, y), 1)
    pygame.draw.rect(bg, (52, 72, 66), scene, 1, border_radius=16)
    # Small drafting corners, deliberately quieter than the velocity vectors.
    for x, dx in ((scene.left + 12, 1), (scene.right - 12, -1)):
        for y, dy in ((scene.top + 12, 1), (scene.bottom - 12, -1)):
            pygame.draw.line(bg, (99, 124, 112), (x, y), (x + 10 * dx, y))
            pygame.draw.line(bg, (99, 124, 112), (x, y), (x, y + 10 * dy))
    return bg


@lru_cache(maxsize=96)
def _sphere(radius, color):
    """Small cached matte sphere, softly lit from above left."""
    radius = max(2, radius)
    image = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            d = (x*x + y*y) / (radius*radius)
            if d > 1:
                continue
            z = math.sqrt(1-d)
            light = max(0, (-x/radius*.35 - y/radius*.45 + z*.82))
            shade = .55 + .40*light
            c = tuple(min(255, int(v*shade + 17*light)) for v in color)
            image.set_at((x+radius+2, y+radius+2), (*c, int(255*min(1, (1-d)*radius))))
    return image


def draw_matte_ball(surface, pos, radius, color):
    image = _sphere(int(radius), tuple(color))
    surface.blit(image, (pos[0]-radius-2, pos[1]-radius-2))

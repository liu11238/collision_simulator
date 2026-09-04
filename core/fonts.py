"""字体加载和应用程序字体实例。

字体实例通过 LRU 缓存复用；``font(size, bold)`` 是语义化取字体的
统一入口，供响应式排版按 ``LayoutMetrics`` 中的字号动态取用。
"""

from __future__ import annotations

import os
from functools import lru_cache

import pygame


@lru_cache(maxsize=256)
def get_font(size: int, bold: bool = False):
    size = max(6, int(size))
    win_dir = os.environ.get("WINDIR", r"C:\Windows")

    paths = [
        os.path.join(win_dir, "Fonts", "msyh.ttc"),
        os.path.join(win_dir, "Fonts", "msyhbd.ttc"),
        os.path.join(win_dir, "Fonts", "simhei.ttf"),
        os.path.join(win_dir, "Fonts", "simsun.ttc"),
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, size)
                font.set_bold(bold)
                return font
            except Exception:
                pass
    font = pygame.font.Font(None, size)

    font.set_bold(bold)
    return font


def font(size: int, bold: bool = False):
    """语义化字体入口；带缓存，同参数永远返回同一实例。"""
    return get_font(size, bold)


FONT = get_font(20)
FONT_SMALL = get_font(16)
FONT_TINY = get_font(14)

FONT_BIG = get_font(27, True)
FONT_TITLE = get_font(34, True)
TITLE_LETTER_SPACING = 6  # 标题字符之间的横向间距（像素）

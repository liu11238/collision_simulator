"""字体加载和应用程序字体实例。

字体实例通过 LRU 缓存复用；``font(size, bold)`` 是语义化取字体的
统一入口，供响应式排版按 ``LayoutMetrics`` 中的字号动态取用。

pygame 不会自动做字体回退：当前字体缺字形时 ``Font.render`` 只会画出
方框。因此这里还提供“符号回退字体链”与基于 ``Font.metrics`` 的缺字
形检测，:func:`render_text` 会把主字体缺的字形交给回退字体按基线拼接。
"""

from __future__ import annotations

import os
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import pygame

# 基于源码位置的绝对路径：无论工作目录如何（快捷方式启动、PyInstaller
# 的 _internal），字体资源都能被正确定位。
BASE_DIR = Path(__file__).resolve().parent.parent
BUNDLED_FONT = str(BASE_DIR / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf")
BUNDLED_SYMBOL_FONT = str(
    BASE_DIR / "assets" / "fonts" / "NotoSansSymbols2-Regular.ttf")

# 记录 get_font 创建的字体对应的 (size, bold)，供回退字体按同规格创建。
_FONT_META: dict[int, tuple[int, bool]] = {}


@lru_cache(maxsize=256)
def get_font(size: int, bold: bool = False):
    size = max(6, int(size))
    win_dir = os.environ.get("WINDIR", r"C:\Windows")

    paths = [
        # 项目自带的简体中文字体放在首位，确保各平台显示一致，不再依赖
        # 操作系统是否安装微软雅黑、苹方或 Noto CJK。
        BUNDLED_FONT,
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
                _FONT_META[id(font)] = (size, bool(bold))
                return font
            except Exception:
                pass
    font = pygame.font.Font(None, size)

    font.set_bold(bold)
    _FONT_META[id(font)] = (size, bool(bold))
    return font


def _symbol_font_candidates() -> list[str]:
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    return [
        # 项目自带的符号字体（Noto Sans Symbols 2）放在首位。
        BUNDLED_SYMBOL_FONT,
        # Windows 系统自带，覆盖 ✓✔√→≤≥² 等数学与符号字形。
        os.path.join(win_dir, "Fonts", "seguisym.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansSymbols2-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Apple Symbols.ttf",
        "/System/Library/Fonts/Supplemental/Apple Symbols.ttf",
    ]


@lru_cache(maxsize=64)
def get_symbol_font(size: int, bold: bool = False):
    """符号回退字体；主字体缺字形（✓、√、箭头等）时使用。"""
    size = max(6, int(size))
    for path in _symbol_font_candidates():
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, size)
                font.set_bold(bold)
                _FONT_META[id(font)] = (size, bool(bold))
                return font
            except Exception:
                pass
    return None


@lru_cache(maxsize=64)
def _tofu_signature(font):
    """渲染保证未分配的码位，得到该字体的“豆腐块”位图签名。

    部分字体把缺字形映射到 .notdef，此时 ``metrics`` 仍返回非 None，
    只有比对位图才能识别真正缺字形。渲染为空白时返回 None，表示
    无法构造模板，跳过位图校验。
    """
    try:
        image = font.render("\u0378", True, (255, 255, 255))
    except Exception:
        return None
    if image.get_width() <= 0 or image.get_height() <= 0:
        return None
    return image.get_size(), pygame.image.tobytes(image, "RGBA")


@lru_cache(maxsize=16384)
def _char_supported(font, ch: str) -> bool:
    """字体是否真的拥有该字形。

    两层检测：``metrics`` 返回 None 是缺字形；返回非 None 也可能是
    假阳性（.notdef 映射），需再与豆腐模板位图比对。
    """
    try:
        metrics = font.metrics(ch)
    except Exception:
        return True
    if not metrics or metrics[0] is None:
        return False
    tofu = _tofu_signature(font)
    if tofu is None:
        return True
    try:
        image = font.render(ch, True, (255, 255, 255))
    except Exception:
        return True
    if image.get_size() != tofu[0]:
        return True
    return pygame.image.tobytes(image, "RGBA") != tofu[1]


def font_covers(font, text) -> bool:
    """字体是否覆盖文本中的全部字形。"""
    return all(_char_supported(font, ch) for ch in str(text))


def _fallback_font_for(font):
    meta = _FONT_META.get(id(font))
    if meta is None:
        # 非本模块创建的字体：按高度近似字号。
        size = max(6, int(round(font.get_height() * 0.8)))
        bold = font.get_bold()
    else:
        size, bold = meta
    return get_symbol_font(size, bold)


def split_font_runs(text, font):
    """把文本切成 ``[(font, run)]``；主字体缺字形的字符交给回退字体。

    相同字体的相邻字符合并为一段；任何回退字体都覆盖不了的字符保留
    在主字体段里，不改变版式。
    """
    runs: list = []
    for ch in str(text):
        target = font
        if not _char_supported(font, ch):
            fallback = _fallback_font_for(font)
            if fallback is not None and _char_supported(fallback, ch):
                target = fallback
        if runs and runs[-1][0] is target:
            runs[-1][1].append(ch)
        else:
            runs.append((target, [ch]))
    return [(target, "".join(chars)) for target, chars in runs]


def text_width(text, font) -> int:
    """文本渲染后的实际宽度（按回退分段求和，与 render_text 一致）。"""
    return sum(target.size(part)[0]
               for target, part in split_font_runs(text, font))


_RENDER_CACHE_LIMIT = 2048
_RENDER_CACHE: OrderedDict = OrderedDict()


def render_text(text, font, color):
    """渲染文本为单张表面（带 LRU 缓存）。

    语义与 ``Font.render(text, True, color)`` 一致；多段拼接时按各
    字体的 ascent 对齐基线，避免回退字体偏高或偏低。
    """
    key = (id(font), str(text), tuple(color))
    image = _RENDER_CACHE.get(key)
    if image is not None:
        _RENDER_CACHE.move_to_end(key)
        return image

    text = str(text)
    runs = split_font_runs(text, font)
    if not text:
        image = font.render(text, True, color)
    elif len(runs) == 1:
        image = runs[0][0].render(runs[0][1], True, color)
    else:
        images = [(target, target.render(part, True, color))
                  for target, part in runs]
        ascent = max(target.get_ascent() for target, _ in images)
        descent = max(img.get_height() - target.get_ascent()
                      for target, img in images)
        width = sum(img.get_width() for _, img in images)
        image = pygame.Surface((width, ascent + descent), pygame.SRCALPHA)
        x = 0
        for target, img in images:
            image.blit(img, (x, ascent - target.get_ascent()))
            x += img.get_width()

    _RENDER_CACHE[key] = image
    if len(_RENDER_CACHE) > _RENDER_CACHE_LIMIT:
        _RENDER_CACHE.popitem(last=False)
    return image


def font(size: int, bold: bool = False):
    """语义化字体入口；带缓存，同参数永远返回同一实例。"""
    return get_font(size, bold)


FONT = get_font(20)
FONT_SMALL = get_font(16)
FONT_TINY = get_font(14)

FONT_BIG = get_font(27, True)
FONT_TITLE = get_font(34, True)
TITLE_LETTER_SPACING = 6  # 标题字符之间的横向间距（像素）
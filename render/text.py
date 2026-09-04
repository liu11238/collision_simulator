"""受限宽度文本工具：测量、省略、中文换行和数值-单位列绘制。

面板内的所有文本都必须先经过这里的测量与裁剪，禁止直接把任意
长度的字符串绘制到面板上导致重叠或越界。
"""

from __future__ import annotations

import contextlib

import pygame

from core.fonts import get_font

# CJK 文本允许的额外断行点（英文默认可在空格处断行）。
CJK_BREAK_CHARS = "，。；：、（）【】《》！？+-=→*/%±"


def measure_text(text, font) -> tuple[int, int]:
    """返回文本在指定字体下的 (宽, 高)。"""
    if not text:
        return 0, font.get_height()
    return font.size(str(text))


def ellipsize_text(text, font, max_width: int) -> str:
    """按宽度截断文本并在结尾追加省略号；无需截断时原样返回。"""
    text = str(text)
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "…"
    if font.size(ellipsis)[0] > max_width:
        return ""
    # 二分查找可保留的最大前缀。
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if font.size(text[:mid] + ellipsis)[0] <= max_width:
            low = mid
        else:
            high = mid - 1
    return text[:low] + ellipsis


def clip_text(text, font, max_width: int) -> str:
    """按宽度硬截断（不追加省略号）。"""
    text = str(text)
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if font.size(text[:mid])[0] <= max_width:
            low = mid
        else:
            high = mid - 1
    return text[:low]


def fit_text(text, font, max_width: int, overflow: str = "ellipsis"):
    """返回 ``(适配后的文本, 字体)``。

    overflow: ``clip`` 硬截断；``ellipsis`` 省略号；``shrink`` 先缩小
    字号再省略；其他值按 ``ellipsis`` 处理。
    """
    text = str(text)
    if max_width is None or font.size(text)[0] <= max_width:
        return text, font
    if overflow == "shrink":
        size = font.get_height()
        while size > 8:
            size -= 1
            smaller = get_font(size, font.get_bold())
            if smaller.size(text)[0] <= max_width:
                return text, smaller
        font = get_font(8, font.get_bold())
    if overflow == "clip":
        return clip_text(text, font, max_width), font
    return ellipsize_text(text, font, max_width), font


def wrap_chinese_text(text, font, max_width: int) -> list[str]:
    """把文本按 ``max_width`` 拆成多行，支持 CJK 任意字符处断行。"""
    text = str(text)
    if max_width <= 0:
        return [""] if text else []
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and font.size(candidate)[0] > max_width:
                if current[-1] in CJK_BREAK_CHARS or char == " ":
                    lines.append(current)
                    current = char if char != " " else ""
                else:
                    lines.append(current)
                    current = char
            else:
                current = candidate
        lines.append(current)
    return lines or [""]


def draw_text_box(surface, rect, lines, font, color, line_gap=4,
                  overflow="ellipsis", align="left"):
    """在矩形内绘制多行文本：逐行省略、超出高度的行丢弃。"""
    rect = pygame.Rect(rect)
    if rect.h <= 0 or rect.w <= 0:
        return 0
    surface.set_clip(rect)
    try:
        y = rect.y
        drawn = 0
        for line in lines:
            if y + font.get_height() > rect.bottom:
                break
            text, used_font = fit_text(line, font, rect.w, overflow)
            img = used_font.render(text, True, color)
            if align == "center":
                pos = (rect.centerx - img.get_width() // 2, y)
            elif align == "right":
                pos = (rect.right - img.get_width(), y)
            else:
                pos = (rect.x, y)
            surface.blit(img, pos)
            y += font.get_height() + line_gap
            drawn += 1
        return drawn
    finally:
        surface.set_clip(None)


def format_measurement(value, sig: int = 4) -> str:
    """物理量的紧凑显示：过大/过小用科学计数法，否则用有效数字。"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if value == 0.0:
        return "0"
    abs_value = abs(value)
    if abs_value < 1e-4 or abs_value >= 1e4:
        return f"{value:.{max(1, sig - 1)}e}"
    return f"{value:.{sig}g}"


def draw_value_unit(surface, right_x, y, value, unit="", font=None,
                    value_color=(230, 238, 255), unit_color=(140, 155, 190),
                    max_width=None):
    """右对齐的“数值 + 单位”两列绘制；返回整体矩形。"""
    unit = str(unit).strip()
    value_text = format_measurement(value)
    unit_img = font.render(unit, True, unit_color) if unit else None
    unit_w = unit_img.get_width() + 2 if unit_img else 0

    value_max = max_width - unit_w if max_width else None
    value_text, used_font = fit_text(value_text, font, value_max, "shrink") \
        if value_max else (value_text, font)
    value_img = used_font.render(value_text, True, value_color)

    total_w = value_img.get_width() + unit_w
    x = right_x - total_w
    surface.blit(value_img, (x, y))
    if unit_img is not None:
        surface.blit(unit_img, (x + value_img.get_width() + 2, y))
    return pygame.Rect(x, y, total_w, font.get_height())


@contextlib.contextmanager
def clipped(surface, rect):
    """临时把 ``surface`` 的可绘制区域限制到 ``rect``。"""
    previous = surface.get_clip()
    surface.set_clip(pygame.Rect(rect))
    try:
        yield rect
    finally:
        surface.set_clip(previous)

"""与界面和物理计算无关的通用工具函数。"""

from __future__ import annotations

import math

def clamp(x, a, b):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t



def lerp_color(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))

def format_num(x):
    # 精确输入框仍保留较多数字，避免输入值在编辑时被过早舍入。
    if abs(x) >= 100:
        return f"{x:.2f}"
    if abs(x) >= 10:
        return f"{x:.3f}"
    return f"{x:.4f}"


def format_sig3(x):
    """界面物理量统一显示 3 位有效数字。

    例：12.345 -> 12.3，1.2345 -> 1.23，0.012345 -> 0.0123。
    很大/很小的数自动使用科学计数法；0 显示为 0.00。
    """

    try:
        x = float(x)
    except Exception:
        return str(x)
    if not math.isfinite(x):
        return str(x)
    if x == 0.0:
        return "0.00"
    return f"{x:.3g}"


def safe_float(s, fallback=None):
    try:
        value = float(s)

        return value if math.isfinite(value) else fallback
    except Exception:
        return fallback

"""应用程序尺寸、布局和视觉主题配置。"""

from __future__ import annotations

from dataclasses import dataclass


WIDTH, HEIGHT = 1280, 720
FPS = 60
UI_H = 270
SIM_H = HEIGHT - UI_H


BG_TOP = (6, 10, 22)
BG_MID = (12, 20, 42)
BG_BOTTOM = (18, 30, 58)
PANEL = (16, 22, 40)
PANEL_2 = (24, 33, 56)
TEXT = (230, 238, 255)

MUTED = (140, 155, 190)
ACCENT = (80, 170, 255)
ACCENT_2 = (255, 200, 70)
ACCENT_3 = (120, 255, 180)
ROD_COLOR = (240, 205, 80)

ROD_EDGE = (255, 245, 160)
ROD_GLOW = (255, 220, 60)
BALL1_COLOR = (90, 210, 255)
BALL1_EDGE = (205, 245, 255)
BALL1_GLOW = (55, 155, 255)

BALL2_COLOR = (255, 155, 85)
BALL2_EDGE = (255, 235, 195)
BALL2_GLOW = (255, 125, 55)
PLATFORM = (90, 105, 140)
PLATFORM_TOP = (130, 148, 190)

GREEN = (100, 230, 160)
RED = (255, 90, 90)
INPUT_BG = (12, 18, 34)
INPUT_BORDER = (65, 80, 120)
INPUT_ACTIVE = (80, 170, 255)

SELECT_BG = (50, 100, 170)

TITLE_LETTER_SPACING = 6  # 标题字符之间的横向间距（像素）

@dataclass(frozen=True)
class AppLayout:
    """1280×720 默认画布的统一布局骨架。

    Rect 使用 ``(x, y, width, height)`` 元组保存，避免配置层依赖 pygame；
    绘制层可直接用 ``pygame.Rect(layout.analysis_rect)`` 转换。所有区域都
    由 ``build_layout`` 计算，后续调整窗口尺寸时不需要散落地修改坐标。
    """

    width: int
    height: int
    sim_h: int
    ui_h: int
    scene_rect: tuple[int, int, int, int]
    info_rect: tuple[int, int, int, int]
    timeline_rect: tuple[int, int, int, int]
    analysis_rect: tuple[int, int, int, int]
    controls_rect: tuple[int, int, int, int]
    formula_rect: tuple[int, int, int, int]
    action_rect: tuple[int, int, int, int]


def build_layout(width=WIDTH, height=HEIGHT):
    """计算 16:9 界面分区；当前默认目标为 1280×720。"""
    width = int(width)
    height = int(height)
    ui_h = max(220, int(round(height * 270 / 720)))
    sim_h = height - ui_h
    pad = max(18, int(round(width * 24 / 1280)))
    gap = max(18, int(round(width * 16 / 1280)))
    info_w = max(320, int(round(width * 356 / 1280)))
    info_x = width - pad - info_w
    scene_w = info_x - gap - pad
    bottom_right_x = int(round(width * 650 / 1280))
    bottom_left_w = bottom_right_x - gap - pad
    bottom_right_w = width - bottom_right_x - pad

    return AppLayout(
        width=width,
        height=height,
        sim_h=sim_h,
        ui_h=ui_h,
        scene_rect=(pad, 0, scene_w, sim_h),
        info_rect=(info_x, 104, info_w, max(280, sim_h - 122)),
        timeline_rect=(pad, sim_h - 38, scene_w, 28),
        analysis_rect=(pad, sim_h + 56, bottom_left_w, ui_h - 66),
        controls_rect=(bottom_right_x, sim_h, bottom_right_w, ui_h),
        formula_rect=(bottom_right_x, sim_h, bottom_right_w, 46),
        action_rect=(bottom_right_x, sim_h + 56, bottom_right_w, 30),
    )


LAYOUT = build_layout()

# Named aliases are intentionally retained for the existing model/control and
# regression-test interfaces.  They now describe the new 16:9 regions.
BOTTOM_PAD_X = LAYOUT.scene_rect[0]
BOTTOM_GAP_X = 16
BOTTOM_LEFT_X = LAYOUT.analysis_rect[0]
BOTTOM_RIGHT_X = LAYOUT.controls_rect[0]
BOTTOM_PANEL_TOP = 0
BOTTOM_PANEL_H = UI_H
BOTTOM_CONTROL_Y = SIM_H + 94
BOTTOM_FORMULA_Y = LAYOUT.formula_rect[1]
BOTTOM_FORMULA_H = LAYOUT.formula_rect[3]
BOTTOM_ACTION_Y = LAYOUT.action_rect[1]
BOTTOM_ACTION_H = LAYOUT.action_rect[3]
BOTTOM_SUMMARY_Y = SIM_H + 70
BOTTOM_TIMELINE_X = LAYOUT.timeline_rect[0]
BOTTOM_TIMELINE_Y = LAYOUT.timeline_rect[1]
BOTTOM_TIMELINE_W = LAYOUT.timeline_rect[2]
BOTTOM_TIMELINE_LABEL_Y = SIM_H - 62
# Legacy summary-card constants remain import-compatible but the cards are no
# longer drawn; the analysis panel replaces them without overlaying controls.
BOTTOM_CARD_Y = SIM_H + 100
BOTTOM_CARD_H = 54

ANALYSIS_X, ANALYSIS_Y, ANALYSIS_W, ANALYSIS_H = LAYOUT.analysis_rect
INFO_X, INFO_Y, INFO_W, INFO_H = LAYOUT.info_rect
CONTROLS_X, CONTROLS_Y, CONTROLS_W, CONTROLS_H = LAYOUT.controls_rect
SCENE_X, SCENE_Y, SCENE_W, SCENE_H = LAYOUT.scene_rect
TAB_Y = 104

LEFT_X, RIGHT_X = CONTROLS_X + 16, CONTROLS_X + 310
SLIDER_W = 170
INPUT_W, INPUT_GAP = 82, 8
LEFT_INPUT_X = LEFT_X + SLIDER_W + INPUT_GAP
RIGHT_INPUT_X = RIGHT_X + SLIDER_W + INPUT_GAP

# Compatibility names used by the slider/control code.  A 34px row leaves the
# fifth rod parameter fully visible above the 720px bottom edge.
BASE_Y = BOTTOM_CONTROL_Y
ROW = 34

# Display-time collision replay semantics.  This is deliberately independent
# from the physics integrator's clock.
COLLISION_REPLAY_WINDOW = 0.15

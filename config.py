"""应用程序尺寸、布局和视觉主题配置。"""

from __future__ import annotations

from dataclasses import dataclass


WIDTH, HEIGHT = 1280, 720
FPS = 60

# The screen is divided into four horizontal bands.  Keep these values in one
# place: scene code may use the geometry, but it must not decide how much room
# the interface owns.
HEADER_H = 80
SCENE_H = 260
TIMELINE_H = 40
BOTTOM_H = 340
UI_H = TIMELINE_H + BOTTOM_H
SIM_H = HEADER_H + SCENE_H


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
    """统一的 16:9 布局骨架。

    新代码使用 ``header``、``tabs``、``scene``、``info``、``timeline``、
    ``analysis`` 和两个参数区。旧的 ``*_rect`` 名称通过只读属性保留，
    这样外部插件和旧测试仍可使用同一份布局数据。
    """

    width: int
    height: int
    header: tuple[int, int, int, int]
    tabs: tuple[int, int, int, int]
    scene: tuple[int, int, int, int]
    info: tuple[int, int, int, int]
    timeline: tuple[int, int, int, int]
    analysis: tuple[int, int, int, int]
    params_left: tuple[int, int, int, int]
    params_right: tuple[int, int, int, int]
    formula: tuple[int, int, int, int]
    action: tuple[int, int, int, int]

    @property
    def sim_h(self):
        return self.header[3] + self.scene[3]

    @property
    def ui_h(self):
        return self.height - self.sim_h

    # Compatibility aliases for the previous layout API.
    @property
    def scene_rect(self):
        return self.scene

    @property
    def info_rect(self):
        return self.info

    @property
    def timeline_rect(self):
        return self.timeline

    @property
    def analysis_rect(self):
        return self.analysis

    @property
    def controls_rect(self):
        left = self.params_left
        right = self.params_right
        x = min(left[0], right[0])
        right_edge = max(left[0] + left[2], right[0] + right[2])
        return x, left[1], right_edge - x, left[3]

    @property
    def formula_rect(self):
        return self.formula

    @property
    def action_rect(self):
        return self.action


def build_layout(width=WIDTH, height=HEIGHT):
    """计算 16:9 界面分区；默认基准为 1280×720。"""
    width = int(width)
    height = int(height)
    sx = width / WIDTH
    sy = height / HEIGHT
    header_h = max(56, int(round(HEADER_H * sy)))
    scene_h = max(180, int(round(SCENE_H * sy)))
    timeline_h = max(28, int(round(TIMELINE_H * sy)))
    bottom_h = height - header_h - scene_h - timeline_h

    pad = max(18, int(round(24 * sx)))
    gap = max(14, int(round(16 * sx)))
    info_w = max(300, int(round(356 * sx)))
    scene_w = max(420, width - 2 * pad - gap - info_w)
    info_x = pad + scene_w + gap

    bottom_y = header_h + scene_h + timeline_h
    analysis_w = max(360, int(round(430 * sx)))
    params_x = pad + analysis_w + gap
    params_w = width - params_x - pad
    params_gap = max(12, int(round(14 * sx)))
    params_left_w = max(300, int(round(params_w * 0.48)))
    params_right_x = params_x + params_left_w + params_gap
    params_right_w = width - pad - params_right_x

    formula_h = max(48, int(round(50 * sy)))
    action_h = max(28, int(round(32 * sy)))
    action_y = height - pad - action_h
    formula_y = action_y - formula_h - 8
    control_y = bottom_y + max(42, int(round(48 * sy)))

    return AppLayout(
        width=width,
        height=height,
        header=(0, 0, width, header_h),
        tabs=(max(pad, width - int(round(496 * sx)) - pad),
              max(12, int(round(18 * sy))), int(round(496 * sx)),
              max(32, int(round(38 * sy)))),
        scene=(pad, header_h, scene_w, scene_h),
        info=(info_x, header_h, info_w, scene_h),
        timeline=(pad, header_h + scene_h, width - 2 * pad, timeline_h),
        analysis=(pad, bottom_y, analysis_w, bottom_h),
        params_left=(params_x, bottom_y, params_left_w, bottom_h),
        params_right=(params_right_x, bottom_y, params_right_w, bottom_h),
        formula=(params_right_x + 12, formula_y, params_right_w - 24, formula_h),
        action=(params_right_x + 12, action_y, params_right_w - 24, action_h),
    )


LAYOUT = build_layout()

# Named aliases are intentionally retained for the existing model/control and
# regression-test interfaces.  They now describe the new 16:9 regions.
BOTTOM_PAD_X = LAYOUT.analysis_rect[0]
BOTTOM_GAP_X = 16
BOTTOM_LEFT_X = LAYOUT.analysis_rect[0]
BOTTOM_RIGHT_X = LAYOUT.controls_rect[0]
BOTTOM_PANEL_TOP = LAYOUT.analysis_rect[1]
BOTTOM_PANEL_H = LAYOUT.analysis_rect[3]
BOTTOM_CONTROL_Y = LAYOUT.params_left[1] + max(42, int(round(48 * (LAYOUT.height / HEIGHT))))
BOTTOM_FORMULA_Y = LAYOUT.formula_rect[1]
BOTTOM_FORMULA_H = LAYOUT.formula_rect[3]
# These legacy values are retained for callers that only inspect the old
# ordering constants.  Rendering uses LAYOUT.formula/action directly.
BOTTOM_ACTION_Y = LAYOUT.action_rect[1]
BOTTOM_ACTION_H = LAYOUT.action_rect[3]
BOTTOM_SUMMARY_Y = LAYOUT.analysis_rect[1] + 70
BOTTOM_TIMELINE_X = LAYOUT.timeline_rect[0]
BOTTOM_TIMELINE_Y = LAYOUT.timeline_rect[1] + 6
BOTTOM_TIMELINE_W = LAYOUT.timeline_rect[2]
BOTTOM_TIMELINE_LABEL_Y = LAYOUT.timeline_rect[1] + 5
# Legacy summary-card constants remain import-compatible but the cards are no
# longer drawn; the analysis panel replaces them without overlaying controls.
BOTTOM_CARD_Y = LAYOUT.action_rect[1] + LAYOUT.action_rect[3] + 2
# Legacy summary cards are no longer rendered.  Keep a compact, in-bounds
# compatibility rectangle for callers that still inspect these names.
BOTTOM_CARD_H = 20

ANALYSIS_X, ANALYSIS_Y, ANALYSIS_W, ANALYSIS_H = LAYOUT.analysis_rect
INFO_X, INFO_Y, INFO_W, INFO_H = LAYOUT.info_rect
CONTROLS_X, CONTROLS_Y, CONTROLS_W, CONTROLS_H = LAYOUT.controls_rect
SCENE_X, SCENE_Y, SCENE_W, SCENE_H = LAYOUT.scene_rect
TAB_Y = LAYOUT.tabs[1]

LEFT_X, RIGHT_X = LAYOUT.params_left[0] + 16, LAYOUT.params_right[0] + 16
SLIDER_W = 154
INPUT_W, INPUT_GAP = 82, 8
LEFT_INPUT_X = LEFT_X + 232
RIGHT_INPUT_X = RIGHT_X + 232

# Compatibility names used by the slider/control code.  A 34px row leaves the
# fifth rod parameter fully visible above the 720px bottom edge.
BASE_Y = BOTTOM_CONTROL_Y
ROW = 38

# Display-time collision replay semantics.  This is deliberately independent
# from the physics integrator's clock.
COLLISION_REPLAY_WINDOW = 0.15

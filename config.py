"""应用程序尺寸、布局和视觉主题配置。

本模块是响应式布局的唯一几何事实来源：

* 设计基准为 1600×900，最小支持 1280×720；
* ``build_layout(width, height)`` 为任意窗口尺寸计算全部命名区域；
* ``LAYOUT`` 是常驻的动态布局句柄，``apply()`` 原地更新，
  任何模块在窗口缩放后通过 ``LAYOUT.*`` 读取的都是最新几何；
* 文件末尾的整型常量（``SCENE_X`` 等）只是默认布局的快照，
  仅为兼容旧脚本而保留，新代码禁止使用。
"""

from __future__ import annotations

from dataclasses import dataclass

FPS = 60

# 设计基准（16:9）与响应式约束。
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1600, 900
MIN_WIDTH, MIN_HEIGHT = 1280, 720
MIN_SCALE, MAX_SCALE = 0.80, 1.25

# 旧入口名保留，避免外部脚本立刻失效；新代码使用 DEFAULT_*。
WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT

# 垂直五带：1600×900 时的默认高度，以及 1280×720 时的最小高度。
# 两个锚点各自恰好铺满窗口高度，中间尺寸线性插值。
BAND_DEFAULT = {"header": 72, "scene": 430, "timeline": 58, "bottom": 292, "footer": 48}
BAND_MINIMUM = {"header": 58, "scene": 310, "timeline": 42, "bottom": 266, "footer": 44}
BAND_ORDER = ("header", "scene", "timeline", "bottom", "footer")

# 密度分档阈值（按宽度）。
DENSITY_COMPACT_MAX = 1439
DENSITY_SPACIOUS_MIN = 1800

Rect = tuple[int, int, int, int]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _clamp(value, low, high):
    return max(low, min(high, value))


@dataclass(frozen=True)
class LayoutMetrics:
    """随窗口尺寸变化的排版度量。"""

    scale: float
    density: str
    outer_padding: int
    panel_gap: int
    panel_padding: int
    title_font_size: int
    body_font_size: int
    small_font_size: int
    tiny_font_size: int
    parameter_row_height: int


@dataclass(frozen=True)
class AppLayout:
    """统一的响应式布局骨架。

    新代码使用 ``header``、``scene``、``inspector``、``timeline``、
    ``replay_panel``、``parameter_panel``、``energy_panel`` 和 ``footer``。
    旧的 ``*_rect`` 名称通过只读属性保留。
    """

    width: int
    height: int
    header: Rect
    tabs: Rect
    scene: Rect
    inspector: Rect
    timeline: Rect
    replay_panel: Rect
    parameter_panel: Rect
    energy_panel: Rect
    footer: Rect
    formula: Rect
    action: Rect

    @property
    def sim_h(self):
        return self.header[3] + self.scene[3]

    @property
    def ui_h(self):
        return self.height - self.sim_h

    # ---- 旧布局 API 的兼容别名 -------------------------------------
    @property
    def scene_rect(self):
        return self.scene

    @property
    def info(self):
        return self.inspector

    @property
    def info_rect(self):
        return self.inspector

    @property
    def timeline_rect(self):
        return self.timeline

    @property
    def analysis(self):
        return self.replay_panel

    @property
    def analysis_rect(self):
        return self.replay_panel

    @property
    def controls_rect(self):
        return self.parameter_panel

    @property
    def params_left(self):
        x, y, w, h = self.parameter_panel
        return (x, y, w // 2, h)

    @property
    def params_right(self):
        x, y, w, h = self.parameter_panel
        return (x + w // 2, y, w - w // 2, h)

    @property
    def formula_rect(self):
        return self.formula

    @property
    def action_rect(self):
        return self.action


def vertical_band_heights(height: int) -> dict[str, int]:
    """计算五个垂直带的高度，总和恒等于 ``height``。"""
    height = int(height)
    lo, hi = MIN_HEIGHT, DEFAULT_HEIGHT
    if height <= lo:
        heights = dict(BAND_MINIMUM)
    elif height >= hi:
        scale = _clamp(height / DEFAULT_HEIGHT, 1.0, MAX_SCALE)
        heights = {
            name: max(BAND_MINIMUM[name], int(round(BAND_DEFAULT[name] * scale)))
            for name in BAND_ORDER
        }
    else:
        t = (height - lo) / (hi - lo)
        heights = {
            name: max(BAND_MINIMUM[name],
                      int(round(_lerp(BAND_MINIMUM[name], BAND_DEFAULT[name], t))))
            for name in BAND_ORDER
        }

    # 舍入误差与富余空间都由场景带吸收，它是弹性最大的区域。
    total = sum(heights.values())
    heights["scene"] += height - total
    if heights["scene"] < BAND_MINIMUM["scene"]:
        heights["scene"] = BAND_MINIMUM["scene"]
    return heights


def horizontal_split(width: int):
    """返回 (outer, gap, inspector_w, scene_w, 底部三面板宽度)。"""
    width = int(width)
    t = _clamp((width - MIN_WIDTH) / (DEFAULT_WIDTH - MIN_WIDTH), 0.0, 1.0)
    outer = int(round(_lerp(12, 16, t)))
    gap = int(round(_lerp(12, 16, t)))

    inspector_w = _clamp(int(round(width * _lerp(0.27, 0.255, t))), 300, 480)
    scene_w = max(420, width - outer * 2 - gap - inspector_w)

    avail = max(300, width - outer * 2 - gap * 2)
    replay_frac = _lerp(0.33, 0.34, t)
    param_frac = _lerp(0.39, 0.36, t)
    energy_frac = _lerp(0.28, 0.30, t)
    total = replay_frac + param_frac + energy_frac
    replay_w = int(round(avail * replay_frac / total))
    param_w = int(round(avail * param_frac / total))
    energy_w = avail - replay_w - param_w
    return outer, gap, inspector_w, scene_w, (replay_w, param_w, energy_w)


def build_layout(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT) -> AppLayout:
    """为任意窗口尺寸计算界面分区；默认基准为 1600×900。"""
    width = max(MIN_WIDTH, int(width))
    height = max(MIN_HEIGHT, int(height))

    bands = vertical_band_heights(height)
    header_h = bands["header"]
    scene_h = bands["scene"]
    timeline_h = bands["timeline"]
    bottom_h = bands["bottom"]
    footer_h = bands["footer"]

    outer, gap, inspector_w, scene_w, (replay_w, param_w, energy_w) = horizontal_split(width)

    scene_y = header_h
    timeline_y = scene_y + scene_h
    bottom_y = timeline_y + timeline_h
    footer_y = bottom_y + bottom_h

    tabs_w = min(500, max(360, width // 3))
    tabs_h = min(44, header_h - 12)
    tabs = (width - outer - tabs_w, (header_h - tabs_h) // 2, tabs_w, tabs_h)

    footer_btn_w = min(max(330, int(width * 0.22)), max(200, width // 3))
    action = (width - outer - footer_btn_w, footer_y + 6,
              footer_btn_w, footer_h - 12)
    formula = (outer, footer_y + 6,
               width - outer * 2 - gap - footer_btn_w, footer_h - 12)

    return AppLayout(
        width=width,
        height=height,
        header=(0, 0, width, header_h),
        tabs=tabs,
        scene=(outer, scene_y, scene_w, scene_h),
        inspector=(outer + scene_w + gap, scene_y, inspector_w, scene_h),
        timeline=(outer, timeline_y, width - outer * 2, timeline_h),
        replay_panel=(outer + param_w + gap, bottom_y, replay_w, bottom_h),
        parameter_panel=(outer, bottom_y, param_w, bottom_h),
        energy_panel=(outer + replay_w + gap + param_w + gap, bottom_y,
                      energy_w, bottom_h),
        footer=(0, footer_y, width, footer_h),
        formula=formula,
        action=action,
    )


def build_metrics(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT) -> LayoutMetrics:
    """根据窗口尺寸推导排版度量（字号、间距、参数行高）。"""
    width = max(MIN_WIDTH, int(width))
    height = max(MIN_HEIGHT, int(height))
    t = _clamp((width - MIN_WIDTH) / (DEFAULT_WIDTH - MIN_WIDTH), 0.0, 1.0)

    if width <= DENSITY_COMPACT_MAX:
        density = "compact"
    elif width >= DENSITY_SPACIOUS_MIN:
        density = "spacious"
    else:
        density = "normal"

    return LayoutMetrics(
        scale=round(_clamp(min(width / DEFAULT_WIDTH, height / DEFAULT_HEIGHT),
                           MIN_SCALE, MAX_SCALE), 4),
        density=density,
        outer_padding=int(round(_lerp(12, 16, t))),
        panel_gap=int(round(_lerp(12, 16, t))),
        panel_padding=int(round(_lerp(12, 16, t))),
        title_font_size=int(round(_lerp(28, 34, t))),
        body_font_size=int(round(_lerp(15, 17, t))),
        small_font_size=int(round(_lerp(13, 15, t))),
        tiny_font_size=int(round(_lerp(12, 13, t))),
        # 参数单元使用“标签/数值 + 滑块”两层布局；44px 是 720p 下
        # 不发生纵向遮挡的最小高度。
        parameter_row_height=int(round(_lerp(44, 50, t))),
    )


class LiveLayout:
    """常驻的当前布局句柄。

    窗口缩放时调用 :meth:`apply`，内部布局对象被整体替换；由于句柄
    本身身份不变，所有 ``from config import LAYOUT`` 的模块都能立即
    读取到最新几何，无需重新导入。
    """

    def __init__(self):
        self._layout = build_layout()
        self._metrics = build_metrics()

    def apply(self, width: int, height: int):
        width = max(MIN_WIDTH, int(width))
        height = max(MIN_HEIGHT, int(height))
        self._layout = build_layout(width, height)
        self._metrics = build_metrics(width, height)
        return self._layout

    @property
    def layout(self) -> AppLayout:
        return self._layout

    @property
    def metrics(self) -> LayoutMetrics:
        return self._metrics

    @property
    def width(self):
        return self._layout.width

    @property
    def height(self):
        return self._layout.height

    @property
    def sim_h(self):
        return self._layout.sim_h

    @property
    def ui_h(self):
        return self._layout.ui_h

    # 命名区域（返回元组，与 AppLayout 字段一致）。
    @property
    def header(self):
        return self._layout.header

    @property
    def tabs(self):
        return self._layout.tabs

    @property
    def scene(self):
        return self._layout.scene

    @property
    def inspector(self):
        return self._layout.inspector

    @property
    def timeline(self):
        return self._layout.timeline

    @property
    def replay_panel(self):
        return self._layout.replay_panel

    @property
    def parameter_panel(self):
        return self._layout.parameter_panel

    @property
    def energy_panel(self):
        return self._layout.energy_panel

    @property
    def footer(self):
        return self._layout.footer

    @property
    def formula(self):
        return self._layout.formula

    @property
    def action(self):
        return self._layout.action

    # 旧 *_rect 名称。
    @property
    def scene_rect(self):
        return self._layout.scene

    @property
    def info_rect(self):
        return self._layout.inspector

    @property
    def timeline_rect(self):
        return self._layout.timeline

    @property
    def analysis_rect(self):
        return self._layout.replay_panel

    @property
    def controls_rect(self):
        return self._layout.parameter_panel

    @property
    def formula_rect(self):
        return self._layout.formula

    @property
    def action_rect(self):
        return self._layout.action

    @property
    def params_left(self):
        x, y, w, h = self._layout.parameter_panel
        return (x, y, w // 2, h)

    @property
    def params_right(self):
        x, y, w, h = self._layout.parameter_panel
        return (x + w // 2, y, w - w // 2, h)

    # 逐分量访问，供场景映射和面板绘制直接使用。
    @property
    def header_h(self):
        return self._layout.header[3]

    @property
    def scene_x(self):
        return self._layout.scene[0]

    @property
    def scene_y(self):
        return self._layout.scene[1]

    @property
    def scene_w(self):
        return self._layout.scene[2]

    @property
    def scene_h(self):
        return self._layout.scene[3]

    @property
    def info_x(self):
        return self._layout.inspector[0]

    @property
    def info_y(self):
        return self._layout.inspector[1]

    @property
    def info_w(self):
        return self._layout.inspector[2]

    @property
    def info_h(self):
        return self._layout.inspector[3]

    @property
    def analysis_x(self):
        return self._layout.replay_panel[0]

    @property
    def analysis_y(self):
        return self._layout.replay_panel[1]

    @property
    def analysis_w(self):
        return self._layout.replay_panel[2]

    @property
    def analysis_h(self):
        return self._layout.replay_panel[3]

    @property
    def controls_x(self):
        return self._layout.parameter_panel[0]

    @property
    def controls_y(self):
        return self._layout.parameter_panel[1]

    @property
    def controls_w(self):
        return self._layout.parameter_panel[2]

    @property
    def controls_h(self):
        return self._layout.parameter_panel[3]


LAYOUT = LiveLayout()

# iOS dark appearance: system surfaces, separators and semantic colours.
BG_TOP = (0, 0, 0)
BG_MID = (8, 8, 10)
BG_BOTTOM = (18, 18, 20)
PANEL = (0, 0, 0)
PANEL_2 = (28, 28, 30)
TEXT = (242, 242, 247)
MUTED = (142, 142, 147)
ACCENT = (10, 132, 255)       # systemBlue
ACCENT_2 = (255, 159, 10)     # systemOrange
ACCENT_3 = (48, 209, 88)      # systemGreen
ROD_COLOR = (255, 159, 10)
ROD_EDGE = (255, 214, 150)
ROD_GLOW = (255, 159, 10)
BALL1_COLOR = (10, 132, 255)
BALL1_EDGE = (176, 216, 255)
BALL1_GLOW = (10, 132, 255)
BALL2_COLOR = (255, 69, 58)
BALL2_EDGE = (255, 190, 185)
BALL2_GLOW = (255, 69, 58)
PLATFORM = (72, 72, 74)
PLATFORM_TOP = (142, 142, 147)
GREEN = (48, 209, 88)
RED = (255, 69, 58)
INPUT_BG = (44, 44, 46)
INPUT_BORDER = (72, 72, 74)
INPUT_ACTIVE = ACCENT
SELECT_BG = (0, 64, 221)
TITLE_LETTER_SPACING = 0

# ------------------------------------------------------------------
# 旧常量兼容层：全部来自默认布局（1600×900）的快照。
# 仅在窗口未缩放时与真实几何一致；新代码必须使用 LAYOUT.*。
# ------------------------------------------------------------------
HEADER_H, SCENE_H, TIMELINE_H, BOTTOM_H, FOOTER_H = (
    BAND_DEFAULT["header"], BAND_DEFAULT["scene"], BAND_DEFAULT["timeline"],
    BAND_DEFAULT["bottom"], BAND_DEFAULT["footer"])
UI_H = TIMELINE_H + BOTTOM_H
SIM_H = HEADER_H + SCENE_H

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

BASE_Y = LAYOUT.controls_y + 48
ROW = 38

BOTTOM_FORMULA_Y = LAYOUT.formula_rect[1]
BOTTOM_FORMULA_H = LAYOUT.formula_rect[3]
BOTTOM_ACTION_Y = LAYOUT.action_rect[1]
BOTTOM_ACTION_H = LAYOUT.action_rect[3]
BOTTOM_CARD_Y = LAYOUT.footer[1]
BOTTOM_CARD_H = LAYOUT.footer[3]
BOTTOM_TIMELINE_X = LAYOUT.timeline_rect[0]
BOTTOM_TIMELINE_Y = LAYOUT.timeline_rect[1] + 6
BOTTOM_TIMELINE_W = LAYOUT.timeline_rect[2]
BOTTOM_TIMELINE_LABEL_Y = LAYOUT.timeline_rect[1] + 5

# 瞬时碰撞后的纯视觉衰减时长；不占用时间轴，也不冻结物理状态。
IMPACT_REPLAY_FX_DURATION = 0.15
# 旧扩展代码可能仍导入该名称；保留为视觉时长别名。
COLLISION_REPLAY_WINDOW = IMPACT_REPLAY_FX_DURATION

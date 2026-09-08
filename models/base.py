"""所有碰撞模型共享的状态、控件和界面绘制逻辑。

界面按五个垂直带绘制：header / scene / timeline / 底部三面板 / footer。
全部几何都来自 ``config.LAYOUT``（响应式），模型不再决定绝对坐标。
面板内容一律先测量再绘制，超出面板的部分被裁剪或滚动。
"""

from __future__ import annotations

import theme

import math

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, LAYOUT, MUTED, PANEL, PANEL_2,
                    TEXT, TITLE_LETTER_SPACING)
from core import display
from core.fonts import FONT_SMALL, FONT_TINY, font
from effects.particles import Particle, ShockWave
from render.primitives import (draw_horizontal_gradient_line, draw_spaced_text,
                               draw_text, rounded_rect)
from render.text import clipped, draw_text_box, wrap_chinese_text
from ui.widgets import InputBox, Slider, TimelineSlider, Toggle
from utils import clamp, format_sig3, lerp_color, safe_float

PANEL_TITLE_H = 30


class BaseModel:
    name = ""
    short_name = ""

    def __init__(self):
        self.app = None
        self.running = False
        self.phase = "ready"

        self.t = 0.0
        self.flash = 0.0
        self.last_result = None
        self.particles: list[Particle] = []
        self.shockwaves: list[ShockWave] = []

        self.notice = ""
        self._info_payload = None
        self._control_specs: dict[str, dict] = {}
        self.sliders: dict[str, Slider] = {}
        self.input_boxes: dict[str, InputBox] = {}
        self._toggle_specs: dict[str, dict] = {}
        self.toggles: dict[str, Toggle] = {}
        self.build_controls()
        self.timeline_slider = TimelineSlider(140, 180, 201)
        self.inspector_scroll = 0
        self.replay_scroll = 0
        self.ui_time = 0.0
        self.ui_reveal = 0.0
        self._info_glass = self._build_info_glass()
        self.layout_controls()
        self.reset()

        self.sync_inputs(force=True)

    # ---- 响应式布局 -------------------------------------------------
    def _build_info_glass(self):
        glass = pygame.Surface((max(1, LAYOUT.info_w), max(1, LAYOUT.info_h)),
                               pygame.SRCALPHA).convert_alpha()
        rounded_rect(glass, glass.get_rect(), (38, 52, 45, 20), 18)
        return glass

    def relayout(self):
        """窗口尺寸变化后重新摆放全部控件和派生表面。"""
        self.layout_controls()
        self._info_glass = self._build_info_glass()
        self.inspector_scroll = 0
        self.replay_scroll = 0

    def build_controls(self):
        raise NotImplementedError

    def add_control(self, key, label, column, row, vmin, vmax, value,
                    unit="", decimals=3):
        """登记控件；几何在 :meth:`layout_controls` 中按当前布局计算。"""
        self._control_specs[key] = {"label": label, "column": int(column),
                                    "row": int(row)}
        self.sliders[key] = Slider(label, 0, 0, 120, vmin, vmax, value,
                                   unit, decimals)
        self.input_boxes[key] = InputBox(key, "精确输入", 0, 0, 84, value,
                                         unit.strip())

    def add_toggle(self, key, label, column, row, value=True):
        """登记开关控件；几何在 :meth:`layout_controls` 中按当前布局计算。"""
        self._toggle_specs[key] = {"label": label, "column": int(column),
                                   "row": int(row)}
        self.toggles[key] = Toggle(0, 0, bool(value))

    def layout_controls(self):
        """把参数按“标签/数值 + 滑块”的两层单元摆进参数面板。"""
        metrics = LAYOUT.metrics
        panel = pygame.Rect(LAYOUT.parameter_panel)
        pad = metrics.panel_padding
        content = panel.inflate(-2 * pad, 0)
        content.top = panel.top + PANEL_TITLE_H + 8

        input_w = 84
        unit_w = 44
        col_gap = pad
        col_w = max(200, (content.w - col_gap) // 2)
        row_h = metrics.parameter_row_height

        for key, spec in self._control_specs.items():
            column = spec["column"]
            row = spec["row"]
            x = content.x + column * (col_w + col_gap)
            cell_y = content.y + row * row_h
            slider_y = cell_y + min(29, row_h - 13)
            if key in self.sliders:
                # 滑块占据单元第二行；第一行专用于名称与精确输入。
                # 两端为 14px 半径的旋钮留出空间，极值时也不会被裁剪。
                self.sliders[key].set_rect(x + 14, slider_y, col_w - 28)
            input_key = "h" if key == "height_ratio" and "h" in self.input_boxes else key
            if input_key in self.input_boxes:
                self.input_boxes[input_key].set_rect(
                    x + col_w - input_w - unit_w, cell_y,
                    input_w, min(26, row_h - 16)
                )

        for key, spec in self._toggle_specs.items():
            x = content.x + spec["column"] * (col_w + col_gap)
            cell_y = content.y + spec["row"] * row_h
            # 开关与标签同处单元第一行右端（与精确输入框垂直对齐）。放在
            # 第二行会使最后一行的胶囊超出面板内容裁剪区而被遮挡一半。
            toggle = self.toggles[key]
            toggle.set_rect(x + col_w - toggle.track_w - 4, cell_y + 2)

    def any_input_active(self):
        return any(box.active for box in self.input_boxes.values())

    def sync_inputs(self, force=False):
        for key, value in self.input_values().items():
            if key not in self.input_boxes:
                continue
            box = self.input_boxes[key]
            if force or not box.active:
                box.set_text_value(value)

    def input_values(self):
        return {key: slider.value for key, slider in self.sliders.items()}

    def apply_input_value(self, key, text):
        fallback = self.input_values()[key]
        value = safe_float(text)
        if value is None:
            box = self.input_boxes[key]
            box.invalid_flash = 1.0

            box.text = box.format_value(fallback)
            box.cursor = box.anchor = len(box.text)
            return False
        self.set_control_value(key, value)
        self.sync_inputs(force=True)

        return True

    def set_control_value(self, key, value):
        self.sliders[key].set_value(value)

    def reset(self, keep_running=False):
        raise NotImplementedError

    def start_pause(self):
        raise NotImplementedError

    def jump_to_collision(self):
        raise NotImplementedError

    def step(self, dt):
        raise NotImplementedError

    def draw_scene(self):
        raise NotImplementedError

    def interface_state(self):
        """返回统一 Header 所需的状态文本和显示时间。"""
        return self.phase, self.t

    def formula_lines(self):
        return "", ""

    def formula_rect(self):
        return pygame.Rect(LAYOUT.formula)

    def summary_line(self):
        return ""

    def energy_panel_lines(self):
        """能量面板的文本行；模型可覆写以提供账本数据。"""
        return []

    def draw_slider_value(self, key, slider):
        slider.draw(display.screen, show_value=False, show_label=False)

    def update_inputs(self, dt):
        self.ui_time += max(0.0, min(float(dt), 0.1))
        self.ui_reveal = min(1.0, self.ui_reveal + max(0.0, dt) * 1.8)
        for box in self.input_boxes.values():
            box.update(dt)

    def handle_input_event(self, event):
        input_was_active = self.any_input_active()
        input_consumed = False
        input_result = None
        for box in self.input_boxes.values():
            result = box.handle_event(event)

            if result is not None:
                input_consumed = True
                if result[0] in ("commit", "cancel"):
                    input_result = result
                if result[0] == "consume":
                    break

        changed = False
        if input_result is not None:
            action, key, text = input_result

            if action == "commit":
                changed = self.apply_input_value(key, text)
            else:
                self.sync_inputs(force=True)
        return input_was_active, input_consumed, changed

    def handle_sliders(self, event):
        changed = False
        for slider in self.sliders.values():
            if slider.handle_event(event):
                changed = True
        if changed:
            self.sync_inputs(force=False)

        return changed

    def handle_toggles(self, event):
        """处理参数面板开关点击；返回是否有开关被切换。"""
        changed = False
        for key, toggle in self.toggles.items():
            if toggle.handle_event(event):
                changed = True
                self.on_toggle_changed(key, toggle.value)
        return changed

    def on_toggle_changed(self, key, value):
        """开关切换回调；模型可覆写以同步内部状态。"""

    def handle_timeline(self, event):
        """处理回放时间轴；只对接入 ReplayTimeline 的模型生效。"""
        if not hasattr(self, "replay"):
            return False
        changed = self.timeline_slider.handle_event(event)
        if changed and hasattr(self, "seek_replay"):
            self.seek_replay(self.timeline_slider.value, side="after")
        return changed

    def handle_panel_scroll(self, event):
        """滚轮落在信息/回放面板上时滚动其内容；返回是否消费事件。"""
        if event.type != pygame.MOUSEWHEEL:
            return False
        mouse = pygame.mouse.get_pos()
        step = -int(event.y) * 42
        targets = (
            (pygame.Rect(LAYOUT.info_rect), "inspector_scroll"),
            (pygame.Rect(LAYOUT.replay_panel), "replay_scroll"),
        )
        for rect, attr in targets:
            if rect.collidepoint(mouse):
                setattr(self, attr, max(0, getattr(self, attr) + step))
                return True
        return False

    def draw_ui(self):
        """兼容旧主循环的界面入口。"""
        self.draw_interface()

    # ---- 界面绘制 ---------------------------------------------------
    def draw_interface(self):
        """统一绘制五个垂直带；模型只提供内容，不决定区域边界。"""
        screen = display.screen

        timeline_rect = pygame.Rect(LAYOUT.timeline)
        pygame.draw.rect(screen, theme.PANEL,
                         (0, timeline_rect.y, LAYOUT.width,
                          LAYOUT.height - timeline_rect.y))
<<<<<<< HEAD
        pygame.draw.line(screen, (56, 56, 58), (0, timeline_rect.y),
                         (LAYOUT.width, timeline_rect.y), 2)
        footer_rect = pygame.Rect(LAYOUT.footer)
        pygame.draw.line(screen, (56, 56, 58), (0, footer_rect.y),
=======
        pygame.draw.line(screen, theme.color((56, 56, 58)), (0, timeline_rect.y),
                         (LAYOUT.width, timeline_rect.y), 2)
        footer_rect = pygame.Rect(LAYOUT.footer)
        pygame.draw.line(screen, theme.color((56, 56, 58)), (0, footer_rect.y),
>>>>>>> 8a39dbc0035165c99ba623dafd6a847e929d9c13
                         (LAYOUT.width, footer_rect.y), 1)

        state_text, display_time = self.interface_state()
        self.draw_header(state_text, display_time=display_time)
        if self.app is not None:
            self.app.draw_mode_tabs()

        self.draw_timeline()
        self.draw_inspector_panel()
        self.draw_bottom_panels()
        self.draw_footer()

    def _draw_panel_frame(self, rect, title):
        """绘制面板底板和标题，返回内容矩形。"""
        screen = display.screen
        metrics = LAYOUT.metrics
        rect = pygame.Rect(rect)
<<<<<<< HEAD
        rounded_rect(screen, rect, PANEL_2, 16, 1, (56, 56, 58))
=======
        rounded_rect(screen, rect, theme.PANEL_2, 16, 1, theme.color((56, 56, 58)))
>>>>>>> 8a39dbc0035165c99ba623dafd6a847e929d9c13
        pad = metrics.panel_padding
        title_font = font(metrics.small_font_size, True)
        number, _, label = title.partition("   ")
        badge = pygame.Rect(rect.x + pad, rect.y + 7, 25, 18)
<<<<<<< HEAD
        rounded_rect(screen, badge, (0, 64, 140), 6)
=======
        rounded_rect(screen, badge, theme.color((0, 64, 140)), 6)
>>>>>>> 8a39dbc0035165c99ba623dafd6a847e929d9c13
        draw_text(screen, number, badge.center,
                  font(metrics.tiny_font_size, True), theme.ACCENT, anchor="center")
        draw_text(screen, label or number, (badge.right + 8, rect.y + 7),
<<<<<<< HEAD
                  title_font, TEXT, max_width=rect.w - 2 * pad - 35)
        pygame.draw.line(screen, (56, 56, 58),
=======
                  title_font, theme.TEXT, max_width=rect.w - 2 * pad - 35)
        pygame.draw.line(screen, theme.color((56, 56, 58)),
>>>>>>> 8a39dbc0035165c99ba623dafd6a847e929d9c13
                         (rect.x + pad, rect.y + PANEL_TITLE_H),
                         (rect.right - pad, rect.y + PANEL_TITLE_H), 1)
        reveal = 1.0 - (1.0 - self.ui_reveal) ** 3
        if reveal > 0.001:
            pygame.draw.line(screen, theme.ACCENT,
                             (rect.x + pad, rect.y + PANEL_TITLE_H),
                             (rect.x + pad + int((rect.w - 2 * pad) * reveal),
                              rect.y + PANEL_TITLE_H), 1)
        return pygame.Rect(rect.x + pad, rect.y + PANEL_TITLE_H + 4,
                           rect.w - 2 * pad,
                           max(0, rect.h - PANEL_TITLE_H - 4 - pad))

    def draw_inspector_panel(self):
        """右侧信息面板：分组文本 + 滚动 + 省略号。"""
        if self._info_payload is None:
            return
        self.draw_info_panel(*self._info_payload)

    def draw_info_panel(self, current_lines, collision_lines=None, tips=None,
                        highlight_keywords=()):
        screen = display.screen
        metrics = LAYOUT.metrics
        info_rect = pygame.Rect(LAYOUT.info_rect)
<<<<<<< HEAD
        rounded_rect(screen, info_rect, (28, 28, 30), 18)
=======
        rounded_rect(screen, info_rect, theme.PANEL_2, 18)
>>>>>>> 8a39dbc0035165c99ba623dafd6a847e929d9c13
        if self._info_glass.get_size() != (info_rect.w, info_rect.h):
            self._info_glass = self._build_info_glass()
        screen.blit(self._info_glass, info_rect.topleft)

<<<<<<< HEAD
        pygame.draw.rect(screen, (56, 56, 58), info_rect, width=1,
=======
        pygame.draw.rect(screen, theme.color((56, 56, 58)), info_rect, width=1,
>>>>>>> 8a39dbc0035165c99ba623dafd6a847e929d9c13
                         border_radius=18)

        title_font = font(metrics.body_font_size, True)
        small = font(metrics.small_font_size)
        tiny = font(metrics.tiny_font_size)
        draw_text(screen, "观测记录", (info_rect.x + 18, info_rect.y + 10),
                  title_font, theme.TEXT, max_width=info_rect.w - 36)
        draw_text(screen, "LIVE DATA", (info_rect.right - 18, info_rect.y + 13),
                  tiny, theme.ACCENT, anchor="topright")
        draw_horizontal_gradient_line(
            screen, info_rect.x + 16,
            info_rect.y + 10 + title_font.get_height() + 6,
<<<<<<< HEAD
            info_rect.w - 32, ACCENT, (56, 56, 58), 1)
=======
            info_rect.w - 32, theme.ACCENT, theme.color((56, 56, 58)), 1)
>>>>>>> 8a39dbc0035165c99ba623dafd6a847e929d9c13
        collision_lines = collision_lines or []

        # 保留完整碰撞快照，不再按关键词截成两行。面板高度不足时由
        # inspector_scroll 浏览，避免关键的碰前/碰后参数被静默丢弃。
        groups = (
            ("实时状态", list(current_lines), theme.ACCENT),
            ("碰撞瞬间（碰前 → 碰后）", list(collision_lines), theme.ACCENT_3),
            ("说明", list(tips or [])[:2], theme.ACCENT_2),
        )

        rows = []
        for title, lines, color in groups:
            rows.append((title, color, True))
            if lines:
                for line in lines:
                    rows.append(
                        (line, theme.TEXT if title == "实时状态" else theme.MUTED, False))
            else:
                fallback = (tips or ["尚未发生碰撞"])[0]
                rows.append((fallback, theme.MUTED, False))

        content_top = info_rect.y + 10 + title_font.get_height() + 14
        content = pygame.Rect(info_rect.x + 18, content_top,
                              info_rect.w - 36,
                              max(0, info_rect.bottom - 10 - content_top))
        line_h = tiny.get_height() + 4
        max_scroll = max(0, len(rows) * line_h - content.h)
        self.inspector_scroll = clamp(self.inspector_scroll, 0, max_scroll)
        with clipped(screen, content):
            y = content.y - self.inspector_scroll
            for text, color, is_title in rows:
                used_font = small if is_title else tiny
                draw_text(screen, text, (content.x, y), used_font, color,
                          max_width=content.w)
                y += line_h
        if max_scroll > 0:
            rail = pygame.Rect(info_rect.right - 8, content.top, 3, content.h)
            pygame.draw.rect(screen, theme.color((48, 66, 59)), rail, border_radius=2)
            thumb_h = max(22, int(content.h * content.h / (len(rows) * line_h)))
            thumb_y = rail.y + int((rail.h - thumb_h) * self.inspector_scroll / max_scroll)
            pygame.draw.rect(screen, theme.MUTED, (rail.x, thumb_y, 3, thumb_h), border_radius=2)

    def draw_timeline(self):
        screen = display.screen
        timeline_rect = pygame.Rect(LAYOUT.timeline)
        draw_text(screen, "时间轴 / REPLAY" if hasattr(self, "replay") else "实验操作",
                  (timeline_rect.x, timeline_rect.y + 5), FONT_SMALL, theme.MUTED)
        state = "回放中" if getattr(self, "replay_mode", False) else "实时"
        draw_text(screen, state, (timeline_rect.right, timeline_rect.y + 5),
                  FONT_SMALL, theme.ACCENT_3, anchor="topright")
        if not hasattr(self, "replay"):
            draw_text(screen, "Space 开始 / 暂停    ·    C 直达碰撞    ·    R 重置    ·    E 慢放讲解",
                      (timeline_rect.x + 150, timeline_rect.y + 5), FONT_SMALL, theme.MUTED,
                      max_width=timeline_rect.w - 230)
        if hasattr(self, "replay"):
            self.timeline_slider.set_duration(self.replay.duration)
            self.timeline_slider.set_value(self.replay.cursor)
            collision_times = [frame.time for frame in self.replay.frames
                               if frame.event == "collision_before"]
            self.timeline_slider.set_rect(
                timeline_rect.x + 150,
                timeline_rect.y + (timeline_rect.h - 28) // 2 + 3,
                timeline_rect.w - 150 - 64)
            self.timeline_slider.draw(screen, collision_times)

    def draw_summary_cards(self):
        """旧摘要卡兼容入口；实际内容已经迁移到统一分析面板。"""
        self.draw_analysis_panel(pygame.Rect(LAYOUT.replay_panel))

    def draw_bottom_panels(self):
        """底部三面板：回放分析 / 参数 / 能量。"""
        screen = display.screen
        metrics = LAYOUT.metrics

        content = self._draw_panel_frame(LAYOUT.replay_panel, "02   碰撞过程")
        with clipped(screen, content):
            self.draw_analysis_panel(content)

        param_content = self._draw_panel_frame(LAYOUT.parameter_panel, "01   实验参数")
        panel = pygame.Rect(LAYOUT.parameter_panel)
        pad = metrics.panel_padding
        col_w = (param_content.w - pad) // 2
        tiny = font(metrics.tiny_font_size)
        rows_rect = pygame.Rect(param_content)
        with clipped(screen, rows_rect):
            # 名称和数值在每个参数单元第一行，滑块只占第二行。
            for key, spec in self._control_specs.items():
                column, row = spec["column"], spec["row"]
                cell_x = rows_rect.x + column * (col_w + pad)
                cell_y = rows_rect.y + row * metrics.parameter_row_height
                input_key = "h" if key == "height_ratio" and "h" in self.input_boxes else key
                input_box = self.input_boxes.get(input_key)
                label_right = (input_box.rect.x - 6
                               if input_box is not None else cell_x + col_w)
                draw_text(screen, spec["label"], (cell_x, cell_y + 3), tiny,
                          theme.MUTED, max_width=max(20, label_right - cell_x))
            for key, slider in self.sliders.items():
                self.draw_slider_value(key, slider)
            for box in self.input_boxes.values():
                box.draw(screen)
            for key, spec in self._toggle_specs.items():
                column, row = spec["column"], spec["row"]
                cell_x = rows_rect.x + column * (col_w + pad)
                cell_y = rows_rect.y + row * metrics.parameter_row_height
                toggle = self.toggles[key]
                draw_text(screen, spec["label"], (cell_x, cell_y + 3), tiny,
                          theme.MUTED,
                          max_width=max(20, toggle.rect.x - 34 - cell_x))
            for toggle in self.toggles.values():
                toggle.draw(screen)

        energy_content = self._draw_panel_frame(LAYOUT.energy_panel, "03   能量账本")
        with clipped(screen, energy_content):
            self.draw_energy_panel(energy_content)

    def draw_analysis_panel(self, rect):
        """回放面板默认内容：参数摘要和提示信息。"""
        screen = display.screen
        tiny = font(LAYOUT.metrics.tiny_font_size)
        summary = self.summary_line()
        if summary:
            draw_text(screen, summary, rect.topleft, tiny, theme.MUTED,
                      max_width=rect.w)
        lines = wrap_chinese_text(self.notice or "", tiny, rect.w)
        line_h = tiny.get_height() + 4
        offset = line_h if summary else 0
        rows = max(0, int((rect.h - offset) // line_h))
        with clipped(screen, pygame.Rect(rect.x, rect.y + offset, rect.w,
                                         max(0, rect.h - offset))):
            for index, line in enumerate(lines[:rows]):
                draw_text(screen, line,
                          (rect.x, rect.y + offset + index * line_h),
                          tiny, theme.MUTED)

    def draw_energy_panel(self, rect):
        """能量面板默认内容。模型可覆写以绘制结构化账本。"""
        lines = self.energy_panel_lines()
        if not lines and self.summary_line():
            lines = [self.summary_line()]
        draw_text_box(display.screen, rect, lines,
                      font(LAYOUT.metrics.tiny_font_size), theme.MUTED)

    def draw_footer(self):
        """footer：左侧公式，右侧操作按钮。"""
        screen = display.screen
        metrics = LAYOUT.metrics
        formula_rect = pygame.Rect(LAYOUT.formula)
        body_font = font(metrics.small_font_size)
        size = metrics.small_font_size
        while body_font.get_height() * 2 > formula_rect.h and size > 6:
            size -= 1
            body_font = font(size)
        line_h = formula_rect.h // 2
        line_1, line_2 = self.formula_lines()
        draw_text(screen, line_1, formula_rect.topleft, body_font, theme.ACCENT_2,
                  max_width=formula_rect.w)
        draw_text(screen, line_2,
                  (formula_rect.x, formula_rect.y + line_h),
                  body_font, theme.MUTED, max_width=formula_rect.w)
        if self.app is not None:
            self.app.btn_start.draw(screen, self.running)
            self.app.btn_reset.draw(screen)
            self.app.btn_snap.draw(screen)

    def draw_header(self, state_text, display_time=None):
        screen = display.screen
        metrics = LAYOUT.metrics
        pygame.draw.rect(screen, theme.PANEL, LAYOUT.header)
        # An orbital mark gives the utility a modest visual identity.
        cx, cy = 34, LAYOUT.header_h // 2
        pygame.draw.circle(screen, theme.ACCENT, (cx - 5, cy), 10, 1)
        pygame.draw.circle(screen, theme.ACCENT_2, (cx + 7, cy), 6)
        draw_text(screen, "碰撞之间", (58, 6), font(22, True), theme.TEXT)
        if display_time is None:
            display_time = self.t
        status_color = theme.ACCENT_3 if self.running else theme.ACCENT_2
        pulse = (1.0 + math.sin(self.ui_time * 3.2)) * .5
        pygame.draw.circle(screen, lerp_color(status_color, theme.TEXT, pulse * .2),
                           (60, LAYOUT.header_h - 15), 3 + int(pulse > .86))
        draw_text(screen, f"COLLISION STUDIO   {state_text}   {format_sig3(display_time)} s",
                  (69, LAYOUT.header_h - 23), font(metrics.tiny_font_size), theme.MUTED,
                  max_width=280)
        if self.app is not None:
            self.app.btn_sound.draw(screen, self.app.sound.enabled)

    def step_particles(self, real_dt, gravity=0.0):
        for particle in self.particles:
            particle.step(real_dt, gravity)
        self.particles = [p for p in self.particles if p.life > 0]
        for wave in self.shockwaves:
            wave.step(real_dt)
        self.shockwaves = [w for w in self.shockwaves if w.life > 0]

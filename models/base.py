"""所有碰撞模型共享的状态、控件和界面绘制逻辑。"""

from __future__ import annotations

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BASE_Y, BOTTOM_ACTION_Y,
                    BOTTOM_FORMULA_H, BOTTOM_FORMULA_Y, BOTTOM_TIMELINE_LABEL_Y,
                    BOTTOM_TIMELINE_W, BOTTOM_TIMELINE_X, BOTTOM_TIMELINE_Y,
                    CONTROLS_X, CONTROLS_Y, CONTROLS_W, INFO_H, INFO_W, INFO_X,
                    INFO_Y, INPUT_GAP, INPUT_W, LEFT_INPUT_X, LEFT_X, MUTED,
                    PANEL, PANEL_2, RIGHT_INPUT_X, RIGHT_X, ROW, SIM_H,
                    SLIDER_W, TEXT, TITLE_LETTER_SPACING, UI_H, WIDTH, HEIGHT,
                    ANALYSIS_H, ANALYSIS_W, ANALYSIS_X, ANALYSIS_Y, LAYOUT)
from core.display import clock, screen
from core.fonts import FONT, FONT_BIG, FONT_SMALL, FONT_TINY, FONT_TITLE
from effects.particles import Particle, ShockWave
from render.primitives import (draw_horizontal_gradient_line, draw_spaced_text,
                               draw_text, rounded_rect)
from render.energy import EnergyState
from ui.widgets import InputBox, Slider, TimelineSlider
from utils import format_sig3, safe_float

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

        self._info_glass = pygame.Surface(
            (INFO_W, INFO_H), pygame.SRCALPHA
        ).convert_alpha()
        rounded_rect(self._info_glass, self._info_glass.get_rect(),
                     (38, 52, 88, 55), 18)

        self.notice = ""
        self._info_payload = None
        self.sliders: dict[str, Slider] = {}
        self.input_boxes: dict[str, InputBox] = {}
        self.build_controls()
        self.timeline_slider = TimelineSlider(
            BOTTOM_TIMELINE_X, BOTTOM_TIMELINE_Y, BOTTOM_TIMELINE_W
        )
        self.reset()

        self.sync_inputs(force=True)

    def build_controls(self):
        raise NotImplementedError

    def add_control(self, key, label, column, row, vmin, vmax, value, unit="", decimals=3):
        x = LEFT_X if column == 0 else RIGHT_X
        input_x = LEFT_INPUT_X if column == 0 else RIGHT_INPUT_X
        row_height = getattr(self, "control_row_height", ROW)
        y = BASE_Y + row * row_height

        self.sliders[key] = Slider(label, x, y, SLIDER_W, vmin, vmax, value, unit, decimals)
        self.input_boxes[key] = InputBox(key, "精确输入", input_x, y - 8, INPUT_W, value, unit.strip())

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


    def draw_slider_value(self, key, slider):
        slider.draw(screen, show_value=False)

    def update_inputs(self, dt):
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

    def handle_timeline(self, event):
        """处理回放时间轴；只对接入 ReplayTimeline 的模型生效。"""
        if not hasattr(self, "replay"):
            return False
        changed = self.timeline_slider.handle_event(event)
        if changed and hasattr(self, "seek_replay"):
            self.seek_replay(self.timeline_slider.value, side="after")
        return changed

    def draw_ui(self):
        """兼容旧主循环的界面入口。"""
        self.draw_interface()

    def draw_interface(self):
        """统一绘制时间轴和底部界面，不让模型重新决定区域边界。"""
        timeline_rect = pygame.Rect(LAYOUT.timeline)
        bottom_y = timeline_rect.bottom
        state_text, display_time = self.interface_state()
        self.draw_header(state_text, display_time=display_time)
        if self.app is not None:
            self.app.draw_mode_tabs()
        pygame.draw.rect(screen, PANEL, (0, timeline_rect.y, WIDTH, HEIGHT - timeline_rect.y))
        pygame.draw.line(screen, (65, 80, 125), (0, timeline_rect.y),
                         (WIDTH, timeline_rect.y), 2)
        pygame.draw.line(screen, (90, 110, 160), (0, bottom_y),
                         (WIDTH, bottom_y), 1)

        analysis_rect = pygame.Rect(LAYOUT.analysis)
        left_rect = pygame.Rect(LAYOUT.params_left)
        right_rect = pygame.Rect(LAYOUT.params_right)
        rounded_rect(screen, analysis_rect, PANEL_2, 14, 1, (58, 72, 112))
        rounded_rect(screen, left_rect, PANEL_2, 14, 1, (58, 72, 112))
        rounded_rect(screen, right_rect, PANEL_2, 14, 1, (58, 72, 112))

        if self._info_payload is not None:
            self.draw_info_panel(*self._info_payload)

        draw_text(screen, "参数", (left_rect.x + 14, left_rect.y + 12),
                  FONT_SMALL, TEXT)
        draw_text(screen, "参数", (right_rect.x + 14, right_rect.y + 12),
                  FONT_SMALL, TEXT)
        draw_text(screen, "滑块", (left_rect.x + 166, left_rect.y + 12),
                  FONT_TINY, MUTED)
        draw_text(screen, "数值", (left_rect.right - 16, left_rect.y + 12),
                  FONT_TINY, MUTED, anchor="topright")
        draw_text(screen, "滑块", (right_rect.x + 166, right_rect.y + 12),
                  FONT_TINY, MUTED)
        draw_text(screen, "数值", (right_rect.right - 16, right_rect.y + 12),
                  FONT_TINY, MUTED, anchor="topright")

        for key, slider in self.sliders.items():
            self.draw_slider_value(key, slider)
        for box in self.input_boxes.values():
            box.draw(screen)

        formula_1, formula_2 = self.formula_lines()

        formula_rect = self.formula_rect()
        rounded_rect(screen, formula_rect, (18, 26, 46), 10, 1, (48, 64, 100))
        draw_text(screen, formula_1,
                  (formula_rect.x + 12, formula_rect.y + 8), FONT_SMALL, ACCENT_2)
        draw_text(screen, formula_2,
                  (formula_rect.x + 12, formula_rect.y + 28), FONT_SMALL, MUTED)

        self.app.btn_start.draw(screen, self.running)
        self.app.btn_reset.draw(screen)
        self.app.btn_snap.draw(screen)
        self.draw_timeline()
        self.draw_analysis_panel()

    def draw_analysis_panel(self):
        """绘制底部左侧分析区；模型可覆写以嵌入讲解或能量流。"""
        rect = pygame.Rect(ANALYSIS_X, ANALYSIS_Y, ANALYSIS_W, ANALYSIS_H)
        draw_text(screen, "碰撞分析", (rect.x + 14, rect.y + 10), FONT_SMALL, TEXT)
        draw_text(screen, self.summary_line(), (rect.x + 14, rect.y + 38),
                  FONT_TINY, MUTED)

    def draw_timeline(self):
        if not hasattr(self, "replay"):
            return
        self.timeline_slider.set_duration(self.replay.duration)
        self.timeline_slider.set_value(self.replay.cursor)
        collision_times = [frame.time for frame in self.replay.frames
                           if frame.event == "collision_before"]
        collision_windows = [
            (start, end)
            for start, end, _ in self.replay.collision_windows
        ]
        draw_text(screen, "Replay 时间轴", (BOTTOM_TIMELINE_X,
                                             BOTTOM_TIMELINE_LABEL_Y),
                  FONT_SMALL, MUTED)
        state = "回放中" if getattr(self, "replay_mode", False) else "实时"
        draw_text(screen, state, (BOTTOM_TIMELINE_X + BOTTOM_TIMELINE_W,
                                  BOTTOM_TIMELINE_LABEL_Y), FONT_SMALL, ACCENT_3,
                  anchor="topright")
        self.timeline_slider.draw(screen, collision_times, collision_windows)

    def draw_summary_cards(self):
        """旧摘要卡兼容入口；实际内容已经迁移到统一分析面板。"""
        self.draw_analysis_panel()

    def draw_header(self, state_text, display_time=None):
        # 标题采用逐字绘制，确保中文字符之间有明显的横向间距。
        title = draw_spaced_text(
            screen, self.name, (24, 10), FONT_TITLE, TEXT,
            spacing=TITLE_LETTER_SPACING
        )
        draw_horizontal_gradient_line(screen, 24, title.bottom + 3,
                                      title.width, ACCENT, (40, 60, 100), 3)
        if display_time is None:
            display_time = self.t
        draw_text(screen,
                  f"状态：{state_text}    时间：{format_sig3(display_time)} s    FPS:{clock.get_fps():.0f}",
                  (28, 52), FONT_SMALL, MUTED)

    def step_particles(self, real_dt, gravity=0.0):
        for particle in self.particles:
            particle.step(real_dt, gravity)
        self.particles = [p for p in self.particles if p.life > 0]
        for wave in self.shockwaves:
            wave.step(real_dt)
        self.shockwaves = [w for w in self.shockwaves if w.life > 0]


    def draw_info_panel(self, current_lines, collision_lines=None, tips=None,
                        highlight_keywords=()):
        info_rect = pygame.Rect(INFO_X, INFO_Y, INFO_W, INFO_H)
        rounded_rect(screen, info_rect, (10, 16, 32), 18)
        screen.blit(self._info_glass, info_rect.topleft)

        pygame.draw.rect(screen, (55, 72, 115), info_rect, width=1, border_radius=18)

        draw_text(screen, "信息面板", (info_rect.x + 18, info_rect.y + 10), FONT_BIG, TEXT)
        draw_horizontal_gradient_line(screen, info_rect.x + 16, info_rect.y + 50,
                                      info_rect.w - 32, ACCENT, (30, 45, 80), 1)
        collision_lines = collision_lines or []

        def select_lines(lines, keywords, limit=3):
            selected = [line for line in lines if any(key in line for key in keywords)]
            return selected[:limit] or list(lines[:limit])

        groups = (
            ("实时状态", list(current_lines[:3]), ACCENT),
            ("守恒检查", select_lines(collision_lines, ("角动量", "动量误差", "守恒", "总量")), ACCENT_3),
            ("能量", select_lines(
                list(current_lines[3:]) + collision_lines,
                ("能量", "动能", "耗散", "残差", "摩擦"),
            ), ACCENT_2),
        )
        section_y = info_rect.y + 61
        for title, lines, color in groups:
            draw_text(screen, title, (info_rect.x + 18, section_y), FONT_SMALL, color)
            section_y += 19
            for line in lines[:2]:
                draw_text(screen, line, (info_rect.x + 24, section_y), FONT_TINY,
                          TEXT if title == "实时状态" else MUTED)
                section_y += 18
            if not lines:
                fallback = (tips or ["尚未发生碰撞"])[0]
                draw_text(screen, fallback, (info_rect.x + 24, section_y),
                          FONT_TINY, MUTED)
                section_y += 18
            if title != "能量":
                draw_horizontal_gradient_line(screen, info_rect.x + 16, section_y + 3,
                                              info_rect.w - 32, (60, 80, 130), (20, 30, 55), 1)
                section_y += 10

"""所有碰撞模型共享的状态、控件和界面绘制逻辑。"""

from __future__ import annotations

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BASE_Y, INPUT_GAP, INPUT_W,
                    LEFT_INPUT_X, LEFT_X,
                    MUTED, PANEL, PANEL_2, RIGHT_INPUT_X, RIGHT_X, ROW, SIM_H,
                    SLIDER_W, TEXT, TITLE_LETTER_SPACING, UI_H, WIDTH)
from core.display import clock, screen
from core.fonts import FONT, FONT_BIG, FONT_SMALL, FONT_TITLE
from effects.particles import Particle, ShockWave
from render.primitives import (draw_horizontal_gradient_line, draw_spaced_text,
                               draw_text, rounded_rect)
from ui.widgets import InputBox, Slider
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

        self.notice = ""
        self.sliders: dict[str, Slider] = {}
        self.input_boxes: dict[str, InputBox] = {}
        self.build_controls()
        self.reset()

        self.sync_inputs(force=True)

    def build_controls(self):
        raise NotImplementedError

    def add_control(self, key, label, column, row, vmin, vmax, value, unit="", decimals=3):
        x = LEFT_X if column == 0 else RIGHT_X
        input_x = LEFT_INPUT_X if column == 0 else RIGHT_INPUT_X
        y = BASE_Y + row * ROW

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

    def formula_lines(self):
        return "", ""

    def formula_rect(self):
        return pygame.Rect(690, SIM_H + 218, 528, 52)

    def summary_line(self):
        return ""


    def draw_slider_value(self, key, slider):
        slider.draw(screen)

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

    def draw_ui(self):
        ui_y = SIM_H
        pygame.draw.rect(screen, PANEL, (0, ui_y, WIDTH, UI_H))
        pygame.draw.line(screen, (65, 80, 125), (0, ui_y), (WIDTH, ui_y), 2)
        pygame.draw.line(screen, (90, 110, 160), (0, ui_y + 1), (WIDTH, ui_y + 1), 1)


        rounded_rect(screen, pygame.Rect(22, ui_y + 16, 604, 312),
                     PANEL_2, 18, 1, (58, 72, 112))
        rounded_rect(screen, pygame.Rect(672, ui_y + 16, 580, 312),
                     PANEL_2, 18, 1, (58, 72, 112))

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
        draw_text(screen, self.summary_line(), (535, SIM_H + 294),
                  FONT_SMALL, (165, 182, 218))

    def draw_header(self, state_text):
        # 标题采用逐字绘制，确保中文字符之间有明显的横向间距。
        title = draw_spaced_text(
            screen, self.name, (34, 24), FONT_TITLE, TEXT,
            spacing=TITLE_LETTER_SPACING
        )
        draw_horizontal_gradient_line(screen, 34, title.bottom + 4,
                                      title.width, ACCENT, (40, 60, 100), 3)
        draw_text(screen,
                  f"状态：{state_text}    时间：{format_sig3(self.t)} s    FPS:{clock.get_fps():.0f}",
                  (38, 72), FONT, MUTED)

        draw_text(screen,
                  "1/2 切换模型 | Space 开始/暂停 | R 重置 | C 直接到碰撞 | Esc 退出",
                  (38, 96), FONT_SMALL, (160, 175, 210))

    def step_particles(self, real_dt, gravity=0.0):
        for particle in self.particles:
            particle.step(real_dt, gravity)
        self.particles = [p for p in self.particles if p.life > 0]
        for wave in self.shockwaves:
            wave.step(real_dt)
        self.shockwaves = [w for w in self.shockwaves if w.life > 0]


    def draw_info_panel(self, current_lines, collision_lines=None, tips=None,
                        highlight_keywords=()):
        info_rect = pygame.Rect(815, 118, 438, SIM_H - 140)
        rounded_rect(screen, info_rect, (10, 16, 32), 18)
        glass = pygame.Surface((info_rect.w, info_rect.h), pygame.SRCALPHA).convert_alpha()
        rounded_rect(glass, glass.get_rect(), (38, 52, 88, 55), 18)
        screen.blit(glass, info_rect.topleft)

        pygame.draw.rect(screen, (55, 72, 115), info_rect, width=1, border_radius=18)

        draw_text(screen, "实时物理量", (info_rect.x + 20, info_rect.y + 14), FONT_BIG, TEXT)
        draw_horizontal_gradient_line(screen, info_rect.x + 16, info_rect.y + 50,
                                      info_rect.w - 32, ACCENT, (30, 45, 80), 1)
        y = info_rect.y + 62
        for line in current_lines:
            label, sep, value = line.partition("=")

            if sep:
                draw_text(screen, label + "=", (info_rect.x + 20, y), FONT_SMALL, MUTED)
                w = FONT_SMALL.size(label + "=")[0]
                draw_text(screen, value, (info_rect.x + 20 + w, y), FONT_SMALL, TEXT)
            else:
                draw_text(screen, line, (info_rect.x + 20, y), FONT_SMALL, MUTED)
            y += 24

        y += 2

        draw_horizontal_gradient_line(screen, info_rect.x + 16, y,
                                      info_rect.w - 32, (60, 80, 130), (20, 30, 55), 1)
        y += 10

        if collision_lines:
            draw_text(screen, "碰撞瞬时数据", (info_rect.x + 20, y), FONT, ACCENT_2)
            y += 28
            for line in collision_lines:
                highlight = any(key in line for key in highlight_keywords)
                draw_text(screen, line, (info_rect.x + 20, y), FONT_SMALL,
                          ACCENT_3 if highlight else MUTED)

                y += 21
                if y > info_rect.bottom - 24:
                    break
        else:
            draw_text(screen, "尚未发生碰撞", (info_rect.x + 20, y), FONT, MUTED)
            y += 30
            for tip in tips or []:
                draw_text(screen, tip, (info_rect.x + 28, y), FONT_SMALL, (110, 130, 170))
                y += 24

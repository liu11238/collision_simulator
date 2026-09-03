"""所有碰撞模型共享的状态、控件和界面绘制逻辑。"""

from __future__ import annotations

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BASE_Y, INPUT_GAP, INPUT_W,
                    LEFT_INPUT_X, LEFT_X,
                    MUTED, PANEL, PANEL_2, RIGHT_INPUT_X, RIGHT_X, ROW, SIM_H,
                    SLIDER_W, TEXT, TITLE_LETTER_SPACING, UI_H, WIDTH)
from core.display import clock, screen
from core.fonts import FONT, FONT_BIG, FONT_SMALL, FONT_TINY, FONT_TITLE
from effects.particles import Particle, ShockWave
from render.primitives import (draw_horizontal_gradient_line, draw_spaced_text,
                               draw_text, rounded_rect)
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
            (438, SIM_H - 140), pygame.SRCALPHA
        ).convert_alpha()
        rounded_rect(self._info_glass, self._info_glass.get_rect(),
                     (38, 52, 88, 55), 18)

        self.notice = ""
        self.sliders: dict[str, Slider] = {}
        self.input_boxes: dict[str, InputBox] = {}
        self.build_controls()
        self.timeline_slider = TimelineSlider(38, SIM_H - 42, 730)
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

    def handle_timeline(self, event):
        """处理回放时间轴；只对接入 ReplayTimeline 的模型生效。"""
        if not hasattr(self, "replay"):
            return False
        changed = self.timeline_slider.handle_event(event)
        if changed and hasattr(self, "seek_replay"):
            self.seek_replay(self.timeline_slider.value, side="after")
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
        self.draw_timeline()
        self.draw_summary_cards()

    def draw_timeline(self):
        if not hasattr(self, "replay"):
            return
        self.timeline_slider.set_duration(self.replay.duration)
        self.timeline_slider.set_value(self.replay.cursor)
        collision_times = [frame.time for frame in self.replay.frames
                           if frame.event == "collision_before"]
        draw_text(screen, "Replay 时间轴", (38, SIM_H - 67), FONT_SMALL, MUTED)
        state = "回放中" if getattr(self, "replay_mode", False) else "实时"
        draw_text(screen, state, (768, SIM_H - 67), FONT_SMALL, ACCENT_3,
                  anchor="topright")
        self.timeline_slider.draw(screen, collision_times)

    def draw_summary_cards(self):
        """在底部给出可快速读出的 Energy / Collision 双栏摘要。"""
        y = SIM_H + 350
        left = pygame.Rect(22, y, 604, 54)
        right = pygame.Rect(672, y, 580, 54)
        for rect in (left, right):
            rounded_rect(screen, rect, (18, 26, 46), 10, 1, (48, 64, 100))

        if hasattr(self, "energy_breakdown"):
            account = self.energy_breakdown()
            replay_frame = self.replay_frame() if getattr(
                self, "replay_mode", False
            ) and hasattr(self, "replay_frame") else None
            if replay_frame is not None:
                collision = (
                    self.replay_collision_snapshot(replay_frame)
                    if hasattr(self, "replay_collision_snapshot")
                    else replay_frame.collision
                )
                committed = collision is not None and replay_frame.phase == "after"
                collision_loss = (
                    collision.collision_energy_loss if committed else 0.0
                )
                damping = replay_frame.friction_energy if committed else 0.0
                initial = self.initial_energy
                account = {
                    "initial": initial,
                    "mechanical": replay_frame.total_energy,
                    "collision": collision_loss,
                    "damping": damping,
                    "residual": initial - replay_frame.total_energy
                    - collision_loss - damping,
                }
            draw_text(screen, "Energy", (left.x + 12, left.y + 8), FONT_SMALL,
                      ACCENT_3)
            draw_text(screen,
                      f"机械能 {format_sig3(account.get('mechanical', 0.0))} J  "
                      f"碰撞损失 {format_sig3(account.get('collision', 0.0))} J  "
                      f"摩擦 {format_sig3(account.get('damping', 0.0))} J",
                      (left.x + 98, left.y + 10), FONT_TINY, TEXT)
            draw_text(screen, f"账本误差 {format_sig3(account.get('residual', 0.0))} J",
                      (left.x + 12, left.y + 32), FONT_TINY, MUTED)
        else:
            draw_text(screen, "Energy", (left.x + 12, left.y + 18), FONT_SMALL, ACCENT_3)
            draw_text(screen, "当前模型未提供能量账本", (left.x + 98, left.y + 18),
                      FONT_TINY, MUTED)

        result = getattr(self, "last_result", None)
        replay_frame = self.replay_frame() if getattr(
            self, "replay_mode", False
        ) and hasattr(self, "replay_frame") else None
        if replay_frame is not None:
            result = (
                self.replay_collision_snapshot(replay_frame)
                if hasattr(self, "replay_collision_snapshot")
                else replay_frame.collision
            )
        draw_text(screen, "Collision", (right.x + 12, right.y + 8), FONT_SMALL,
                  ACCENT_2)
        if result:
            if hasattr(result, "impulse"):
                text = (f"t={format_sig3(result.impact_time)} s  "
                        f"J={format_sig3(result.impulse)} N*s  "
                        f"e={format_sig3(result.e)}")
            else:
                text = (f"t={format_sig3(result['impact_time'])} s  "
                        f"J={format_sig3(result['impulse'])} N*s  "
                        f"e={format_sig3(result['e'])}")
            draw_text(screen, text, (right.x + 112, right.y + 10), FONT_TINY, TEXT)
            draw_text(screen, "碰撞标记可在时间轴上拖拽查看碰前 / 碰后帧",
                      (right.x + 12, right.y + 32), FONT_TINY, MUTED)
        else:
            draw_text(screen, "尚未发生碰撞", (right.x + 112, right.y + 18), FONT_TINY, MUTED)

    def draw_header(self, state_text, display_time=None):
        # 标题采用逐字绘制，确保中文字符之间有明显的横向间距。
        title = draw_spaced_text(
            screen, self.name, (34, 24), FONT_TITLE, TEXT,
            spacing=TITLE_LETTER_SPACING
        )
        draw_horizontal_gradient_line(screen, 34, title.bottom + 4,
                                      title.width, ACCENT, (40, 60, 100), 3)
        if display_time is None:
            display_time = self.t
        draw_text(screen,
                  f"状态：{state_text}    时间：{format_sig3(display_time)} s    FPS:{clock.get_fps():.0f}",
                  (38, 72), FONT, MUTED)

        extra_hint = " | E 讲解开关 | Space 跳过讲解" if getattr(
            self, "supports_impact_explanation", False
        ) else ""
        replay_hint = " | 时间轴拖拽/←→逐帧/P退出回放" if hasattr(
            self, "replay"
        ) else ""
        draw_text(screen,
                  "1/2 切换模型 | Space 开始/暂停 | R 重置 | C 直接到碰撞 | Esc 退出"
                  + extra_hint + replay_hint,
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
        screen.blit(self._info_glass, info_rect.topleft)

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

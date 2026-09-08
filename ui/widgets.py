"""可复用的滑块、按钮和精确输入框控件。"""

from __future__ import annotations

import theme

from dataclasses import dataclass, field

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, INPUT_ACTIVE, INPUT_BG,
                    INPUT_BORDER, MUTED, RED, SELECT_BG, TEXT)
from core.fonts import FONT_SMALL, FONT_TINY
from render.primitives import draw_text, rounded_rect
from utils import clamp, format_num, format_sig3, lerp_color

@dataclass
class Slider:
    label: str
    x: int
    y: int

    w: int
    vmin: float
    vmax: float
    value: float
    unit: str = ""

    decimals: int = 2
    dragging: bool = False

    def __post_init__(self):
        self._build_track()

    def knob_x(self):
        t = (self.value - self.vmin) / max(1e-12, self.vmax - self.vmin)
        return int(self.x + clamp(t, 0.0, 1.0) * self.w)

    def set_value(self, value):
        self.value = clamp(float(value), self.vmin, self.vmax)

    def set_from_mouse(self, mx):
        t = clamp((mx - self.x) / self.w, 0.0, 1.0)

        self.value = self.vmin + t * (self.vmax - self.vmin)

    def set_rect(self, x, y, w):
        """响应式重排：更新滑块位置和轨道宽度并重建静态轨道图层。"""
        self.x = int(x)
        self.y = int(y)
        self.w = max(40, int(w))
        self._static_track = None
        self._build_track()

    def _build_track(self):
        self._static_track = pygame.Surface((self.w + 1, 16), pygame.SRCALPHA)
        pygame.draw.line(self._static_track, theme.color((72, 72, 74)),
                         (0, 8), (self.w, 8), 3)
        for i in range(6):
            tx = i * self.w / 5
            pygame.draw.circle(self._static_track, theme.color((142, 142, 147)), (tx, 8), 1)

    def handle_event(self, event):
        changed = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            kx = self.knob_x()
            hit_knob = abs(mx - kx) < 16 and abs(my - self.y) < 18

            hit_track = self.x <= mx <= self.x + self.w and abs(my - self.y) < 12
            if hit_knob or hit_track:
                self.dragging = True
                self.set_from_mouse(mx)
                changed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.set_from_mouse(event.pos[0])
            changed = True

        return changed

    def draw(self, surface, value_text=None, show_value=True, show_label=True,
             label_font=None):
        surface.blit(self._static_track, (self.x, self.y - 8))
        kx = self.knob_x()
        if kx > self.x:
            pygame.draw.line(surface, theme.ACCENT,
                             (self.x, self.y), (kx, self.y), 3)

        pygame.draw.circle(surface, theme.INPUT_BG, (kx, self.y + 1), 9)
        pygame.draw.circle(surface, theme.ACCENT, (kx, self.y), 7 if not self.dragging else 9)
        pygame.draw.circle(surface, theme.color((255, 255, 255)), (kx, self.y), 3)
        if theme.current in ('light', 'dark'):
            pygame.draw.circle(surface, (255, 255, 255), (kx, self.y), 8)
        label_width = max(40, int(self.w * 0.62))
        value_width = max(40, self.w - label_width + 10)
        if show_label:
            draw_text(surface, self.label, (self.x, self.y - 30),
                      label_font or FONT_SMALL, theme.MUTED, max_width=label_width)
        if value_text is None:
            value_text = f"{format_sig3(self.value)}{self.unit}"
        if show_value:
            draw_text(surface, value_text, (self.x + self.w, self.y - 30),
                      FONT_SMALL, theme.TEXT, anchor="topright",
                      max_width=value_width)


class TimelineSlider:
    """回放专用时间轴，支持点击、拖拽和碰撞标记。"""

    def __init__(self, x, y, w, duration=0.0):
        self.rect = pygame.Rect(x, y, w, 28)
        self.duration = max(0.0, float(duration))
        self.value = 0.0
        self.dragging = False

    def set_rect(self, x, y, w):
        """响应式重排：更新时间轴矩形（高度固定为 28）。"""
        self.rect = pygame.Rect(int(x), int(y), max(120, int(w)), 28)

    def set_duration(self, duration):
        self.duration = max(0.0, float(duration))
        self.value = clamp(self.value, 0.0, self.duration)

    def _x_for_value(self, value=None):
        value = self.value if value is None else value
        ratio = value / max(1e-12, self.duration)
        return int(self.rect.x + clamp(ratio, 0.0, 1.0) * self.rect.w)

    def _value_from_x(self, x):
        ratio = clamp((x - self.rect.x) / max(1, self.rect.w), 0.0, 1.0)
        return ratio * self.duration

    def set_value(self, value):
        self.value = clamp(float(value), 0.0, self.duration)

    def handle_event(self, event):
        changed = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.inflate(0, 14).collidepoint(event.pos):
                self.dragging = True
                self.value = self._value_from_x(event.pos[0])
                changed = True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._value_from_x(event.pos[0])
            changed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        return changed

    def draw(self, surface, collision_times=()):
        pygame.draw.line(surface, theme.color((44, 44, 46)),
                         (self.rect.x, self.rect.centery),
                         (self.rect.right, self.rect.centery), 8)
        pygame.draw.line(surface, theme.color((72, 72, 74)),
                         (self.rect.x, self.rect.centery),
                         (self.rect.right, self.rect.centery), 3)
        for time in collision_times:
            x = self._x_for_value(time)
            pygame.draw.line(surface, theme.ACCENT_2,
                             (x, self.rect.y + 1),
                             (x, self.rect.bottom - 1), 2)
            pygame.draw.circle(surface, theme.ACCENT_2, (x, self.rect.centery), 5)
        knob_x = self._x_for_value()
        pygame.draw.circle(surface, (0, 0, 0), (knob_x + 2, self.rect.centery + 2), 10)
        pygame.draw.circle(surface, theme.ACCENT, (knob_x, self.rect.centery), 8)
        draw_text(surface, f"{self.value:0.2f}s", (self.rect.right, self.rect.y - 3),
                  FONT_TINY, theme.TEXT, anchor="topright")



@dataclass
class Button:
    text: str
    rect: pygame.Rect
    _hover: bool = field(default=False, init=False, repr=False)
    _hover_t: float = field(default=0.0, init=False, repr=False)
    _active_t: float = field(default=0.0, init=False, repr=False)
    _press_t: float = field(default=0.0, init=False, repr=False)

    def set_rect(self, rect):
        """响应式重排：更新按钮矩形。"""
        self.rect = pygame.Rect(rect)

    def draw(self, surface, active=False):
        self._hover = self.rect.collidepoint(pygame.mouse.get_pos())
        self._hover_t += ((1.0 if self._hover else 0.0) - self._hover_t) * 0.18
        self._active_t += ((1.0 if active else 0.0) - self._active_t) * 0.22
        self._press_t *= 0.68
        base_bg, base_border = theme.color((44, 44, 46)), theme.color((72, 72, 74))
        bg = lerp_color(base_bg, theme.color((58, 58, 60)), self._hover_t)
        border = lerp_color(base_border, theme.color((99, 99, 102)), self._hover_t)
        bg = lerp_color(bg, theme.color((0, 92, 200)), self._active_t)
        border = lerp_color(border, theme.ACCENT, self._active_t)
        ink = lerp_color(theme.MUTED, theme.TEXT, max(self._hover_t, self._active_t))
        visual_rect = self.rect.move(0, int(round(self._press_t * 2)))
        rounded_rect(surface, visual_rect, bg, min(14, visual_rect.h // 2), 1, border)
        if self._hover_t > 0.01:
            sheen_w = max(1, int((visual_rect.w - 24) * self._hover_t))
            pygame.draw.line(surface, lerp_color(bg, theme.TEXT, 0.22),
                             (visual_rect.x + 12, visual_rect.y + 2),
                             (visual_rect.x + 12 + sheen_w, visual_rect.y + 2), 1)
        if self._active_t > 0.01:
            indicator_w = int((visual_rect.w - 24) * self._active_t)
            pygame.draw.rect(surface, theme.ACCENT,
                             (visual_rect.centerx - indicator_w // 2,
                              visual_rect.bottom - 3, indicator_w, 2),
                             border_radius=1)
        draw_text(surface, self.text, visual_rect.center,
                  FONT_SMALL, ink, anchor="center", max_width=self.rect.w - 12)

    def clicked(self, event):
        hit = (event.type == pygame.MOUSEBUTTONDOWN
               and event.button == 1
               and self.rect.collidepoint(event.pos))
        if hit:
            self._press_t = 1.0
        return hit


class InputBox:
    def __init__(self, key, label, x, y, w, value, unit=""):
        self.key = key
        self.label = label

        self.rect = pygame.Rect(x, y, w, 28)
        self.unit = unit
        self.text = self.format_value(value)
        self.old_text = self.text
        self.active = False

        self.cursor = len(self.text)
        self.anchor = self.cursor
        self.dragging = False
        self.blink_timer = 0.0
        self.show_cursor = True

        self.invalid_flash = 0.0

    def format_value(self, value):
        if self.key in ("anim_speed", "speed"):
            return f"{value:.2f}"
        return format_num(value)

    def set_rect(self, x, y, w, h=None):
        """响应式重排：更新输入框矩形。"""
        self.rect = pygame.Rect(int(x), int(y), max(40, int(w)),
                                self.rect.h if h is None else int(h))

    def set_text_value(self, value):
        if not self.active:
            self.text = self.format_value(value)
            self.cursor = len(self.text)

            self.anchor = self.cursor
            self.old_text = self.text

    def has_selection(self):
        return self.cursor != self.anchor

    def selection_range(self):
        return min(self.cursor, self.anchor), max(self.cursor, self.anchor)

    def text_width(self, s):
        return FONT_SMALL.size(s)[0]

    def index_from_mouse_x(self, mx):
        rel_x = max(0, mx - (self.rect.x + 7))

        best, best_dist = 0, 10**9
        for i in range(len(self.text) + 1):
            dist = abs(self.text_width(self.text[:i]) - rel_x)
            if dist < best_dist:
                best_dist, best = dist, i
        return best

    def delete_selection(self):
        if not self.has_selection():
            return False

        a, b = self.selection_range()
        self.text = self.text[:a] + self.text[b:]
        self.cursor = self.anchor = a
        return True

    def insert_text(self, s):
        self.delete_selection()

        self.text = self.text[:self.cursor] + s + self.text[self.cursor:]
        self.cursor += len(s)
        self.anchor = self.cursor

    def move_cursor(self, new_pos, selecting=False):
        self.cursor = int(clamp(new_pos, 0, len(self.text)))
        if not selecting:
            self.anchor = self.cursor


    def consume_key(self, event):
        ctrl = bool(event.mod & pygame.KMOD_CTRL)
        shift = bool(event.mod & pygame.KMOD_SHIFT)
        if ctrl and event.key == pygame.K_a:
            self.anchor, self.cursor = 0, len(self.text)
            return None
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.active = self.dragging = False

            return "commit", self.key, self.text
        if event.key == pygame.K_ESCAPE:
            self.text = self.old_text
            self.cursor = self.anchor = len(self.text)
            self.active = self.dragging = False
            return "cancel", self.key, None
        if event.key == pygame.K_LEFT:
            self.move_cursor(self.cursor - 1, shift)
        elif event.key == pygame.K_RIGHT:
            self.move_cursor(self.cursor + 1, shift)
        elif event.key == pygame.K_HOME:
            self.move_cursor(0, shift)
        elif event.key == pygame.K_END:
            self.move_cursor(len(self.text), shift)
        elif event.key == pygame.K_BACKSPACE:
            if not self.delete_selection() and self.cursor > 0:
                self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]

                self.cursor -= 1
                self.anchor = self.cursor
        elif event.key == pygame.K_DELETE:
            if not self.delete_selection() and self.cursor < len(self.text):
                self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
                self.anchor = self.cursor
        elif event.unicode in "0123456789.-+eE":
            self.insert_text(event.unicode)
        return None

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True

                self.old_text = self.text
                idx = self.index_from_mouse_x(event.pos[0])
                self.cursor = self.anchor = idx
                self.dragging = True
                self.blink_timer = 0.0

                self.show_cursor = True
                return "consume", self.key, None
            if self.active:
                self.active = self.dragging = False
                return "commit", self.key, self.text
        elif event.type == pygame.MOUSEMOTION and self.active and self.dragging:
            self.cursor = self.index_from_mouse_x(event.pos[0])
            return "consume", self.key, None
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            self.dragging = False

            return "consume", self.key, None
        elif event.type == pygame.KEYDOWN and self.active:
            result = self.consume_key(event)
            return result if result is not None else ("consume", self.key, None)
        return None

    def update(self, dt):
        if self.active:
            self.blink_timer += dt
            if self.blink_timer >= 0.42:
                self.blink_timer = 0.0

                self.show_cursor = not self.show_cursor
        else:
            self.show_cursor = False
        self.invalid_flash = max(0.0, self.invalid_flash - dt * 3.0)

    def draw(self, surface):
        # 参数名称已由 ParameterPanel 在单元第一行统一绘制。旧的
        # “精确输入”辅助标签会侵入面板标题，尤其遮挡第一行，故不再常驻。
        border = theme.RED if self.invalid_flash > 0 else (
            theme.INPUT_ACTIVE if self.active else theme.INPUT_BORDER
        )
        rounded_rect(surface, self.rect, theme.INPUT_BG, 7, 1, border)

        text_x = self.rect.x + 7
        text_y = self.rect.centery - FONT_SMALL.get_height() // 2
        if self.active and self.has_selection():
            a, b = self.selection_range()
            sx = text_x + self.text_width(self.text[:a])
            sw = self.text_width(self.text[a:b])
            pygame.draw.rect(surface, theme.SELECT_BG,
                             (sx, self.rect.y + 4,
                              max(1, sw), self.rect.h - 8),
                             border_radius=3)
        draw_text(surface, self.text, (text_x, text_y), FONT_SMALL, theme.TEXT)

        if self.active and self.show_cursor:
            cx = text_x + self.text_width(self.text[:self.cursor])
            pygame.draw.line(surface, theme.color((245, 250, 255)),
                             (cx, self.rect.y + 5),
                             (cx, self.rect.bottom - 5), 1)
        if self.unit:
            draw_text(surface, self.unit,
                      (self.rect.right + 5,
                       self.rect.centery - FONT_TINY.get_height() // 2),
                      FONT_TINY, theme.MUTED)


@dataclass
class Toggle:
    """参数面板用滑动开关：胶囊轨道 + 圆形旋钮，点击切换布尔状态。"""

    x: int
    y: int
    value: bool = True

    track_w: int = 46
    track_h: int = 22
    _hover: bool = field(default=False, init=False, repr=False)
    _position: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self):
        self.rect = pygame.Rect(int(self.x), int(self.y), self.track_w,
                                self.track_h)
        self._position = 1.0 if self.value else 0.0

    def set_rect(self, x, y):
        """响应式重排：更新开关位置（尺寸固定）。"""
        self.x = int(x)
        self.y = int(y)
        self.rect = pygame.Rect(self.x, self.y, self.track_w, self.track_h)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.inflate(8, 12).collidepoint(event.pos):
                self.value = not self.value
                return True
        return False

    def draw(self, surface):
        self._hover = self.rect.collidepoint(pygame.mouse.get_pos())
        target = 1.0 if self.value else 0.0
        self._position += (target - self._position) * 0.22
        hover = 1.0 if self._hover else 0.0
        track = lerp_color(theme.color((27, 37, 35)), theme.color((34, 96, 84)), self._position)
        border = lerp_color(theme.color((61, 83, 79)), theme.color((96, 210, 170)), self._position)
        knob = lerp_color(theme.color((76, 104, 99)), theme.ACCENT_3, self._position)
        track = lerp_color(track, theme.color((48, 68, 62)), hover * (1.0 - self._position) * .5)
        if theme.current in ('light', 'dark'):
            track = lerp_color(theme.INPUT_BORDER, (48, 209, 88), self._position)
            border = track
            knob = (255, 255, 255)

        rounded_rect(surface, self.rect, track, self.track_h // 2, 1, border)
        left = self.rect.x + self.track_h // 2
        right = self.rect.right - self.track_h // 2
        knob_x = int(round(left + (right - left) * self._position))
        pygame.draw.circle(surface, (12, 16, 16),
                           (knob_x + 1, self.rect.centery + 1), 8)
        pygame.draw.circle(surface, knob, (knob_x, self.rect.centery), 8)

        state = "开" if self.value else "关"
        draw_text(surface, state, (self.rect.x - 10, self.rect.y + 3),
                  FONT_TINY, theme.ACCENT_3 if self.value else theme.MUTED,
                  anchor="topright")

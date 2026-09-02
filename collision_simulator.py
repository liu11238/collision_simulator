"""
弹性碰撞仿真器

包含两个理想弹性碰撞模型：
1. 两自由质点一维碰撞
2. 质点与定轴细杆碰撞

运行环境：Python 3 + pygame
"""

from __future__ import annotations

import math

import os
import random
import sys
from dataclasses import dataclass, field
from typing import Callable


import pygame

# ============================ 基础设置 ============================
WIDTH, HEIGHT = 1280, 960
FPS = 60
UI_H = 340
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

pygame.init()
pygame.display.set_caption('弹性碰撞仿真器')
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# 可复用透明层
particle_surf = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()

trail_surf_1 = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
trail_surf_2 = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
glow_surf = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
flash_surf = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()


# ============================ 字体 ============================
def get_font(size: int, bold: bool = False):
    win_dir = os.environ.get("WINDIR", r"C:\Windows")

    paths = [
        os.path.join(win_dir, "Fonts", "msyh.ttc"),
        os.path.join(win_dir, "Fonts", "msyhbd.ttc"),
        os.path.join(win_dir, "Fonts", "simhei.ttf"),
        os.path.join(win_dir, "Fonts", "simsun.ttc"),
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, size)
                font.set_bold(bold)
                return font
            except Exception:
                pass
    font = pygame.font.Font(None, size)

    font.set_bold(bold)
    return font


FONT = get_font(20)
FONT_SMALL = get_font(16)
FONT_TINY = get_font(14)

FONT_BIG = get_font(27, True)
FONT_TITLE = get_font(34, True)
TITLE_LETTER_SPACING = 6  # 标题字符之间的横向间距（像素）


# ============================ 工具函数 ============================
def clamp(x, a, b):
    return max(a, min(b, x))


def lerp(a, b, t):
    return a + (b - a) * t



def lerp_color(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def draw_text(surface, text, pos, font=FONT, color=TEXT, anchor="topleft"):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(img, rect)

    return rect


def draw_spaced_text(surface, text, pos, font=FONT, color=TEXT,
                     spacing=0, anchor="topleft"):
    """逐字绘制文本，并在相邻字符之间加入指定的横向间距。"""
    text = str(text)
    if not text:
        rect = pygame.Rect(0, 0, 0, font.get_height())
        setattr(rect, anchor, pos)

        return rect

    glyphs = [font.render(char, True, color) for char in text]
    total_width = sum(glyph.get_width() for glyph in glyphs)
    total_width += max(0, len(glyphs) - 1) * spacing
    total_height = max(font.get_height(), *(glyph.get_height() for glyph in glyphs))


    rect = pygame.Rect(0, 0, total_width, total_height)
    setattr(rect, anchor, pos)

    x = rect.x
    for index, glyph in enumerate(glyphs):
        y = rect.y + (total_height - glyph.get_height()) // 2
        surface.blit(glyph, (x, y))

        x += glyph.get_width()
        if index < len(glyphs) - 1:
            x += spacing
    return rect

def rounded_rect(surface, rect, color, radius=14, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surface, border_color, rect, width=border, border_radius=radius)



def draw_gradient_3(surface, rect, c_top, c_mid, c_bot):
    x, y, w, h = rect
    half = h // 2
    for i in range(half):
        c = lerp_color(c_top, c_mid, i / max(1, half - 1))
        pygame.draw.line(surface, c, (x, y + i), (x + w, y + i))
    for i in range(h - half):
        c = lerp_color(c_mid, c_bot, i / max(1, h - half - 1))

        pygame.draw.line(surface, c, (x, y + half + i), (x + w, y + half + i))


def draw_horizontal_gradient_line(surface, x, y, w, c1, c2, height=1):
    width = max(0, int(w))
    for i in range(width):
        c = lerp_color(c1, c2, i / max(1, width - 1))
        pygame.draw.line(surface, c, (x + i, y), (x + i, y + height - 1))


def draw_arrow(surface, start, end, color, width=3):
    pygame.draw.line(surface, color, start, end, width)
    dx = end[0] - start[0]

    dy = end[1] - start[1]
    ang = math.atan2(dy, dx)
    size = 12
    left = (
        end[0] - size * math.cos(ang - 0.45),
        end[1] - size * math.sin(ang - 0.45),
    )
    right = (
        end[0] - size * math.cos(ang + 0.45),
        end[1] - size * math.sin(ang + 0.45),
    )

    pygame.draw.polygon(surface, color, [end, left, right])


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


def create_static_background():
    bg = pygame.Surface((WIDTH, SIM_H)).convert()
    draw_gradient_3(bg, (0, 0, WIDTH, SIM_H), BG_TOP, BG_MID, BG_BOTTOM)

    stars = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
    rng = random.Random(42)

    for _ in range(130):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, SIM_H - 1)
        a = rng.randint(35, 135)
        r = rng.randint(1, 2)
        pygame.draw.circle(stars, (200, 215, 255, a), (x, y), r)
    bg.blit(stars, (0, 0))


    soft = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()
    for r, a in [(280, 12), (195, 18), (120, 26), (65, 36)]:
        pygame.draw.circle(soft, (70, 130, 255, a), (1010, 110), r)
    for r, a in [(170, 10), (95, 16)]:
        pygame.draw.circle(soft, (255, 125, 90, a), (180, SIM_H - 85), r)
    bg.blit(soft, (0, 0))

    grid = pygame.Surface((WIDTH, SIM_H), pygame.SRCALPHA).convert_alpha()

    for x in range(0, WIDTH, 50):
        pygame.draw.line(grid, (255, 255, 255, 8), (x, 0), (x, SIM_H))
    for y in range(0, SIM_H, 50):
        pygame.draw.line(grid, (255, 255, 255, 7), (0, y), (WIDTH, y))
    for x in range(0, WIDTH, 100):
        pygame.draw.line(grid, (255, 255, 255, 14), (x, 0), (x, SIM_H))
    for y in range(0, SIM_H, 100):
        pygame.draw.line(grid, (255, 255, 255, 12), (0, y), (WIDTH, y))
    bg.blit(grid, (0, 0))

    return bg


STATIC_BG = create_static_background()


# ============================ UI 控件 ============================
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

    def knob_x(self):
        t = (self.value - self.vmin) / max(1e-12, self.vmax - self.vmin)
        return int(self.x + clamp(t, 0.0, 1.0) * self.w)

    def set_value(self, value):
        self.value = clamp(float(value), self.vmin, self.vmax)

    def set_from_mouse(self, mx):
        t = clamp((mx - self.x) / self.w, 0.0, 1.0)

        self.value = self.vmin + t * (self.vmax - self.vmin)

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

    def draw(self, surface, value_text=None):
        pygame.draw.line(surface, (40, 50, 80),
                         (self.x, self.y + 2), (self.x + self.w, self.y + 2), 8)
        pygame.draw.line(surface, (55, 68, 105),
                         (self.x, self.y), (self.x + self.w, self.y), 6)
        kx = self.knob_x()
        if kx > self.x:
            pygame.draw.line(surface, ACCENT,
                             (self.x, self.y), (kx, self.y), 6)

        for i in range(6):
            tx = self.x + i * self.w / 5
            pygame.draw.line(surface, (80, 95, 135),
                             (tx, self.y - 6), (tx, self.y + 6), 1)
        pygame.draw.circle(surface, (4, 8, 18), (kx + 2, self.y + 3), 14)
        pygame.draw.circle(surface, (50, 80, 130), (kx, self.y), 14)
        pygame.draw.circle(surface, ACCENT, (kx, self.y), 12)

        pygame.draw.circle(surface, (140, 200, 255), (kx, self.y), 8)
        pygame.draw.circle(surface, (220, 245, 255), (kx - 4, self.y - 4), 4)
        draw_text(surface, self.label, (self.x, self.y - 30), FONT_SMALL, MUTED)
        if value_text is None:
            value_text = f"{format_sig3(self.value)}{self.unit}"
        draw_text(surface, value_text, (self.x + self.w, self.y - 30),
                  FONT_SMALL, TEXT, anchor="topright")



@dataclass
class Button:
    text: str
    rect: pygame.Rect
    _hover: bool = field(default=False, init=False, repr=False)

    def draw(self, surface, active=False):
        self._hover = self.rect.collidepoint(pygame.mouse.get_pos())
        if active:
            bg, border = (45, 88, 145), (100, 160, 240)
        elif self._hover:
            bg, border = (38, 52, 90), (90, 115, 165)
        else:
            bg, border = (28, 38, 66), (65, 82, 125)
        rounded_rect(surface, self.rect, bg, 12, 1, border)

        pygame.draw.rect(surface, (230, 240, 255),
                         (self.rect.x + 5, self.rect.y + 2,
                          self.rect.w - 10, 2), border_radius=2)
        draw_text(surface, self.text, self.rect.center,
                  FONT_SMALL, TEXT, anchor="center")

    def clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


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
        draw_text(surface, self.label,
                  (self.rect.x, self.rect.y - 18), FONT_TINY, MUTED)
        border = RED if self.invalid_flash > 0 else (
            INPUT_ACTIVE if self.active else INPUT_BORDER
        )
        rounded_rect(surface, self.rect, INPUT_BG, 7, 1, border)

        text_x, text_y = self.rect.x + 7, self.rect.y + 6
        if self.active and self.has_selection():
            a, b = self.selection_range()
            sx = text_x + self.text_width(self.text[:a])
            sw = self.text_width(self.text[a:b])
            pygame.draw.rect(surface, SELECT_BG,
                             (sx, self.rect.y + 4,
                              max(1, sw), self.rect.h - 8),
                             border_radius=3)
        surface.blit(FONT_SMALL.render(self.text, True, TEXT), (text_x, text_y))

        if self.active and self.show_cursor:
            cx = text_x + self.text_width(self.text[:self.cursor])
            pygame.draw.line(surface, (245, 250, 255),
                             (cx, self.rect.y + 5),
                             (cx, self.rect.bottom - 5), 1)
        if self.unit:
            draw_text(surface, self.unit,
                      (self.rect.right + 5, self.rect.y + 6), FONT_TINY, MUTED)


# ============================ 粒子系统 ============================
class Particle:
    __slots__ = (
        "kind", "x", "y", "vx", "vy", "life", "max_life", "size",
        "color_start", "color_end", "trail", "max_trail", "angle", "spin"
    )

    def __init__(self, kind, x, y, vx, vy, life, size=3.0,
                 color_start=(255, 240, 160), color_end=(255, 80, 20),
                 trail_len=0, angle=0.0, spin=0.0):
        self.kind = kind

        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.size = size
        self.color_start, self.color_end = color_start, color_end

        self.trail = []
        self.max_trail = trail_len
        self.angle, self.spin = angle, spin

    @property
    def t(self):
        return clamp(self.life / max(1e-9, self.max_life), 0.0, 1.0)

    def step(self, dt, gravity=0.0):
        if self.max_trail > 0:
            self.trail.append((self.x, self.y))

            if len(self.trail) > self.max_trail:
                self.trail.pop(0)
        self.vx *= max(0.0, 1.0 - 0.60 * dt)
        self.vy = self.vy * max(0.0, 1.0 - 0.25 * dt) + gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        self.angle += self.spin * dt
        self.life -= dt

    def draw(self, surface, world_to_screen: Callable[[float, float], tuple[int, int]], streak_scale=8.0):
        sx, sy = world_to_screen(self.x, self.y)
        if sx < -120 or sx > WIDTH + 120 or sy < -120 or sy > SIM_H + 120:
            return
        t = self.t
        alpha = int(255 * t)

        color = lerp_color(self.color_end, self.color_start, t)
        size = max(1.0, self.size * t)

        if self.kind == "spark":
            for i in range(len(self.trail) - 1):
                p1 = world_to_screen(*self.trail[i])
                p2 = world_to_screen(*self.trail[i + 1])
                a = int(alpha * (i + 1) / max(1, len(self.trail)) * 0.65)

                pygame.draw.line(surface, (*color, a), p1, p2,
                                 max(1, int(size * 0.6)))
            pygame.draw.circle(surface, (*color, alpha), (sx, sy), max(1, int(size)))
        elif self.kind == "ember":
            r = max(2, int(size * 1.4))
            pygame.draw.circle(surface, (*color, max(0, alpha - 90)), (sx, sy), r + 3)
            pygame.draw.circle(surface, (*color, alpha), (sx, sy), r)
        elif self.kind == "debris":
            half = max(1, int(size))
            ca, sa = math.cos(self.angle), math.sin(self.angle)

            pts = []
            for px, py in [(-half, -half), (half, -half), (half, half), (-half, half)]:
                pts.append((int(sx + px * ca - py * sa),
                            int(sy + px * sa + py * ca)))
            pygame.draw.polygon(surface, (*color, alpha), pts)
        elif self.kind == "streak":
            speed = math.hypot(self.vx, self.vy)
            if speed > 0.01:
                nx, ny = self.vx / speed, self.vy / speed
                tail = clamp(speed * streak_scale, 4, 48)

                end = (sx - int(nx * tail), sy - int(ny * tail))
                pygame.draw.line(surface, (*color, alpha),
                                 (sx, sy), end, max(1, int(size)))


class ShockWave:
    __slots__ = ("x", "y", "r", "max_r", "life", "max_life", "color", "width")

    def __init__(self, x, y, max_r, life, color, width=2):
        self.x, self.y = x, y
        self.r = 0.0

        self.max_r = max_r
        self.life = self.max_life = life
        self.color = color
        self.width = width

    def step(self, dt):
        self.life -= dt
        self.r = self.max_r * (1.0 - clamp(self.life / self.max_life, 0.0, 1.0))


    def draw(self, surface, world_to_screen, scale):
        t = clamp(self.life / max(1e-9, self.max_life), 0.0, 1.0)
        alpha = int(200 * t * t)
        sx, sy = world_to_screen(self.x, self.y)
        r = max(1, int(self.r * scale))
        pygame.draw.circle(surface, (*self.color, alpha), (sx, sy), r, self.width)

        if r > 7:
            pygame.draw.circle(surface, (255, 255, 255, alpha // 3),
                               (sx, sy), r - 3, 1)


def spawn_impact_particles(particles, shockwaves, x, y, strength, direction=1.0,
                           vertical_bias=0.0, symmetric=False):
    strength = clamp(abs(strength), 0.8, 14.0)
    root = math.sqrt(strength)

    for _ in range(52):
        side = random.choice((-1.0, 1.0)) if symmetric else direction
        ang = random.uniform(-0.95, 0.95)

        speed = random.uniform(0.7, 2.5) * root
        vx = side * abs(math.cos(ang)) * speed
        vy = math.sin(ang) * speed + vertical_bias
        particles.append(Particle(
            "spark", x, y, vx, vy, random.uniform(0.28, 0.72),
            size=random.uniform(2.0, 4.6),
            color_start=lerp_color((255, 255, 225), (255, 185, 45), random.random()),
            color_end=lerp_color((255, 100, 20), (120, 35, 12), random.random()),
            trail_len=random.randint(4, 9),
        ))

    for _ in range(28):
        ang = random.uniform(0, 2 * math.pi)

        speed = random.uniform(0.2, 1.3) * root
        particles.append(Particle(
            "ember", x, y,
            math.cos(ang) * speed,
            math.sin(ang) * speed + vertical_bias,
            random.uniform(0.5, 1.2),
            size=random.uniform(3.0, 6.0),
            color_start=(255, 215, 90),
            color_end=(60, 15, 5),
        ))

    for _ in range(12):
        side = random.choice((-1.0, 1.0)) if symmetric else direction
        ang = random.uniform(-1.2, 1.2)
        speed = random.uniform(0.5, 1.9) * root

        particles.append(Particle(
            "debris", x, y,
            side * abs(math.cos(ang)) * speed,
            math.sin(ang) * speed + vertical_bias,
            random.uniform(0.4, 0.9),
            size=random.uniform(3.5, 7.0),
            color_start=(240, 190, 90),
            color_end=(40, 15, 5),
            angle=random.uniform(0, 2 * math.pi),
            spin=random.uniform(-8, 8),
        ))

    for _ in range(18):
        side = random.choice((-1.0, 1.0)) if symmetric else direction
        speed = random.uniform(2.8, 6.5) * root
        particles.append(Particle(
            "streak", x, y,
            side * speed,
            random.uniform(-1.4, 1.4) + vertical_bias,
            random.uniform(0.10, 0.28),
            size=2.5,
            color_start=(255, 255, 255),
            color_end=(180, 220, 255),
        ))

    for radius, life, color, width in [
        (0.22, 0.22, (255, 240, 160), 3),
        (0.40, 0.34, (255, 180, 80), 2),
        (0.62, 0.48, (120, 200, 255), 2),
    ]:
        shockwaves.append(ShockWave(x, y, radius, life, color, width))



# ============================ 通用模型基类 ============================
LEFT_X, RIGHT_X = 38, 690
SLIDER_W = 380
INPUT_W, INPUT_GAP = 112, 18
LEFT_INPUT_X = LEFT_X + SLIDER_W + INPUT_GAP
RIGHT_INPUT_X = RIGHT_X + SLIDER_W + INPUT_GAP
BASE_Y = SIM_H + 62

ROW = 50


class BaseModel:
    name = ""
    short_name = ""

    def __init__(self):
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

        APP.btn_start.draw(screen, self.running)

        APP.btn_reset.draw(screen)
        APP.btn_snap.draw(screen)
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



# ============================ 模型二：质点‑定轴细杆碰撞（失重） ============================
class BallHitsRod(BaseModel):
    name = "质点‑定轴细杆碰撞仿真"
    short_name = "质点‑定轴细杆"

    def build_controls(self):
        self.add_control("m", "小球质量 m", 0, 0, 0.05, 10.0, 1.00, " kg", 3)
        self.add_control("M", "杆质量 M", 0, 1, 0.10, 20.0, 4.00, " kg", 3)
        self.add_control("u0", "小球入射速率 u0", 0, 2, 0.00, 15.0, 5.00, " m/s", 3)

        self.add_control("L", "杆长 L", 1, 0, 0.25, 2.00, 1.00, " m", 3)
        self.add_control("height_ratio", "碰撞高度 h/L", 1, 1, 0.00, 1.00, 0.72, "", 4)
        self.add_control("anim_speed", "动画速度", 1, 2, 0.20, 2.50, 1.00, "x", 2)
        self.input_boxes.pop("height_ratio")
        self.input_boxes["h"] = InputBox(
            "h", "精确输入", RIGHT_INPUT_X, BASE_Y + ROW - 8,
            INPUT_W, self.current_h(), "m"
        )


    def current_h(self):
        return self.sliders["height_ratio"].value * self.sliders["L"].value

    def input_values(self):
        return {
            "m": self.sliders["m"].value,
            "M": self.sliders["M"].value,
            "u0": self.sliders["u0"].value,
            "L": self.sliders["L"].value,
            "h": self.current_h(),
            "anim_speed": self.sliders["anim_speed"].value,
        }

    def set_control_value(self, key, value):
        if key == "L":
            old_h = self.current_h()
            self.sliders["L"].set_value(value)
            self.sliders["height_ratio"].set_value(old_h / max(1e-9, self.sliders["L"].value))
        elif key == "h":
            L = self.sliders["L"].value

            self.sliders["height_ratio"].set_value(clamp(value, 0.0, L) / max(1e-9, L))
        else:
            self.sliders[key].set_value(value)

    def ball_radius_world(self):
        return 0.055 * self.sliders["L"].value

    def start_x(self):
        # 小球位于杆的左侧，向右运动并撞击竖直杆。
        return -(self.ball_radius_world() + 0.85 * self.sliders["L"].value)

    def reset(self, keep_running=False):
        self.running = keep_running
        self.phase = "ready"
        self.theta = math.pi / 2

        self.omega = 0.0
        self.ball_x = self.start_x()
        self.ball_v = self.sliders["u0"].value
        self.t = 0.0
        self.collided = False

        self.flash = 0.0
        self.last_result = None
        self.rod_trail = []
        self.ball_trail = []
        self.particles.clear()

        self.shockwaves.clear()
        self.notice = ""

    def start_pause(self):
        if self.phase == "ready":
            self.phase = "approaching"
        self.running = not self.running

    def jump_to_collision(self):
        self.phase = "approaching"

        self.ball_x = -self.ball_radius_world()
        self.ball_v = self.sliders["u0"].value
        self.do_collision()
        self.running = True

    def do_collision(self):
        m = self.sliders["m"].value

        M = self.sliders["M"].value
        L = self.sliders["L"].value
        h = self.current_h()
        I = M * L * L / 3.0
        e = 1.0
        u_before = self.ball_v

        omega_before = self.omega
        relative_before = u_before - h * omega_before
        denominator = 1.0 / m + h * h / I
        impulse = -(1.0 + e) * relative_before / denominator
        v_after = u_before + impulse / m

        omega_after = omega_before - impulse * h / I

        ke_before = 0.5 * m * u_before * u_before + 0.5 * I * omega_before * omega_before
        ke_after = 0.5 * m * v_after * v_after + 0.5 * I * omega_after * omega_after

        # 绕定轴的有符号角动量。按本程序的坐标/转向约定，
        # 杆为 I*w，小球为 m*h*v；两者之和应在碰撞瞬间守恒。
        rod_L_before = I * omega_before
        ball_MRV_before = m * h * u_before

        total_L_before = rod_L_before + ball_MRV_before
        rod_L_after = I * omega_after
        ball_MRV_after = m * h * v_after
        total_L_after = rod_L_after + ball_MRV_after

        self.ball_v = v_after

        self.omega = omega_after
        self.phase = "after"
        self.collided = True
        self.flash = 1.0
        self.last_result = {
            "I": I,
            "h": h,
            "u_before": u_before,
            "v_after": v_after,
            "omega_before": omega_before,
            "omega_after": omega_after,
            "contact_before": h * omega_before,
            "contact_after": h * omega_after,
            "relative_before": relative_before,
            "relative_after": v_after - h * omega_after,
            "impulse": impulse,
            "ke_before": ke_before,
            "ke_after": ke_after,
            "rod_L_before": rod_L_before,
            "ball_MRV_before": ball_MRV_before,
            "total_L_before": total_L_before,
            "rod_L_after": rod_L_after,
            "ball_MRV_after": ball_MRV_after,
            "total_L_after": total_L_after,
            "impact_time": self.t,
        }

        direction = -1.0 if impulse > 0 else 1.0
        spawn_impact_particles(self.particles, self.shockwaves, 0.0, h,
                               relative_before, direction=direction, vertical_bias=-0.3)

    def step(self, dt):
        if not self.running:
            return
        h = self.current_h()
        speed = self.sliders["anim_speed"].value

        sim_dt = dt * speed
        self.t += sim_dt
        n = max(1, int(sim_dt / 0.0025))
        sub = sim_dt / n

        for _ in range(n):
            if self.phase == "approaching":
                old_x = self.ball_x
                self.ball_x += self.ball_v * sub

                contact_x = -self.ball_radius_world()
                if old_x < contact_x and self.ball_x >= contact_x:
                    self.ball_x = contact_x
                    self.do_collision()
            elif self.phase == "after":
                # 失重环境：无外力矩，杆角速度保持不变；小球做匀速直线运动。
                self.ball_x += self.ball_v * sub
                self.theta += self.omega * sub

        self.step_particles(dt, gravity=0.0)

        self.flash = max(0.0, self.flash - sim_dt * 2.2)
        if not self.rod_trail or abs(self.rod_trail[-1] - self.theta) > 0.010:
            self.rod_trail.append(self.theta)
            if len(self.rod_trail) > 70:
                self.rod_trail.pop(0)
        self.ball_trail.append((self.ball_x, h))
        if len(self.ball_trail) > 75:
            self.ball_trail.pop(0)


    def formula_lines(self):
        return (
            "L_rod=I*w，MRV=m*h*v",
            "绕定轴角动量守恒：I*w + m*h*v = constant",
        )

    def summary_line(self):
        return (f"失重  m={format_sig3(self.sliders['m'].value)}  M={format_sig3(self.sliders['M'].value)}  "
                f"L={format_sig3(self.sliders['L'].value)}  h={format_sig3(self.current_h())}  "
                f"u0={format_sig3(self.sliders['u0'].value)}")

    def draw_slider_value(self, key, slider):
        if key == "height_ratio":
            slider.draw(screen, f"h = {format_sig3(self.current_h())} m  ({format_sig3(slider.value)}L)")
        else:
            slider.draw(screen)

    def draw_scene(self):
        m = self.sliders["m"].value
        M = self.sliders["M"].value

        L = self.sliders["L"].value
        h = self.current_h()
        I = M * L * L / 3.0
        rb = self.ball_radius_world()
        # 物理长度整体缩小为原版的 1/3，但画面中的视觉尺寸保持接近原版。
        # 也就是说：当前 L=1 m 对应原版约 L=3 m 的屏幕占用，
        # 当前最大 L=2 m 对应原版约 L=6 m 的屏幕占用。
        # 不能简单固定把 px/m 乘 3，否则 L=2 m 时会超出画面；
        # 因此按“原版等效长度 = 3L”计算自适应比例，再把 px/m 放大 3 倍。
        physical_scale_ratio = 3.0

        equivalent_old_L = physical_scale_ratio * L
        old_scale = min(
            145.0,
            395.0 / equivalent_old_L,
            (SIM_H - 235) / (equivalent_old_L + 0.35),
        )
        scale = physical_scale_ratio * old_scale
        # 杆放在画面右侧，小球从左侧向右入射。
        pivot = (565, 195)

        def w2s(x, y):
            return int(pivot[0] + x * scale), int(pivot[1] + y * scale)

        screen.blit(STATIC_BG, (0, 0))

        self.draw_header({"ready": "待开始", "approaching": "小球接近杆", "after": "碰撞后运动"}.get(self.phase, self.phase))
        APP.draw_mode_tabs()

        platform_y = h + rb
        sx1, sy = w2s(min(-1.5 * L, self.ball_x - 0.8 * L), platform_y)
        sx2, _ = w2s(1.25 * L, platform_y)

        sx1, sx2 = max(-80, sx1), min(WIDTH + 80, sx2)
        pygame.draw.line(screen, (22, 28, 48), (sx1, sy + 10), (sx2, sy + 10), 10)
        pygame.draw.line(screen, (35, 44, 70), (sx1, sy + 4), (sx2, sy + 4), 8)
        pygame.draw.line(screen, PLATFORM, (sx1, sy), (sx2, sy), 5)
        pygame.draw.line(screen, PLATFORM_TOP, (sx1, sy - 1), (sx2, sy - 1), 2)

        for tx in range(max(-40, sx1), min(WIDTH + 40, sx2), 18):
            pygame.draw.line(screen, (100, 115, 155), (tx, sy), (tx + 6, sy + 4), 1)

        hx, hy = w2s(-0.36 * L, h)
        pygame.draw.line(screen, (100, 120, 165), (hx, pivot[1]), (hx, hy), 2)
        pygame.draw.line(screen, (100, 120, 165), (hx - 9, pivot[1]), (hx + 9, pivot[1]), 2)
        pygame.draw.line(screen, (100, 120, 165), (hx - 9, hy), (hx + 9, hy), 2)

        draw_text(screen, f"h={format_sig3(h)}m", (hx - 10, (pivot[1] + hy) // 2), FONT_SMALL, MUTED, anchor="midright")

        trail_surf_1.fill((0, 0, 0, 0))
        # 视觉上把杆做细；仅改变绘制宽度，不改变质量、长度或转动惯量。
        rod_w = max(5, int(0.028 * scale))
        for i, theta in enumerate(self.rod_trail):
            p = i / max(1, len(self.rod_trail) - 1)
            end = w2s(-L * math.cos(theta), L * math.sin(theta))

            pygame.draw.line(trail_surf_1, (*ROD_GLOW, int(10 + 45 * p)), pivot, end,
                             max(2, int(rod_w * (0.35 + 0.65 * p))))
        screen.blit(trail_surf_1, (0, 0))

        end = w2s(-L * math.cos(self.theta), L * math.sin(self.theta))
        glow_surf.fill((0, 0, 0, 0))
        pygame.draw.line(glow_surf, (*ROD_GLOW, 35), pivot, end, rod_w + 12)
        pygame.draw.line(glow_surf, (*ROD_GLOW, 60), pivot, end, rod_w + 5)

        screen.blit(glow_surf, (0, 0))
        pygame.draw.line(screen, (0, 0, 0), (pivot[0] + 5, pivot[1] + 7),
                         (end[0] + 5, end[1] + 7), rod_w + 4)
        pygame.draw.line(screen, ROD_COLOR, pivot, end, rod_w)
        pygame.draw.line(screen, ROD_EDGE, pivot, end, max(2, rod_w // 4))
        pygame.draw.circle(screen, (160, 110, 30), end, rod_w // 2 + 3)

        pygame.draw.circle(screen, ROD_EDGE, end, max(3, rod_w // 4))

        px, py = pivot
        pygame.draw.rect(screen, (38, 48, 76), (px - 24, py - 38, 14, 76), border_radius=5)
        pygame.draw.circle(screen, (5, 8, 18), (px + 3, py + 4), 26)
        pygame.draw.circle(screen, (50, 62, 95), pivot, 24)

        pygame.draw.circle(screen, (28, 38, 64), pivot, 20)
        pygame.draw.circle(screen, (65, 82, 128), pivot, 16)
        pygame.draw.circle(screen, ACCENT, pivot, 6)
        pygame.draw.circle(screen, (210, 240, 255), pivot, 3)

        # 角速度固定显示在定轴旁，避免随杆转动而移动。
        w_rect = pygame.Rect(px + 32, py - 30, 190, 34)

        rounded_rect(screen, w_rect, (12, 20, 38), 9, 1, (70, 95, 145))
        draw_text(screen, f"w = {format_sig3(self.omega)} rad/s", w_rect.center,
                  FONT_SMALL, ACCENT_3, anchor="center")

        cpx, cpy = w2s(-h * math.cos(self.theta), h * math.sin(self.theta))
        pygame.draw.circle(screen, ACCENT_2, (cpx, cpy), 9, 2)
        pygame.draw.circle(screen, (255, 255, 255), (cpx, cpy), 4)


        trail_surf_2.fill((0, 0, 0, 0))
        for i, (bx, by) in enumerate(self.ball_trail):
            p = i / max(1, len(self.ball_trail) - 1)
            pos = w2s(bx, by)
            if -100 <= pos[0] <= WIDTH + 100:
                r = max(2, int(rb * scale * (0.22 + 0.40 * p)))
                pygame.draw.circle(trail_surf_2, (*BALL1_GLOW, int(12 + 75 * p)), pos, r + 3)

                pygame.draw.circle(trail_surf_2, (*BALL1_COLOR, int(12 + 75 * p)), pos, r)
        screen.blit(trail_surf_2, (0, 0))

        particle_surf.fill((0, 0, 0, 0))
        for particle in self.particles:
            particle.draw(particle_surf, w2s, streak_scale=scale * 0.08)
        for wave in self.shockwaves:
            wave.draw(particle_surf, w2s, scale)
        screen.blit(particle_surf, (0, 0))


        ball_pos = w2s(self.ball_x, h)
        br = max(12, int(rb * scale))
        pygame.draw.ellipse(screen, (0, 0, 0),
                            (ball_pos[0] - br - 4, sy - max(3, br // 4), 2 * br + 8, max(6, br // 2)))
        glow_surf.fill((0, 0, 0, 0))
        pygame.draw.circle(glow_surf, (*BALL1_GLOW, 28), ball_pos, br + 20)

        pygame.draw.circle(glow_surf, (*BALL1_GLOW, 45), ball_pos, br + 12)
        screen.blit(glow_surf, (0, 0))
        pygame.draw.circle(screen, (4, 10, 23), (ball_pos[0] + 4, ball_pos[1] + 5), br + 2)
        pygame.draw.circle(screen, BALL1_COLOR, ball_pos, br)
        pygame.draw.circle(screen, (31, 125, 190), ball_pos, br, 2)

        pygame.draw.circle(screen, BALL1_EDGE,
                           (ball_pos[0] - br // 3, ball_pos[1] - br // 3), max(3, br // 4))
        pygame.draw.circle(screen, (255, 255, 255),
                           (ball_pos[0] - br // 3 - 1, ball_pos[1] - br // 3 - 1), max(2, br // 7))

        if self.flash > 0:
            contact = w2s(0.0, h)
            flash_surf.fill((0, 0, 0, 0))
            f = self.flash

            r0 = int(clamp((1.15 - f) * 80 + 10, 5, 90))
            a0 = int(220 * f)
            pygame.draw.circle(flash_surf, (255, 255, 255, a0), contact, r0)
            pygame.draw.circle(flash_surf, (255, 210, 80, int(a0 * 0.45)), contact, r0 + int(30 * f))
            pygame.draw.circle(flash_surf, (120, 180, 255, int(a0 * 0.20)), contact, r0 + int(55 * f))

            screen.blit(flash_surf, (0, 0))

        if abs(self.ball_v) > 0.01:
            arrow_len = clamp(abs(self.ball_v) * scale * 0.07, 35, 150)
            direction = 1 if self.ball_v > 0 else -1
            ay = ball_pos[1] - br - 12
            finish = (int(ball_pos[0] + direction * arrow_len), ay)
            draw_arrow(screen, (ball_pos[0], ay), finish, GREEN, 3)

            draw_text(screen, f"v={format_sig3(self.ball_v)} m/s",
                      (finish[0] + (10 if direction > 0 else -10), ay - 12), FONT_SMALL, GREEN,
                      anchor="topleft" if direction > 0 else "topright")

        if not self.collided:
            draw_text(screen, f"入射速率 u0={format_sig3(self.sliders['u0'].value)} m/s",
                      (245, 205), FONT_SMALL, ACCENT_3)

        rod_L_now = I * self.omega
        ball_MRV_now = m * h * self.ball_v
        total_L_now = rod_L_now + ball_MRV_now

        current_lines = [
            f"转动惯量 I = {format_sig3(I)} kg*m^2",
            f"小球速度 v = {format_sig3(self.ball_v)} m/s",
            f"杆角速度 w = {format_sig3(self.omega)} rad/s",
            f"杆角动量 I*w = {format_sig3(rod_L_now)} kg*m^2/s",
            f"小球 MRV=m*h*v = {format_sig3(ball_MRV_now)} kg*m^2/s",
            f"总角动量 = {format_sig3(total_L_now)} kg*m^2/s",
        ]
        collision_lines = None
        if self.last_result:
            r = self.last_result
            collision_lines = [
                f"碰撞时刻 t = {format_sig3(r['impact_time'])} s",
                f"碰前杆角动量 = {format_sig3(r['rod_L_before'])}",
                f"碰前小球 MRV = {format_sig3(r['ball_MRV_before'])}",
                f"碰前总角动量 = {format_sig3(r['total_L_before'])}",
                f"碰后杆角动量 = {format_sig3(r['rod_L_after'])}",
                f"碰后小球 MRV = {format_sig3(r['ball_MRV_after'])}",
                f"碰后总角动量 = {format_sig3(r['total_L_after'])}",
                f"角动量误差 = {format_sig3(abs(r['total_L_after'] - r['total_L_before']))}",
                f"能量误差 = {format_sig3(abs(r['ke_after'] - r['ke_before']))} J",
            ]
        self.draw_info_panel(current_lines, collision_lines,
                             ["失重：碰后杆做匀角速度转动", "MRV 中 R=h，为小球到定轴的垂直距离", "按 C 直接显示碰撞结果"],
                             ("碰后总角动量", "角动量误差", "能量误差"))



# ============================ 模型一：两自由质点弹性碰撞 ============================
class BallBallCollision(BaseModel):
    name = "两自由质点弹性碰撞仿真"
    short_name = "两自由质点"
    BALL_RADIUS_WORLD = 0.34

    def build_controls(self):
        self.add_control("m1", "左球质量 m1", 0, 0, 0.05, 10.0, 1.00, " kg", 3)
        self.add_control("u1", "左球初速度 u1", 0, 1, -12.0, 12.0, 6.00, " m/s", 3)

        self.add_control("gap", "两球初始表面间距 d", 0, 2, 0.30, 8.00, 3.00, " m", 3)
        self.add_control("m2", "右球质量 m2", 1, 0, 0.05, 10.0, 2.00, " kg", 3)
        self.add_control("u2", "右球初速度 u2", 1, 1, -12.0, 12.0, 0.00, " m/s", 3)
        self.add_control("e", "恢复系数 e", 1, 2, 0.00, 1.00, 1.00, "", 3)
        self.add_control("anim_speed", "动画速度", 1, 3, 0.20, 2.50, 1.00, "x", 2)


    def reset(self, keep_running=False):
        u1 = self.sliders["u1"].value
        u2 = self.sliders["u2"].value
        gap = self.sliders["gap"].value
        r = self.BALL_RADIUS_WORLD
        self.running = keep_running
        self.phase = "ready"

        self.x1 = -gap / 2.0 - r
        self.x2 = gap / 2.0 + r
        self.v1 = u1
        self.v2 = u2
        self.t = 0.0

        self.collided = False
        self.flash = 0.0
        self.last_result = None
        self.trail1 = []
        self.trail2 = []

        self.particles.clear()
        self.shockwaves.clear()
        self.notice = ""

    def can_collide(self):
        return self.v1 > self.v2 + 1e-10

    def start_pause(self):
        if self.phase == "ready":
            self.phase = "moving"

            if not self.can_collide():
                self.notice = "当前 u1 <= u2，两球间距不会缩小，因此不会发生碰撞。"
        self.running = not self.running

    def jump_to_collision(self):
        if not self.can_collide():
            self.phase = "moving"
            self.running = False
            self.notice = "无法跳到碰撞：当前 u1 <= u2，两球不会相撞。"

            return
        r = self.BALL_RADIUS_WORLD
        self.x1 = -r
        self.x2 = r
        self.phase = "moving"

        self.do_collision(0.0)
        self.running = True

    def do_collision(self, contact_x):
        m1 = self.sliders["m1"].value
        m2 = self.sliders["m2"].value
        e = self.sliders["e"].value
        u1, u2 = self.v1, self.v2

        relative_before = u1 - u2
        impulse = -(1.0 + e) * relative_before / (1.0 / m1 + 1.0 / m2)
        v1 = u1 + impulse / m1
        v2 = u2 - impulse / m2

        p_before = m1 * u1 + m2 * u2

        p_after = m1 * v1 + m2 * v2
        ke_before = 0.5 * m1 * u1 * u1 + 0.5 * m2 * u2 * u2
        ke_after = 0.5 * m1 * v1 * v1 + 0.5 * m2 * v2 * v2

        self.v1, self.v2 = v1, v2
        self.phase = "after"

        self.collided = True
        self.flash = 1.0
        self.notice = ""
        self.last_result = {
            "e": e,
            "u1": u1,
            "u2": u2,
            "v1": v1,
            "v2": v2,
            "relative_before": relative_before,
            "relative_after": v1 - v2,
            "impulse": impulse,
            "p_before": p_before,
            "p_after": p_after,
            "ke_before": ke_before,
            "ke_after": ke_after,
            "impact_time": self.t,
            "contact_x": contact_x,
        }
        spawn_impact_particles(self.particles, self.shockwaves, contact_x, 0.0,
                               relative_before, symmetric=True)


    def step(self, dt):
        if not self.running:
            return
        speed = self.sliders["anim_speed"].value
        sim_dt = dt * speed
        self.t += sim_dt
        n = max(1, int(sim_dt / 0.0025))

        sub = sim_dt / n
        r = self.BALL_RADIUS_WORLD

        for _ in range(n):
            old_x1, old_x2 = self.x1, self.x2
            self.x1 += self.v1 * sub
            self.x2 += self.v2 * sub
            if not self.collided and self.v1 > self.v2:
                old_gap = (old_x2 - r) - (old_x1 + r)

                new_gap = (self.x2 - r) - (self.x1 + r)
                if old_gap > 0.0 and new_gap <= 0.0:
                    contact_x = ((self.x1 + r) + (self.x2 - r)) / 2.0
                    self.x1 = contact_x - r
                    self.x2 = contact_x + r
                    self.do_collision(contact_x)


        self.step_particles(dt, gravity=0.0)
        self.flash = max(0.0, self.flash - sim_dt * 2.2)
        self.trail1.append(self.x1)
        self.trail2.append(self.x2)
        if len(self.trail1) > 85:
            self.trail1.pop(0)

        if len(self.trail2) > 85:
            self.trail2.pop(0)

    def formula_lines(self):
        return (
            "J=-(1+e)(u1-u2)/(1/m1+1/m2)",
            "v1=u1+J/m1，v2=u2-J/m2；e=1 时总动能守恒",
        )

    def formula_rect(self):
        return pygame.Rect(38, SIM_H + 218, 570, 52)

    def summary_line(self):
        return (f"m1={format_sig3(self.sliders['m1'].value)}  u1={format_sig3(self.sliders['u1'].value)}  "
                f"m2={format_sig3(self.sliders['m2'].value)}  u2={format_sig3(self.sliders['u2'].value)}  "
                f"d={format_sig3(self.sliders['gap'].value)}  e={format_sig3(self.sliders['e'].value)}")

    def draw_ui(self):
        super().draw_ui()

        # v1-v2 判定移到右下角参数区；一旦开始运行（phase != ready）即隐藏。
        if self.phase == "ready":
            relation = "会相撞" if self.v1 > self.v2 else "不会相撞"
            delta_v = self.v1 - self.v2
            rect = pygame.Rect(690, SIM_H + 218, 528, 52)
            rounded_rect(screen, rect, (18, 26, 46), 10, 1, (48, 64, 100))
            draw_text(screen, "碰撞判定", (rect.x + 12, rect.y + 7), FONT_SMALL, MUTED)

            draw_text(screen,
                      f"v1-v2 = {format_sig3(delta_v)} m/s  →  {relation}",
                      (rect.x + 12, rect.y + 27), FONT_SMALL,
                      ACCENT_3 if delta_v > 0 else RED)

    def draw_scene(self):
        m1 = self.sliders["m1"].value
        m2 = self.sliders["m2"].value
        scale = 92.0
        origin_x = 405
        center_y = 375

        radius_px = int(self.BALL_RADIUS_WORLD * scale)
        platform_y = center_y + radius_px + 14

        def w2s(x, y=0.0):
            return int(origin_x + x * scale), int(center_y - y * scale)

        screen.blit(STATIC_BG, (0, 0))
        self.draw_header({"ready": "待开始", "moving": "两球运动中", "after": "碰撞后运动"}.get(self.phase, self.phase))

        APP.draw_mode_tabs()

        pygame.draw.line(screen, (22, 28, 48), (-80, platform_y + 10), (WIDTH + 80, platform_y + 10), 10)
        pygame.draw.line(screen, (35, 44, 70), (-80, platform_y + 4), (WIDTH + 80, platform_y + 4), 8)
        pygame.draw.line(screen, PLATFORM, (-80, platform_y), (WIDTH + 80, platform_y), 5)
        pygame.draw.line(screen, PLATFORM_TOP, (-80, platform_y - 1), (WIDTH + 80, platform_y - 1), 2)

        for tx in range(-80, WIDTH + 80, 18):
            pygame.draw.line(screen, (100, 115, 155), (tx, platform_y), (tx + 6, platform_y + 4), 1)

        pygame.draw.line(screen, (80, 100, 150), (35, center_y), (780, center_y), 1)
        for world_x in range(-4, 5):
            sx, _ = w2s(world_x)
            pygame.draw.line(screen, (85, 105, 150), (sx, center_y - 7), (sx, center_y + 7), 1)
            draw_text(screen, f"{world_x}", (sx, center_y + 12), FONT_TINY, MUTED, anchor="midtop")


        if not self.collided:
            left_surface = self.x1 + self.BALL_RADIUS_WORLD
            right_surface = self.x2 - self.BALL_RADIUS_WORLD
            if right_surface > left_surface:
                p1 = w2s(left_surface, -0.72)
                p2 = w2s(right_surface, -0.72)
                pygame.draw.line(screen, (105, 125, 175), p1, p2, 2)

                pygame.draw.line(screen, (105, 125, 175), (p1[0], p1[1] - 7), (p1[0], p1[1] + 7), 2)
                pygame.draw.line(screen, (105, 125, 175), (p2[0], p2[1] - 7), (p2[0], p2[1] + 7), 2)
                draw_text(screen, f"当前间距={format_sig3(right_surface - left_surface)} m",
                          ((p1[0] + p2[0]) // 2, p1[1] + 10), FONT_SMALL, MUTED, anchor="midtop")

        trail_surf_1.fill((0, 0, 0, 0))
        for i, x in enumerate(self.trail1):
            p = i / max(1, len(self.trail1) - 1)

            pos = w2s(x)
            if -100 <= pos[0] <= WIDTH + 100:
                r = max(2, int(radius_px * (0.12 + 0.26 * p)))
                pygame.draw.circle(trail_surf_1, (*BALL1_GLOW, int(10 + 70 * p)), pos, r + 3)
                pygame.draw.circle(trail_surf_1, (*BALL1_COLOR, int(10 + 70 * p)), pos, r)
        screen.blit(trail_surf_1, (0, 0))

        trail_surf_2.fill((0, 0, 0, 0))

        for i, x in enumerate(self.trail2):
            p = i / max(1, len(self.trail2) - 1)
            pos = w2s(x)
            if -100 <= pos[0] <= WIDTH + 100:
                r = max(2, int(radius_px * (0.12 + 0.26 * p)))
                pygame.draw.circle(trail_surf_2, (*BALL2_GLOW, int(10 + 70 * p)), pos, r + 3)
                pygame.draw.circle(trail_surf_2, (*BALL2_COLOR, int(10 + 70 * p)), pos, r)

        screen.blit(trail_surf_2, (0, 0))

        particle_surf.fill((0, 0, 0, 0))
        for particle in self.particles:
            particle.draw(particle_surf, w2s, streak_scale=5.5)
        for wave in self.shockwaves:
            wave.draw(particle_surf, w2s, scale)
        screen.blit(particle_surf, (0, 0))


        def draw_ball(pos, radius, base_color, edge_color, glow_color, label, mass):
            px, py = pos
            pygame.draw.ellipse(screen, (0, 0, 0),
                                (px - radius - 6, platform_y - max(4, radius // 4),
                                 2 * radius + 12, max(8, radius // 2)))
            glow_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(glow_surf, (*glow_color, 28), pos, radius + 20)
            pygame.draw.circle(glow_surf, (*glow_color, 46), pos, radius + 11)

            screen.blit(glow_surf, (0, 0))
            pygame.draw.circle(screen, (4, 10, 23), (px + 4, py + 5), radius + 2)
            pygame.draw.circle(screen, base_color, pos, radius)
            pygame.draw.circle(screen, lerp_color(base_color, (15, 55, 100), 0.35), pos, radius, 2)
            pygame.draw.circle(screen, edge_color,
                               (px - radius // 3, py - radius // 3), max(4, radius // 4))

            pygame.draw.circle(screen, (255, 255, 255),
                               (px - radius // 3 - 1, py - radius // 3 - 1), max(2, radius // 8))
            draw_text(screen, label, (px, py - radius - 38), FONT_BIG, edge_color, anchor="midbottom")
            draw_text(screen, f"m={format_sig3(mass)} kg", (px, py + radius + 18), FONT_SMALL, MUTED, anchor="midtop")

        pos1, pos2 = w2s(self.x1), w2s(self.x2)
        draw_ball(pos1, radius_px, BALL1_COLOR, BALL1_EDGE, BALL1_GLOW, "球 1", m1)
        draw_ball(pos2, radius_px, BALL2_COLOR, BALL2_EDGE, BALL2_GLOW, "球 2", m2)


        def draw_velocity(pos, velocity, label):
            if abs(velocity) < 0.01:
                draw_text(screen, f"{label}=0", (pos[0], pos[1] - radius_px - 15),
                          FONT_SMALL, GREEN, anchor="midbottom")
                return
            direction = 1 if velocity > 0 else -1
            arrow_len = clamp(abs(velocity) * 10.0, 35, 150)
            y = pos[1] - radius_px - 18

            finish = (int(pos[0] + direction * arrow_len), y)
            draw_arrow(screen, (pos[0], y), finish, GREEN, 3)
            draw_text(screen, f"{label}={format_sig3(velocity)} m/s",
                      (finish[0] + (10 if direction > 0 else -10), y - 12), FONT_SMALL, GREEN,
                      anchor="topleft" if direction > 0 else "topright")

        draw_velocity(pos1, self.v1, "v1")
        draw_velocity(pos2, self.v2, "v2")


        if self.flash > 0 and self.last_result:
            contact = w2s(self.last_result["contact_x"])
            flash_surf.fill((0, 0, 0, 0))
            f = self.flash
            r0 = int(clamp((1.15 - f) * 80 + 10, 5, 90))
            a0 = int(220 * f)

            pygame.draw.circle(flash_surf, (255, 255, 255, a0), contact, r0)
            pygame.draw.circle(flash_surf, (255, 210, 80, int(a0 * 0.45)), contact, r0 + int(30 * f))
            pygame.draw.circle(flash_surf, (120, 180, 255, int(a0 * 0.20)), contact, r0 + int(55 * f))
            screen.blit(flash_surf, (0, 0))

        if self.notice:
            notice_rect = pygame.Rect(38, 192, 730, 40)

            rounded_rect(screen, notice_rect, (62, 28, 38), 10, 1, (145, 65, 80))
            draw_text(screen, self.notice, notice_rect.center, FONT_SMALL, (255, 185, 190), anchor="center")

        p_now = m1 * self.v1 + m2 * self.v2
        ke1 = 0.5 * m1 * self.v1 * self.v1
        ke2 = 0.5 * m2 * self.v2 * self.v2
        current_lines = [
            f"左球速度 v1 = {format_sig3(self.v1)} m/s",
            f"右球速度 v2 = {format_sig3(self.v2)} m/s",
            f"相对速度 v1-v2 = {format_sig3(self.v1 - self.v2)} m/s",
            f"质心速度 Vcm = {format_sig3(p_now / (m1 + m2))} m/s",
            f"左球动能 = {format_sig3(ke1)} J",
            f"右球动能 = {format_sig3(ke2)} J",
            f"总动量 = {format_sig3(p_now)} kg*m/s",
        ]

        collision_lines = None
        if self.last_result:
            r = self.last_result
            collision_lines = [
                f"碰撞时刻 t = {format_sig3(r['impact_time'])} s",
                f"恢复系数 e = {format_sig3(r['e'])}",
                f"碰前 u1 = {format_sig3(r['u1'])} m/s",
                f"碰前 u2 = {format_sig3(r['u2'])} m/s",
                f"碰后 v1 = {format_sig3(r['v1'])} m/s",
                f"碰后 v2 = {format_sig3(r['v2'])} m/s",
                f"冲量 J = {format_sig3(r['impulse'])} N*s",
                f"动量误差 = {format_sig3(abs(r['p_after'] - r['p_before']))}",
                f"动能变化 = {format_sig3(r['ke_after'] - r['ke_before'])} J",
            ]
        self.draw_info_panel(current_lines, collision_lines,
                             ["仅当 u1 > u2 时两球会相撞", "e=1 为理想弹性碰撞", "正速度向右，负速度向左"],
                             ("碰后 v1", "碰后 v2", "冲量", "动量误差"))


class DiagnosticsBuffer:
    # Small in-memory sample buffer used while checking numerical behavior.

    def __init__(self, capacity=180):
        self.capacity = max(1, int(capacity))

        self.enabled = False
        self.samples = []

    def clear(self):
        self.samples.clear()

    def push(self, **values):
        if not self.enabled:
            return
        sample = {}

        for key, value in values.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                sample[key] = float(value)
            else:
                sample[key] = value
        self.samples.append(sample)
        if len(self.samples) > self.capacity:
            del self.samples[:len(self.samples) - self.capacity]

    def latest(self):
        return dict(self.samples[-1]) if self.samples else None

    def range_of(self, key):
        values = [s[key] for s in self.samples if isinstance(s.get(key), (int, float))]

        if not values:
            return None
        return min(values), max(values)

    def mean_of(self, key):
        values = [s[key] for s in self.samples if isinstance(s.get(key), (int, float))]
        if not values:
            return None
        return sum(values) / len(values)


    def snapshot(self):
        return [dict(sample) for sample in self.samples]


def finite_or(value, fallback=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return fallback
    return value if math.isfinite(value) else fallback


def relative_error(a, b, floor=1e-12):
    a = finite_or(a)
    b = finite_or(b)

    return abs(a - b) / max(abs(a), abs(b), floor)


def elastic_energy(mass, speed):
    mass = max(0.0, finite_or(mass))
    speed = finite_or(speed)
    return 0.5 * mass * speed * speed


def rod_inertia_about_end(mass, length):
    mass = max(0.0, finite_or(mass))
    length = max(0.0, finite_or(length))

    return mass * length * length / 3.0


def linear_momentum(mass, speed):
    return finite_or(mass) * finite_or(speed)


def orbital_angular_momentum(mass, radius, tangential_speed):
    return finite_or(mass) * finite_or(radius) * finite_or(tangential_speed)


def rotational_angular_momentum(inertia, angular_speed):
    return finite_or(inertia) * finite_or(angular_speed)


def close_enough(a, b, rel=1e-9, abs_tol=1e-12):
    a = finite_or(a)

    b = finite_or(b)
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b)))


def collision_check_ball_ball(m1, m2, u1, u2, v1, v2):
    p0 = linear_momentum(m1, u1) + linear_momentum(m2, u2)
    p1 = linear_momentum(m1, v1) + linear_momentum(m2, v2)
    e0 = elastic_energy(m1, u1) + elastic_energy(m2, u2)

    e1 = elastic_energy(m1, v1) + elastic_energy(m2, v2)
    return {
        'momentum_before': p0,
        'momentum_after': p1,
        'energy_before': e0,
        'energy_after': e1,
        'momentum_error': p1 - p0,
        'energy_error': e1 - e0,
    }


def collision_check_ball_rod(m, M, L, h, u, v, w):
    inertia = rod_inertia_about_end(M, L)
    l0 = orbital_angular_momentum(m, h, u)
    l1 = orbital_angular_momentum(m, h, v) + rotational_angular_momentum(inertia, w)

    e0 = elastic_energy(m, u)
    e1 = elastic_energy(m, v) + 0.5 * inertia * w * w
    return {
        'angular_momentum_before': l0,
        'angular_momentum_after': l1,
        'energy_before': e0,
        'energy_after': e1,
        'angular_momentum_error': l1 - l0,
        'energy_error': e1 - e0,
    }


# ============================ 主程序 ============================
class App:
    def __init__(self):
        self.models = [BallBallCollision(), BallHitsRod()]
        self.mode_index = 0

        self.btn_start = Button("开始 / 暂停  Space", pygame.Rect(38, SIM_H + 286, 180, 38))
        self.btn_reset = Button("重置  R", pygame.Rect(236, SIM_H + 286, 110, 38))
        self.btn_snap = Button("直接到碰撞  C", pygame.Rect(364, SIM_H + 286, 150, 38))
        self.mode_buttons = [
            Button("1  两自由质点弹性碰撞仿真", pygame.Rect(38, 118, 280, 36)),
            Button("2  质点‑定轴细杆碰撞仿真", pygame.Rect(330, 118, 280, 36)),
        ]

    @property
    def model(self):
        return self.models[self.mode_index]

    def switch_mode(self, index):
        if 0 <= index < len(self.models) and index != self.mode_index:
            for box in self.model.input_boxes.values():
                box.active = False

                box.dragging = False
            self.model.running = False
            self.mode_index = index
            for box in self.model.input_boxes.values():
                box.active = False
                box.dragging = False

            self.model.running = False

    def draw_mode_tabs(self):
        for i, button in enumerate(self.mode_buttons):
            button.draw(screen, active=(i == self.mode_index))

    def run(self):
        running_app = True
        while running_app:
            dt = clock.tick(FPS) / 1000.0
            model = self.model

            model.update_inputs(dt)
            need_reset = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running_app = False
                    continue

                switched = False

                for i, button in enumerate(self.mode_buttons):
                    if button.clicked(event):
                        self.switch_mode(i)
                        switched = True
                        break
                if switched:
                    continue

                model = self.model

                input_was_active, input_consumed, input_changed = model.handle_input_event(event)
                if input_changed:
                    need_reset = True

                if event.type == pygame.KEYDOWN and not model.any_input_active():
                    if event.key == pygame.K_ESCAPE:
                        running_app = False
                    elif event.key == pygame.K_1:
                        self.switch_mode(0)
                    elif event.key == pygame.K_2:
                        self.switch_mode(1)
                    elif event.key == pygame.K_SPACE:
                        model.start_pause()
                    elif event.key == pygame.K_r:
                        model.reset()
                    elif event.key == pygame.K_c:
                        model.jump_to_collision()

                if input_consumed or input_was_active:
                    continue

                if self.btn_start.clicked(event):
                    model.start_pause()
                if self.btn_reset.clicked(event):
                    model.reset()

                if self.btn_snap.clicked(event):
                    model.jump_to_collision()

                if model.handle_sliders(event):
                    need_reset = True

            model = self.model
            if need_reset:
                model.reset(keep_running=False)
                model.sync_inputs(force=False)


            model.step(dt)
            model.draw_scene()
            model.draw_ui()
            pygame.display.flip()

        pygame.quit()

        sys.exit()


APP = App()

if __name__ == "__main__":
    APP.run()

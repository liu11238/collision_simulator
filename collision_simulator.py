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
import pygame

WIDTH, HEIGHT = 1180, 820
FPS = 60

SIM_H = 560
BG = (16, 21, 34)
PANEL = (28, 34, 50)
TEXT = (235, 240, 250)

MUTED = (155, 165, 185)
BLUE = (70, 170, 245)
ORANGE = (245, 165, 75)
YELLOW = (235, 205, 85)
GREEN = (95, 220, 150)

RED = (245, 95, 95)
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('弹性碰撞仿真器')

clock = pygame.time.Clock()


def font(size=18, bold=False):
    paths = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            f = pygame.font.Font(p, size)
            f.set_bold(bold)

            return f
    f = pygame.font.Font(None, size)
    f.set_bold(bold)
    return f


FONT = font(18)
SMALL = font(15)
BIG = font(28, True)


def text(s, x, y, f=FONT, c=TEXT, anchor="topleft"):
    img = f.render(str(s), True, c)
    r = img.get_rect()

    setattr(r, anchor, (x, y))
    screen.blit(img, r)
    return r


def clamp(x, a, b):
    return max(a, min(b, x))



def format_value(value, digits=2):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return '--'
    if not math.isfinite(value):
        return '--'
    return f'{value:.{digits}f}'


def momentum(mass, velocity):
    return float(mass) * float(velocity)



def kinetic_energy(mass, velocity):
    velocity = float(velocity)
    return 0.5 * float(mass) * velocity * velocity


def rod_inertia_end(mass, length):
    return float(mass) * float(length) * float(length) / 3.0


def solve_ball_ball(m1, m2, u1, u2):
    total = m1 + m2
    if total <= 1e-12:
        return u1, u2

    v1 = ((m1 - m2) * u1 + 2.0 * m2 * u2) / total
    v2 = (2.0 * m1 * u1 + (m2 - m1) * u2) / total
    return v1, v2


def solve_ball_rod(m, M, L, h, u):
    inertia = rod_inertia_end(M, L)

    denominator = inertia + m * h * h
    if denominator <= 1e-12:
        return u, 0.0
    v = (m * h * h - inertia) * u / denominator
    omega = 2.0 * m * h * u / denominator

    return v, omega


def check_ball_ball(m1, m2, u1, u2, v1, v2):
    p0 = momentum(m1, u1) + momentum(m2, u2)
    p1 = momentum(m1, v1) + momentum(m2, v2)
    e0 = kinetic_energy(m1, u1) + kinetic_energy(m2, u2)

    e1 = kinetic_energy(m1, v1) + kinetic_energy(m2, v2)
    return p1 - p0, e1 - e0


def check_ball_rod(m, M, L, h, u, v, omega):
    inertia = rod_inertia_end(M, L)
    l0 = m * h * u
    l1 = m * h * v + inertia * omega

    e0 = kinetic_energy(m, u)
    e1 = kinetic_energy(m, v) + 0.5 * inertia * omega * omega
    return l1 - l0, e1 - e0


def clamp01(value):
    return max(0.0, min(1.0, float(value)))



def remap(value, in_lo, in_hi, out_lo, out_hi):
    if abs(in_hi - in_lo) <= 1e-12:
        return 0.5 * (out_lo + out_hi)
    t = (value - in_lo) / (in_hi - in_lo)
    return out_lo + t * (out_hi - out_lo)


def draw_centered_circle(surface, color, pos, radius, outline=None):
    pygame.draw.circle(surface, color, (int(pos[0]), int(pos[1])), max(1, int(radius)))

    if outline is not None:
        pygame.draw.circle(surface, outline, (int(pos[0]), int(pos[1])), max(1, int(radius)), 1)


def draw_rule(surface, x1, x2, y, step=25):
    pygame.draw.line(surface, (72, 82, 102), (x1, y), (x2, y), 1)
    x = x1
    while x <= x2:
        pygame.draw.line(surface, (72, 82, 102), (x, y - 3), (x, y + 3), 1)
        x += step



class FrameStats:
    def __init__(self):
        self.frame_count = 0
        self.elapsed = 0.0
        self.last_dt = 0.0

    def push(self, dt):
        self.last_dt = max(0.0, float(dt))

        self.elapsed += self.last_dt
        self.frame_count += 1

    @property
    def average_fps(self):
        if self.elapsed <= 1e-12:
            return 0.0
        return self.frame_count / self.elapsed



class Range:
    def __init__(self, lo, hi):
        self.lo = float(lo)
        self.hi = float(hi)

    def clamp(self, value):
        return max(self.lo, min(self.hi, float(value)))

    def fraction(self, value):
        if self.hi <= self.lo:
            return 0.0

        return clamp01((float(value) - self.lo) / (self.hi - self.lo))


class Slider:
    def __init__(self, label, x, y, w, lo, hi, value, unit=""):
        self.label, self.x, self.y, self.w = label, x, y, w
        self.lo, self.hi, self.value, self.unit = lo, hi, value, unit
        self.drag = False

    def knob(self):
        t = (self.value - self.lo) / max(1e-12, self.hi - self.lo)

        return int(self.x + t * self.w)

    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.x - 8 <= e.pos[0] <= self.x + self.w + 8 and abs(e.pos[1] - self.y) < 14:
                self.drag = True
                self.set_mouse(e.pos[0])
                return True

        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.drag = False
        if e.type == pygame.MOUSEMOTION and self.drag:
            self.set_mouse(e.pos[0])
            return True
        return False


    def set_mouse(self, mx):
        t = clamp((mx - self.x) / self.w, 0.0, 1.0)
        self.value = self.lo + t * (self.hi - self.lo)

    def draw(self):
        pygame.draw.line(screen, (65, 75, 100), (self.x, self.y), (self.x + self.w, self.y), 5)
        k = self.knob()
        pygame.draw.line(screen, BLUE, (self.x, self.y), (k, self.y), 5)

        pygame.draw.circle(screen, BLUE, (k, self.y), 10)
        text(self.label, self.x, self.y - 28, SMALL, MUTED)
        text(f"{self.value:.2f}{self.unit}", self.x + self.w, self.y - 28, SMALL, TEXT, "topright")


class Button:
    def __init__(self, label, rect):
        self.label, self.rect = label, pygame.Rect(rect)


    def clicked(self, e):
        return e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos)

    def draw(self, active=False):
        c = (55, 95, 145) if active else (45, 52, 70)
        pygame.draw.rect(screen, c, self.rect, border_radius=9)
        pygame.draw.rect(screen, (90, 105, 135), self.rect, 1, border_radius=9)

        text(self.label, *self.rect.center, SMALL, TEXT, "center")


# world coordinates are converted only when drawing
class TwoBalls:
    title = "1：两自由质点弹性碰撞仿真"
    def __init__(self):
        self.sliders = [
            Slider("质点1质量 m1", 50, 635, 250, 0.2, 5.0, 1.0, " kg"),
            Slider("质点2质量 m2", 50, 710, 250, 0.2, 5.0, 2.0, " kg"),
            Slider("质点1初速度 v1", 420, 635, 250, -6.0, 6.0, 3.0, " m/s"),
            Slider("质点2初速度 v2", 420, 710, 250, -6.0, 6.0, -1.0, " m/s"),
            Slider("动画速度", 790, 635, 250, 0.2, 2.5, 1.0, "x"),
        ]
        self.reset()


    def reset(self):
        self.running = False
        self.hit = False
        self.t = 0.0
        self.x1, self.x2 = -2.4, 2.4
        self.v1 = self.sliders[2].value

        self.v2 = self.sliders[3].value

    def start(self):
        if not self.running and self.t == 0:
            self.v1 = self.sliders[2].value
            self.v2 = self.sliders[3].value
        self.running = not self.running


    def changed(self):
        if not self.running:
            self.reset()

    def step(self, dt):
        if not self.running:
            return
        dt *= self.sliders[4].value
        self.t += dt

        old_gap = self.x2 - self.x1
        self.x1 += self.v1 * dt
        self.x2 += self.v2 * dt
        if not self.hit and self.v1 > self.v2 and old_gap > 0 and self.x2 - self.x1 <= 0.46:
            m1, m2 = self.sliders[0].value, self.sliders[1].value
            u1, u2 = self.v1, self.v2

            self.v1 = ((m1-m2)*u1 + 2*m2*u2)/(m1+m2)
            self.v2 = (2*m1*u1 + (m2-m1)*u2)/(m1+m2)
            self.hit = True

    def event(self, e):
        changed = False

        for s in self.sliders:
            changed |= s.event(e)
        if changed:
            self.changed()

    def draw(self):
        text(self.title, 32, 26, BIG)
        text(f"时间 {self.t:.2f} s    {'运行中' if self.running else '待开始'}", 34, 68, SMALL, MUTED)

        y = 320
        pygame.draw.line(screen, (95, 105, 120), (55, y+34), (760, y+34), 3)
        scale = 105
        cx = 405

        p1 = (int(cx + self.x1*scale), y)
        p2 = (int(cx + self.x2*scale), y)
        pygame.draw.circle(screen, BLUE, p1, 22)
        pygame.draw.circle(screen, ORANGE, p2, 22)
        text(f"v1={self.v1:.2f}", p1[0], p1[1]-50, SMALL, BLUE, "center")

        text(f"v2={self.v2:.2f}", p2[0], p2[1]-50, SMALL, ORANGE, "center")
        text("弹性碰撞后速度由动量、动能守恒确定", 820, 278, SMALL, MUTED)
        for s in self.sliders:
            s.draw()


# uniform rod, pivot at one end
class BallRod:
    title = "2：质点-定轴细杆碰撞仿真"

    def __init__(self):
        self.sliders = [
            Slider("质点质量 m", 50, 635, 250, 0.2, 5.0, 1.0, " kg"),
            Slider("杆质量 M", 50, 710, 250, 0.2, 8.0, 3.0, " kg"),
            Slider("杆长 L", 420, 635, 250, 0.25, 2.0, 1.2, " m"),
            Slider("碰撞位置 h/L", 420, 710, 250, 0.1, 0.95, 0.65, ""),
            Slider("质点速度 u", 790, 635, 250, 0.0, 8.0, 4.0, " m/s"),
            Slider("动画速度", 790, 710, 250, 0.2, 2.5, 1.0, "x"),
        ]
        self.reset()

    def reset(self):
        self.running = False
        self.hit = False

        self.t = 0.0
        self.theta = 0.0
        self.w = 0.0
        self.ball_x = -2.1
        self.ball_v = self.sliders[4].value


    def start(self):
        if not self.running and self.t == 0:
            self.ball_v = self.sliders[4].value
        self.running = not self.running

    def changed(self):
        if not self.running:
            self.reset()

    def collide(self):
        m, M, L = self.sliders[0].value, self.sliders[1].value, self.sliders[2].value

        h = self.sliders[3].value * L
        I = M*L*L/3.0
        u = self.ball_v
        den = I + m*h*h

        self.ball_v = (m*h*h - I) * u / den
        self.w = 2*m*h*u / den
        self.hit = True

    def step(self, dt):
        if not self.running:
            return

        dt *= self.sliders[5].value
        self.t += dt
        L = self.sliders[2].value
        h = self.sliders[3].value * L
        old = self.ball_x

        self.ball_x += self.ball_v * dt
        contact_x = -0.08
        if not self.hit and self.ball_v > 0 and old < contact_x <= self.ball_x:
            self.ball_x = contact_x
            self.collide()

        if self.hit:
            self.theta += self.w * dt

    def event(self, e):
        changed = False
        for s in self.sliders:
            changed |= s.event(e)
        if changed:
            self.changed()


    def draw(self):
        text(self.title, 32, 26, BIG)
        text(f"时间 {self.t:.2f} s    {'运行中' if self.running else '待开始'}", 34, 68, SMALL, MUTED)
        L = self.sliders[2].value
        h = self.sliders[3].value * L
        scale = min(280, 330/max(L, 0.3))

        pivot = (690, 180)
        end = (int(pivot[0] + L*math.sin(self.theta)*scale), int(pivot[1] + L*math.cos(self.theta)*scale))
        pygame.draw.line(screen, YELLOW, pivot, end, 8)
        pygame.draw.circle(screen, BLUE, pivot, 11)

        by = int(pivot[1] + h*scale)
        bx = int(pivot[0] + self.ball_x*scale)
        pygame.draw.circle(screen, BLUE, (bx, by), 20)
        text(f"w={self.w:.2f} rad/s", pivot[0]+22, pivot[1]-18, SMALL, GREEN)

        text("无重力，杆碰后匀角速度转动", 820, 250, FONT, MUTED)
        text("I = ML² / 3", 820, 288, SMALL, MUTED)
        for s in self.sliders:
            s.draw()


class App:
    def __init__(self):
        self.models = [TwoBalls(), BallRod()]

        self.index = 0
        self.start_btn = Button("开始 / 暂停", (835, 742, 120, 42))
        self.reset_btn = Button("重置", (970, 742, 80, 42))
        self.tab1 = Button("1 两质点", (825, 25, 130, 40))
        self.tab2 = Button("2 质点-杆", (965, 25, 150, 40))


    @property
    def model(self):
        return self.models[self.index]

    def switch(self, i):
        self.index = i

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_1: self.switch(0)
            if e.key == pygame.K_2: self.switch(1)

            if e.key == pygame.K_SPACE: self.model.start()
            if e.key == pygame.K_r: self.model.reset()
        if self.tab1.clicked(e): self.switch(0)
        if self.tab2.clicked(e): self.switch(1)

        if self.start_btn.clicked(e): self.model.start()
        if self.reset_btn.clicked(e): self.model.reset()
        self.model.event(e)

    def draw(self):
        screen.fill(BG)
        pygame.draw.rect(screen, PANEL, (0, SIM_H, WIDTH, HEIGHT-SIM_H))

        pygame.draw.line(screen, (70, 80, 100), (0, SIM_H), (WIDTH, SIM_H), 2)
        self.model.draw()
        self.tab1.draw(self.index == 0)
        self.tab2.draw(self.index == 1)

        self.start_btn.draw(self.model.running)
        self.reset_btn.draw()
        text("第1版 Prototype", 1080, 795, SMALL, MUTED, "bottomright")

    def run(self):
        alive = True

        while alive:
            dt = min(clock.tick(FPS)/1000.0, 0.04)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    alive = False
                else:
                    self.event(e)
            self.model.step(dt)
            self.draw()

            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    App().run()

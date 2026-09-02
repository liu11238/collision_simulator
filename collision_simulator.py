"""
弹性碰撞仿真器

包含两个理想弹性碰撞模型：
1. 两自由质点一维碰撞
2. 质点与定轴细杆碰撞

运行环境：Python 3 + pygame
"""
from __future__ import annotations

import math, os, pygame
from dataclasses import dataclass

WIDTH, HEIGHT, SIM_H, FPS = (1240, 900, 590, 60)
UI_H = HEIGHT - SIM_H

BG1, BG2 = ((8, 14, 28), (20, 32, 56))
PANEL, CARD = ((20, 28, 46), (29, 40, 64))

TEXT, MUTED = ((235, 242, 255), (145, 160, 190))
BLUE, ORANGE, YELLOW = ((75, 175, 250), (255, 155, 80), (240, 205, 80))

GREEN, RED = ((100, 235, 165), (255, 95, 95))
pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

pygame.display.set_caption('弹性碰撞仿真器')

def get_font(size=18, bold=False):
    for p in ['C:\\Windows\\Fonts\\msyh.ttc', 'C:\\Windows\\Fonts\\simhei.ttf', '/System/Library/Fonts/PingFang.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if os.path.exists(p):
            f = pygame.font.Font(p, size)

            f.set_bold(bold)
            return f

    f = pygame.font.Font(None, size)
    f.set_bold(bold)

    return f
FONT, SMALL, TINY, BIG = (get_font(18), get_font(15), get_font(13), get_font(28, True))


def clamp(x, a, b):
    return max(a, min(b, x))

def fmt(x):
    if abs(x) >= 100:
        return f'{x:.1f}'

    if abs(x) >= 10:
        return f'{x:.2f}'
    return f'{x:.3f}'


def draw_text(s, pos, f=FONT, c=TEXT, anchor='topleft'):
    im = f.render(str(s), True, c)
    r = im.get_rect()

    setattr(r, anchor, pos)
    screen.blit(im, r)

    return r

def gradient_background():
    for y in range(SIM_H):
        t = y / max(1, SIM_H - 1)

        c = tuple((int(BG1[i] * (1 - t) + BG2[i] * t) for i in range(3)))
        pygame.draw.line(screen, c, (0, y), (WIDTH, y))

    for x in range(0, WIDTH, 50):
        pygame.draw.line(screen, (33, 47, 72), (x, 0), (x, SIM_H), 1)
    for y in range(0, SIM_H, 50):
        pygame.draw.line(screen, (33, 47, 72), (0, y), (WIDTH, y), 1)

@dataclass
class Slider:
    label: str

    x: int
    y: int

    w: int
    lo: float

    hi: float
    value: float

    unit: str = ''
    drag: bool = False


    def knob(self):
        return int(self.x + (self.value - self.lo) / max(1e-12, self.hi - self.lo) * self.w)

    def set_mouse(self, mx):
        self.value = self.lo + clamp((mx - self.x) / self.w, 0, 1) * (self.hi - self.lo)


    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and (self.x - 10 <= e.pos[0] <= self.x + self.w + 10) and (abs(e.pos[1] - self.y) < 15):
            self.drag = True
            self.set_mouse(e.pos[0])

            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.drag = False

        if e.type == pygame.MOUSEMOTION and self.drag:
            self.set_mouse(e.pos[0])
            return True

        return False

    def draw(self):
        pygame.draw.line(screen, (55, 68, 96), (self.x, self.y), (self.x + self.w, self.y), 6)

        k = self.knob()
        pygame.draw.line(screen, BLUE, (self.x, self.y), (k, self.y), 6)

        pygame.draw.circle(screen, BLUE, (k, self.y), 11)
        draw_text(self.label, (self.x, self.y - 28), SMALL, MUTED)

        draw_text(fmt(self.value) + self.unit, (self.x + self.w, self.y - 28), SMALL, TEXT, 'topright')

class InputBox:

    def __init__(self, key, x, y, w, value):
        self.key = key

        self.rect = pygame.Rect(x, y, w, 28)
        self.text = fmt(value)

        self.active = False

    def set(self, v):
        if not self.active:
            self.text = fmt(v)


    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.active = True
                return 'focus'

            if self.active:
                self.active = False
                return 'commit'
        if e.type == pygame.KEYDOWN and self.active:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.active = False

                return 'commit'
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.unicode in '0123456789.-+eE':
                self.text += e.unicode

            return 'edit'
        return None


    def draw(self):
        pygame.draw.rect(screen, (11, 17, 30), self.rect, border_radius=5)
        pygame.draw.rect(screen, BLUE if self.active else (70, 82, 112), self.rect, 1, border_radius=5)

        draw_text(self.text, (self.rect.x + 6, self.rect.y + 5), SMALL, TEXT)

class Button:

    def __init__(self, label, rect):
        self.label = label

        self.rect = pygame.Rect(rect)

    def clicked(self, e):
        return e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos)


    def draw(self, active=False):
        pygame.draw.rect(screen, (48, 92, 145) if active else (36, 47, 70), self.rect, border_radius=9)
        pygame.draw.rect(screen, (80, 100, 140), self.rect, 1, border_radius=9)

        draw_text(self.label, self.rect.center, SMALL, TEXT, 'center')

class BaseModel:
    title = ''


    def __init__(self):
        self.sliders = {}
        self.inputs = {}

        self.last = None
        self.running = False

        self.t = 0
        self.build()

        self.reset()
        self.sync()


    def add(self, key, label, x, y, lo, hi, val, unit=''):
        self.sliders[key] = Slider(label, x, y, 280, lo, hi, val, unit)
        self.inputs[key] = InputBox(key, x + 290, y - 8, 82, val)


    def sync(self):
        for k, s in self.sliders.items():
            self.inputs[k].set(s.value)

    def controls_event(self, e):
        changed = False

        for k, b in self.inputs.items():
            r = b.event(e)
            if r == 'commit':
                try:
                    self.sliders[k].value = clamp(float(b.text), self.sliders[k].lo, self.sliders[k].hi)

                    changed = True
                except:
                    pass

        for s in self.sliders.values():
            changed |= s.event(e)
        if changed:
            self.sync()

            self.reset()

    def draw_controls(self):
        for s in self.sliders.values():
            s.draw()
        for b in self.inputs.values():
            b.draw()


    def draw_header(self):
        draw_text(self.title, (30, 24), BIG)
        draw_text(f"状态：{('运行中' if self.running else '待开始')}    t={self.t:.3f}s", (32, 64), SMALL, MUTED)


    def formula(self):
        return []

    def current(self):
        return []


    def draw_cards(self):
        r = pygame.Rect(825, 120, 385, 310)
        pygame.draw.rect(screen, (12, 19, 34), r, border_radius=14)

        pygame.draw.rect(screen, (54, 70, 105), r, 1, border_radius=14)
        draw_text('实时物理量', (r.x + 18, r.y + 16), FONT, TEXT)

        y = r.y + 52
        for line in self.current():
            draw_text(line, (r.x + 18, y), SMALL, MUTED)

            y += 24
        y += 8

        draw_text('碰撞结果', (r.x + 18, y), FONT, YELLOW)
        y += 30

        if self.last:
            for line in self.last:
                draw_text(line, (r.x + 18, y), SMALL, GREEN)
                y += 22
        else:
            draw_text('尚未发生碰撞', (r.x + 18, y), SMALL, MUTED)

        fr = pygame.Rect(825, 450, 385, 92)
        pygame.draw.rect(screen, (18, 26, 44), fr, border_radius=10)

        y = fr.y + 12
        for line in self.formula():
            draw_text(line, (fr.x + 14, y), TINY, YELLOW)

            y += 25

class TwoBalls(BaseModel):
    title = '1：两自由质点弹性碰撞仿真'


    def build(self):
        self.add('m1', '质点1质量 m1', 35, 650, 0.2, 5, 1, ' kg')
        self.add('m2', '质点2质量 m2', 35, 720, 0.2, 5, 2, ' kg')

        self.add('u1', '质点1初速度 v1', 430, 650, -6, 6, 3, ' m/s')
        self.add('u2', '质点2初速度 v2', 430, 720, -6, 6, -1, ' m/s')

        self.add('speed', '动画速度', 825, 650, 0.2, 2.5, 1, 'x')

    def reset(self):
        self.running = False

        self.t = 0
        self.hit = False

        self.x1 = -2.5
        self.x2 = 2.5
        self.v1 = self.sliders['u1'].value

        self.v2 = self.sliders['u2'].value
        self.last = None


    def start(self):
        self.running = not self.running

    def snap(self):
        self.x1 = -0.23

        self.x2 = 0.23
        self.v1 = self.sliders['u1'].value

        self.v2 = self.sliders['u2'].value
        self.do_collision()

        self.running = True

    def do_collision(self):
        m1, m2 = (self.sliders['m1'].value, self.sliders['m2'].value)

        u1, u2 = (self.v1, self.v2)
        p0 = m1 * u1 + m2 * u2

        e0 = 0.5 * m1 * u1 * u1 + 0.5 * m2 * u2 * u2
        self.v1 = ((m1 - m2) * u1 + 2 * m2 * u2) / (m1 + m2)

        self.v2 = (2 * m1 * u1 + (m2 - m1) * u2) / (m1 + m2)
        self.hit = True

        p1 = m1 * self.v1 + m2 * self.v2
        e1 = 0.5 * m1 * self.v1 ** 2 + 0.5 * m2 * self.v2 ** 2

        self.last = [f"v1'={fmt(self.v1)} m/s", f"v2'={fmt(self.v2)} m/s", f'Δp={fmt(p1 - p0)}', f'ΔE={fmt(e1 - e0)} J']

    def step(self, dt):
        if not self.running:
            return

        dt *= self.sliders['speed'].value
        self.t += dt

        old = self.x2 - self.x1
        self.x1 += self.v1 * dt

        self.x2 += self.v2 * dt
        if not self.hit and self.v1 > self.v2 and (old > 0.46) and (self.x2 - self.x1 <= 0.46):
            self.do_collision()


    def formula(self):
        return ['p=m1*v1+m2*v2', 'Ek=(1/2)m1v1^2+(1/2)m2v2^2']

    def current(self):
        return [f'x1={fmt(self.x1)} m', f'x2={fmt(self.x2)} m', f'v1={fmt(self.v1)} m/s', f'v2={fmt(self.v2)} m/s']


    def draw_scene(self):
        scale = 105
        cx = 405

        y = 315
        pygame.draw.line(screen, (100, 112, 135), (45, y + 35), (790, y + 35), 3)

        p1 = (int(cx + self.x1 * scale), y)
        p2 = (int(cx + self.x2 * scale), y)
        pygame.draw.circle(screen, BLUE, p1, 22)

        pygame.draw.circle(screen, ORANGE, p2, 22)
        draw_text('1', p1, SMALL, (10, 20, 30), 'center')

        draw_text('2', p2, SMALL, (35, 20, 10), 'center')

class BallRod(BaseModel):
    title = '2：质点-定轴细杆碰撞仿真'


    def build(self):
        self.add('m', '质点质量 m', 35, 650, 0.2, 5, 1, ' kg')
        self.add('M', '杆质量 M', 35, 720, 0.2, 8, 3, ' kg')

        self.add('L', '杆长 L', 430, 650, 0.25, 2, 1.2, ' m')
        self.add('ratio', '碰撞位置 h/L', 430, 720, 0.1, 0.95, 0.65, '')

        self.add('u', '质点初速度 u', 825, 650, 0, 8, 4, ' m/s')
        self.add('speed', '动画速度', 825, 720, 0.2, 2.5, 1, 'x')


    def reset(self):
        self.running = False
        self.t = 0

        self.hit = False
        self.theta = 0

        self.w = 0
        self.ball_x = -2

        self.ball_v = self.sliders['u'].value
        self.last = None


    def start(self):
        self.running = not self.running

    def do_collision(self):
        m, M, L = (self.sliders['m'].value, self.sliders['M'].value, self.sliders['L'].value)

        h = self.sliders['ratio'].value * L
        I = M * L * L / 3

        u = self.ball_v
        den = I + m * h * h

        L0 = m * h * u
        E0 = 0.5 * m * u * u

        self.ball_v = (m * h * h - I) * u / den
        self.w = 2 * m * h * u / den

        self.hit = True
        L1 = I * self.w + m * h * self.ball_v

        E1 = 0.5 * I * self.w * self.w + 0.5 * m * self.ball_v * self.ball_v
        self.last = [f"v'={fmt(self.ball_v)} m/s", f'w={fmt(self.w)} rad/s', f'ΔL={fmt(L1 - L0)}', f'ΔE={fmt(E1 - E0)} J']


    def snap(self):
        self.ball_x = -0.08
        self.ball_v = self.sliders['u'].value
        self.do_collision()

        self.running = True

    def step(self, dt):
        if not self.running:
            return

        dt *= self.sliders['speed'].value
        self.t += dt

        old = self.ball_x
        self.ball_x += self.ball_v * dt

        if not self.hit and self.ball_v > 0 and (old < -0.08 <= self.ball_x):
            self.ball_x = -0.08
            self.do_collision()

        if self.hit:
            self.theta += self.w * dt

    def formula(self):
        return ['I=(1/3)ML^2', 'L_about_pivot=I*w+m*h*v']


    def current(self):
        L = self.sliders['L'].value
        h = self.sliders['ratio'].value * L

        I = self.sliders['M'].value * L * L / 3
        return [f'h={fmt(h)} m', f'I={fmt(I)} kg*m^2', f'v={fmt(self.ball_v)} m/s', f'w={fmt(self.w)} rad/s']


    def draw_scene(self):
        L = self.sliders['L'].value
        h = self.sliders['ratio'].value * L

        scale = min(300, 350 / max(0.3, L))
        pivot = (690, 165)

        end = (int(pivot[0] + L * math.sin(self.theta) * scale), int(pivot[1] + L * math.cos(self.theta) * scale))
        pygame.draw.line(screen, YELLOW, pivot, end, 8)

        pygame.draw.circle(screen, BLUE, pivot, 11)
        by = int(pivot[1] + h * scale)

        bx = int(pivot[0] + self.ball_x * scale)
        pygame.draw.circle(screen, BLUE, (bx, by), 20)

        draw_text(f'w={fmt(self.w)}', (pivot[0] + 20, pivot[1] - 16), SMALL, GREEN)


class ValueHistory:
    def __init__(self, limit=120):
        self.limit = max(2, int(limit))

        self.values = []

    def clear(self):
        self.values.clear()


    def append(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return
        if not math.isfinite(value):
            return

        self.values.append(value)
        if len(self.values) > self.limit:
            del self.values[0]

    def last(self, default=0.0):
        return self.values[-1] if self.values else default


    def minimum(self, default=0.0):
        return min(self.values) if self.values else default

    def maximum(self, default=0.0):
        return max(self.values) if self.values else default



class TextCache:
    def __init__(self):
        self._cache = {}

    def clear(self):
        self._cache.clear()


    def render(self, font, value, color):
        key = (id(font), str(value), tuple(color))
        image = self._cache.get(key)

        if image is None:
            image = font.render(str(value), True, color)
            self._cache[key] = image

        return image


def map_range(value, a0, a1, b0, b1):
    if abs(a1 - a0) < 1e-12:
        return 0.5 * (b0 + b1)

    t = (value - a0) / (a1 - a0)
    return b0 + t * (b1 - b0)



def nice_step(span, divisions=5):
    span = abs(float(span))
    if span <= 0.0:
        return 1.0

    raw = span / max(1, divisions)
    power = 10 ** math.floor(math.log10(raw))

    scaled = raw / power
    if scaled <= 1:
        factor = 1
    elif scaled <= 2:
        factor = 2
    elif scaled <= 5:
        factor = 5
    else:
        factor = 10

    return factor * power


def ticks_for_range(lo, hi, divisions=5):
    if hi < lo:
        lo, hi = hi, lo

    step = nice_step(hi - lo, divisions)
    value = math.ceil(lo / step) * step

    ticks = []
    for _ in range(100):
        if value > hi + step * 1e-9:
            break

        ticks.append(value)
        value += step

    return ticks


def draw_axis(surface, rect, lo, hi, color=(76, 92, 120)):
    y = rect.centery

    pygame.draw.line(surface, color, (rect.left, y), (rect.right, y), 1)
    for value in ticks_for_range(lo, hi):
        x = int(map_range(value, lo, hi, rect.left, rect.right))

        pygame.draw.line(surface, color, (x, y - 4), (x, y + 4), 1)


def draw_value_bar(surface, rect, value, lo, hi, fill=(75, 175, 250)):
    pygame.draw.rect(surface, (29, 38, 58), rect, border_radius=4)

    if hi <= lo:
        return
    t = clamp((value - lo) / (hi - lo), 0.0, 1.0)
    filled = rect.copy()

    filled.width = int(rect.width * t)
    if filled.width:
        pygame.draw.rect(surface, fill, filled, border_radius=4)



def momentum_1d(mass, velocity):
    return float(mass) * float(velocity)


def kinetic_energy_1d(mass, velocity):
    velocity = float(velocity)

    return 0.5 * float(mass) * velocity * velocity


def ball_ball_invariants(m1, m2, v1, v2):
    p = momentum_1d(m1, v1) + momentum_1d(m2, v2)

    e = kinetic_energy_1d(m1, v1) + kinetic_energy_1d(m2, v2)
    return p, e



def rod_inertia(mass, length):
    return float(mass) * float(length) * float(length) / 3.0


def angular_momentum_ball(mass, radius, speed):
    return float(mass) * float(radius) * float(speed)



def angular_momentum_rod(inertia, omega):
    return float(inertia) * float(omega)


def energy_rod(inertia, omega):
    omega = float(omega)

    return 0.5 * float(inertia) * omega * omega


def almost_equal(a, b, rel_tol=1e-8, abs_tol=1e-10):
    a = float(a)

    b = float(b)
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))



class FrameTimer:
    def __init__(self, smoothing=0.9):
        self.smoothing = clamp(float(smoothing), 0.0, 0.999)
        self.filtered_dt = 1.0 / 60.0

        self.frames = 0

    def push(self, dt):
        dt = max(0.0, float(dt))

        self.filtered_dt = self.filtered_dt * self.smoothing + dt * (1.0 - self.smoothing)
        self.frames += 1


    @property
    def fps(self):
        if self.filtered_dt <= 1e-12:
            return 0.0
        return 1.0 / self.filtered_dt



class KeyLatch:
    def __init__(self):
        self.down = set()

    def event(self, event):
        if event.type == pygame.KEYDOWN:
            first = event.key not in self.down

            self.down.add(event.key)
            return first

        if event.type == pygame.KEYUP:
            self.down.discard(event.key)
        return False


    def held(self, key):
        return key in self.down


class Notice:
    def __init__(self):
        self.text = ''
        self.time_left = 0.0


    def show(self, value, duration=1.6):
        self.text = str(value)
        self.time_left = max(0.0, float(duration))


    def step(self, dt):
        self.time_left = max(0.0, self.time_left - max(0.0, dt))

    def draw(self, surface, font, pos):
        if self.time_left <= 0.0 or not self.text:
            return

        image = font.render(self.text, True, MUTED)
        surface.blit(image, pos)



class NumericSnapshot:
    def __init__(self):
        self.values = {}

    def clear(self):
        self.values.clear()


    def set(self, key, value):
        self.values[str(key)] = value

    def get(self, key, default=None):
        return self.values.get(str(key), default)


    def copy(self):
        other = NumericSnapshot()
        other.values = dict(self.values)

        return other


class SceneScale:
    def __init__(self, pixels_per_meter=100.0, origin=(0, 0)):
        self.pixels_per_meter = max(1e-6, float(pixels_per_meter))

        self.origin = tuple(origin)

    def set_scale(self, pixels_per_meter):
        self.pixels_per_meter = max(1e-6, float(pixels_per_meter))


    def world_to_screen(self, x, y):
        ox, oy = self.origin
        s = self.pixels_per_meter

        return int(ox + x * s), int(oy + y * s)

    def screen_to_world(self, x, y):
        ox, oy = self.origin

        s = self.pixels_per_meter
        return (x - ox) / s, (y - oy) / s



class TraceBuffer:
    def __init__(self, length=80):
        self.length = max(2, int(length))
        self.points = []


    def clear(self):
        self.points.clear()

    def add(self, x, y):
        self.points.append((float(x), float(y)))

        if len(self.points) > self.length:
            del self.points[0]

    def draw(self, surface, transform, color, width=1):
        if len(self.points) < 2:
            return

        pts = [transform(x, y) for x, y in self.points]
        pygame.draw.lines(surface, color, False, pts, width)



class ValueTable:
    def __init__(self, x, y, row_height=21):
        self.x = int(x)
        self.y = int(y)

        self.row_height = int(row_height)
        self.rows = []

    def clear(self):
        self.rows.clear()


    def add(self, label, value, unit=''):
        self.rows.append((str(label), value, str(unit)))

    def draw(self, surface, font, label_color=MUTED, value_color=TEXT):
        y = self.y

        for label, value, unit in self.rows:
            label_image = font.render(label, True, label_color)
            value_image = font.render(f'{value}{unit}', True, value_color)

            surface.blit(label_image, (self.x, y))
            surface.blit(value_image, (self.x + 150, y))

            y += self.row_height


class CollisionLedger:
    def __init__(self):
        self.before = None

        self.after = None

    def reset(self):
        self.before = None

        self.after = None

    def capture_before(self, **values):
        self.before = dict(values)


    def capture_after(self, **values):
        self.after = dict(values)

    def difference(self, key):
        if self.before is None or self.after is None:
            return None

        if key not in self.before or key not in self.after:
            return None
        return self.after[key] - self.before[key]



class MouseCapture:
    def __init__(self):
        self.owner = None

    def take(self, owner):
        if self.owner is None or self.owner is owner:
            self.owner = owner

            return True
        return False


    def release(self, owner):
        if self.owner is owner:
            self.owner = None

    def held_by(self, owner):
        return self.owner is owner



def safe_number(text_value, default=None):
    try:
        value = float(text_value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default

    return value


def lerp_number(a, b, t):
    return float(a) + (float(b) - float(a)) * clamp(float(t), 0.0, 1.0)



def lerp_rgb(a, b, t):
    t = clamp(float(t), 0.0, 1.0)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))



def draw_soft_panel(surface, rect, fill=(24, 33, 53), border=(58, 72, 105)):
    pygame.draw.rect(surface, fill, rect, border_radius=10)
    pygame.draw.rect(surface, border, rect, 1, border_radius=10)



def draw_separator(surface, x1, x2, y, color=(58, 72, 105)):
    pygame.draw.line(surface, color, (x1, y), (x2, y), 1)


def signed_text(value, digits=3):
    value = float(value)
    return f'{value:+.{digits}f}'



class App:

    def __init__(self):
        self.models = [TwoBalls(), BallRod()]
        self.index = 0

        self.start = Button('开始 / 暂停', (835, 815, 120, 42))
        self.reset = Button('重置', (965, 815, 80, 42))

        self.snap = Button('直接到碰撞', (1055, 815, 130, 42))
        self.tabs = [Button('1 两自由质点', (830, 25, 160, 40)), Button('2 质点-细杆', (1000, 25, 170, 40))]


    @property
    def m(self):
        return self.models[self.index]

    def switch(self, i):
        self.index = i


    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_1:
                self.switch(0)
            elif e.key == pygame.K_2:
                self.switch(1)
            elif e.key == pygame.K_SPACE:
                self.m.start()
            elif e.key == pygame.K_r:
                self.m.reset()
            elif e.key == pygame.K_c:
                self.m.snap()
        for i, b in enumerate(self.tabs):
            if b.clicked(e):
                self.switch(i)

        if self.start.clicked(e):
            self.m.start()
        if self.reset.clicked(e):
            self.m.reset()

        if self.snap.clicked(e):
            self.m.snap()
        self.m.controls_event(e)


    def draw(self):
        gradient_background()
        pygame.draw.rect(screen, PANEL, (0, SIM_H, WIDTH, UI_H))

        pygame.draw.line(screen, (65, 82, 118), (0, SIM_H), (WIDTH, SIM_H), 2)
        self.m.draw_header()

        self.m.draw_scene()
        self.m.draw_cards()

        self.m.draw_controls()
        for i, b in enumerate(self.tabs):
            b.draw(self.index == i)

        self.start.draw(self.m.running)
        self.reset.draw()

        self.snap.draw()
        draw_text('第2版 Functional UI', (1210, 885), TINY, MUTED, 'bottomright')


    def run(self):
        alive = True
        while alive:
            dt = min(clock.tick(FPS) / 1000, 0.04)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    alive = False
                else:
                    self.event(e)
            self.m.step(dt)

            self.draw()
            pygame.display.flip()

        pygame.quit()
if __name__ == '__main__':
    App().run()

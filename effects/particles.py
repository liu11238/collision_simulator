"""碰撞粒子、冲击波及其生成和更新逻辑。"""

from __future__ import annotations

import math
import random
from typing import Callable

import pygame

from config import LAYOUT
from utils import clamp, lerp_color

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
        if sx < -120 or sx > LAYOUT.width + 120 or sy < -120 or sy > LAYOUT.sim_h + 120:
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

"""双球一维碰撞的物理模型和场景绘制。"""

from __future__ import annotations

import math

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BALL1_COLOR, BALL1_EDGE,
                    BALL1_GLOW, BALL2_COLOR, BALL2_EDGE, BALL2_GLOW,
                    BOTTOM_FORMULA_H, BOTTOM_FORMULA_Y, GREEN, MUTED, PLATFORM,
                    PLATFORM_TOP,
                    RED, SIM_H, WIDTH, ANALYSIS_H, ANALYSIS_W, ANALYSIS_X,
                    ANALYSIS_Y, TEXT, SCENE_X, SCENE_W, CONTROLS_X, CONTROLS_W,
                    LAYOUT, SCENE_Y, SCENE_H)
from core.display import (STATIC_BG, flash_surf, glow_surf, particle_surf,
                          screen, trail_surf_1, trail_surf_2)
from core.fonts import FONT_BIG, FONT_SMALL, FONT_TINY
from effects.particles import spawn_impact_particles
from models.base import BaseModel
from render.primitives import draw_arrow, draw_text, rounded_rect
from utils import clamp, format_sig3, lerp_color

class BallBallCollision(BaseModel):
    name = "双球一维碰撞仿真"
    short_name = "双球模型"
    BALL_RADIUS_WORLD = 0.34
    MAX_SUBSTEP = 0.0025

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


    def _advance_simulation_substep(self, sub):
        r = self.BALL_RADIUS_WORLD

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

    def step(self, dt):
        if not self.running:
            return
        speed = self.sliders["anim_speed"].value
        sim_dt = dt * speed
        self.t += sim_dt
        # 使用 ceil 保证每一个物理子步都不超过 MAX_SUBSTEP。
        n = max(1, math.ceil(sim_dt / self.MAX_SUBSTEP))

        sub = sim_dt / n
        for _ in range(n):
            self._advance_simulation_substep(sub)


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
        return pygame.Rect(LAYOUT.formula)

    def interface_state(self):
        return ({"ready": "待开始", "moving": "两球运动中", "after": "碰撞后运动"}
                .get(self.phase, self.phase), self.t)

    def summary_line(self):
        return (f"m1={format_sig3(self.sliders['m1'].value)}  u1={format_sig3(self.sliders['u1'].value)}  "
                f"m2={format_sig3(self.sliders['m2'].value)}  u2={format_sig3(self.sliders['u2'].value)}  "
                f"d={format_sig3(self.sliders['gap'].value)}  e={format_sig3(self.sliders['e'].value)}")

    def draw_ui(self):
        super().draw_ui()

        # 判定内容在底部分析区绘制，避免覆盖公式和操作按钮。

    def draw_analysis_panel(self):
        rect = pygame.Rect(ANALYSIS_X, ANALYSIS_Y, ANALYSIS_W, ANALYSIS_H)
        rounded_rect(screen, rect, (8, 13, 29), 14, 1, (70, 95, 145))
        draw_text(screen, "碰撞分析", (rect.x + 14, rect.y + 10), FONT_BIG, TEXT)
        draw_text(screen, self.summary_line(), (rect.x + 14, rect.y + 43),
                  FONT_TINY, MUTED)

        # v1-v2 判定集中在分析区；一旦开始运行仍保留参数摘要。
        if self.phase == "ready":
            relation = "会相撞" if self.v1 > self.v2 else "不会相撞"
            delta_v = self.v1 - self.v2
            draw_text(screen, "碰撞判定", (rect.x + 14, rect.y + 76), FONT_SMALL, MUTED)

            draw_text(screen,
                      f"v1-v2 = {format_sig3(delta_v)} m/s  →  {relation}",
                      (rect.x + 14, rect.y + 100), FONT_SMALL,
                      ACCENT_3 if delta_v > 0 else RED)

    def draw_scene(self):
        m1 = self.sliders["m1"].value
        m2 = self.sliders["m2"].value
        scale = 92.0
        origin_x = SCENE_X + int(SCENE_W * 0.44)
        center_y = SCENE_Y + int(SCENE_H * 0.56)

        radius_px = int(self.BALL_RADIUS_WORLD * scale)
        platform_y = center_y + radius_px + 14

        def w2s(x, y=0.0):
            return int(origin_x + x * scale), int(center_y - y * scale)

        screen.blit(STATIC_BG, (0, 0))
        scene_left, scene_right = SCENE_X, SCENE_X + SCENE_W
        pygame.draw.line(screen, (22, 28, 48), (scene_left, platform_y + 10), (scene_right, platform_y + 10), 10)
        pygame.draw.line(screen, (35, 44, 70), (scene_left, platform_y + 4), (scene_right, platform_y + 4), 8)
        pygame.draw.line(screen, PLATFORM, (scene_left, platform_y), (scene_right, platform_y), 5)
        pygame.draw.line(screen, PLATFORM_TOP, (scene_left, platform_y - 1), (scene_right, platform_y - 1), 2)

        for tx in range(scene_left, scene_right, 18):
            pygame.draw.line(screen, (100, 115, 155), (tx, platform_y), (tx + 6, platform_y + 4), 1)

        pygame.draw.line(screen, (80, 100, 150), (scene_left, center_y), (scene_right, center_y), 1)
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

        if self.trail1:
            trail_surf_1.fill((0, 0, 0, 0))
            for i, x in enumerate(self.trail1):
                p = i / max(1, len(self.trail1) - 1)

                pos = w2s(x)
                if -100 <= pos[0] <= WIDTH + 100:
                    r = max(2, int(radius_px * (0.12 + 0.26 * p)))
                    pygame.draw.circle(trail_surf_1, (*BALL1_GLOW, int(10 + 70 * p)), pos, r + 3)
                    pygame.draw.circle(trail_surf_1, (*BALL1_COLOR, int(10 + 70 * p)), pos, r)
            screen.blit(trail_surf_1, (0, 0))

        if self.trail2:
            trail_surf_2.fill((0, 0, 0, 0))

            for i, x in enumerate(self.trail2):
                p = i / max(1, len(self.trail2) - 1)
                pos = w2s(x)
                if -100 <= pos[0] <= WIDTH + 100:
                    r = max(2, int(radius_px * (0.12 + 0.26 * p)))
                    pygame.draw.circle(trail_surf_2, (*BALL2_GLOW, int(10 + 70 * p)), pos, r + 3)
                    pygame.draw.circle(trail_surf_2, (*BALL2_COLOR, int(10 + 70 * p)), pos, r)

            screen.blit(trail_surf_2, (0, 0))

        if self.particles or self.shockwaves:
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
            f"两球系统总线动量 = {format_sig3(p_now)} kg*m/s",
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
        tips = ["仅当 u1 > u2 时两球会相撞", "e=1 为理想弹性碰撞", "正速度向右，负速度向左"]
        if self.notice:
            tips.insert(0, self.notice)
        self._info_payload = (
            current_lines,
            collision_lines,
            tips,
            ("碰后 v1", "碰后 v2", "冲量", "动量误差"),
        )


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

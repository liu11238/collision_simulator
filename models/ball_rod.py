"""质点与定轴细杆碰撞的物理模型和场景绘制。"""

from __future__ import annotations

import math

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BALL1_COLOR, BALL1_EDGE,
                    BALL1_GLOW, BASE_Y, GREEN, INPUT_W, MUTED,
                    PLATFORM, PLATFORM_TOP, RIGHT_INPUT_X, ROD_COLOR, ROD_EDGE,
                    ROD_GLOW, ROW, SIM_H, WIDTH)
from core.display import (STATIC_BG, flash_surf, glow_surf, particle_surf,
                          screen, trail_surf_1, trail_surf_2)
from core.fonts import FONT_SMALL
from effects.particles import spawn_impact_particles
from models.base import BaseModel
from render.primitives import draw_arrow, draw_text, rounded_rect
from ui.widgets import InputBox
from utils import clamp, format_sig3

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
        self.app.draw_mode_tabs()

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

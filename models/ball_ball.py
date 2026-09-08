"""双球一维碰撞的物理模型和场景绘制。"""

from __future__ import annotations

import theme

import math

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BALL1_COLOR, BALL1_EDGE,
                    BALL1_GLOW, BALL2_COLOR, BALL2_EDGE, BALL2_GLOW,
                    GREEN, MUTED, PLATFORM, PLATFORM_TOP,
                    RED, TEXT, LAYOUT)
from core import display
from core.fonts import FONT_BIG, FONT_SMALL, FONT_TINY
from effects.particles import spawn_impact_particles
from models.base import BaseModel
from presentation.impact_motion import (SceneCamera, draw_scene_explanation,
                                        fitted_camera, flow_dots, focus_strength,
                                        stage_progress)
from replay.timeline import ReplayFrame, ReplayTimeline
from render.energy import EnergyState, draw_energy_ledger
from render.primitives import (draw_arrow, draw_matte_ball, draw_soft_shadow,
                               draw_text, rounded_rect)
from render.replay_fx import draw_impact_fx
from render.text import clipped
from utils import clamp, format_sig3, lerp_color

class BallBallCollision(BaseModel):
    name = "双球一维碰撞仿真"
    short_name = "双球模型"
    BALL_RADIUS_WORLD = 0.34
    MAX_SUBSTEP = 0.0025

    def __init__(self):
        self.replay = ReplayTimeline()
        self.replay_mode = False
        self.replay_side = "after"
        super().__init__()

    def build_controls(self):
        self.add_control("m1", "左球质量 m1", 0, 0, 0.05, 10.0, 1.00, " kg", 3)
        self.add_control("u1", "左球初速度 u1", 0, 1, -12.0, 12.0, 6.00, " m/s", 3)

        self.add_control("gap", "两球初始表面间距 d", 0, 2, 0.30, 8.00, 3.00, " m", 3)
        self.add_control("m2", "右球质量 m2", 1, 0, 0.05, 10.0, 2.00, " kg", 3)
        self.add_control("u2", "右球初速度 u2", 1, 1, -12.0, 12.0, 0.00, " m/s", 3)
        self.add_control("e", "恢复系数 e", 1, 2, 0.00, 1.00, 1.00, "", 3)
        self.add_control("anim_speed", "动画速度", 1, 3, 0.20, 2.50, 1.00, "x", 2)
        self.add_toggle("explain", "慢放讲解", 0, 3, False)


    def reset(self, keep_running=False):
        u1 = self.sliders["u1"].value
        u2 = self.sliders["u2"].value
        gap = self.sliders["gap"].value
        r = self.BALL_RADIUS_WORLD
        self.running = keep_running
        self.replay.clear()
        self.replay_mode = False
        self.replay_side = "after"
        self.phase = "ready"
        self.explain_elapsed = 0.0

        self.x1 = -gap / 2.0 - r
        self.x2 = gap / 2.0 + r
        self.v1 = u1
        self.v2 = u2
        self.initial_energy = (0.5 * self.sliders["m1"].value * u1 * u1
                               + 0.5 * self.sliders["m2"].value * u2 * u2)
        self.t = 0.0

        self.collided = False
        self.flash = 0.0
        self.last_result = None
        self.trail1 = []
        self.trail2 = []

        self.particles.clear()
        self.shockwaves.clear()
        self.notice = ""
        self.replay.record_initial(self._replay_frame())

    def _replay_frame(self, *, phase=None, left_x=None, right_x=None,
                      left_v=None, right_v=None, collision=None,
                      impact_strength=0.0, impact_flash=0.0):
        """Copy the two-ball display state into an immutable replay frame."""
        left_x = self.x1 if left_x is None else left_x
        right_x = self.x2 if right_x is None else right_x
        left_v = self.v1 if left_v is None else left_v
        right_v = self.v2 if right_v is None else right_v
        phase = self.phase if phase is None else phase
        m1 = self.sliders["m1"].value
        m2 = self.sliders["m2"].value
        left_ke = 0.5 * m1 * left_v * left_v
        right_ke = 0.5 * m2 * right_v * right_v
        loss = 0.0
        if phase == "after":
            source = collision if collision is not None else self.last_result
            loss = source["collision_energy_loss"] if source else 0.0
        total = left_ke + right_ke
        return ReplayFrame(
            time=self.t,
            phase=phase,
            left_x=left_x,
            right_x=right_x,
            left_v=left_v,
            right_v=right_v,
            mechanical_energy=total,
            total_energy=total,
            left_kinetic_energy=left_ke,
            right_kinetic_energy=right_ke,
            rod_kinetic_energy=left_ke,
            ball_kinetic_energy=right_ke,
            collision_energy_loss=loss,
            energy_residual=self.initial_energy - total - loss,
            linear_momentum=m1 * left_v + m2 * right_v,
            collision=collision,
            impact_strength=impact_strength,
            impact_flash=impact_flash,
        )

    def _record_replay_sample(self, force=False):
        self.replay.record_sample(self._replay_frame(), force=force)

    def replay_frame(self, time=None, side=None):
        if not self.replay_mode:
            return None
        return self.replay.frame_at(
            self.replay.cursor if time is None else time,
            side=side or self.replay_side,
        )

    def replay_collision_snapshot(self, frame=None):
        if frame is None:
            frame = self.replay_frame()
        if frame is None:
            return None
        if frame.collision is not None:
            return frame.collision
        cutoff = self.replay.cursor + 1e-10
        for candidate in reversed(self.replay.frames):
            if candidate.time <= cutoff and candidate.collision is not None:
                return candidate.collision
        return None

    def seek_replay(self, time, side="after"):
        if not self.replay.has_frames:
            return None
        self.replay_mode = True
        self.replay_side = side
        self.replay.playing = False
        return self.replay.seek(time, side=side)

    def toggle_replay(self):
        if not self.replay.has_frames:
            return False
        self.replay_mode = True
        return self.replay.toggle()

    def leave_replay(self):
        self.replay_mode = False
        self.replay.playing = False
        self.replay.go_live()

    def replay_playback_step(self, dt):
        if not self.replay_mode:
            return None
        return self.replay.step_playback(dt)

    def can_collide(self):
        return self.v1 > self.v2 + 1e-10

    def start_pause(self):
        if self.replay_mode:
            self.toggle_replay()
            return
        if self.phase == "impact_explain":
            self.phase = "after"
            return
        if self.phase == "ready":
            self.phase = "moving"

            if not self.can_collide():
                self.notice = "当前 u1 <= u2，两球间距不会缩小，因此不会发生碰撞。"
        self.running = not self.running

    def jump_to_collision(self):
        if self.phase == "impact_explain":
            self.phase = "after"
            return
        if self.collided:
            self.notice = "本次碰撞已完成；按 R 重置后可重新讲解。"
            return
        if not self.can_collide():
            self.phase = "moving"
            self.running = False
            self.notice = "无法跳到碰撞：当前 u1 <= u2，两球不会相撞。"

            return
        r = self.BALL_RADIUS_WORLD
        surface_gap = (self.x2 - r) - (self.x1 + r)
        flight_time = max(0.0, surface_gap / (self.v1 - self.v2))
        self.x1 += self.v1 * flight_time
        self.x2 += self.v2 * flight_time
        self.t += flight_time
        self.phase = "moving"
        contact_x = ((self.x1 + r) + (self.x2 - r)) / 2.0
        self.x1 = contact_x - r
        self.x2 = contact_x + r
        self.do_collision(contact_x)
        self.running = True

    def do_collision(self, contact_x):
        m1 = self.sliders["m1"].value
        m2 = self.sliders["m2"].value
        e = self.sliders["e"].value
        u1, u2 = self.v1, self.v2

        if self.app is not None:
            self.app.sound.play("impact")
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
            "collision_energy_loss": max(0.0, ke_before - ke_after),
            "impact_time": self.t,
            "contact_x": contact_x,
        }
        self.replay.record_collision(
            self._replay_frame(
                phase="moving", left_v=u1, right_v=u2,
                collision=self.last_result,
                impact_strength=abs(relative_before), impact_flash=1.0,
            ),
            self._replay_frame(
                phase="after", left_v=v1, right_v=v2,
                collision=self.last_result,
                impact_strength=abs(relative_before), impact_flash=1.0,
            ),
        )
        spawn_impact_particles(self.particles, self.shockwaves, contact_x, 0.0,
                               relative_before, symmetric=True)
        if self.toggles['explain'].value:
            self.phase = 'impact_explain'
            self.explain_elapsed = 0.0

    def toggle_explanation(self):
        toggle = self.toggles['explain']
        toggle.value = not toggle.value
        self.on_toggle_changed('explain', toggle.value)
        return toggle.value

    def on_toggle_changed(self, key, value):
        if key == 'explain' and not value and self.phase == 'impact_explain':
            self.phase = 'after'

    def energy_state_for_display(self):
        replay_frame = self.replay_frame()
        if replay_frame is not None:
            return EnergyState(
                initial=self.initial_energy,
                mechanical=replay_frame.total_energy,
                rod_kinetic=replay_frame.left_kinetic_energy,
                ball_kinetic=replay_frame.right_kinetic_energy,
                collision_loss=replay_frame.collision_energy_loss,
                residual=replay_frame.energy_residual,
            )
        m1 = self.sliders["m1"].value
        m2 = self.sliders["m2"].value
        ke1 = 0.5 * m1 * self.v1 * self.v1
        ke2 = 0.5 * m2 * self.v2 * self.v2
        if self.last_result:
            initial = self.last_result["ke_before"]
            loss = self.last_result["collision_energy_loss"]
            if self.phase == 'impact_explain':
                r = self.last_result
                p = stage_progress(self.explain_elapsed, 3.0, 2)
                before1 = .5 * m1 * r['u1'] ** 2
                before2 = .5 * m2 * r['u2'] ** 2
                ke1 = before1 + (ke1 - before1) * p
                ke2 = before2 + (ke2 - before2) * p
                loss *= p
        else:
            initial = ke1 + ke2
            loss = 0.0
        mechanical = ke1 + ke2
        return EnergyState(initial=initial, mechanical=mechanical,
                           rod_kinetic=ke1, ball_kinetic=ke2,
                           collision_loss=loss,
                           residual=initial - mechanical - loss)

    def draw_energy_panel(self, rect):
        draw_energy_ledger(display.screen, rect, self.energy_state_for_display(),
                           kinetic_labels=('左球动能', '右球动能'))


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
        if self.replay_mode:
            self.replay_playback_step(dt)
            return
        if not self.running:
            return
        if self.phase == 'impact_explain':
            self.explain_elapsed += max(0.0, dt)
            if self.explain_elapsed >= 9.0:
                self.phase = 'after'
            return
        speed = self.sliders["anim_speed"].value
        sim_dt = dt * speed
        # 使用 ceil 保证每一个物理子步都不超过 MAX_SUBSTEP。
        n = max(1, math.ceil(sim_dt / self.MAX_SUBSTEP))

        sub = sim_dt / n
        for _ in range(n):
            self.t += sub
            self._advance_simulation_substep(sub)
            if self.phase == 'impact_explain':
                break


        self.step_particles(dt, gravity=0.0)
        self.flash = max(0.0, self.flash - sim_dt * 2.2)
        self.trail1.append(self.x1)
        self.trail2.append(self.x2)
        if len(self.trail1) > 85:
            self.trail1.pop(0)

        if len(self.trail2) > 85:
            self.trail2.pop(0)
        self._record_replay_sample()

    def formula_lines(self):
        return (
            "J=-(1+e)(u1-u2)/(1/m1+1/m2)",
            "v1=u1+J/m1，v2=u2-J/m2；e=1 时总动能守恒",
        )

    def formula_rect(self):
        return pygame.Rect(LAYOUT.formula)

    def interface_state(self):
        frame = self.replay_frame()
        phase = frame.phase if frame is not None else self.phase
        state = {
            "ready": "待开始",
            "moving": "碰撞前回放" if frame is not None else "两球运动中",
            "after": "碰撞后回放" if frame is not None else "碰撞后运动",
            "impact_explain": "慢放讲解（物理冻结）",
        }.get(phase, phase)
        return state, frame.time if frame is not None else self.t

    def summary_line(self):
        return (f"m1={format_sig3(self.sliders['m1'].value)}  u1={format_sig3(self.sliders['u1'].value)}  "
                f"m2={format_sig3(self.sliders['m2'].value)}  u2={format_sig3(self.sliders['u2'].value)}  "
                f"d={format_sig3(self.sliders['gap'].value)}  e={format_sig3(self.sliders['e'].value)}")

    def draw_ui(self):
        super().draw_ui()

        # 判定内容在底部分析区绘制，避免覆盖公式和操作按钮。

    def draw_analysis_panel(self, rect):
        rect = pygame.Rect(rect)
        replay_frame = self.replay_frame()
        replay_result = self.replay_collision_snapshot() if self.replay_mode else None
        result = replay_result if self.replay_mode else self.last_result
        if result:
            from presentation.impact_panel import draw_impact_panel
            r = result
            m1, m2 = self.sliders['m1'].value, self.sliders['m2'].value
            draw_impact_panel(display.screen, rect,
                self.explain_elapsed if self.phase == 'impact_explain' else 0.0, 3.0,
                [('左球', r['u1'], r['v1']), ('右球', r['u2'], r['v2'])],
                impulses=(r['impulse'], -r['impulse']),
                momenta=[('左球 m1v1', m1*r['u1'], m1*r['v1']),
                         ('右球 m2v2', m2*r['u2'], m2*r['v2'])],
                conserved=('总动量', r['p_before'], r['p_after'], 'kg·m/s'),
                energy_parts=[('左球动能', .5*m1*r['u1']**2, .5*m1*r['v1']**2),
                              ('右球动能', .5*m2*r['u2']**2, .5*m2*r['v2']**2),
                              ('碰撞耗散', 0.0, r['collision_energy_loss'])],
                active=self.phase == 'impact_explain' and not self.replay_mode,
                running=self.running)
            return
        draw_text(display.screen, self.summary_line(), (rect.x + 2, rect.y + 2),
                  FONT_TINY, theme.MUTED, max_width=rect.w - 4)

        # v1-v2 判定集中在分析区；一旦开始运行仍保留参数摘要。
        panel_phase = replay_frame.phase if replay_frame is not None else self.phase
        if panel_phase in {"ready", "moving"}:
            relation = "会相撞" if self.v1 > self.v2 else "不会相撞"
            delta_v = self.v1 - self.v2
            draw_text(display.screen, "碰撞判定",
                      (rect.x + 2, rect.y + 34), FONT_SMALL, theme.MUTED)

            draw_text(display.screen,
                      f"v1-v2 = {format_sig3(delta_v)} m/s  →  {relation}",
                      (rect.x + 2, rect.y + 58), FONT_SMALL,
                      theme.ACCENT_3 if delta_v > 0 else theme.RED, max_width=rect.w - 4)

    def draw_scene(self):
        with clipped(display.screen, pygame.Rect(LAYOUT.scene)):
            self._draw_scene_contents()

    def scene_camera(self):
        origin = (LAYOUT.scene_x + int(LAYOUT.scene_w * 0.44),
                  LAYOUT.scene_y + int(LAYOUT.scene_h * 0.56))
        scale = 92.0
        if self.phase != 'impact_explain' or self.replay_mode:
            return SceneCamera(origin, scale, 1.0)
        r = self.BALL_RADIUS_WORLD
        return fitted_camera(LAYOUT.scene, origin, scale,
                             (self.last_result['contact_x'], 0.0),
                             (self.x1-r, -r, self.x2+r, r),
                             1.0 + .24 * focus_strength(self.explain_elapsed, 9.0),
                             (190, 110, 190, 55))

    def explanation_velocities(self):
        if self.phase != 'impact_explain':
            return self.v1, self.v2
        p = stage_progress(self.explain_elapsed, 3.0, 0)
        r = self.last_result
        return r['u1'] + (r['v1'] - r['u1']) * p, r['u2'] + (r['v2'] - r['u2']) * p

    def _draw_scene_contents(self):
        m1 = self.sliders["m1"].value
        m2 = self.sliders["m2"].value
        replay_frame = self.replay_frame()
        replay_active = replay_frame is not None
        display_x1 = replay_frame.left_x if replay_active else self.x1
        display_x2 = replay_frame.right_x if replay_active else self.x2
        display_v1 = replay_frame.left_v if replay_active else self.v1
        display_v2 = replay_frame.right_v if replay_active else self.v2
        display_phase = replay_frame.phase if replay_active else self.phase
        display_result = (self.replay_collision_snapshot(replay_frame)
                          if replay_active else self.last_result)
        explaining = self.phase == 'impact_explain' and not replay_active
        camera = self.scene_camera()
        scale = camera.scale
        center_y = round(camera.origin[1])

        radius_px = int(self.BALL_RADIUS_WORLD * scale)
        platform_y = center_y + radius_px + 14

        def w2s(x, y=0.0):
            return camera.point(x, -y)

        display.screen.blit(display.STATIC_BG, (0, 0))
        scene_left, scene_right = LAYOUT.scene_x, LAYOUT.scene_x + LAYOUT.scene_w
        pygame.draw.line(display.screen, theme.color((23, 31, 29)), (scene_left, platform_y + 10), (scene_right, platform_y + 10), 10)
        pygame.draw.line(display.screen, theme.color((33, 45, 43)), (scene_left, platform_y + 4), (scene_right, platform_y + 4), 8)
        pygame.draw.line(display.screen, theme.PLATFORM, (scene_left, platform_y), (scene_right, platform_y), 5)
        pygame.draw.line(display.screen, theme.PLATFORM_TOP, (scene_left, platform_y - 1), (scene_right, platform_y - 1), 2)

        for tx in range(scene_left, scene_right, 18):
            pygame.draw.line(display.screen, theme.color((74, 100, 96)), (tx, platform_y), (tx + 6, platform_y + 4), 1)

        pygame.draw.line(display.screen, theme.color((72, 97, 93)), (scene_left, center_y), (scene_right, center_y), 1)
        for world_x in range(-4, 5):
            sx, _ = w2s(world_x)
            pygame.draw.line(display.screen, theme.color((72, 97, 93)), (sx, center_y - 7), (sx, center_y + 7), 1)
            draw_text(display.screen, f"{world_x}", (sx, center_y + 12), FONT_TINY, theme.MUTED, anchor="midtop")


        if display_phase in {'ready', 'moving'}:
            left_surface = display_x1 + self.BALL_RADIUS_WORLD
            right_surface = display_x2 - self.BALL_RADIUS_WORLD
            if right_surface > left_surface:
                p1 = w2s(left_surface, -0.72)
                p2 = w2s(right_surface, -0.72)
                pygame.draw.line(display.screen, theme.color((84, 113, 108)), p1, p2, 2)

                pygame.draw.line(display.screen, theme.color((84, 113, 108)), (p1[0], p1[1] - 7), (p1[0], p1[1] + 7), 2)
                pygame.draw.line(display.screen, theme.color((84, 113, 108)), (p2[0], p2[1] - 7), (p2[0], p2[1] + 7), 2)
                draw_text(display.screen, f"当前间距={format_sig3(right_surface - left_surface)} m",
                          ((p1[0] + p2[0]) // 2, p1[1] + 10), FONT_SMALL, theme.MUTED, anchor="midtop")

        if replay_active:
            trail_start = replay_frame.time - 0.8
            replay_history = [
                item for item in self.replay.frames
                if trail_start <= item.time <= replay_frame.time + 1e-10
            ]
            trail1 = [item.left_x for item in replay_history
                      if abs(item.left_v) > 0.03]
            trail2 = [item.right_x for item in replay_history
                      if abs(item.right_v) > 0.03]
        else:
            trail1, trail2 = self.trail1, self.trail2

        if trail1:
            display.trail_surf_1.fill((0, 0, 0, 0))
            for i, x in enumerate(trail1):
                p = i / max(1, len(trail1) - 1)

                pos = w2s(x)
                if -100 <= pos[0] <= LAYOUT.width + 100:
                    r = max(2, int(radius_px * (0.12 + 0.26 * p)))
                    pygame.draw.circle(display.trail_surf_1, (*theme.BALL1_GLOW, int(10 + 70 * p)), pos, r + 3)
                    pygame.draw.circle(display.trail_surf_1, (*theme.BALL1_COLOR, int(10 + 70 * p)), pos, r)
            display.screen.blit(display.trail_surf_1, (0, 0))

        if trail2:
            display.trail_surf_2.fill((0, 0, 0, 0))

            for i, x in enumerate(trail2):
                p = i / max(1, len(trail2) - 1)
                pos = w2s(x)
                if -100 <= pos[0] <= LAYOUT.width + 100:
                    r = max(2, int(radius_px * (0.12 + 0.26 * p)))
                    pygame.draw.circle(display.trail_surf_2, (*theme.BALL2_GLOW, int(10 + 70 * p)), pos, r + 3)
                    pygame.draw.circle(display.trail_surf_2, (*theme.BALL2_COLOR, int(10 + 70 * p)), pos, r)

            display.screen.blit(display.trail_surf_2, (0, 0))

        if (not replay_active and self.phase != 'impact_explain'
                and (self.particles or self.shockwaves)):
            display.particle_surf.fill((0, 0, 0, 0))
            for particle in self.particles:
                particle.draw(display.particle_surf, w2s, streak_scale=5.5)
            for wave in self.shockwaves:
                wave.draw(display.particle_surf, w2s, scale)
            display.screen.blit(display.particle_surf, (0, 0))


        def draw_ball(pos, radius, base_color, edge_color, glow_color, label, mass):
            px, py = pos
            draw_soft_shadow(
                display.screen,
                (px - radius - 6, platform_y - max(4, radius // 4),
                 2 * radius + 12, max(8, radius // 2)),
            )
            draw_matte_ball(display.screen, pos, radius, base_color)
            draw_text(display.screen, label, (px, py + 4), FONT_TINY, (20, 27, 26), anchor="center")
            draw_text(display.screen, f"m={format_sig3(mass)} kg", (px, py + radius + 18), FONT_TINY, theme.MUTED,
                      anchor="topright" if label == '球 1' else "topleft")

        pos1, pos2 = w2s(display_x1), w2s(display_x2)
        draw_ball(pos1, radius_px, theme.BALL1_COLOR, theme.BALL1_EDGE, theme.BALL1_GLOW, "球 1", m1)
        draw_ball(pos2, radius_px, theme.BALL2_COLOR, theme.BALL2_EDGE, theme.BALL2_GLOW, "球 2", m2)


        def draw_velocity(pos, velocity, label):
            # Two separate lanes remain readable when both velocities point
            # right (or left) and the balls are touching during explanation.
            y = pos[1] - radius_px - (18 if label == 'v1' else 60)
            if abs(velocity) < 0.01:
                draw_text(display.screen, f"{label}=0", (pos[0], y),
                          FONT_SMALL, theme.GREEN, anchor="midbottom")
                return
            direction = 1 if velocity > 0 else -1
            arrow_len = clamp(abs(velocity) * 10.0, 35, 150)
            finish = (int(pos[0] + direction * arrow_len), y)
            draw_arrow(display.screen, (pos[0], y), finish, theme.GREEN, 3)
            if explaining:
                flow_dots(display.screen, (pos[0], y), finish, self.explain_elapsed,
                          theme.GREEN, count=2, radius=2)
            draw_text(display.screen, f"{label}={format_sig3(velocity)} m/s",
                      (finish[0] + (10 if direction > 0 else -10), y - 12), FONT_SMALL, theme.GREEN,
                      anchor="topleft" if direction > 0 else "topright")

        if not explaining or self.explain_elapsed < 3.0:
            v1, v2 = ((display_v1, display_v2) if replay_active
                      else self.explanation_velocities())
            draw_velocity(pos1, v1, "v1")
            draw_velocity(pos2, v2, "v2")
        if explaining:
            r = self.last_result
            draw_scene_explanation(display.screen, LAYOUT.scene, self.explain_elapsed, 3.0,
                [pos1, pos2], [radius_px, radius_px], (r['impulse'], -r['impulse']),
                (.5*m1*r['u1']**2, .5*m2*r['u2']**2),
                (.5*m1*r['v1']**2, .5*m2*r['v2']**2), running=self.running)


        if (not replay_active and self.phase != 'impact_explain'
                and self.flash > 0 and self.last_result):
            contact = w2s(self.last_result["contact_x"])
            display.flash_surf.fill((0, 0, 0, 0))
            f = self.flash
            r0 = int(clamp((1.15 - f) * 80 + 10, 5, 90))
            a0 = int(220 * f)

            pygame.draw.circle(display.flash_surf, (255, 255, 255, a0), contact, r0)
            pygame.draw.circle(display.flash_surf, (255, 210, 80, int(a0 * 0.45)), contact, r0 + int(30 * f))
            pygame.draw.circle(display.flash_surf, (120, 180, 255, int(a0 * 0.20)), contact, r0 + int(55 * f))
            display.screen.blit(display.flash_surf, (0, 0))

        if replay_active and display_result is not None:
            contact = w2s(display_result["contact_x"])
            draw_impact_fx(display.screen, contact, replay_frame.impact_flash,
                           replay_frame.impact_strength)

        p_now = m1 * display_v1 + m2 * display_v2
        ke1 = 0.5 * m1 * display_v1 * display_v1
        ke2 = 0.5 * m2 * display_v2 * display_v2
        current_lines = [
            f"左球速度 v1 = {format_sig3(display_v1)} m/s",
            f"右球速度 v2 = {format_sig3(display_v2)} m/s",
            f"相对速度 v1-v2 = {format_sig3(display_v1 - display_v2)} m/s",
            f"质心速度 Vcm = {format_sig3(p_now / (m1 + m2))} m/s",
            f"左球动能 = {format_sig3(ke1)} J",
            f"右球动能 = {format_sig3(ke2)} J",
            f"两球系统总线动量 = {format_sig3(p_now)} kg*m/s",
        ]

        collision_lines = None
        if display_result:
            r = display_result
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

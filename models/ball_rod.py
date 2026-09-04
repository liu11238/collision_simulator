"""重力场中质点与定轴细杆碰撞的物理模型和场景绘制。"""

from __future__ import annotations

import math

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BALL1_COLOR, BALL1_EDGE,
                    BALL1_GLOW, BASE_Y, BOTTOM_FORMULA_H, BOTTOM_FORMULA_Y,
                    GREEN, INPUT_W, MUTED, PLATFORM, PLATFORM_TOP,
                    RIGHT_INPUT_X, ROD_COLOR, ROD_EDGE, ROD_GLOW, ROW, SIM_H,
                    WIDTH)
from core.display import (STATIC_BG, flash_surf, glow_surf, particle_surf,
                          screen, trail_surf_1, trail_surf_2)
from core.fonts import FONT_SMALL
from effects.particles import spawn_impact_particles
from models.base import BaseModel
from models.collision_data import CollisionSnapshot
from presentation.collision_explainer import CollisionExplainer
from replay.timeline import ReplayFrame, ReplayTimeline
from render.primitives import draw_arrow, draw_text, rounded_rect
from render.energy_flow import draw_energy_flow
from render.replay_fx import draw_impact_fx
from ui.widgets import InputBox
from utils import clamp, format_sig3


class BallHitsRod(BaseModel):
    """杆从初始摆角摆到竖直位置，并以指定碰撞点速度撞击小球。

    ``theta`` 的定义沿用原模型：杆端坐标为
    ``(-L*cos(theta), L*sin(theta))``，所以 ``theta=pi/2`` 是竖直向下，
    ``theta=0`` 是水平向左。UI 中的 ``initial_angle_deg`` 则是相对于竖直
    向下方向的摆角，范围为 0--90 度。
    """

    name = "质点‑定轴细杆碰撞仿真"
    short_name = "质点‑定轴细杆"
    EPS = 1e-12
    MAX_SUBSTEP = 0.0025
    control_row_height = 42
    supports_impact_explanation = True

    def __init__(self):
        self.replay = ReplayTimeline()
        self.replay_mode = False
        self.replay_side = "after"
        self._fast_forwarding = False
        super().__init__()

    def build_controls(self):
        self.add_control("m", "小球质量 m", 0, 0, 0.05, 10.0, 1.00, " kg", 3)
        self.add_control("M", "杆质量 M", 0, 1, 0.10, 20.0, 4.00, " kg", 3)
        self.add_control("vc", "目标碰撞点速率 vc", 0, 2, 0.00, 30.0, 3.00, " m/s", 3)
        self.add_control("g", "重力加速度 g", 0, 3, 0.00, 25.0, 9.80, " m/s^2", 3)

        self.add_control("L", "杆长 L", 1, 0, 0.25, 2.00, 1.00, " m", 3)
        self.add_control("height_ratio", "碰撞高度 h/L", 1, 1, 0.00, 1.00, 0.72, "", 4)
        self.add_control("anim_speed", "动画速度", 1, 2, 0.20, 2.50, 1.00, "x", 2)
        self.add_control("e", "恢复系数 e", 1, 3, 0.00, 1.00, 1.00, "", 3)
        self.add_control("tau0", "恒定摩擦矩 τ0", 0, 4, 0.00, 0.500, 0.000, " N*m", 4)

        # h 仍然保留精确输入，但滑块用 h/L 表示，便于同时调整 L 和碰撞位置。
        self.input_boxes.pop("height_ratio")
        self.input_boxes["h"] = InputBox(
            "h", "精确输入", RIGHT_INPUT_X,
            BASE_Y + self.control_row_height - 8,
            INPUT_W, self.current_h(), "m"
        )

    def current_h(self):
        return self.sliders["height_ratio"].value * self.sliders["L"].value

    def input_values(self):
        return {
            "m": self.sliders["m"].value,
            "M": self.sliders["M"].value,
            "vc": self.sliders["vc"].value,
            "g": self.sliders["g"].value,
            "L": self.sliders["L"].value,
            "h": self.current_h(),
            "anim_speed": self.sliders["anim_speed"].value,
            "e": self.sliders["e"].value,
            "tau0": self.sliders["tau0"].value,
        }

    def set_control_value(self, key, value):
        # b 是上一版本的参数名，保留它作为 tau0 的兼容别名；物理含义
        # 已经改为恒定摩擦矩，不再执行 tau=-b*omega。
        if key == "b":
            key = "tau0"
        if key == "L":
            old_h = self.current_h()
            self.sliders["L"].set_value(value)
            self.sliders["height_ratio"].set_value(
                old_h / max(1e-9, self.sliders["L"].value)
            )
        elif key == "h":
            L = self.sliders["L"].value
            self.sliders["height_ratio"].set_value(
                clamp(value, 0.0, L) / max(1e-9, L)
            )
        else:
            self.sliders[key].set_value(value)

    def ball_radius_world(self):
        return 0.055 * self.sliders["L"].value

    def _replay_frame(self, *, phase=None, theta=None, omega=None,
                      ball_x=None, ball_v=None, collision=None,
                      event=None, collision_id=None, impact_strength=0.0,
                      impact_flash=0.0, impact_progress=1.0):
        """将当前或显式指定的展示状态复制为只读回放帧。"""
        theta = self.theta if theta is None else theta
        omega = self.omega if omega is None else omega
        ball_x = self.ball_x if ball_x is None else ball_x
        ball_v = self.ball_v if ball_v is None else ball_v
        phase = self.phase if phase is None else phase
        potential = self.gravity_potential(theta)
        rod_energy = 0.5 * self.inertia() * omega * omega + potential
        ball_energy = 0.5 * self.sliders["m"].value * ball_v * ball_v
        total_energy = rod_energy + ball_energy
        angular_momentum = self.inertia() * omega + (
            self.sliders["m"].value * self.current_h() * ball_v
        )
        return ReplayFrame(
            time=self.t,
            phase=phase,
            theta=theta,
            omega=omega,
            ball_x=ball_x,
            ball_v=ball_v,
            mechanical_energy=rod_energy,
            total_energy=total_energy,
            friction_energy=self.damping_energy,
            angular_momentum=angular_momentum,
            collision=collision,
            collision_id=collision_id,
            event=event,
            impact_strength=impact_strength,
            impact_flash=impact_flash,
            impact_progress=impact_progress,
        )

    def _record_replay_sample(self, force=False):
        self.replay.record_sample(self._replay_frame(), force=force)

    def replay_frame(self, time=None, side=None):
        """取得回放展示帧；回放关闭时返回 None。"""
        if not self.replay_mode:
            return None
        return self.replay.frame_at(
            self.replay.cursor if time is None else time,
            side=side or self.replay_side,
        )

    def replay_collision_snapshot(self, frame=None):
        """返回当前回放游标之前最近一次碰撞的快照。"""
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

    def inertia(self):
        M = self.sliders["M"].value
        L = self.sliders["L"].value
        return M * L * L / 3.0

    def friction_moment(self):
        """返回库仑型恒定转轴摩擦矩 ``tau0``，单位为 N*m。"""
        return self.sliders["tau0"].value

    def friction_torque(self, omega=None):
        """返回始终阻碍转动的恒定摩擦矩 ``-tau0*sign(omega)``。"""
        if omega is None:
            omega = self.omega
        if abs(omega) <= self.EPS:
            return 0.0
        return -self.friction_moment() * math.copysign(1.0, omega)

    # 旧展示代码和外部调用仍使用 damping 名称；它们现在指向恒定摩擦，
    # 而不是旧版的线性黏性阻尼。
    damping_coefficient = friction_moment
    damping_torque = friction_torque

    def percussion_center(self):
        """均匀细杆的打击中心（相对转轴的距离）。

        细杆质心距转轴 ``L/2``，而 ``I=M*L^2/3``，因此使碰撞时转轴
        水平反力冲量为零的打击中心为 ``I/(M*L/2)=2L/3``。
        """
        return 2.0 * self.sliders["L"].value / 3.0

    # 这个别名便于展示层和旧的教学文案使用更直观的名称。
    center_of_percussion = percussion_center

    def target_collision_speed(self):
        """目标为碰撞点（距转轴 h 处）的线速度，单位 m/s。"""
        return self.sliders["vc"].value

    def target_angular_speed(self):
        h = self.current_h()
        if h <= self.EPS:
            return 0.0
        return self.target_collision_speed() / h

    def compute_launch_state(self):
        """由目标碰撞速度反解初始摆角和初始角速度。

        杆从 ``theta_start`` 摆到竖直位置 ``pi/2``。重力释放能够提供的
        最大角速度对应 ``theta_start=0``；若目标速度超过该值，则从 90
        度摆角出发并补充初始角速度。
        """
        L = self.sliders["L"].value
        g = self.sliders["g"].value
        target_omega = self.target_angular_speed()

        # sin(theta_start) = 1 - omega_c^2 * L / (3g)。
        gravity_omega_sq = 3.0 * g / L if g > self.EPS else 0.0
        target_omega_sq = target_omega * target_omega

        if target_omega <= self.EPS:
            # 目标速度为零时，杆直接处于竖直最低位置；g=0 也需要这个
            # 特殊分支，否则通用的“90°出发”状态永远不会到达碰撞位置。
            theta_start = math.pi / 2.0
            omega_start = 0.0
            uses_initial_speed = False
        elif g > self.EPS and target_omega_sq <= gravity_omega_sq + self.EPS:
            sin_start = clamp(
                1.0 - target_omega_sq / gravity_omega_sq, 0.0, 1.0
            )
            theta_start = math.asin(sin_start)
            omega_start = 0.0
            uses_initial_speed = False
        else:
            # theta=0 即相对竖直向下 90 度，剩余速度由初始角速度提供。
            theta_start = 0.0
            omega_start = math.sqrt(
                max(0.0, target_omega_sq - gravity_omega_sq)
            )
            uses_initial_speed = target_omega > self.EPS

        angle_from_vertical = math.pi / 2.0 - theta_start
        return {
            "theta_start": theta_start,
            "omega_start": omega_start,
            "target_omega": target_omega,
            "angle_from_vertical": angle_from_vertical,
            "angle_deg": math.degrees(angle_from_vertical),
            "uses_initial_speed": uses_initial_speed,
            "gravity_omega_max": math.sqrt(gravity_omega_sq),
            "h_valid": self.current_h() > self.EPS,
        }

    def gravity_potential(self, theta=None):
        """相对杆竖直向下位置的重力势能，零点固定在 ``theta=pi/2``。"""
        if theta is None:
            theta = self.theta
        M = self.sliders["M"].value
        L = self.sliders["L"].value
        g = self.sliders["g"].value
        return M * g * L * (1.0 - math.sin(theta)) / 2.0

    def mechanical_energy(self, theta=None, omega=None):
        if theta is None:
            theta = self.theta
        if omega is None:
            omega = self.omega
        return 0.5 * self.inertia() * omega * omega + self.gravity_potential(theta)

    def total_mechanical_energy(self):
        """细杆机械能加小球平动动能。"""
        m = self.sliders["m"].value
        return self.mechanical_energy() + 0.5 * m * self.ball_v * self.ball_v

    def energy_breakdown(self):
        """返回可审计的能量账本。

        ``initial`` 是本次运行从碰撞前状态继承的总机械能；碰撞瞬时损失
        和碰后阻尼耗散分别记账，``residual`` 为数值积分与账本的误差。
        """
        initial = self.initial_energy
        if self.last_result is not None:
            initial = self.last_result.energy_before
        mechanical = self.total_mechanical_energy()
        committed = self.phase == "after"
        collision = self.collision_energy_loss if committed else 0.0
        damping = self.damping_energy if committed else 0.0
        residual = initial - mechanical - collision - damping
        return {
            "initial": initial,
            "mechanical": mechanical,
            "collision": collision,
            "damping": damping,
            "residual": residual,
            "collision_energy_loss": collision,
            "damping_energy": damping,
            "friction": damping,
            "friction_energy": damping,
        }

    @property
    def friction_energy(self):
        return self.damping_energy

    def collision_point_speed(self):
        if self.phase == "impact_explain" and self.collision_snapshot is not None:
            return abs(self.collision_snapshot.contact_after)
        return abs(self.current_h() * self.omega)

    def reset(self, keep_running=False):
        launch = self.compute_launch_state()
        self.replay.clear()
        self.replay_mode = False
        self.replay_side = "after"
        self.running = keep_running
        self.phase = "ready"
        self.theta = launch["theta_start"]
        self.omega = launch["omega_start"]
        self.initial_theta = launch["theta_start"]
        self.initial_omega = launch["omega_start"]
        self.initial_angle_deg = launch["angle_deg"]
        self.target_omega = launch["target_omega"]
        self.gravity_omega_max = launch["gravity_omega_max"]
        self.uses_initial_speed = launch["uses_initial_speed"]
        self.initial_energy = self.mechanical_energy()

        # 小球静止在碰撞位置；vc 只表示杆的碰撞点速度，不是小球入射速度。
        self.ball_x = 0.0
        self.ball_v = 0.0
        self.t = 0.0
        self.collided = False
        self.damping_energy = 0.0
        self.collision_energy_loss = 0.0

        self.flash = 0.0
        self.last_result = None
        self.collision_snapshot = None
        self.impact_explainer = None
        if not hasattr(self, "explain_enabled"):
            self.explain_enabled = True
        self.camera_zoom = 1.0
        self.camera_focus = None
        self.rod_trail = [self.theta]
        self.ball_trail = [(self.ball_x, self.current_h())]
        self.particles.clear()
        self.shockwaves.clear()
        self.notice = ""
        self._record_replay_sample(force=True)
        if self.current_h() <= self.EPS:
            self.notice = "碰撞高度 h=0，碰撞点位于转轴，无法定义有效碰撞点速度。"

    def start_pause(self):
        if self.replay_mode:
            self.toggle_replay()
            return
        if self.phase == "impact_explain":
            self.skip_explanation()
            return
        if self.phase == "ready":
            self.phase = "swinging"
        self.running = not self.running

    def jump_to_collision(self):
        """通过真实物理子步快进到碰撞，而不是伪造碰撞时刻。

        C 键仍然是一个便捷入口，但碰撞时刻 ``result.impact_time`` 和
        Replay 的展示时长来自同一套实际积分。120 秒是防止异常参数或
        数值状态导致无限循环的硬上限。
        """
        if self.phase == "impact_explain":
            self.skip_explanation()
        if self.collided:
            self.running = True
            return
        self.phase = "swinging"
        self.running = True
        self._fast_forwarding = True
        try:
            guard_time = 0.0
            while not self.collided and guard_time < 120.0:
                self._advance_simulation_substep(self.MAX_SUBSTEP)
                guard_time += self.MAX_SUBSTEP
        finally:
            self._fast_forwarding = False
        if not self.collided:
            self.running = False
            self.notice = "C 键快进在 120 s 内未到达碰撞位置，请检查参数。"

    def do_collision(self):
        """兼容旧调用方：立即计算并提交碰撞结果。"""
        self.begin_collision(explain=False)

    def begin_collision(self, explain=None):
        """创建碰撞快照，并按设置进入讲解冻结阶段或直接提交。"""
        if explain is None:
            explain = self.explain_enabled
        result = self.solve_collision()
        self.collision_snapshot = result
        before_frame = self._replay_frame(
            phase="swinging", theta=result.theta_before,
            omega=result.omega_before, ball_v=self.ball_v,
            collision=result,
            impact_strength=abs(result.relative_before),
            impact_flash=1.0,
            impact_progress=0.0,
        )
        after_frame = self._replay_frame(
            phase="after", theta=math.pi / 2.0,
            omega=result.omega_after, ball_v=result.v_after,
            collision=result,
            impact_strength=abs(result.relative_before),
            impact_flash=0.0,
            impact_progress=1.0,
        )
        self.replay.record_collision(before_frame, after_frame)
        if explain:
            # 快照对外可见，但碰后运动状态仍冻结到讲解结束。
            self.collided = True
            self.last_result = result
            self.phase = "impact_explain"
            self.impact_explainer = CollisionExplainer(result)
            self.flash = 1.0
            direction = -1.0 if result.impulse > 0 else 1.0
            spawn_impact_particles(
                self.particles, self.shockwaves, 0.0, result.h,
                result.relative_before, direction=direction, vertical_bias=-0.3
            )
            self.camera_zoom = 1.0
            self.camera_focus = (0.0, result.h)
        else:
            self.apply_collision_result(result)

    def skip_explanation(self):
        """跳过当前讲解并提交冻结的碰撞结果。"""
        if self.phase != "impact_explain" or self.collision_snapshot is None:
            return False
        self.apply_collision_result(self.collision_snapshot, spawn_fx=False)
        return True

    def toggle_explanation(self):
        self.explain_enabled = not self.explain_enabled
        state = "开启" if self.explain_enabled else "关闭"
        self.notice = f"碰撞讲解已{state}（E 切换）"
        return self.explain_enabled

    def _legacy_do_collision(self):
        result = self.solve_collision()
        self.apply_collision_result(result)

    def solve_collision(self):
        """只计算瞬时碰撞结果，不修改模型状态。"""
        m = self.sliders["m"].value
        M = self.sliders["M"].value
        L = self.sliders["L"].value
        h = self.current_h()
        I = self.inertia()
        e = self.sliders["e"].value
        u_before = self.ball_v
        omega_before = self.omega
        relative_before = u_before - h * omega_before
        denominator = 1.0 / m + h * h / I
        impulse = -(1.0 + e) * relative_before / denominator
        v_after = u_before + impulse / m
        omega_after = omega_before - impulse * h / I

        ke_before = 0.5 * m * u_before * u_before + 0.5 * I * omega_before * omega_before
        ke_after = 0.5 * m * v_after * v_after + 0.5 * I * omega_after * omega_after
        potential = self.gravity_potential(math.pi / 2.0)
        ball_ke_before = 0.5 * m * u_before * u_before
        ball_ke_after = 0.5 * m * v_after * v_after
        rod_ke_before = 0.5 * I * omega_before * omega_before
        rod_ke_after = 0.5 * I * omega_after * omega_after
        collision_loss = max(0.0, ke_before - ke_after)
        mu_eff = 1.0 / denominator
        collision_loss_theory = (
            0.5 * mu_eff * (1.0 - e * e) * relative_before * relative_before
        )

        # 绕定轴的有符号角动量：杆为 I*w，小球为 m*h*v。
        rod_L_before = I * omega_before
        ball_MRV_before = m * h * u_before
        total_L_before = rod_L_before + ball_MRV_before
        rod_L_after = I * omega_after
        ball_MRV_after = m * h * v_after
        total_L_after = rod_L_after + ball_MRV_after

        # 碰撞时杆质心的水平速度为 L*w/2；系统线动量不守恒的差额是转轴外冲量。
        rod_p_before = M * L * 0.5 * omega_before
        rod_p_after = M * L * 0.5 * omega_after
        system_p_before = m * u_before + rod_p_before
        system_p_after = m * v_after + rod_p_after

        return CollisionSnapshot(
            m=m, M=M, L=L, I=I, h=h, e=e, theta_before=self.theta,
            u_before=u_before, v_after=v_after,
            omega_before=omega_before, omega_after=omega_after,
            contact_before=h * omega_before, contact_after=h * omega_after,
            relative_before=relative_before,
            relative_after=v_after - h * omega_after,
            impulse=impulse,
            ke_before=ke_before, ke_after=ke_after,
            ball_ke_before=ball_ke_before, ball_ke_after=ball_ke_after,
            rod_ke_before=rod_ke_before, rod_ke_after=rod_ke_after,
            potential=potential,
            energy_before=ke_before + potential,
            energy_after=ke_after + potential,
            collision_energy_loss=collision_loss,
            collision_loss_theory=collision_loss_theory,
            mu_eff=mu_eff,
            rod_L_before=rod_L_before,
            ball_MRV_before=ball_MRV_before,
            total_L_before=total_L_before,
            rod_L_after=rod_L_after,
            ball_MRV_after=ball_MRV_after,
            total_L_after=total_L_after,
            rod_p_before=rod_p_before, rod_p_after=rod_p_after,
            system_p_before=system_p_before, system_p_after=system_p_after,
            # 系统线动量的变化就是转轴外冲量；在 h=2L/3 时应为零。
            pivot_impulse=system_p_after - system_p_before,
            impact_time=self.t,
        )

    def apply_collision_result(self, result, spawn_fx=True):
        """提交已计算的碰撞结果并启动碰撞后的物理状态。"""
        self.ball_v = result.v_after
        self.omega = result.omega_after
        self.theta = math.pi / 2.0
        self.phase = "after"
        self.collided = True
        self.flash = 1.0
        self.notice = ""
        self.last_result = result
        self.collision_snapshot = result
        self.impact_explainer = None
        self.collision_energy_loss = result.collision_energy_loss
        self.camera_zoom = 1.0
        self.camera_focus = None
        if (not self.replay.frames
                or self.t > self.replay.frames[-1].time + 1e-10):
            self._record_replay_sample(force=True)

        if spawn_fx:
            direction = -1.0 if result.impulse > 0 else 1.0
            spawn_impact_particles(
                self.particles, self.shockwaves, 0.0, result.h,
                result.relative_before, direction=direction, vertical_bias=-0.3
            )

    def _swing_speed(self, theta):
        """由摆动机械能直接得到当前角速度的正值。"""
        L = self.sliders["L"].value
        g = self.sliders["g"].value
        sin_start = math.sin(self.initial_theta)
        omega_sq = self.initial_omega ** 2 + 3.0 * g / L * (
            math.sin(theta) - sin_start
        )
        return math.sqrt(max(0.0, omega_sq))

    def _advance_swing(self, dt):
        """用角加速度速度 Verlet 推进，并投影回初始机械能。

        不能直接积分 ``dtheta/dt=sqrt(...)``：从静止释放时右侧在起点为
        0，数值积分会错误地把杆卡在起点。因此这里先用动力学方程启动，
        再用能量关系消除积分误差。
        """
        a0 = self._post_acceleration(self.theta)
        omega_half = self.omega + 0.5 * a0 * dt
        self.theta += omega_half * dt
        omega_vv = omega_half + 0.5 * self._post_acceleration(self.theta) * dt

        available = 2.0 * (
            self.initial_energy - self.gravity_potential(self.theta)
        ) / self.inertia()
        magnitude = math.sqrt(max(0.0, available))
        if abs(omega_vv) > self.EPS:
            self.omega = math.copysign(magnitude, omega_vv)
        else:
            self.omega = 0.0

    def _post_acceleration(self, theta):
        L = self.sliders["L"].value
        g = self.sliders["g"].value
        return 3.0 * g * math.cos(theta) / (2.0 * L)

    def _after_derivatives(self, theta, omega):
        """碰撞后状态方程及恒定摩擦耗散功率。

        碰撞前仍使用解析能量反解；摩擦只从碰撞瞬间开始计入，避免改变
        原有的碰撞前速度和瞬时冲量公式。
        """
        inertia = self.inertia()
        acceleration = self._post_acceleration(theta)
        acceleration += self.friction_torque(omega) / inertia
        dissipation_power = self.friction_moment() * abs(omega)
        return omega, acceleration, dissipation_power

    def _can_stick(self, theta, omega):
        """判断杆是否已进入静摩擦可维持的低速平衡。"""
        if self.friction_moment() <= self.EPS or abs(omega) > 2.0e-3:
            return False
        gravity_torque = abs(self.sliders["M"].value
                             * self.sliders["g"].value
                             * self.sliders["L"].value
                             * math.cos(theta) / 2.0)
        return gravity_torque <= self.friction_moment() + 1e-10

    def _advance_after_collision(self, dt):
        """用 RK4 推进碰撞后的 ``theta``、``omega`` 和耗散能。"""
        theta0, omega0, dissipated0 = self.theta, self.omega, self.damping_energy

        k1 = self._after_derivatives(theta0, omega0)
        k2 = self._after_derivatives(
            theta0 + 0.5 * dt * k1[0],
            omega0 + 0.5 * dt * k1[1],
        )
        k3 = self._after_derivatives(
            theta0 + 0.5 * dt * k2[0],
            omega0 + 0.5 * dt * k2[1],
        )
        k4 = self._after_derivatives(
            theta0 + dt * k3[0],
            omega0 + dt * k3[1],
        )

        self.theta = theta0 + dt * (
            k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]
        ) / 6.0
        self.omega = omega0 + dt * (
            k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]
        ) / 6.0
        self.damping_energy = dissipated0 + dt * (
            k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2]
        ) / 6.0
        if self._can_stick(self.theta, self.omega):
            # 把本子步内剩余的微小动能也计入摩擦账本，避免“钳零”凭空
            # 制造或删除能量；势能保持在当前位置。
            kinetic_before_lock = 0.5 * self.inertia() * self.omega ** 2
            self.damping_energy += kinetic_before_lock
            self.omega = 0.0

    def _advance_simulation_substep(self, sub):
        if self.phase == "swinging" and not self.collided:
            # 目标为零或初始状态已经竖直时，直接进入碰撞结算。
            if self.theta >= math.pi / 2.0 - self.EPS:
                self.theta = math.pi / 2.0
                self.omega = self.target_omega
                self.begin_collision(explain=False if self._fast_forwarding else None)
            else:
                self._advance_swing(sub)
                if self.theta >= math.pi / 2.0 - self.EPS:
                    self.theta = math.pi / 2.0
                    self.omega = self.target_omega
                    self.begin_collision(explain=False if self._fast_forwarding else None)
        elif self.phase == "after":
            self.ball_x += self.ball_v * sub
            self._advance_after_collision(sub)

        # 进入讲解阶段后，碰撞时刻就是当前时刻；不能把冻结期间的
        # 物理时间再额外推进一个子步。
        if self.phase != "impact_explain":
            self.t += sub

    def _update_explanation_camera(self):
        if self.impact_explainer is None:
            self.camera_zoom = 1.0
            return
        self.camera_zoom = 1.0 + 0.24 * self.impact_explainer.focus_strength()

    def step(self, dt):
        if self.replay_mode:
            self.replay_playback_step(dt)
            return

        if not self.running:
            return

        if self.phase == "impact_explain":
            completed = self.impact_explainer.update(dt)
            self._update_explanation_camera()
            self.step_particles(dt, gravity=self.sliders["g"].value)
            self.flash = max(0.0, self.flash - dt * 1.8)
            if completed:
                self.apply_collision_result(self.collision_snapshot, spawn_fx=False)
            return

        speed = self.sliders["anim_speed"].value
        sim_dt = dt * speed
        # 子步长不能超过物理积分上限；ceil 而不是 int，避免向下取整后
        # sim_dt/n 反而大于 MAX_SUBSTEP。
        n = max(1, math.ceil(sim_dt / self.MAX_SUBSTEP))
        sub = sim_dt / n

        for _ in range(n):
            self._advance_simulation_substep(sub)
            if self.phase == "impact_explain":
                break

        self.step_particles(dt, gravity=self.sliders["g"].value)
        self.flash = max(0.0, self.flash - sim_dt * 2.2)

        if not self.rod_trail or abs(self.rod_trail[-1] - self.theta) > 0.010:
            self.rod_trail.append(self.theta)
            if len(self.rod_trail) > 70:
                self.rod_trail.pop(0)
        self.ball_trail.append((self.ball_x, self.current_h()))
        if len(self.ball_trail) > 75:
            self.ball_trail.pop(0)
        self._record_replay_sample()

    def formula_lines(self):
        return (
            "I=ML^2/3，vc=h*wc，J=-(1+e)(v-hw)/(1/m+h^2/I)",
            "碰后：I*w' = MgL*cos(theta)/2 + tau_f，tau_f=-tau0*sign(w)；U=MgL(1-sin(theta))/2",
        )

    def formula_rect(self):
        return pygame.Rect(690, BOTTOM_FORMULA_Y, 528, BOTTOM_FORMULA_H)

    def summary_line(self):
        mode = "重力释放" if not self.uses_initial_speed else "90°+初始角速度"
        return (
            f"g={format_sig3(self.sliders['g'].value)}  "
            f"vc={format_sig3(self.target_collision_speed())}  "
            f"初始摆角={format_sig3(self.initial_angle_deg)}°  {mode}"
        )

    def draw_slider_value(self, key, slider):
        if key == "height_ratio":
            slider.draw(
                screen,
                f"h = {format_sig3(self.current_h())} m  ({format_sig3(slider.value)}L)"
            )
        else:
            slider.draw(screen)

    def draw_scene(self):
        m = self.sliders["m"].value
        L = self.sliders["L"].value
        h = self.current_h()
        I = self.inertia()
        rb = self.ball_radius_world()

        # 物理长度整体缩小为原版的 1/3，但画面中的视觉尺寸保持接近原版。
        physical_scale_ratio = 3.0
        equivalent_old_L = physical_scale_ratio * L
        old_scale = min(
            145.0,
            395.0 / equivalent_old_L,
            (SIM_H - 235) / (equivalent_old_L + 0.35),
        )
        scale = physical_scale_ratio * old_scale
        pivot = (565, 195)

        explainer = (
            self.impact_explainer
            if self.phase == "impact_explain" and not self.replay_mode
            else None
        )
        replay_frame = self.replay_frame()
        replay_active = replay_frame is not None
        display_collision = (
            self.replay_collision_snapshot(replay_frame)
            if replay_active
            else self.collision_snapshot
        )
        display_theta = (
            replay_frame.theta if replay_frame is not None else self.theta
        )
        display_ball_x = (
            replay_frame.ball_x if replay_frame is not None
            else explainer.ball_x_display() if explainer else self.ball_x
        )
        display_ball_v = (
            replay_frame.ball_v if replay_frame is not None
            else explainer.ball_v_display() if explainer else self.ball_v
        )
        display_omega = (
            replay_frame.omega if replay_frame is not None
            else explainer.rod_omega_display() if explainer else self.omega
        )
        display_contact_speed = (
            explainer.contact_speed_display()
            if explainer else h * display_omega
        )
        display_phase = replay_frame.phase if replay_active else self.phase
        display_collided = display_phase in {"after", "impact_explain"}
        display_friction_energy = (
            replay_frame.friction_energy if replay_active else self.damping_energy
        )
        if replay_active:
            display_account = {
                "initial": self.initial_energy,
                "mechanical": replay_frame.total_energy,
                "collision": (
                    display_collision.collision_energy_loss
                    if display_collision is not None and display_phase == "after"
                    else 0.0
                ),
                "damping": display_friction_energy,
                "residual": self.initial_energy - replay_frame.total_energy
                - (
                    display_collision.collision_energy_loss
                    if display_collision is not None and display_phase == "after"
                    else 0.0
                ) - display_friction_energy,
            }
        else:
            display_account = self.energy_breakdown()

        zoom = self.camera_zoom if explainer is not None else 1.0
        if zoom > 1.0 and self.camera_focus is not None:
            focus_x, focus_y = self.camera_focus
            focus_screen = (pivot[0], 315)

            def w2s(x, y):
                return (
                    int(focus_screen[0] + (x - focus_x) * scale * zoom),
                    int(focus_screen[1] + (y - focus_y) * scale * zoom),
                )
        else:

            def w2s(x, y):
                return int(pivot[0] + x * scale), int(pivot[1] + y * scale)

        scene_pivot = w2s(0.0, 0.0)

        screen.blit(STATIC_BG, (0, 0))
        display_state = {
            "ready": "待开始",
            "swinging": "碰撞前回放" if replay_active else (
                "杆摆下并准备碰撞" if not self.collided else "碰撞后物理摆"
            ),
            "impact_explain": "碰撞讲解（物理冻结）",
            "after": "碰撞后物理摆",
        }.get(display_phase, display_phase)
        self.draw_header(display_state,
                         display_time=replay_frame.time if replay_active else None)
        self.app.draw_mode_tabs()

        platform_y = h + rb
        sx1, sy = w2s(min(-1.5 * L, display_ball_x - 0.8 * L), platform_y)
        sx2, _ = w2s(1.25 * L, platform_y)
        sx1, sx2 = max(-80, sx1), min(WIDTH + 80, sx2)
        pygame.draw.line(screen, (22, 28, 48), (sx1, sy + 10), (sx2, sy + 10), 10)
        pygame.draw.line(screen, (35, 44, 70), (sx1, sy + 4), (sx2, sy + 4), 8)
        pygame.draw.line(screen, PLATFORM, (sx1, sy), (sx2, sy), 5)
        pygame.draw.line(screen, PLATFORM_TOP, (sx1, sy - 1), (sx2, sy - 1), 2)
        for tx in range(max(-40, sx1), min(WIDTH + 40, sx2), 18):
            pygame.draw.line(screen, (100, 115, 155), (tx, sy), (tx + 6, sy + 4), 1)

        # 竖直参考线和碰撞高度标记。
        ref_x, ref_y = w2s(0.0, L)
        for y in range(scene_pivot[1] + 4, ref_y, 12):
            pygame.draw.line(screen, (80, 105, 150), (scene_pivot[0], y),
                             (scene_pivot[0], min(y + 6, ref_y)), 1)
        hx, hy = w2s(-0.36 * L, h)
        pygame.draw.line(screen, (100, 120, 165), (hx, scene_pivot[1]), (hx, hy), 2)
        pygame.draw.line(screen, (100, 120, 165), (hx - 9, scene_pivot[1]), (hx + 9, scene_pivot[1]), 2)
        pygame.draw.line(screen, (100, 120, 165), (hx - 9, hy), (hx + 9, hy), 2)
        draw_text(screen, f"h={format_sig3(h)}m", (hx - 10, (scene_pivot[1] + hy) // 2),
                  FONT_SMALL, MUTED, anchor="midright")
        draw_text(screen, "竖直碰撞位置", (scene_pivot[0] + 12, ref_y - 20), FONT_SMALL, MUTED)

        # 摆角弧线以转轴为圆心，显示竖直向下方向与细杆之间的夹角。
        if not display_collided and 0.0 <= display_theta <= math.pi / 2.0:
            arc_radius = 66
            arc_rect = pygame.Rect(
                             scene_pivot[0] - arc_radius, scene_pivot[1] - arc_radius,
                2 * arc_radius, 2 * arc_radius,
            )
            pygame.draw.arc(screen, ACCENT_2, arc_rect,
                            math.pi + display_theta, 1.5 * math.pi, 2)
            bisector = 1.25 * math.pi + 0.5 * display_theta
            label_radius = arc_radius + 18
            label_pos = (
                scene_pivot[0] + int(label_radius * math.cos(bisector)),
                scene_pivot[1] - int(label_radius * math.sin(bisector)),
            )
            draw_text(
                screen,
                f"ψ={format_sig3(math.degrees(math.pi / 2 - display_theta))}°",
                label_pos, FONT_SMALL, ACCENT_2, anchor="center",
            )

        if replay_active:
            replay_history = [
                frame for frame in self.replay.frames
                if frame.time <= replay_frame.time + 1e-10
            ]
            display_rod_trail = [frame.theta for frame in replay_history]
            display_ball_trail = [
                (frame.ball_x, h) for frame in replay_history
            ]
            if (not display_rod_trail
                    or abs(display_rod_trail[-1] - display_theta) > 1e-10):
                display_rod_trail.append(display_theta)
            if (not display_ball_trail
                    or abs(display_ball_trail[-1][0] - display_ball_x) > 1e-10):
                display_ball_trail.append((display_ball_x, h))
        else:
            display_rod_trail = self.rod_trail
            display_ball_trail = self.ball_trail

        rod_w = max(5, int(0.028 * scale))
        if display_rod_trail:
            trail_surf_1.fill((0, 0, 0, 0))
            for i, theta in enumerate(display_rod_trail):
                p = i / max(1, len(display_rod_trail) - 1)
                end = w2s(-L * math.cos(theta), L * math.sin(theta))
                pygame.draw.line(trail_surf_1, (*ROD_GLOW, int(10 + 45 * p)), scene_pivot, end,
                                 max(2, int(rod_w * (0.35 + 0.65 * p))))
            screen.blit(trail_surf_1, (0, 0))

        end = w2s(-L * math.cos(display_theta), L * math.sin(display_theta))
        glow_surf.fill((0, 0, 0, 0))
        pygame.draw.line(glow_surf, (*ROD_GLOW, 35), scene_pivot, end, rod_w + 12)
        pygame.draw.line(glow_surf, (*ROD_GLOW, 60), scene_pivot, end, rod_w + 5)
        screen.blit(glow_surf, (0, 0))
        pygame.draw.line(screen, (0, 0, 0), (scene_pivot[0] + 5, scene_pivot[1] + 7),
                         (end[0] + 5, end[1] + 7), rod_w + 4)
        pygame.draw.line(screen, ROD_COLOR, scene_pivot, end, rod_w)
        pygame.draw.line(screen, ROD_EDGE, scene_pivot, end, max(2, rod_w // 4))
        pygame.draw.circle(screen, (160, 110, 30), end, rod_w // 2 + 3)
        pygame.draw.circle(screen, ROD_EDGE, end, max(3, rod_w // 4))

        px, py = scene_pivot
        pygame.draw.rect(screen, (38, 48, 76), (px - 24, py - 38, 14, 76), border_radius=5)
        pygame.draw.circle(screen, (5, 8, 18), (px + 3, py + 4), 26)
        pygame.draw.circle(screen, (50, 62, 95), scene_pivot, 24)
        pygame.draw.circle(screen, (28, 38, 64), scene_pivot, 20)
        pygame.draw.circle(screen, (65, 82, 128), scene_pivot, 16)
        pygame.draw.circle(screen, ACCENT, scene_pivot, 6)
        pygame.draw.circle(screen, (210, 240, 255), scene_pivot, 3)

        w_rect = pygame.Rect(px + 32, py - 30, 210, 34)
        rounded_rect(screen, w_rect, (12, 20, 38), 9, 1, (70, 95, 145))
        draw_text(screen, f"w = {format_sig3(display_omega)} rad/s", w_rect.center,
                  FONT_SMALL, ACCENT_3, anchor="center")

        cpx, cpy = w2s(-h * math.cos(display_theta), h * math.sin(display_theta))
        pygame.draw.circle(screen, ACCENT_2, (cpx, cpy), 9, 2)
        pygame.draw.circle(screen, (255, 255, 255), (cpx, cpy), 4)

        if explainer and explainer.phase in ("velocity", "momentum"):
            tangent_len = clamp(abs(display_contact_speed) * scale * 0.07, 18, 105)
            tangent_direction = 1 if display_contact_speed >= 0 else -1
            tangent_end = (cpx + int(tangent_direction * tangent_len), cpy)
            draw_arrow(screen, (cpx, cpy), tangent_end, ACCENT_2, 3)
            draw_text(screen, f"hω={format_sig3(display_contact_speed)} m/s",
                      (tangent_end[0] + (7 if tangent_direction > 0 else -7), cpy + 8),
                      FONT_SMALL, ACCENT_2,
                      anchor="topleft" if tangent_direction > 0 else "topright")

        if explainer and explainer.phase == "momentum":
            impulse = explainer.impulse_display()
            impulse_len = clamp(abs(impulse) * scale * 0.11, 8, 135)
            impulse_direction = 1 if impulse >= 0 else -1
            impulse_end = (cpx + int(impulse_direction * impulse_len), cpy)
            draw_arrow(screen, (cpx, cpy), impulse_end, ACCENT_2, 4)
            draw_text(screen, f"J={format_sig3(impulse)} N*s",
                      (impulse_end[0] + (8 if impulse_direction > 0 else -8), cpy - 18),
                      FONT_SMALL, ACCENT_2,
                      anchor="topleft" if impulse_direction > 0 else "topright")

        if explainer and explainer.phase == "energy":
            loss_ratio = clamp(
                explainer.energy_parts_display()["loss"]
                / max(explainer.snapshot.ke_before, 1e-9),
                0.0,
                1.0,
            )
            heat_radius = int(12 + 42 * loss_ratio * explainer.energy_progress)
            if heat_radius > 12:
                flash_surf.fill((0, 0, 0, 0))
                pygame.draw.circle(flash_surf, (255, 90, 45, 55), (cpx, cpy), heat_radius)
                pygame.draw.circle(flash_surf, (255, 210, 80, 100),
                                   (cpx, cpy), max(5, heat_radius // 3))
                screen.blit(flash_surf, (0, 0))

        # 重力方向示意箭头。
        gx, gy = w2s(-0.5 * L * math.cos(display_theta),
                     0.5 * L * math.sin(display_theta))
        draw_arrow(screen, (gx, gy), (gx, gy + int(0.20 * scale)), ACCENT_3, 2)

        if display_ball_trail:
            trail_surf_2.fill((0, 0, 0, 0))
            for i, (bx, by) in enumerate(display_ball_trail):
                p = i / max(1, len(display_ball_trail) - 1)
                pos = w2s(bx, by)
                if -100 <= pos[0] <= WIDTH + 100:
                    r = max(2, int(rb * scale * (0.22 + 0.40 * p)))
                    pygame.draw.circle(trail_surf_2, (*BALL1_GLOW, int(12 + 75 * p)), pos, r + 3)
            screen.blit(trail_surf_2, (0, 0))

        if not replay_active and (self.particles or self.shockwaves):
            particle_surf.fill((0, 0, 0, 0))
            for particle in self.particles:
                particle.draw(particle_surf, w2s, streak_scale=scale * 0.08)
            for wave in self.shockwaves:
                wave.draw(particle_surf, w2s, scale)
            screen.blit(particle_surf, (0, 0))

        ball_pos = w2s(display_ball_x, h)
        br = max(12, int(rb * scale))
        pygame.draw.ellipse(screen, (0, 0, 0),
                            (ball_pos[0] - br - 4, sy - max(3, br // 4),
                             2 * br + 8, max(6, br // 2)))
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
                           (ball_pos[0] - br // 3 - 1, ball_pos[1] - br // 3 - 1),
                           max(2, br // 7))

        if not replay_active and self.flash > 0:
            contact = w2s(0.0, h)
            flash_surf.fill((0, 0, 0, 0))
            f = self.flash
            r0 = int(clamp((1.15 - f) * 80 + 10, 5, 90))
            a0 = int(220 * f)
            pygame.draw.circle(flash_surf, (255, 255, 255, a0), contact, r0)
            pygame.draw.circle(flash_surf, (255, 210, 80, int(a0 * 0.45)),
                               contact, r0 + int(30 * f))
            pygame.draw.circle(flash_surf, (120, 180, 255, int(a0 * 0.20)),
                               contact, r0 + int(55 * f))
            screen.blit(flash_surf, (0, 0))

        if replay_active and display_collision is not None:
            draw_impact_fx(
                screen, (cpx, cpy), replay_frame.impact_flash,
                replay_frame.impact_strength,
            )

        if abs(display_ball_v) > 0.01:
            arrow_len = clamp(abs(display_ball_v) * scale * 0.07, 35, 150)
            direction = 1 if display_ball_v > 0 else -1
            ay = ball_pos[1] - br - 12
            finish = (int(ball_pos[0] + direction * arrow_len), ay)
            draw_arrow(screen, (ball_pos[0], ay), finish, GREEN, 3)
            draw_text(screen, f"v={format_sig3(display_ball_v)} m/s",
                      (finish[0] + (10 if direction > 0 else -10), ay - 12), FONT_SMALL,
                      GREEN, anchor="topleft" if direction > 0 else "topright")
        elif not display_collided:
            draw_text(screen, "小球静止等待碰撞", (245, 205), FONT_SMALL, ACCENT_3)

        if self.notice and not replay_active:
            notice_rect = pygame.Rect(38, 192, 730, 40)
            rounded_rect(screen, notice_rect, (62, 28, 38), 10, 1, (145, 65, 80))
            draw_text(screen, self.notice, notice_rect.center,
                      FONT_SMALL, (255, 185, 190), anchor="center")

        if not replay_active and self.phase == "impact_explain" and self.impact_explainer is not None:
            self.impact_explainer.draw(screen, pygame.Rect(38, 376, 730, 228))

        if (not replay_active and self.phase == "after") or (
                replay_active and display_phase == "after"):
            draw_energy_flow(screen, pygame.Rect(38, 244, 730, 126),
                             display_account)

        if explainer:
            rod_L_now = explainer.rod_L_display()
            ball_MRV_now = explainer.ball_MRV_display()
            display_parts = explainer.energy_parts_display()
            display_mechanical_energy = (
                display_parts["rod"] + display_parts["ball"]
                + self.collision_snapshot.potential
            )
        elif replay_active:
            ball_MRV_now = m * h * display_ball_v
            rod_L_now = replay_frame.angular_momentum - ball_MRV_now
            display_mechanical_energy = replay_frame.total_energy
        else:
            rod_L_now = I * self.omega
            ball_MRV_now = m * h * self.ball_v
            display_mechanical_energy = self.total_mechanical_energy()
        total_L_now = rod_L_now + ball_MRV_now
        display_point_speed = display_contact_speed
        current_lines = [
            f"重力加速度 g = {format_sig3(self.sliders['g'].value)} m/s^2",
            f"转动惯量 I = {format_sig3(I)} kg*m^2",
            f"摆角 ψ = {format_sig3(math.degrees(math.pi / 2 - display_theta))}°",
            f"杆角速度 w = {format_sig3(display_omega)} rad/s",
            f"碰撞点速率 h*w = {format_sig3(display_point_speed)} m/s",
            f"机械能 E = {format_sig3(display_mechanical_energy)} J",
            f"摩擦耗散 Wf = {format_sig3(display_friction_energy)} J",
            f"总角动量 = {format_sig3(total_L_now)} kg*m^2/s",
        ]
        collision_lines = None
        result = display_collision if replay_active else self.last_result
        if result:
            r = result
            collision_lines = [
                f"目标碰撞点速率 = {format_sig3(self.target_collision_speed())} m/s",
                f"碰撞时刻 t = {format_sig3(r['impact_time'])} s",
                f"恢复系数 e = {format_sig3(r['e'])}",
                f"碰前杆角动量 = {format_sig3(r['rod_L_before'])}",
                f"碰前小球 MRV = {format_sig3(r['ball_MRV_before'])}",
                f"碰前总角动量 = {format_sig3(r['total_L_before'])}",
                f"碰后杆角动量 = {format_sig3(r['rod_L_after'])}",
                f"碰后小球 MRV = {format_sig3(r['ball_MRV_after'])}",
                f"碰后总角动量 = {format_sig3(r['total_L_after'])}",
                f"角动量误差 = {format_sig3(abs(r['total_L_after'] - r['total_L_before']))}",
                f"均匀细杆打击中心 2L/3 = {format_sig3(self.percussion_center())} m",
                f"转轴外冲量 = {format_sig3(r['pivot_impulse'])} N*s（h=2L/3 时为零）",
                f"能量误差 = {format_sig3(abs(r['energy_after'] - r['energy_before']))} J",
            ]
        self.draw_info_panel(
            current_lines, collision_lines,
            [
                "小球静止于杆的碰撞高度，vc 是杆碰撞点线速度",
                "ψ 从竖直向下方向量起，0°--90° 可由重力释放",
                "超出范围时自动使用 90° 摆角和初始角速度",
                "势能零点在杆竖直向下；恒定摩擦矩 tau_f=-tau0*sign(w)",
            ],
            ("目标碰撞点速率", "恢复系数", "碰后总角动量", "角动量误差", "能量误差")
        )

"""重力场中质点与定轴细杆碰撞的物理模型和场景绘制。"""

from __future__ import annotations

import theme

import math
from dataclasses import dataclass

import pygame

from config import (ACCENT, ACCENT_2, ACCENT_3, BALL1_COLOR, BALL1_EDGE,
                    BALL1_GLOW, GREEN, MUTED, PLATFORM, PLATFORM_TOP,
                    ROD_COLOR, ROD_EDGE, ROD_GLOW, TEXT, LAYOUT)
from core import display
from core.fonts import FONT_BIG, FONT_SMALL, FONT_TINY
from effects.particles import spawn_impact_particles
from models.base import BaseModel
from models.collision_data import ConservationState, CollisionSnapshot
from presentation.collision_explainer import CollisionExplainer
from presentation.impact_motion import draw_scene_explanation, fitted_camera, flow_dots
from replay.timeline import ReplayFrame, ReplayTimeline
from render.energy import EnergyState
from render.primitives import (draw_arrow, draw_matte_ball, draw_soft_shadow,
                               draw_text, rounded_rect)
from render.text import clipped
from render.energy.energy_renderer import draw_energy_flow, draw_energy_ledger
from render.replay_fx import draw_friction_heat_fx, draw_impact_fx
from ui.widgets import InputBox
from utils import clamp, format_sig3


@dataclass
class TrailPoint:
    """杆残影的展示快照；年龄而不是列表位置决定透明度。"""

    theta: float
    age: float = 0.0


class BallHitsRod(BaseModel):
    """小球水平入射并撞击初始静止的定轴细杆。

    ``theta`` 的定义沿用原模型：杆端坐标为
    ``(-L*cos(theta), L*sin(theta))``，所以 ``theta=pi/2`` 是竖直向下，
    ``theta=0`` 是水平向左。UI 中的 ``initial_angle_deg`` 则是相对于竖直
    向下方向的摆角。碰撞前细杆固定在 ``theta=pi/2``，小球从左侧向右
    运动；碰撞后小球与杆按冲量结果继续运动。
    """

    name = "质点‑定轴细杆碰撞仿真"
    short_name = "质点‑定轴细杆"
    EPS = 1e-12
    MAX_SUBSTEP = 0.0025
    TRAIL_LIFETIME = 0.8
    TRAIL_SPEED_THRESHOLD = 0.03
    control_row_height = 34
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
        # 保留内部键 omega_c，以兼容旧存档；它现在表示小球入射速率 u。
        self.add_control("omega_c", "小球入射速率 u", 0, 2, 0.00, 20.00, 4.00, " m/s", 3)
        self.add_control("g", "重力加速度 g", 0, 3, 0.00, 25.0, 9.80, " m/s^2", 3)

        self.add_control("L", "杆长 L", 1, 0, 0.00, 0.50, 0.50, " m", 3)
        self.add_control("height_ratio", "碰撞高度 h/L", 1, 1, 0.00, 1.00, 0.72, "", 4)
        self.add_control("anim_speed", "动画速度", 1, 2, 0.20, 2.50, 1.00, "x", 2)
        self.add_control("e", "恢复系数 e", 1, 3, 0.00, 1.00, 1.00, "", 3)
        self.add_control("tau0", "恒定摩擦矩 τ0", 0, 4, 0.00, 0.500, 0.000, " N*m", 4)

        # 慢放讲解开关：仅质点—细杆模型提供，控制碰撞瞬间是否冻结并慢放讲解。
        self.add_toggle("explain", "慢放讲解", 1, 4, False)

        # h 仍然保留精确输入，但滑块用 h/L 表示，便于同时调整 L 和碰撞位置。
        self.input_boxes.pop("height_ratio")
        self.input_boxes["h"] = InputBox(
            "h", "精确输入", 0, 0, 84, self.current_h(), "m"
        )

    def current_h(self):
        return self.sliders["height_ratio"].value * self.sliders["L"].value

    def input_values(self):
        return {
            "m": self.sliders["m"].value,
            "M": self.sliders["M"].value,
            "u": self.sliders["omega_c"].value,
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
        if key in {"vc", "u"}:
            # vc/omega_c 是旧版本键名；新模型统一把该控件解释为小球
            # 入射速率的大小。
            key = "omega_c"
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
        rod_kinetic = 0.5 * self.inertia() * omega * omega
        ball_kinetic = 0.5 * self.sliders["m"].value * ball_v * ball_v
        rod_energy = rod_kinetic + potential
        total_energy = rod_energy + ball_kinetic
        rod_angular_momentum = self.inertia() * omega
        ball_angular_momentum = self.sliders["m"].value * self.current_h() * ball_v
        angular_momentum = rod_angular_momentum + ball_angular_momentum
        collision_loss = 0.0
        if phase == "after":
            collision_loss = (
                collision.collision_energy_loss
                if collision is not None
                else self.collision_energy_loss
            )
        energy_residual = (
            self.initial_energy - total_energy - collision_loss - self.damping_energy
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
            rod_kinetic_energy=rod_kinetic,
            ball_kinetic_energy=ball_kinetic,
            potential_energy=potential,
            collision_energy_loss=collision_loss,
            friction_energy=self.damping_energy,
            energy_residual=energy_residual,
            rod_angular_momentum=rod_angular_momentum,
            ball_angular_momentum=ball_angular_momentum,
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

    def target_angular_speed(self):
        """碰撞前细杆静止；保留此方法供旧调用方使用。"""
        return 0.0

    def target_collision_speed(self):
        """碰撞前杆上碰撞点静止。"""
        return 0.0

    def target_ball_speed(self):
        """小球碰撞前的入射速率，单位 m/s。"""
        return self.sliders["omega_c"].value

    def compute_launch_state(self):
        """返回小球入射前的初始状态；细杆始终从静止竖直位置开始。"""
        theta_start = math.pi / 2.0
        return {
            "theta_start": theta_start,
            "omega_start": 0.0,
            "target_omega": 0.0,
            "angle_from_vertical": 0.0,
            "angle_deg": 0.0,
            "uses_initial_speed": False,
            "gravity_omega_max": 0.0,
            "h_valid": (self.current_h() > self.EPS
                        and self.sliders["L"].value > self.EPS),
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
        rod_kinetic = 0.5 * self.inertia() * self.omega * self.omega
        ball_kinetic = 0.5 * self.sliders["m"].value * self.ball_v * self.ball_v
        potential = self.gravity_potential()
        return EnergyState(
            initial=initial,
            mechanical=mechanical,
            rod_kinetic=rod_kinetic,
            ball_kinetic=ball_kinetic,
            potential=potential,
            collision_loss=collision,
            friction_heat=damping,
            residual=residual,
        )

    def conservation_report(self):
        """返回最近一次碰撞的角动量守恒与能量耗散报告。"""
        if self.last_result is None:
            return None
        return self.last_result.conservation_report()

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
        # 小球从杆左侧向右入射；ball_x=0 表示球面与杆相切的碰撞位置。
        self.ball_x = -max(0.15, 0.80 * self.sliders["L"].value)
        self.ball_v = self.target_ball_speed()
        self.initial_energy = self.total_mechanical_energy()
        self.t = 0.0
        self.collided = False
        self.damping_energy = 0.0
        self.collision_energy_loss = 0.0

        self.flash = 0.0
        self.last_result = None
        self.collision_snapshot = None
        self.impact_explainer = None
        if not hasattr(self, "explain_enabled"):
            self.explain_enabled = False
        self.camera_zoom = 1.0
        self.camera_focus = None
        self.rod_trail: list[TrailPoint] = []
        self.ball_trail = [(self.ball_x, self.current_h())]
        self.particles.clear()
        self.shockwaves.clear()
        self.notice = ""
        self._record_replay_sample(force=True)
        if self.sliders["L"].value <= self.EPS:
            self.notice = "杆长 L=0，仅用于比例尺端点；请将 L 调大后开始仿真。"
        elif self.current_h() <= self.EPS:
            self.notice = "碰撞高度 h=0，碰撞点位于转轴，无法发生有效转动碰撞。"

    def start_pause(self):
        if self.replay_mode:
            self.toggle_replay()
            return
        if self.phase == "impact_explain":
            self.skip_explanation()
            return
        if self.phase == "ready":
            if self.sliders["L"].value <= self.EPS or self.current_h() <= self.EPS:
                return
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
        if self.sliders["L"].value <= self.EPS or self.current_h() <= self.EPS:
            self.running = False
            self.notice = "请将杆长 L 和碰撞高度 h 设置为大于 0。"
            return
        self.phase = "swinging"
        self.running = True
        self._fast_forwarding = True
        try:
            guard_time = 0.0
            while not self.collided and self.running and guard_time < 120.0:
                self._advance_simulation_substep(self.MAX_SUBSTEP)
                guard_time += self.MAX_SUBSTEP
        finally:
            self._fast_forwarding = False
        if not self.collided and not self.notice:
            self.running = False
            self.notice = "C 键快进在 120 s 内未到达碰撞位置，请检查参数。"

    def do_collision(self):
        """兼容旧调用方：立即计算并提交碰撞结果。"""
        self.begin_collision(explain=False)

    def begin_collision(self, explain=None):
        """创建碰撞快照，并按设置进入讲解冻结阶段或直接提交。"""
        if explain is None:
            explain = self.explain_enabled
        if self.app is not None:
            self.app.sound.play("impact")
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
        if not self.explain_enabled:
            self.skip_explanation()
        if "explain" in self.toggles:
            self.toggles["explain"].value = self.explain_enabled
        state = "开启" if self.explain_enabled else "关闭"
        self.notice = f"慢放讲解已{state}（E 切换）"
        return self.explain_enabled

    def on_toggle_changed(self, key, value):
        if key == "explain":
            self.explain_enabled = bool(value)
            if not value:
                self.skip_explanation()
            state = "开启" if value else "关闭"
            self.notice = f"慢放讲解已{state}（面板开关）"

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
        if I <= self.EPS or h <= self.EPS:
            raise ValueError("杆长 L 和碰撞高度 h 必须大于 0")
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

        conservation_before = ConservationState(
            angular_momentum=total_L_before,
            mechanical_energy=ke_before + potential,
            rod_angular_momentum=rod_L_before,
            ball_angular_momentum=ball_MRV_before,
            ball_linear_momentum=m * u_before,
            system_linear_momentum=system_p_before,
            rod_kinetic_energy=rod_ke_before,
            ball_kinetic_energy=ball_ke_before,
            potential_energy=potential,
        )
        conservation_after = ConservationState(
            angular_momentum=total_L_after,
            mechanical_energy=ke_after + potential,
            rod_angular_momentum=rod_L_after,
            ball_angular_momentum=ball_MRV_after,
            ball_linear_momentum=m * v_after,
            system_linear_momentum=system_p_after,
            rod_kinetic_energy=rod_ke_after,
            ball_kinetic_energy=ball_ke_after,
            potential_energy=potential,
        )

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
            conservation_before=conservation_before,
            conservation_after=conservation_after,
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
        return self._static_friction_holds(theta)

    def _static_friction_holds(self, theta):
        """静止时，转轴摩擦是否足以平衡当前位置的重力矩。"""
        gravity_torque = abs(self.sliders["M"].value
                             * self.sliders["g"].value
                             * self.sliders["L"].value
                             * math.cos(theta) / 2.0)
        return gravity_torque <= self.friction_moment() + 1e-10

    def _advance_after_collision(self, dt):
        """用 RK4 推进碰后运动，并在过零时切换到静摩擦。

        库仑摩擦在 ``omega=0`` 处不连续，直接把耗散功率也交给 RK4
        会在过零子步重复计算摩擦功。这里用过零事件决定是否锁止，再用
        杆机械能的实际下降量登记摩擦耗散，使能量账本严格闭合。
        """
        theta0, omega0 = self.theta, self.omega

        # 已经静止且重力矩不足以克服最大静摩擦时，状态必须保持不变，
        # 不能在后续子步中出现数值抖动。
        if self._can_stick(theta0, omega0):
            # 第一次进入该分支时 omega 可能仍在静止判据的微小阈值内；
            # 将被钳除的剩余动能完整记入摩擦耗散。
            if abs(omega0) > self.EPS:
                self.damping_energy += 0.5 * self.inertia() * omega0 * omega0
            self.omega = 0.0
            return

        mechanical0 = self.mechanical_energy(theta0, omega0)

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

        theta1 = theta0 + dt * (
            k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]
        ) / 6.0
        omega1 = omega0 + dt * (
            k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]
        ) / 6.0

        # 若本子步跨过零速，估计真实停点；只有该处重力矩能被静摩擦
        # 平衡时才锁止，否则允许杆越过转折点继续运动。
        crossed_zero = abs(omega0) > self.EPS and omega0 * omega1 <= 0.0
        if crossed_zero:
            fraction = abs(omega0) / max(abs(omega0) + abs(omega1), self.EPS)
            theta_stop = theta0 + fraction * (theta1 - theta0)
            if self._static_friction_holds(theta_stop):
                theta1 = theta_stop
                omega1 = 0.0

        self.theta = theta1
        self.omega = omega1
        if self.friction_moment() > self.EPS:
            mechanical1 = self.mechanical_energy(theta1, omega1)
            # 使用带符号差值，抵消 RK4 在非锁止转折点可能产生的微小
            # 数值能量回升；从碰撞后状态到当前状态的累计值因此始终与
            # 机械能下降严格一致。
            self.damping_energy += mechanical0 - mechanical1

    def _advance_simulation_substep(self, sub):
        if self.phase == "swinging" and not self.collided:
            # 杆保持静止，由小球真实平移到碰撞位置。
            if self.ball_v <= self.EPS:
                self.running = False
                self.notice = "小球入射速率为 0，无法到达杆。"
            elif self.ball_x + self.ball_v * sub >= 0.0:
                time_to_impact = -self.ball_x / self.ball_v
                self.ball_x = 0.0
                self.t += time_to_impact
                self.begin_collision(explain=False if self._fast_forwarding else None)
                sub -= time_to_impact
                if sub > self.EPS and self.phase == "after":
                    self.ball_x += self.ball_v * sub
                    self._advance_after_collision(sub)
                    self.t += sub
                return
            else:
                self.ball_x += self.ball_v * sub
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

    def _update_rod_trail(self, dt):
        """按真实展示时间推进残影，并在杆运动时写入新点。"""
        dt = max(0.0, float(dt))
        for point in self.rod_trail:
            point.age += dt
        self.rod_trail = [
            point for point in self.rod_trail
            if point.age < self.TRAIL_LIFETIME - 1e-9
        ]

        if (self.running and self.phase in {"swinging", "after"}
                and abs(self.omega) > self.TRAIL_SPEED_THRESHOLD):
            self.rod_trail.append(TrailPoint(self.theta))

    def step(self, dt):
        if self.replay_mode:
            self.replay_playback_step(dt)
            return

        if not self.running:
            self._update_rod_trail(dt)
            return

        if self.phase == "impact_explain":
            completed = self.impact_explainer.update(dt)
            self._update_explanation_camera()
            self.step_particles(dt, gravity=self.sliders["g"].value)
            self.flash = max(0.0, self.flash - dt * 1.8)
            self._update_rod_trail(dt)
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
        self._update_rod_trail(dt)
        self.ball_trail.append((self.ball_x, self.current_h()))
        if len(self.ball_trail) > 75:
            self.ball_trail.pop(0)
        self._record_replay_sample()

    def formula_lines(self):
        return (
            "I=ML^2/3，碰前 w=0，J=-(1+e)(u-hw)/(1/m+h^2/I)",
            "碰后：I*w' = MgL*cos(theta)/2 + tau_f，tau_f=-tau0*sign(w)；U=MgL(1-sin(theta))/2",
        )

    def formula_rect(self):
        return pygame.Rect(LAYOUT.formula)

    def interface_state(self):
        replay_frame = self.replay_frame()
        display_phase = replay_frame.phase if replay_frame is not None else self.phase
        state = {
            "ready": "待开始",
            "swinging": "碰撞前回放" if replay_frame is not None else (
                "小球入射并准备撞杆" if not self.collided else "碰撞后物理摆"
            ),
            "impact_explain": "碰撞讲解（物理冻结）",
            "after": "碰撞后物理摆",
        }.get(display_phase, display_phase)
        return state, replay_frame.time if replay_frame is not None else self.t

    def summary_line(self):
        return (
            f"g={format_sig3(self.sliders['g'].value)}  "
            f"小球入射速率={format_sig3(self.target_ball_speed())} m/s  "
            "杆初始静止"
        )

    def draw_slider_value(self, key, slider):
        if key == "height_ratio":
            slider.draw(
                display.screen,
                f"h = {format_sig3(self.current_h())} m  ({format_sig3(slider.value)}L)",
                show_value=False,
                show_label=False,
            )
        else:
            slider.draw(display.screen, show_value=False, show_label=False)

    def draw_scene(self):
        with clipped(display.screen, pygame.Rect(LAYOUT.scene)):
            self._draw_scene_contents()

    def scene_camera(self, explainer=None):
        """Frame pivot, complete rod, ball and labels throughout the zoom."""
        L = self.sliders["L"].value
        display_L = max(L, 0.01)
        h = self.current_h()
        rb = self.ball_radius_world()
        physical_scale_ratio = 3.0
        equivalent_old_L = physical_scale_ratio * display_L
        old_scale = min(
            145.0,
            395.0 / equivalent_old_L,
            (LAYOUT.scene_h - 82) / (equivalent_old_L + 0.35),
        )
        scale = physical_scale_ratio * old_scale
        pivot = (LAYOUT.scene_x + int(LAYOUT.scene_w * 0.63), LAYOUT.scene_y + int(LAYOUT.scene_h * 0.30))
        scale = min(scale, max(1.0, (LAYOUT.scene_y + LAYOUT.scene_h - pivot[1] - 30) / display_L))
        zoom = 1.0 + .24 * explainer.focus_strength() if explainer else 1.0
        return fitted_camera(LAYOUT.scene, pivot, scale, (0.0, h),
                             (-max(1.15 * L, .22 + 2 * rb), 0.0, .38 * L, L), zoom,
                             (36, 48, 230, 30))

    def _draw_scene_contents(self):
        m = self.sliders["m"].value
        L = self.sliders["L"].value
        h = self.current_h()
        I = self.inertia()
        rb = self.ball_radius_world()

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
            display_account = EnergyState(
                initial=self.initial_energy,
                mechanical=replay_frame.total_energy,
                rod_kinetic=replay_frame.rod_kinetic_energy,
                ball_kinetic=replay_frame.ball_kinetic_energy,
                potential=replay_frame.potential_energy,
                collision_loss=replay_frame.collision_energy_loss,
                friction_heat=display_friction_energy,
                residual=replay_frame.energy_residual,
            )
        else:
            display_account = self.energy_breakdown()
        if explainer:
            parts = explainer.energy_parts_display()
            potential = explainer.snapshot.potential
            mechanical = parts['rod'] + parts['ball'] + potential
            display_account = EnergyState(
                initial=parts['total'] + potential, mechanical=mechanical,
                rod_kinetic=parts['rod'], ball_kinetic=parts['ball'],
                potential=potential, collision_loss=parts['loss'],
                residual=parts['total'] + potential - mechanical - parts['loss'])

        camera = self.scene_camera(explainer)
        scale = camera.scale
        w2s = camera.point

        scene_pivot = w2s(0.0, 0.0)

        display.screen.blit(display.STATIC_BG, (0, 0))
        display_state = {
            "ready": "待开始",
            "swinging": "碰撞前回放" if replay_active else (
                "小球入射并准备撞杆" if not self.collided else "碰撞后物理摆"
            ),
            "impact_explain": "碰撞讲解（物理冻结）",
            "after": "碰撞后物理摆",
        }.get(display_phase, display_phase)
        platform_y = h + rb
        sx1, sy = w2s(min(-1.5 * L, display_ball_x - 0.8 * L), platform_y)
        sx2, _ = w2s(1.25 * L, platform_y)
        sx1, sx2 = max(-80, sx1), min(LAYOUT.width + 80, sx2)
        pygame.draw.line(display.screen, theme.color((23, 31, 29)), (sx1, sy + 10), (sx2, sy + 10), 10)
        pygame.draw.line(display.screen, theme.color((33, 45, 43)), (sx1, sy + 4), (sx2, sy + 4), 8)
        pygame.draw.line(display.screen, theme.PLATFORM, (sx1, sy), (sx2, sy), 5)
        pygame.draw.line(display.screen, theme.PLATFORM_TOP, (sx1, sy - 1), (sx2, sy - 1), 2)
        for tx in range(max(-40, sx1), min(LAYOUT.width + 40, sx2), 18):
            pygame.draw.line(display.screen, theme.color((74, 100, 96)), (tx, sy), (tx + 6, sy + 4), 1)

        # 竖直参考线和碰撞高度标记。
        ref_x, ref_y = w2s(0.0, L)
        for y in range(scene_pivot[1] + 4, ref_y, 12):
            pygame.draw.line(display.screen, theme.color((72, 97, 93)), (scene_pivot[0], y),
                             (scene_pivot[0], min(y + 6, ref_y)), 1)
        hx, hy = w2s(-0.36 * L, h)
        pygame.draw.line(display.screen, theme.color((79, 107, 102)), (hx, scene_pivot[1]), (hx, hy), 2)
        pygame.draw.line(display.screen, theme.color((79, 107, 102)), (hx - 9, scene_pivot[1]), (hx + 9, scene_pivot[1]), 2)
        pygame.draw.line(display.screen, theme.color((79, 107, 102)), (hx - 9, hy), (hx + 9, hy), 2)
        draw_text(display.screen, f"h={format_sig3(h)}m", (hx - 10, (scene_pivot[1] + hy) // 2),
                  FONT_SMALL, theme.MUTED, anchor="midright")
        draw_text(display.screen, "竖直碰撞位置", (scene_pivot[0] + 12, ref_y - 20), FONT_SMALL, theme.MUTED)

        # 摆角弧线以转轴为圆心，显示竖直向下方向与细杆之间的夹角。
        if not display_collided and 0.0 <= display_theta <= math.pi / 2.0:
            arc_radius = 66
            arc_rect = pygame.Rect(
                             scene_pivot[0] - arc_radius, scene_pivot[1] - arc_radius,
                2 * arc_radius, 2 * arc_radius,
            )
            pygame.draw.arc(display.screen, theme.ACCENT_2, arc_rect,
                            math.pi + display_theta, 1.5 * math.pi, 2)
            bisector = 1.25 * math.pi + 0.5 * display_theta
            label_radius = arc_radius + 18
            label_pos = (
                scene_pivot[0] + int(label_radius * math.cos(bisector)),
                scene_pivot[1] - int(label_radius * math.sin(bisector)),
            )
            draw_text(
                display.screen,
                f"ψ={format_sig3(math.degrees(math.pi / 2 - display_theta))}°",
                label_pos, FONT_SMALL, theme.ACCENT_2, anchor="center",
            )

        if replay_active:
            replay_history = self.replay.trail_frames(
                replay_frame.time,
                self.TRAIL_LIFETIME,
                self.TRAIL_SPEED_THRESHOLD,
            )
            display_rod_trail = [
                TrailPoint(frame.theta,
                           max(0.0, replay_frame.time - frame.time))
                for frame in replay_history
            ]
            display_ball_trail = [
                (frame.ball_x, h) for frame in replay_history
            ]
            if abs(display_omega) > self.TRAIL_SPEED_THRESHOLD:
                display_rod_trail.append(TrailPoint(display_theta, 0.0))
            if (not display_ball_trail
                    or abs(display_ball_trail[-1][0] - display_ball_x) > 1e-10):
                display_ball_trail.append((display_ball_x, h))
        else:
            display_rod_trail = self.rod_trail
            display_ball_trail = self.ball_trail

        rod_w = max(3, int(0.017 * scale))
        if display_rod_trail:
            display.trail_surf_1.fill((0, 0, 0, 0))
            for point in display_rod_trail:
                life = clamp(1.0 - point.age / self.TRAIL_LIFETIME, 0.0, 1.0)
                if life <= 0.0:
                    continue
                end = w2s(-L * math.cos(point.theta), L * math.sin(point.theta))
                alpha = int(35.0 * life)
                pygame.draw.line(
                    display.trail_surf_1, (*theme.ROD_GLOW, alpha), scene_pivot, end,
                    max(2, int(rod_w * (0.35 + 0.65 * life))),
                )
            display.screen.blit(display.trail_surf_1, (0, 0))

        end = w2s(-L * math.cos(display_theta), L * math.sin(display_theta))
        display.glow_surf.fill((0, 0, 0, 0))
        pygame.draw.line(display.glow_surf, (3, 9, 8, 68),
                         (scene_pivot[0] + 5, scene_pivot[1] + 7),
                         (end[0] + 5, end[1] + 7), rod_w + 5)
        pygame.draw.line(display.glow_surf, (*theme.ROD_GLOW, 10), scene_pivot, end, rod_w + 12)
        pygame.draw.line(display.glow_surf, (*theme.ROD_GLOW, 16), scene_pivot, end, rod_w + 5)
        display.screen.blit(display.glow_surf, (0, 0))
        pygame.draw.line(display.screen, theme.ROD_COLOR, scene_pivot, end, rod_w)
        pygame.draw.line(display.screen, theme.ROD_EDGE, scene_pivot, end, max(2, rod_w // 4))
        pygame.draw.circle(display.screen, theme.color((160, 110, 30)), end, rod_w // 2 + 3)
        pygame.draw.circle(display.screen, theme.ROD_EDGE, end, max(3, rod_w // 4))

        px, py = scene_pivot
        pygame.draw.rect(display.screen, theme.color((36, 49, 47)), (px - 24, py - 38, 14, 76), border_radius=5)
        pygame.draw.circle(display.screen, (8, 11, 11), (px + 3, py + 4), 26)
        pygame.draw.circle(display.screen, theme.color((45, 61, 58)), scene_pivot, 24)
        pygame.draw.circle(display.screen, theme.color((30, 41, 39)), scene_pivot, 20)
        pygame.draw.circle(display.screen, theme.color((61, 83, 79)), scene_pivot, 16)
        pygame.draw.circle(display.screen, theme.ACCENT, scene_pivot, 6)
        pygame.draw.circle(display.screen, theme.color((210, 240, 255)), scene_pivot, 3)

        w_rect = pygame.Rect(px + 32, py - 30, 210, 34)
        rounded_rect(display.screen, w_rect, theme.PANEL_2, 9, 1, theme.INPUT_BORDER)
        draw_text(display.screen, f"w = {format_sig3(display_omega)} rad/s", w_rect.center,
                  FONT_SMALL, theme.ACCENT_3, anchor="center")

        cpx, cpy = w2s(-h * math.cos(display_theta), h * math.sin(display_theta))
        pygame.draw.circle(display.screen, theme.ACCENT_2, (cpx, cpy), 9, 2)
        pygame.draw.circle(display.screen, theme.color((255, 255, 255)), (cpx, cpy), 4)

        if explainer and explainer.phase == "velocity":
            tangent_len = clamp(abs(display_contact_speed) * scale * 0.07, 0, 105)
            tangent_direction = 1 if display_contact_speed >= 0 else -1
            tangent_end = (cpx + int(tangent_direction * tangent_len), cpy)
            draw_arrow(
                display.screen, (cpx, cpy), tangent_end, theme.ACCENT_2, 3,
                head_size=min(12, tangent_len * 0.35),
            )
            flow_dots(display.screen, (cpx, cpy), tangent_end, explainer.elapsed,
                      theme.ACCENT_2, count=2, radius=2)
            draw_text(display.screen, f"hω={format_sig3(display_contact_speed)} m/s",
                      (tangent_end[0] + (7 if tangent_direction > 0 else -7), cpy + 8),
                      FONT_SMALL, theme.ACCENT_2,
                      anchor="topleft" if tangent_direction > 0 else "topright")

        if explainer and explainer.phase == "energy":
            loss_ratio = clamp(
                explainer.energy_parts_display()["loss"]
                / max(explainer.snapshot.ke_before, 1e-9),
                0.0,
                1.0,
            )
            heat_radius = int(12 + 42 * loss_ratio * explainer.energy_progress)
            if heat_radius > 12:
                display.flash_surf.fill((0, 0, 0, 0))
                pygame.draw.circle(display.flash_surf, (255, 90, 45, 55), (cpx, cpy), heat_radius)
                pygame.draw.circle(display.flash_surf, (255, 210, 80, 100),
                                   (cpx, cpy), max(5, heat_radius // 3))
                display.screen.blit(display.flash_surf, (0, 0))

        # 重力方向示意箭头。
        gx, gy = w2s(-0.5 * L * math.cos(display_theta),
                     0.5 * L * math.sin(display_theta))
        draw_arrow(display.screen, (gx, gy), (gx, gy + int(0.20 * scale)), theme.ACCENT_3, 2)

        if display_ball_trail:
            display.trail_surf_2.fill((0, 0, 0, 0))
            for i, (bx, by) in enumerate(display_ball_trail):
                p = i / max(1, len(display_ball_trail) - 1)
                raw_pos = w2s(bx, by)
                pos = (raw_pos[0] - max(12, int(rb * scale)) - (rod_w + 1) // 2, raw_pos[1])
                if -100 <= pos[0] <= LAYOUT.width + 100:
                    r = max(2, int(rb * scale * (0.22 + 0.40 * p)))
                    pygame.draw.circle(display.trail_surf_2, (*theme.BALL1_GLOW, int(12 + 75 * p)), pos, r + 3)
            display.screen.blit(display.trail_surf_2, (0, 0))

        if not replay_active and not explainer and (self.particles or self.shockwaves):
            display.particle_surf.fill((0, 0, 0, 0))
            for particle in self.particles:
                particle.draw(display.particle_surf, w2s, streak_scale=scale * 0.08)
            for wave in self.shockwaves:
                wave.draw(display.particle_surf, w2s, scale)
            display.screen.blit(display.particle_surf, (0, 0))

        br = max(12, int(rb * scale))
        # ball_x is displacement from impact, not the rendered sphere centre.
        # Offset the centre by its radius and half the visible rod thickness.
        raw_ball_pos = w2s(display_ball_x, h)
        ball_pos = (raw_ball_pos[0] - br - (rod_w + 1) // 2, raw_ball_pos[1])
        draw_soft_shadow(
            display.screen,
            (ball_pos[0] - br - 4, sy - max(3, br // 4),
             2 * br + 8, max(6, br // 2)),
        )
        draw_matte_ball(display.screen, ball_pos, br, theme.BALL1_COLOR)

        if not replay_active and not explainer and self.flash > 0:
            contact = w2s(0.0, h)
            display.flash_surf.fill((0, 0, 0, 0))
            f = self.flash
            r0 = int(clamp((1.15 - f) * 80 + 10, 5, 90))
            a0 = int(220 * f)
            pygame.draw.circle(display.flash_surf, (255, 255, 255, a0), contact, r0)
            pygame.draw.circle(display.flash_surf, (255, 210, 80, int(a0 * 0.45)),
                               contact, r0 + int(30 * f))
            pygame.draw.circle(display.flash_surf, (120, 180, 255, int(a0 * 0.20)),
                               contact, r0 + int(55 * f))
            display.screen.blit(display.flash_surf, (0, 0))

        if replay_active and display_collision is not None:
            draw_impact_fx(
                display.screen, (cpx, cpy), replay_frame.impact_flash,
                replay_frame.impact_strength,
            )
        if replay_active:
            draw_friction_heat_fx(
                display.screen, scene_pivot, replay_frame.friction_energy,
                scale=0.85,
            )
        elif self.phase == "after":
            draw_friction_heat_fx(
                display.screen, scene_pivot, self.damping_energy,
                scale=0.85,
            )

        if abs(display_ball_v) > 0.01 and (not explainer or explainer.phase == "velocity"):
            # 慢放阶段必须允许长度连续缩到零，否则速度变号时箭头会
            # 从固定最小长度突然翻向。
            arrow_len = clamp(abs(display_ball_v) * scale * 0.07, 0, 150)
            direction = 1 if display_ball_v > 0 else -1
            ay = ball_pos[1] - br - 12
            finish = (int(ball_pos[0] + direction * arrow_len), ay)
            draw_arrow(
                display.screen, (ball_pos[0], ay), finish, theme.GREEN, 3,
                head_size=min(12, arrow_len * 0.35),
            )
            if explainer:
                flow_dots(display.screen, (ball_pos[0], ay), finish, explainer.elapsed,
                          theme.GREEN, count=2, radius=2)
            draw_text(display.screen, f"v={format_sig3(display_ball_v)} m/s",
                      (finish[0] + (10 if direction > 0 else -10), ay - 12), FONT_SMALL,
                      theme.GREEN, anchor="topleft" if direction > 0 else "topright")
        elif not display_collided:
            draw_text(display.screen, "小球入射速率为 0",
                      (LAYOUT.scene_x + 20, LAYOUT.scene_y + LAYOUT.scene_h - 28),
                      FONT_SMALL, theme.ACCENT_3)

        if explainer:
            s = explainer.snapshot
            draw_scene_explanation(display.screen, LAYOUT.scene, explainer.elapsed,
                explainer.PHASE_DURATION, [(cpx, cpy), ball_pos], [10, br],
                (-s.impulse, s.impulse), (s.rod_ke_before, s.ball_ke_before),
                (s.rod_ke_after, s.ball_ke_after), running=self.running)
            rod_L_now = explainer.rod_L_display()
            ball_MRV_now = explainer.ball_MRV_display()
            display_parts = explainer.energy_parts_display()
            display_mechanical_energy = (
                display_parts["rod"] + display_parts["ball"]
                + self.collision_snapshot.potential
            )
        elif replay_active:
            ball_MRV_now = replay_frame.ball_angular_momentum
            rod_L_now = replay_frame.rod_angular_momentum
            display_mechanical_energy = replay_frame.total_energy
        else:
            rod_L_now = I * self.omega
            ball_MRV_now = m * h * self.ball_v
            display_mechanical_energy = self.total_mechanical_energy()
        total_L_now = rod_L_now + ball_MRV_now
        display_point_speed = display_contact_speed
        self._analysis_explainer = explainer
        self._analysis_account = display_account
        self._analysis_show_energy = (
            (not replay_active and self.phase == "after")
            or (replay_active and display_phase == "after")
        )
        self._analysis_angular_momentum = (rod_L_now, ball_MRV_now, total_L_now)
        self._analysis_L_scale = max(
            abs(rod_L_now), abs(ball_MRV_now), abs(total_L_now), 1e-6
        )
        current_lines = [
            f"摆角 ψ = {format_sig3(math.degrees(math.pi / 2 - display_theta))}°",
            f"杆角速度 w = {format_sig3(display_omega)} rad/s",
            f"碰撞点速率 h*w = {format_sig3(display_point_speed)} m/s",
            f"重力加速度 g = {format_sig3(self.sliders['g'].value)} m/s^2",
            f"转动惯量 I = {format_sig3(I)} kg*m^2",
            f"机械能 E = {format_sig3(display_mechanical_energy)} J",
            f"摩擦耗散 Wf = {format_sig3(display_friction_energy)} J",
            f"绕转轴总角动量 = {format_sig3(total_L_now)} kg*m^2/s",
            f"小球自身线动量 = {format_sig3(m * display_ball_v)} kg*m/s",
        ]
        collision_lines = None
        result = display_collision if replay_active else self.last_result
        if result:
            r = result
            collision_lines = [
                f"碰撞时刻 t = {format_sig3(r['impact_time'])} s",
                f"e={format_sig3(r.e)}  h={format_sig3(r.h)} m  J={format_sig3(r.impulse)} N·s",
                f"小球速度  {format_sig3(r.u_before)} → {format_sig3(r.v_after)} m/s",
                f"杆角速度  {format_sig3(r.omega_before)} → {format_sig3(r.omega_after)} rad/s",
                f"碰撞点速度  {format_sig3(r.contact_before)} → {format_sig3(r.contact_after)} m/s",
                f"相对速度  {format_sig3(r.relative_before)} → {format_sig3(r.relative_after)} m/s",
                f"杆角动量  {format_sig3(r.rod_L_before)} → {format_sig3(r.rod_L_after)}",
                f"球角动量  {format_sig3(r.ball_MRV_before)} → {format_sig3(r.ball_MRV_after)}",
                f"总角动量  {format_sig3(r.total_L_before)} → {format_sig3(r.total_L_after)}",
                f"角动量误差 = {format_sig3(r.angular_momentum_error)} kg·m²/s",
                f"恢复条件误差 = {format_sig3(r.restitution_error)} m/s",
                f"转轴外冲量 = {format_sig3(r.pivot_impulse)} N·s",
                f"动能  {format_sig3(r.ke_before)} → {format_sig3(r.ke_after)} J",
                f"碰撞耗散 = {format_sig3(r.collision_energy_loss)} J",
                f"能量残差 = {format_sig3(r.energy_residual)} J",
            ]
        self._info_payload = (
            current_lines, collision_lines,
            [
                "细杆初始静止，小球从左侧入射并撞击杆",
                "u 是小球入射速率；碰撞前杆角速度为 0",
                "杆长比例尺为 0--0.5 m；L=0 仅作为比例端点",
                "势能零点在杆竖直向下；恒定摩擦矩 tau_f=-tau0*sign(w)",
            ],
            ("小球入射速率", "恢复系数", "碰后绕轴总角动量", "角动量误差", "碰撞账本残差")
        )

    def draw_analysis_panel(self, rect):
        """在回放面板内显示讲解过程或确定性的能量流。"""
        rect = pygame.Rect(rect)
        explainer = getattr(self, "_analysis_explainer", None)
        if explainer is not None:
            explainer.draw(display.screen, rect, running=self.running)
            return
        if getattr(self, "_analysis_show_energy", False):
            snapshot = (self.replay_collision_snapshot()
                        if self.replay_mode else self.collision_snapshot)
            if snapshot is not None:
                self._draw_collision_replay_summary(rect, snapshot)
                return

        draw_text(display.screen, "角动量分量（数值为有符号量）",
                  (rect.x + 2, rect.y + 2), FONT_TINY, theme.MUTED)
        rod_l, ball_l, total_l = getattr(
            self, "_analysis_angular_momentum", (0.0, 0.0, 0.0)
        )
        values = (("杆 Iω", rod_l, theme.ACCENT_2), ("球 m h v", ball_l, theme.ACCENT_3))
        max_value = getattr(self, "_analysis_L_scale", 1e-6)
        x = rect.x + 112
        width = rect.w - 230
        zero_x = x + width // 2
        for index, (label, value, color) in enumerate(values):
            y = rect.y + 76 + index * 38
            draw_text(display.screen, label, (rect.x + 14, y), FONT_TINY, theme.TEXT)
            pygame.draw.rect(display.screen, theme.color((34, 46, 44)), (x, y + 2, width, 12), border_radius=5)
            pygame.draw.line(display.screen, theme.color((220, 230, 250)), (zero_x, y),
                             (zero_x, y + 16), 1)
            bar = int((width // 2 - 5) * clamp(abs(value) / max_value, 0.0, 1.0))
            if bar:
                bar_rect = (zero_x, y + 2, bar, 12) if value >= 0 else (
                    zero_x - bar, y + 2, bar, 12
                )
                pygame.draw.rect(display.screen, color, bar_rect, border_radius=5)
            draw_text(display.screen, format_sig3(value), (rect.right - 14, y - 1),
                      FONT_TINY, color, anchor="topright")
        draw_text(display.screen, f"总角动量 = {format_sig3(total_l)} kg*m^2/s",
                  (rect.x + 14, rect.bottom - 28), FONT_SMALL, theme.ACCENT_3)

    def _draw_collision_replay_summary(self, rect, snapshot):
        """碰撞结束后保留清晰的三阶段概览，而不是占用能量面板。"""
        from core.fonts import font
        rect = pygame.Rect(rect)
        tiny = font(LAYOUT.metrics.tiny_font_size)
        small = font(LAYOUT.metrics.small_font_size, True)
        labels = ("① 碰撞前", "② 冲量传递", "③ 碰撞后")
        centers = [rect.x + int(rect.w * p) for p in (0.16, 0.50, 0.84)]
        y = rect.y + 8
        for i in range(2):
            pygame.draw.line(display.screen, theme.color((60, 81, 77)),
                             (centers[i] + 34, y + 9),
                             (centers[i + 1] - 34, y + 9), 2)
        for center, label in zip(centers, labels):
            pygame.draw.circle(display.screen, theme.ACCENT_2, (center, y + 9), 5)
            draw_text(display.screen, label, (center, y + 22), tiny, theme.TEXT,
                      anchor="midtop", max_width=max(70, rect.w // 3 - 8))
        rows = (
            ("小球速度", snapshot.u_before, snapshot.v_after, "m/s"),
            ("杆角速度", snapshot.omega_before, snapshot.omega_after, "rad/s"),
            ("相对速度", snapshot.relative_before, snapshot.relative_after, "m/s"),
            ("总角动量", snapshot.total_L_before, snapshot.total_L_after, "kg·m²/s"),
        )
        y += 54
        for label, before, after, unit in rows:
            draw_text(display.screen,
                      f"{label}  {format_sig3(before)} → {format_sig3(after)} {unit}",
                      (rect.x + 4, y), tiny, theme.MUTED, max_width=rect.w - 8)
            y += tiny.get_height() + 5
        draw_text(display.screen, f"冲量 J = {format_sig3(snapshot.impulse)} N·s",
                  (rect.x + 4, min(y + 3, rect.bottom - small.get_height())),
                  small, theme.ACCENT_2, max_width=rect.w - 8)

    def draw_energy_panel(self, rect):
        """能量账本始终固定在右侧底部面板。"""
        account = getattr(self, "_analysis_account", None) or self.energy_breakdown()
        snapshot = self.replay_collision_snapshot() if self.replay_mode else self.collision_snapshot
        draw_energy_ledger(display.screen, rect, account, snapshot=snapshot)

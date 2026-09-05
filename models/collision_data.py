"""碰撞事件的只读数据快照。

快照同时支持属性访问和旧代码使用的 ``result["key"]`` 访问方式，
这样物理计算、教学演示和现有信息面板可以共享同一份碰撞数据。
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class ConservationState:
    """碰撞一侧的守恒量状态。

    球—杆系统的碰撞约束是绕转轴的角动量，而不是整个系统的线动量。
    线动量字段仍保留为诊断量，用来明确显示转轴外冲量的来源。
    """

    angular_momentum: float
    mechanical_energy: float
    rod_angular_momentum: float = 0.0
    ball_angular_momentum: float = 0.0
    ball_linear_momentum: float = 0.0
    system_linear_momentum: float = 0.0
    rod_kinetic_energy: float = 0.0
    ball_kinetic_energy: float = 0.0
    potential_energy: float = 0.0

    @property
    def total_angular_momentum(self):
        return self.angular_momentum

    @property
    def energy(self):
        return self.mechanical_energy


def _relative_error(before, after, floor=1e-12):
    return abs(after - before) / max(abs(before), abs(after), floor)


@dataclass(frozen=True)
class CollisionSnapshot:
    """质点-定轴细杆碰撞在瞬间的计算结果。"""

    m: float
    M: float
    L: float
    I: float
    h: float
    e: float
    theta_before: float

    u_before: float
    v_after: float
    omega_before: float
    omega_after: float
    contact_before: float
    contact_after: float
    relative_before: float
    relative_after: float
    impulse: float

    ke_before: float
    ke_after: float
    ball_ke_before: float
    ball_ke_after: float
    rod_ke_before: float
    rod_ke_after: float
    potential: float
    energy_before: float
    energy_after: float
    collision_energy_loss: float
    collision_loss_theory: float
    mu_eff: float

    rod_L_before: float
    ball_MRV_before: float
    total_L_before: float
    rod_L_after: float
    ball_MRV_after: float
    total_L_after: float

    rod_p_before: float
    rod_p_after: float
    system_p_before: float
    system_p_after: float
    pivot_impulse: float

    impact_time: float

    conservation_before: ConservationState | None = None
    conservation_after: ConservationState | None = None

    # New descriptive aliases used by presentation code and exported data.
    @property
    def ball_v_before(self):
        return self.u_before

    @property
    def ball_v_after(self):
        return self.v_after

    @property
    def collision_impulse(self):
        return self.impulse

    @property
    def delta_ball_velocity(self):
        return self.v_after - self.u_before

    @property
    def delta_rod_omega(self):
        return self.omega_after - self.omega_before

    @property
    def angular_momentum_error(self):
        return self.total_L_after - self.total_L_before

    @property
    def restitution_error(self):
        return self.relative_after + self.e * self.relative_before

    @property
    def collision_loss_error(self):
        return self.collision_energy_loss - self.collision_loss_theory

    @property
    def energy_residual(self):
        return self.energy_after - self.energy_before + self.collision_energy_loss

    def conservation_report(self):
        """返回区分物理耗散与数值误差的守恒报告。"""
        before = self.conservation_before
        after = self.conservation_after
        if before is None or after is None:
            return {
                "angular_momentum_before": self.total_L_before,
                "angular_momentum_after": self.total_L_after,
                "angular_momentum_error": self.total_L_after - self.total_L_before,
                "angular_momentum_relative_error": _relative_error(
                    self.total_L_before, self.total_L_after
                ),
                "energy_before": self.energy_before,
                "energy_after": self.energy_after,
                "energy_change": self.energy_after - self.energy_before,
                "energy_dissipation": self.collision_energy_loss,
                "energy_residual": (
                    self.energy_after - self.energy_before
                    + self.collision_energy_loss
                ),
            }

        angular_error = after.angular_momentum - before.angular_momentum
        energy_change = after.mechanical_energy - before.mechanical_energy
        return {
            "angular_momentum_before": before.angular_momentum,
            "angular_momentum_after": after.angular_momentum,
            "angular_momentum_error": angular_error,
            "angular_momentum_relative_error": _relative_error(
                before.angular_momentum, after.angular_momentum
            ),
            "energy_before": before.mechanical_energy,
            "energy_after": after.mechanical_energy,
            "energy_change": energy_change,
            "energy_dissipation": self.collision_energy_loss,
            "energy_residual": energy_change + self.collision_energy_loss,
            "line_momentum_before": before.system_linear_momentum,
            "line_momentum_after": after.system_linear_momentum,
            "pivot_impulse": self.pivot_impulse,
        }

    def __getitem__(self, key):
        """兼容原先 ``last_result["..."]`` 的字典式访问。"""
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def keys(self):
        """返回属性名，便于需要字典接口的调试/导出代码使用。"""
        return tuple(field.name for field in fields(self))

    def items(self):
        return tuple((key, self[key]) for key in self.keys())

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        return key in self.keys()

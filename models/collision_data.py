"""碰撞事件的只读数据快照。

快照同时支持属性访问和旧代码使用的 ``result["key"]`` 访问方式，
这样物理计算、教学演示和现有信息面板可以共享同一份碰撞数据。
"""

from __future__ import annotations

from dataclasses import dataclass, fields


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

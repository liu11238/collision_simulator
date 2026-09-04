"""与 pygame 无关的能量账本状态。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnergyState:
    """一次展示时刻的可审计能量状态，单位均为焦耳。"""

    initial: float = 0.0
    mechanical: float = 0.0
    rod_kinetic: float = 0.0
    ball_kinetic: float = 0.0
    potential: float = 0.0
    collision_loss: float = 0.0
    friction_heat: float = 0.0
    residual: float = 0.0

    @property
    def damping(self):
        """旧账本字段的语义兼容别名。"""
        return self.friction_heat

    @property
    def collision(self):
        """旧账本字段的语义兼容别名。"""
        return self.collision_loss

    @property
    def kinetic(self):
        return self.rod_kinetic + self.ball_kinetic

    @property
    def accounted_loss(self):
        return self.collision_loss + self.friction_heat

    @property
    def rod_ke(self):
        return self.rod_kinetic

    @property
    def ball_ke(self):
        return self.ball_kinetic

    @property
    def potential_energy(self):
        return self.potential

    @property
    def collision_loss_energy(self):
        return self.collision_loss

    @property
    def friction_heat_energy(self):
        return self.friction_heat

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key):
        aliases = {
            "collision": "collision_loss",
            "collision_energy_loss": "collision_loss",
            "damping": "friction_heat",
            "damping_energy": "friction_heat",
            "friction": "friction_heat",
            "friction_energy": "friction_heat",
        }
        key = aliases.get(key, key)
        if key == "mechanical":
            return self.mechanical
        if key == "initial":
            return self.initial
        if key == "residual":
            return self.residual
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def keys(self):
        return (
            "initial", "mechanical", "rod_kinetic", "ball_kinetic",
            "potential", "collision_loss", "friction_heat", "residual",
            "collision", "damping", "friction", "collision_energy_loss",
            "damping_energy", "friction_energy",
        )

    def items(self):
        return tuple((key, self[key]) for key in self.keys())

    def __contains__(self, key):
        return key in self.keys()

    @classmethod
    def from_account(cls, account):
        if isinstance(account, cls):
            return account
        getter = account.get
        return cls(
            initial=getter("initial", 0.0),
            mechanical=getter("mechanical", 0.0),
            rod_kinetic=getter("rod_kinetic", getter("rod_ke", 0.0)),
            ball_kinetic=getter("ball_kinetic", getter("ball_ke", 0.0)),
            potential=getter("potential", getter("potential_energy", 0.0)),
            collision_loss=getter("collision_loss", getter("collision", 0.0)),
            friction_heat=getter("friction_heat", getter("damping", 0.0)),
            residual=getter("residual", 0.0),
        )
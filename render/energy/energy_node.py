"""能量流图的固定节点定义。"""

from __future__ import annotations

import theme

from dataclasses import dataclass

from config import ACCENT, ACCENT_2, ACCENT_3

from .energy_state import EnergyState


@dataclass(frozen=True)
class EnergyNode:
    key: str
    label: str
    value: float
    color: tuple[int, int, int]
    position: tuple[float, float] = (0.0, 0.0)


def energy_nodes(state: EnergyState):
    """按稳定顺序返回绘图节点。"""
    return (
        EnergyNode("mechanical", "当前机械能", max(0.0, state.mechanical), theme.ACCENT, (0.5, 0.18)),
        EnergyNode("collision_loss", "碰撞损失", max(0.0, state.collision_loss), theme.ACCENT_2, (0.76, 0.48)),
        EnergyNode("friction_heat", "摩擦热", max(0.0, state.friction_heat), theme.ACCENT_3, (0.76, 0.82)),
    )
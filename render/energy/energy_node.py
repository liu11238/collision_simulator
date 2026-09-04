"""能量流图的固定节点定义。"""

from __future__ import annotations

from dataclasses import dataclass

from config import ACCENT, ACCENT_2, ACCENT_3

from .energy_state import EnergyState


@dataclass(frozen=True)
class EnergyNode:
    key: str
    label: str
    value: float
    color: tuple[int, int, int]


def energy_nodes(state: EnergyState):
    """按稳定顺序返回绘图节点。"""
    return (
        EnergyNode("mechanical", "当前机械能", max(0.0, state.mechanical), ACCENT),
        EnergyNode("collision_loss", "碰撞损失→热", max(0.0, state.collision_loss), ACCENT_2),
        EnergyNode("friction_heat", "转轴摩擦热", max(0.0, state.friction_heat), ACCENT_3),
    )
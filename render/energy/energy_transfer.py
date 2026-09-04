"""能量流图的确定性几何和数值辅助函数。"""

from __future__ import annotations

from dataclasses import dataclass

from utils import clamp


@dataclass(frozen=True)
class EnergyTransfer:
    source: tuple[int, int]
    target: tuple[int, int]
    value: float
    ratio: float


def transfer_for(value, total, source, target):
    total = max(abs(float(total)), 1e-12)
    value = max(0.0, float(value))
    return EnergyTransfer(
        source=source,
        target=target,
        value=value,
        ratio=clamp(value / total, 0.0, 1.0),
    )
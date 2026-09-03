"""固定采样的只读回放时间轴。

时间轴保存的是展示快照，不拥有也不修改物理模型状态。碰撞事件使用同一
时间戳的 ``collision_before`` / ``collision_after`` 两帧表示，查询时不会把
这两帧跨越插值，从而避免讲解器出现球和杆的瞬移。
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from math import isfinite


@dataclass(frozen=True)
class ReplayFrame:
    """某一物理时刻的只读展示状态。"""

    time: float
    phase: str = "ready"
    theta: float = 0.0
    omega: float = 0.0
    ball_x: float = 0.0
    ball_v: float = 0.0
    mechanical_energy: float = 0.0
    total_energy: float = 0.0
    friction_energy: float = 0.0
    angular_momentum: float = 0.0
    collision: object | None = None
    collision_id: int | None = None
    event: str | None = None

    @property
    def is_collision_boundary(self):
        return self.event in {"collision_before", "collision_after"}

    def interpolated(self, other: "ReplayFrame", progress: float) -> "ReplayFrame":
        """在两个普通连续帧之间插值，不跨越碰撞边界。"""
        p = min(1.0, max(0.0, float(progress)))

        def lerp(a, b):
            return a + (b - a) * p

        return ReplayFrame(
            time=lerp(self.time, other.time),
            phase=other.phase if p >= 0.5 else self.phase,
            theta=lerp(self.theta, other.theta),
            omega=lerp(self.omega, other.omega),
            ball_x=lerp(self.ball_x, other.ball_x),
            ball_v=lerp(self.ball_v, other.ball_v),
            mechanical_energy=lerp(self.mechanical_energy, other.mechanical_energy),
            total_energy=lerp(self.total_energy, other.total_energy),
            friction_energy=lerp(self.friction_energy, other.friction_energy),
            angular_momentum=lerp(self.angular_momentum, other.angular_momentum),
            collision=other.collision if p >= 0.5 else self.collision,
            collision_id=None,
            event=None,
        )


class ReplayTimeline:
    """固定采样、可 seek 的回放帧序列。"""

    def __init__(self, sample_interval=1.0 / 60.0):
        if sample_interval <= 0.0 or not isfinite(float(sample_interval)):
            raise ValueError("sample_interval 必须是正数")
        self.sample_interval = float(sample_interval)
        self.frames: list[ReplayFrame] = []
        self.cursor = 0.0
        self.playing = False
        self.live = True
        self._next_sample = 0.0
        self._collision_count = 0

    @property
    def duration(self):
        return self.frames[-1].time if self.frames else 0.0

    @property
    def has_frames(self):
        return bool(self.frames)

    @property
    def collision_count(self):
        return self._collision_count

    def clear(self):
        self.frames.clear()
        self.cursor = 0.0
        self.playing = False
        self.live = True
        self._next_sample = 0.0
        self._collision_count = 0

    def _append(self, frame: ReplayFrame):
        if frame.time < 0.0 or not isfinite(float(frame.time)):
            raise ValueError("回放帧时间必须是非负有限数")
        if self.frames and frame.time < self.frames[-1].time - 1e-12:
            raise ValueError("回放帧必须按时间顺序写入")
        self.frames.append(frame)
        self.cursor = frame.time

    def record_initial(self, frame: ReplayFrame):
        """写入初始帧；重复调用会重置时间轴。"""
        self.clear()
        self._append(replace(frame, time=0.0, event=None, collision_id=None))
        self._next_sample = self.sample_interval

    def record_sample(self, frame: ReplayFrame, force=False):
        """按固定间隔写入普通帧，force 用于碰撞前后边界。"""
        if not self.frames:
            self.record_initial(frame)
            return True
        if not force and frame.time + 1e-12 < self._next_sample:
            return False
        if force or frame.time + 1e-12 >= self._next_sample:
            self._append(replace(frame, event=None, collision_id=None))
            while self._next_sample <= frame.time + 1e-12:
                self._next_sample += self.sample_interval
            return True
        return False

    def record_collision(self, before: ReplayFrame, after: ReplayFrame):
        """在同一时刻写入碰撞前/碰撞后两帧。"""
        if not self.frames:
            self.record_initial(before)
        if before.time < self.frames[-1].time - 1e-12:
            raise ValueError("碰撞帧不能早于当前时间轴")
        # force 采样可能已经写入了同一时刻的普通帧；碰撞边界应当只保留
        # before/after 两帧，避免 exact seek 无法区分碰前和碰后。
        while (self.frames and abs(self.frames[-1].time - before.time) <= 1e-10
               and self.frames[-1].event is None):
            self.frames.pop()
        collision_id = self._collision_count
        self._collision_count += 1
        self._append(replace(before, collision_id=collision_id,
                             event="collision_before"))
        self._append(replace(after, time=before.time, collision_id=collision_id,
                             event="collision_after"))
        while self._next_sample <= before.time + 1e-12:
            self._next_sample += self.sample_interval
        self.live = True

    def _exact_index(self, time, side):
        indices = [i for i, frame in enumerate(self.frames)
                   if abs(frame.time - time) <= 1e-10]
        if not indices:
            return None
        if side == "after":
            collision_indices = [i for i in indices
                                 if self.frames[i].event == "collision_after"]
            return collision_indices[-1] if collision_indices else indices[-1]
        collision_indices = [i for i in indices
                             if self.frames[i].event == "collision_before"]
        return collision_indices[0] if collision_indices else indices[0]

    def frame_at(self, time=None, side="before"):
        """取得展示帧；普通相邻帧线性插值，碰撞边界不插值。"""
        if not self.frames:
            return None
        if time is None:
            time = self.cursor
        time = min(self.duration, max(0.0, float(time)))

        exact = self._exact_index(time, side)
        if exact is not None:
            return self.frames[exact]

        times = [frame.time for frame in self.frames]
        right_index = bisect_right(times, time)
        if right_index <= 0:
            return self.frames[0]
        if right_index >= len(self.frames):
            return self.frames[-1]
        left = self.frames[right_index - 1]
        right = self.frames[right_index]
        if (left.event == "collision_before"
                and right.event == "collision_after") or abs(right.time - left.time) <= 1e-12:
            # 查询落在碰撞边界附近时保持左侧/碰前状态，不制造跨事件插值。
            return left
        progress = (time - left.time) / (right.time - left.time)
        return left.interpolated(right, progress)

    def seek(self, time, side="before"):
        """移动展示游标并返回帧；不会修改写入的帧或物理对象。"""
        if not self.frames:
            self.cursor = 0.0
            return None
        self.cursor = min(self.duration, max(0.0, float(time)))
        self.live = abs(self.cursor - self.duration) <= 1e-10
        return self.frame_at(self.cursor, side=side)

    def step_playback(self, dt):
        """推进只读回放时钟。"""
        if not self.playing or not self.frames:
            return self.frame_at()
        frame = self.seek(self.cursor + max(0.0, float(dt)), side="after")
        if self.live:
            self.playing = False
        return frame

    def toggle(self):
        if not self.frames:
            return False
        self.playing = not self.playing
        self.live = False
        return self.playing

    def go_live(self):
        self.playing = False
        self.live = True
        self.cursor = self.duration
        return self.frame_at(side="after")

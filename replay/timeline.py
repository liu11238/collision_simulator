"""固定采样的只读回放时间轴。

碰撞是时间轴上的瞬时事件：碰前、碰后快照使用完全相同的时间戳，seek 时
通过 ``side`` 选择边界哪一侧。撞击闪光可以在事件后短暂衰减，但不会冻结
状态、延长时间轴或改变物理时钟。
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from math import isfinite

from config import IMPACT_REPLAY_FX_DURATION


@dataclass(frozen=True)
class ReplayFrame:
    """某一物理时刻的只读展示状态。"""

    time: float
    phase: str = "ready"
    theta: float = 0.0
    omega: float = 0.0
    ball_x: float = 0.0
    ball_v: float = 0.0
    left_x: float = 0.0
    right_x: float = 0.0
    left_v: float = 0.0
    right_v: float = 0.0
    mechanical_energy: float = 0.0
    total_energy: float = 0.0
    rod_kinetic_energy: float = 0.0
    ball_kinetic_energy: float = 0.0
    left_kinetic_energy: float = 0.0
    right_kinetic_energy: float = 0.0
    potential_energy: float = 0.0
    collision_energy_loss: float = 0.0
    friction_energy: float = 0.0
    energy_residual: float = 0.0
    rod_angular_momentum: float = 0.0
    ball_angular_momentum: float = 0.0
    angular_momentum: float = 0.0
    linear_momentum: float = 0.0
    collision: object | None = None
    collision_id: int | None = None
    event: str | None = None
    # Replay-only visual state.  These values are snapshots rather than live
    # pygame objects, so seeking is deterministic and read-only.
    impact_strength: float = 0.0
    impact_flash: float = 0.0
    impact_progress: float = 1.0

    @property
    def is_collision_boundary(self):
        return self.event in {"collision_before", "collision_after"}

    # Short aliases make exported replay data convenient to inspect while the
    # canonical fields above remain explicit and self-documenting.
    @property
    def rod_ke(self):
        return self.rod_kinetic_energy

    @property
    def ball_ke(self):
        return self.ball_kinetic_energy

    @property
    def potential(self):
        return self.potential_energy

    @property
    def collision_loss(self):
        return self.collision_energy_loss

    @property
    def friction_heat(self):
        return self.friction_energy

    @property
    def rod_L(self):
        return self.rod_angular_momentum

    @property
    def ball_L(self):
        return self.ball_angular_momentum

    @property
    def total_L(self):
        return self.angular_momentum

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
            left_x=lerp(self.left_x, other.left_x),
            right_x=lerp(self.right_x, other.right_x),
            left_v=lerp(self.left_v, other.left_v),
            right_v=lerp(self.right_v, other.right_v),
            mechanical_energy=lerp(self.mechanical_energy, other.mechanical_energy),
            total_energy=lerp(self.total_energy, other.total_energy),
            rod_kinetic_energy=lerp(self.rod_kinetic_energy, other.rod_kinetic_energy),
            ball_kinetic_energy=lerp(self.ball_kinetic_energy, other.ball_kinetic_energy),
            left_kinetic_energy=lerp(self.left_kinetic_energy,
                                     other.left_kinetic_energy),
            right_kinetic_energy=lerp(self.right_kinetic_energy,
                                      other.right_kinetic_energy),
            potential_energy=lerp(self.potential_energy, other.potential_energy),
            collision_energy_loss=lerp(self.collision_energy_loss, other.collision_energy_loss),
            friction_energy=lerp(self.friction_energy, other.friction_energy),
            energy_residual=lerp(self.energy_residual, other.energy_residual),
            rod_angular_momentum=lerp(self.rod_angular_momentum, other.rod_angular_momentum),
            ball_angular_momentum=lerp(self.ball_angular_momentum, other.ball_angular_momentum),
            angular_momentum=lerp(self.angular_momentum, other.angular_momentum),
            linear_momentum=lerp(self.linear_momentum, other.linear_momentum),
            collision=other.collision if p >= 0.5 else self.collision,
            collision_id=None,
            event=None,
            impact_strength=lerp(self.impact_strength, other.impact_strength),
            impact_flash=lerp(self.impact_flash, other.impact_flash),
            impact_progress=lerp(self.impact_progress, other.impact_progress),
        )


class ReplayTimeline:
    """固定采样、可 seek 的回放帧序列。"""

    def __init__(self, sample_interval=1.0 / 60.0,
                 impact_effect_duration=IMPACT_REPLAY_FX_DURATION):
        if sample_interval <= 0.0 or not isfinite(float(sample_interval)):
            raise ValueError("sample_interval 必须是正数")
        if (impact_effect_duration < 0.0
                or not isfinite(float(impact_effect_duration))):
            raise ValueError("impact_effect_duration 必须是非负有限数")
        self.sample_interval = float(sample_interval)
        self.impact_effect_duration = float(impact_effect_duration)
        # Backwards-compatible attribute; it now means FX decay, not state time.
        self.collision_window = self.impact_effect_duration
        self.frames: list[ReplayFrame] = []
        self.cursor = 0.0
        self.playing = False
        self.live = True
        self._next_sample = 0.0
        self._collision_count = 0
        self._collision_events = []

    @property
    def duration(self):
        return self.frames[-1].time if self.frames else 0.0

    @property
    def has_frames(self):
        return bool(self.frames)

    @property
    def collision_count(self):
        return self._collision_count

    @property
    def collision_windows(self):
        """兼容旧 API；瞬时事件的 ``start == end``。"""
        return tuple((time, time, collision_id)
                     for time, collision_id in self._collision_events)

    @property
    def collision_events(self):
        """只读的 ``(time, collision_id)`` 瞬时事件序列。"""
        return tuple(self._collision_events)

    def trail_frames(self, cursor_time=None, lifetime=0.8, speed_threshold=0.03):
        """返回时间窗口内可用于重建残影的只读帧。

        Replay 不保存渲染 trail；调用方只需用当前游标、生命周期和速度
        阈值从普通 ``ReplayFrame`` 重建它，因此 seek 前后不会出现状态残留。
        """
        if cursor_time is None:
            cursor_time = self.cursor
        cursor_time = float(cursor_time)
        lifetime = max(0.0, float(lifetime))
        threshold = abs(float(speed_threshold))
        start = cursor_time - lifetime
        return tuple(
            frame for frame in self.frames
            if start - 1e-10 <= frame.time <= cursor_time + 1e-10
            and abs(frame.omega) > threshold
        )

    def clear(self):
        self.frames.clear()
        self.cursor = 0.0
        self.playing = False
        self.live = True
        self._next_sample = 0.0
        self._collision_count = 0
        self._collision_events.clear()

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
        display_time = frame.time
        if not force and display_time + 1e-12 < self._next_sample:
            return False
        if force or display_time + 1e-12 >= self._next_sample:
            self._append(replace(frame, time=display_time, event=None,
                                 collision_id=None))
            while self._next_sample <= display_time + 1e-12:
                self._next_sample += self.sample_interval
            return True
        return False

    def record_collision(self, before: ReplayFrame, after: ReplayFrame):
        """在同一物理时刻写入碰前和碰后边界。"""
        if not self.frames:
            self.record_initial(before)
        impact_time = before.time
        if impact_time < self.frames[-1].time - 1e-12:
            raise ValueError("碰撞帧不能早于当前时间轴")
        # force 采样可能已经写入了同一时刻的普通帧；碰撞边界应当只保留
        # before 帧，避免 exact seek 无法区分碰前和碰后状态。
        while (self.frames and abs(self.frames[-1].time - impact_time) <= 1e-10
               and self.frames[-1].event is None):
            self.frames.pop()
        collision_id = self._collision_count
        self._collision_count += 1
        self._append(replace(before, time=impact_time, collision_id=collision_id,
                             event="collision_before"))
        self._append(replace(
            after,
            time=impact_time,
            collision_id=collision_id,
            event="collision_after",
            impact_flash=max(before.impact_flash, after.impact_flash, 1.0),
        ))
        self._collision_events.append((impact_time, collision_id))
        while self._next_sample <= impact_time + 1e-12:
            self._next_sample += self.sample_interval
        self.live = True

    def collision_window_at(self, time=None):
        """兼容旧 API：仅在游标精确落在碰撞时刻时返回点事件。"""
        if time is None:
            time = self.cursor
        time = float(time)
        for impact_time, collision_id in self._collision_events:
            if abs(time - impact_time) <= 1e-10:
                return impact_time, impact_time, collision_id, 0.0
        return None

    def collision_intensity_at(self, time=None):
        """返回事件后的确定性视觉衰减，不影响状态或时间轴长度。"""
        if time is None:
            time = self.cursor
        time = float(time)
        for impact_time, _ in reversed(self._collision_events):
            elapsed = time - impact_time
            if elapsed < -1e-10:
                continue
            if elapsed <= self.impact_effect_duration + 1e-10:
                progress = elapsed / max(1e-12, self.impact_effect_duration)
                return max(0.0, 1.0 - progress) ** 1.7
            break
        return 0.0

    def _with_impact_visual(self, frame, time):
        """Attach transient replay FX to an otherwise continuous state."""
        intensity = self.collision_intensity_at(time)
        if intensity <= 1e-10:
            return replace(frame, impact_flash=0.0, impact_progress=1.0)
        collision_frame = None
        for candidate in reversed(self.frames):
            if (candidate.event == "collision_after"
                    and candidate.time <= time + 1e-10):
                collision_frame = candidate
                break
        strength = (collision_frame.impact_strength
                    if collision_frame is not None else frame.impact_strength)
        return replace(frame, impact_flash=intensity,
                       impact_strength=strength,
                       impact_progress=1.0 - intensity)

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
        """取得展示帧；普通帧连续插值，碰撞时刻按 side 选择边界。"""
        if not self.frames:
            return None
        if time is None:
            time = self.cursor
        time = min(self.duration, max(0.0, float(time)))

        exact = self._exact_index(time, side)
        if exact is not None:
            return self._with_impact_visual(self.frames[exact], time)

        times = [frame.time for frame in self.frames]
        right_index = bisect_right(times, time)
        if right_index <= 0:
            return self._with_impact_visual(self.frames[0], time)
        if right_index >= len(self.frames):
            return self._with_impact_visual(self.frames[-1], time)
        left = self.frames[right_index - 1]
        right = self.frames[right_index]
        if abs(right.time - left.time) <= 1e-12:
            return self._with_impact_visual(left, time)
        progress = (time - left.time) / (right.time - left.time)
        return self._with_impact_visual(left.interpolated(right, progress), time)

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

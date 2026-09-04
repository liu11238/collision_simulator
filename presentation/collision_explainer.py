"""碰撞瞬间的可冻结讲解流程和过程可视化。"""

from __future__ import annotations

import math

import pygame

from config import ACCENT, ACCENT_2, ACCENT_3, MUTED, RED, TEXT
from core.fonts import FONT_BIG, FONT_SMALL, FONT_TINY
from render.primitives import draw_arrow, draw_text, rounded_rect
from utils import clamp, format_sig3


def _lerp(a, b, p):
    return a + (b - a) * p


def _smooth(p):
    """比线性插值更像真实演示的缓入缓出。"""
    p = clamp(p, 0.0, 1.0)
    return p * p * (3.0 - 2.0 * p)


def _draw_dashed_line(surface, start, end, color, width=2, dash=9, gap=6,
                      offset=0.0):
    """画一条带有流动感的虚线，offset 用来让信息沿箭头移动。"""
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1.0:
        return
    ux, uy = dx / length, dy / length
    cursor = -((offset % (dash + gap)))
    while cursor < length:
        a = max(0.0, cursor)
        b = min(length, cursor + dash)
        if b > a:
            pygame.draw.line(
                surface,
                color,
                (int(x1 + ux * a), int(y1 + uy * a)),
                (int(x1 + ux * b), int(y1 + uy * b)),
                width,
            )
        cursor += dash + gap


def _flow_dot(surface, start, end, progress, color, radius=5):
    p = clamp(progress, 0.0, 1.0)
    pos = (
        int(_lerp(start[0], end[0], p)),
        int(_lerp(start[1], end[1], p)),
    )
    pygame.draw.circle(surface, color, pos, radius + 4)
    pygame.draw.circle(surface, (245, 250, 255), pos, radius)


class CollisionExplainer:
    """用一份碰撞快照重演速度、动量和能量的重新分配。

    这里的所有 display 方法都只返回绘图用的插值结果，不修改模型的
    ``theta``、``omega``、``ball_v`` 或 ``t``，因此 ``impact_explain`` 仍然
    是严格冻结的物理阶段。
    """

    PHASES = ("velocity", "momentum", "energy")
    PHASE_DURATION = 2.2
    FOCUS_IN_END = 0.24
    FOCUS_OUT_START = 0.76

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.elapsed = 0.0
        self.total_duration = self.PHASE_DURATION * len(self.PHASES)
        # Bar scales are presentation state, not per-frame measurements.  A
        # fixed denominator prevents the apparent bar length from jumping when
        # the interpolated value crosses a local maximum.
        self.L_scale = max(
            abs(snapshot.total_L_before),
            abs(snapshot.total_L_after),
            1e-6,
        )
        self.rod_L_scale = max(
            abs(snapshot.rod_L_before), abs(snapshot.rod_L_after), 1e-6
        )
        self.ball_L_scale = max(
            abs(snapshot.ball_MRV_before), abs(snapshot.ball_MRV_after), 1e-6
        )

    @property
    def complete(self):
        return self.elapsed >= self.total_duration

    @property
    def phase_index(self):
        return min(len(self.PHASES) - 1, int(self.elapsed / self.PHASE_DURATION))

    @property
    def phase(self):
        return self.PHASES[self.phase_index]

    @property
    def phase_progress(self):
        return clamp(
            (self.elapsed - self.phase_index * self.PHASE_DURATION)
            / self.PHASE_DURATION,
            0.0,
            1.0,
        )

    @property
    def smooth_phase_progress(self):
        return _smooth(self.phase_progress)

    def _progress_for(self, phase_index):
        if self.phase_index < phase_index:
            return 0.0
        if self.phase_index > phase_index:
            return 1.0
        return self.smooth_phase_progress

    @property
    def velocity_progress(self):
        return self._progress_for(0)

    @property
    def momentum_progress(self):
        return self._progress_for(1)

    @property
    def energy_progress(self):
        return self._progress_for(2)

    def update(self, dt):
        self.elapsed = min(self.total_duration, self.elapsed + max(0.0, dt))
        return self.complete

    def skip(self):
        self.elapsed = self.total_duration

    def focus_strength(self):
        """镜头缩放强度：缓慢拉近、在碰撞细节处停留、最后回落。

        中间的平台期是有意保留的：如果整段讲解只用正弦曲线缩放，镜头
        会在速度、动量和能量阶段持续漂移，观众无法稳定读取公式和图示。
        """
        p = clamp(self.elapsed / self.total_duration, 0.0, 1.0)
        if p <= self.FOCUS_IN_END:
            return _smooth(p / self.FOCUS_IN_END)
        if p < self.FOCUS_OUT_START:
            return 1.0
        return _smooth((1.0 - p) / (1.0 - self.FOCUS_OUT_START))

    # ------------------------------------------------------------------
    # 过程数据：这些是可测试的展示态，不是物理状态。
    # ------------------------------------------------------------------
    def ball_v_display(self):
        s = self.snapshot
        return _lerp(s.u_before, s.v_after, self.velocity_progress)

    def ball_x_display(self, span=0.22):
        """用于场景重演的小球位移；仅为视觉时间轴，不是物理积分。"""
        s = self.snapshot
        if self.phase_index == 0:
            return 0.0
        direction = 1.0 if s.v_after >= 0.0 else -1.0
        progress = self.momentum_progress if self.phase_index == 1 else 1.0
        return direction * span * progress

    def contact_speed_display(self):
        s = self.snapshot
        if self.phase_index == 0:
            return _lerp(s.contact_before, s.contact_after, self.velocity_progress)
        return s.h * self.rod_omega_display()

    def rod_omega_display(self):
        s = self.snapshot
        if self.phase_index == 0:
            if abs(s.h) > 1e-12:
                return self.contact_speed_display() / s.h
            return s.omega_before
        # 速度阶段已经把场景中的展示角速度平滑带到碰后值；动量阶段
        # 改为单独展示带符号的角动量分配，不能把角速度跳回碰前值。
        return s.omega_after

    def rod_L_display(self):
        s = self.snapshot
        return _lerp(s.rod_L_before, s.rod_L_after, self.momentum_progress)

    def ball_MRV_display(self):
        s = self.snapshot
        # 用守恒总量反推小球一侧，动画中的两条流始终严格闭合。
        if self.momentum_progress >= 1.0:
            return s.ball_MRV_after
        return s.total_L_before - self.rod_L_display()

    def impulse_display(self):
        return self.snapshot.impulse * self.momentum_progress

    def energy_parts_display(self):
        s = self.snapshot
        p = self.energy_progress
        rod = _lerp(s.rod_ke_before, s.rod_ke_after, p)
        total = max(0.0, s.ke_before)
        loss = clamp(max(0.0, s.collision_energy_loss) * p, 0.0, total)
        # 由剩余能量反推球的分量，令每一个展示时刻都严格满足
        # rod + ball + loss = total，而不是只在两个端点闭合。
        ball = total - loss - rod
        return {
            "rod": max(0.0, rod),
            "ball": max(0.0, ball),
            "loss": loss,
            "total": total,
        }

    # ------------------------------------------------------------------
    # 三个过程图。
    # ------------------------------------------------------------------
    def _draw_velocity(self, surface, rect):
        s = self.snapshot
        p = self.velocity_progress
        left = (rect.x + 105, rect.y + 112)
        node = (rect.centerx, rect.y + 112)
        right = (rect.right - 105, rect.y + 112)

        draw_text(surface, "碰撞不是瞬移：速度沿冲量方向重新分配",
                  (rect.x + 20, rect.y + 57), FONT_SMALL, MUTED)
        pygame.draw.line(surface, (39, 55, 88), left, node, 8)
        pygame.draw.line(surface, (39, 55, 88), node, right, 8)
        draw_arrow(surface, left, node, ACCENT_2, 3)
        draw_arrow(surface, node, right, ACCENT_3, 3)
        _flow_dot(surface, left, node, p, ACCENT_2)
        _flow_dot(surface, node, right, p, ACCENT_3)

        draw_text(surface, "杆碰撞点", left, FONT_TINY, TEXT, anchor="midbottom")
        draw_text(surface, "冲量 J", node, FONT_TINY, ACCENT_2, anchor="midtop")
        draw_text(surface, "小球", right, FONT_TINY, TEXT, anchor="midbottom")
        draw_text(surface, f"hω: {format_sig3(self.contact_speed_display())} m/s",
                  (left[0], left[1] + 17), FONT_TINY, ACCENT_2, anchor="midtop")
        draw_text(surface, f"v: {format_sig3(self.ball_v_display())} m/s",
                  (right[0], right[1] + 17), FONT_TINY, ACCENT_3, anchor="midtop")
        draw_text(surface,
                  f"相对速度  {format_sig3(s.relative_before)}  →  {format_sig3(s.relative_after)} m/s",
                  (rect.centerx, rect.bottom - 24), FONT_SMALL, ACCENT_3,
                  anchor="center")

    def _draw_momentum(self, surface, rect):
        s = self.snapshot
        p = self.momentum_progress
        rod_l = self.rod_L_display()
        ball_l = self.ball_MRV_display()
        bar_w = rect.w - 220
        x = rect.x + 185

        draw_text(surface, "绕转轴角动量在杆与小球之间重新分配；总量不凭空改变",
                  (rect.x + 20, rect.y + 57), FONT_SMALL, MUTED)
        draw_text(surface, "总角动量守恒",
                  (rect.x + 20, rect.y + 78), FONT_TINY, TEXT)
        draw_text(surface, f"L_before = {format_sig3(s.total_L_before)} kg*m^2/s",
                  (rect.x + 20, rect.y + 94), FONT_TINY, MUTED)
        draw_text(surface, f"L_after  = {format_sig3(s.total_L_after)} kg*m^2/s",
                  (rect.x + 20, rect.y + 110), FONT_TINY, MUTED)
        error = abs(s.total_L_after - s.total_L_before)
        error_percent = 100.0 * error / self.L_scale
        status_color = ACCENT_3 if error_percent < 1e-6 else ACCENT_2
        draw_text(surface, f"误差 = {error_percent:.5f}%  {'✓' if error_percent < 1e-6 else '!'}",
                  (rect.x + 20, rect.y + 126), FONT_TINY, status_color)

        rows = (("杆 Iω", rod_l, self.rod_L_scale, ACCENT_2),
                ("球 m h v", ball_l, self.ball_L_scale, ACCENT_3))
        y = rect.y + 157
        for label, value, scale, color in rows:
            draw_text(surface, label, (rect.x + 20, y), FONT_TINY, TEXT)
            self._draw_signed_bar(surface, x, y + 2, bar_w, value, scale, color, 11)
            draw_text(surface, f"{format_sig3(value)} kg*m^2/s",
                      (rect.right - 20, y - 2), FONT_TINY, color, anchor="topright")
            y += 29

        draw_text(surface, "← 负方向       零点       正方向 →",
                  (x + bar_w / 2, rect.y + 217), FONT_TINY, MUTED, anchor="midtop")

        transfer_start = (x + int(bar_w * 0.30), rect.y + 232)
        transfer_end = (x + int(bar_w * 0.70), rect.y + 232)
        _draw_dashed_line(surface, transfer_start, transfer_end, ACCENT_2,
                          2, offset=self.elapsed * 42.0)
        _flow_dot(surface, transfer_start, transfer_end, p, ACCENT_2, radius=4)
        draw_arrow(surface, transfer_start, transfer_end, ACCENT_2, 2)
        draw_text(surface, f"冲量 J = {format_sig3(self.impulse_display())} N*s",
                  (rect.centerx, rect.bottom - 22), FONT_SMALL, ACCENT_2,
                  anchor="center")

    @staticmethod
    def _draw_signed_bar(surface, x, y, width, value, max_value, color, height):
        """以同一零点绘制带符号的代数量，正负方向不会被取绝对值混淆。"""
        x, y, width, height = int(x), int(y), int(width), int(height)
        zero_x = x + width // 2
        half_width = max(0, width // 2 - 5)
        pygame.draw.rect(surface, (30, 43, 72), (x, y, width, height), border_radius=5)
        pygame.draw.line(surface, (220, 230, 250), (zero_x, y - 2),
                         (zero_x, y + height + 2), 1)
        scaled = int(half_width * clamp(abs(value) / max_value, 0.0, 1.0))
        if scaled <= 0:
            return
        if value >= 0.0:
            bar_rect = (zero_x, y, scaled, height)
        else:
            bar_rect = (zero_x - scaled, y, scaled, height)
        pygame.draw.rect(surface, color, bar_rect, border_radius=5)

    def _draw_ribbon(self, surface, start_x, end_x, source_y, target_y,
                     source_h, target_h, color):
        half_source = source_h / 2.0
        half_target = target_h / 2.0
        points = [
            (start_x, int(source_y - half_source)),
            (start_x, int(source_y + half_source)),
            (end_x, int(target_y + half_target)),
            (end_x, int(target_y - half_target)),
        ]
        pygame.draw.polygon(surface, color, points)

    def _draw_energy(self, surface, rect):
        s = self.snapshot
        parts = self.energy_parts_display()
        total = max(parts["total"], 1e-9)
        values = (
            ("杆转动", parts["rod"], ACCENT_2),
            ("球平动", parts["ball"], ACCENT_3),
            ("碰撞损失/热", parts["loss"], RED),
        )

        draw_text(surface, "碰前动能沿三条路径流出；损失变成不可逆的热",
                  (rect.x + 20, rect.y + 57), FONT_SMALL, MUTED)
        source_x = rect.x + 125
        target_x = rect.right - 225
        source_top = rect.y + 82
        total_h = 94.0
        source_cursor = source_top
        target_cursor = source_top
        centers = []
        for label, value, color in values:
            # 零损失必须真正没有色带；用 max(2,h) 画占位条会制造虚假的
            # 能量分流，尤其在 e=1 的理想弹性碰撞中很明显。
            if value <= 1e-12:
                continue
            h = total_h * clamp(value / total, 0.0, 1.0)
            center_source = source_cursor + h / 2.0
            center_target = target_cursor + h / 2.0
            self._draw_ribbon(surface, source_x, target_x, center_source,
                              center_target, max(2.0, h), max(2.0, h), color)
            centers.append((label, value, color, center_target, h))
            source_cursor += h
            target_cursor += h

        pygame.draw.rect(surface, (230, 238, 255),
                         (source_x - 8, int(source_top), 16, int(total_h)),
                         border_radius=5)
        draw_text(surface, "碰前动能", (source_x - 18, source_top - 17),
                  FONT_TINY, TEXT, anchor="midbottom")
        draw_text(surface, f"{format_sig3(total)} J", (source_x - 18, source_top + total_h + 5),
                  FONT_TINY, ACCENT, anchor="midtop")

        for label, value, color, center, h in centers:
            pygame.draw.rect(surface, color,
                             (target_x - 7, int(center - max(6.0, h) / 2),
                              14, int(max(6.0, h))), border_radius=4)
            draw_text(surface, label, (target_x + 18, center - 13), FONT_TINY, color)
            draw_text(surface, f"{format_sig3(value)} J", (target_x + 18, center + 3),
                      FONT_TINY, TEXT)

        for _, _, color, center, _ in centers:
            _draw_dashed_line(surface, (source_x + 15, center),
                              (target_x - 15, center), color, 2,
                              offset=self.elapsed * 48.0)
            _flow_dot(surface, (source_x + 15, center), (target_x - 15, center),
                      self.energy_progress, color, radius=3)

        draw_text(surface, "碰撞后阻尼耗散将在后续运动中继续累计",
                  (rect.centerx, rect.bottom - 22), FONT_SMALL, ACCENT_3,
                  anchor="center")

    def draw(self, surface, rect):
        """将当前讲解阶段绘制为过程图。"""
        rect = pygame.Rect(rect)
        rounded_rect(surface, rect, (8, 13, 29), 16, 2, (100, 145, 220))
        draw_text(surface, "碰撞过程重演", (rect.x + 18, rect.y + 12), FONT_BIG, TEXT)
        draw_text(surface, "Space 跳过本次讲解", (rect.right - 18, rect.y + 18),
                  FONT_SMALL, ACCENT_2, anchor="topright")
        labels = ("① 速度交换", "② 角动量", "③ 能量流")
        for index, label in enumerate(labels):
            color = ACCENT_3 if index == self.phase_index else MUTED
            card_x = rect.x + 176 + index * 80
            card = pygame.Rect(card_x, rect.y + 10, 76, 27)
            rounded_rect(surface, card, (24, 35, 62), 7, 1, color)
            draw_text(surface, label, card.center, FONT_TINY, color, anchor="center")
        pygame.draw.rect(surface, (30, 43, 72),
                         (rect.x + 18, rect.y + 43, rect.w - 36, 4), border_radius=2)
        progress_w = int((rect.w - 36) * clamp(self.elapsed / self.total_duration, 0.0, 1.0))
        pygame.draw.rect(surface, ACCENT_3,
                         (rect.x + 18, rect.y + 43, progress_w, 4), border_radius=2)

        if self.phase == "velocity":
            self._draw_velocity(surface, rect)
        elif self.phase == "momentum":
            self._draw_momentum(surface, rect)
        else:
            self._draw_energy(surface, rect)
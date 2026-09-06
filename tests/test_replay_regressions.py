"""Replay visual-state, physics-clock, and bottom-layout regressions."""

from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from config import LAYOUT  # noqa: E402
from main import App  # noqa: E402
from models.ball_rod import BallHitsRod  # noqa: E402
from replay.timeline import ReplayFrame, ReplayTimeline  # noqa: E402
from render.replay_fx import draw_impact_fx  # noqa: E402


class ReplayRegressionTest(unittest.TestCase):
    def make_model(self, **values):
        model = BallHitsRod()
        # 旧参数 vc 表示碰撞点线速度：其余参数就位后按最终 h 换算成目标
        # 角速度 omega_c，保持既有场景与断言的数值不变。
        vc = values.pop("vc", None)
        for key, value in values.items():
            model.set_control_value(key, value)
        if vc is not None:
            model.set_control_value("omega_c", vc / model.current_h())
        model.reset()
        return model

    def test_visual_state_is_recorded_and_stateless_fx_is_repeatable(self):
        model = self.make_model(vc=3.0, h=0.72)
        model.jump_to_collision()
        before, after = model.replay.frames[-2:]
        self.assertEqual(before.event, "collision_before")
        self.assertEqual(after.event, "collision_after")
        self.assertGreater(before.impact_strength, 0.0)
        self.assertEqual(before.impact_flash, 1.0)
        self.assertEqual(after.impact_flash, 0.0)
        self.assertAlmostEqual(after.time - before.time, 0.15)

        first = pygame.Surface((120, 120), pygame.SRCALPHA)
        second = pygame.Surface((120, 120), pygame.SRCALPHA)
        draw_impact_fx(first, (60, 60), 0.65, before.impact_strength)
        draw_impact_fx(second, (60, 60), 0.65, before.impact_strength)
        self.assertEqual(pygame.image.tobytes(first, "RGBA"),
                         pygame.image.tobytes(second, "RGBA"))

    def test_c_key_fast_forward_preserves_physics_clock_and_collision_time(self):
        model = self.make_model(vc=3.0, h=0.72)
        model.jump_to_collision()
        result = model.last_result
        self.assertGreater(result.impact_time, 0.0)
        self.assertLess(result.impact_time, 120.0)
        self.assertAlmostEqual(model.t, result.impact_time + model.MAX_SUBSTEP)
        self.assertAlmostEqual(
            model.replay.frames[-2].time, result.impact_time, places=12
        )

    def test_damping_uses_physics_time_not_display_slow_motion_window(self):
        model = self.make_model(vc=3.0, h=0.72, tau0=0.05)
        model.jump_to_collision()
        initial = model.mechanical_energy()
        for _ in range(240):
            model.step(1.0 / 240.0)
        self.assertGreater(model.damping_energy, 0.0)
        self.assertLess(model.mechanical_energy(), initial)
        self.assertAlmostEqual(
            initial - model.mechanical_energy(), model.damping_energy, places=7
        )
        self.assertGreater(model.replay.duration, model.t)

    def test_footer_layout_rects_do_not_overlap(self):
        app = App()
        footer = pygame.Rect(LAYOUT.footer)
        formula = pygame.Rect(LAYOUT.formula)
        action = pygame.Rect(LAYOUT.action)
        self.assertTrue(footer.contains(formula))
        self.assertTrue(footer.contains(action))
        self.assertFalse(formula.colliderect(action))
        self.assertTrue(app.btn_start.rect.colliderect(app.btn_reset.rect) is False)
        self.assertTrue(app.btn_reset.rect.colliderect(app.btn_snap.rect) is False)
        self.assertTrue(footer.contains(app.btn_start.rect))
        self.assertTrue(footer.contains(app.btn_snap.rect))


if __name__ == "__main__":
    unittest.main()

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
from models.ball_ball import BallBallCollision  # noqa: E402
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
        self.assertEqual(after.impact_flash, 1.0)
        self.assertAlmostEqual(after.time - before.time, 0.0)

        first = pygame.Surface((120, 120), pygame.SRCALPHA)
        second = pygame.Surface((120, 120), pygame.SRCALPHA)
        draw_impact_fx(first, (60, 60), 0.65, before.impact_strength)
        draw_impact_fx(second, (60, 60), 0.65, before.impact_strength)
        self.assertEqual(pygame.image.tobytes(first, "RGBA"),
                         pygame.image.tobytes(second, "RGBA"))

    def test_two_ball_replay_is_read_only_and_collision_is_a_point(self):
        model = BallBallCollision()
        model.jump_to_collision()
        model.step(0.2)
        impact_time = model.last_result["impact_time"]
        boundaries = [frame for frame in model.replay.frames
                      if frame.event is not None]
        self.assertEqual([item.event for item in boundaries],
                         ["collision_before", "collision_after"])
        self.assertEqual(boundaries[0].time, boundaries[1].time)
        self.assertAlmostEqual(boundaries[0].time, impact_time)

        physical = (model.x1, model.x2, model.v1, model.v2, model.t)
        instant = model.seek_replay(impact_time, side="after")
        self.assertEqual(instant.event, "collision_after")
        self.assertEqual(instant.impact_flash, 1.0)
        self.assertEqual((model.x1, model.x2, model.v1, model.v2, model.t),
                         physical)
        decay = model.seek_replay(impact_time + 0.05, side="after")
        self.assertIsNone(decay.event)
        self.assertGreater(decay.impact_flash, 0.0)
        self.assertLess(decay.impact_flash, 1.0)

    def test_replay_impact_fx_is_blue(self):
        surface = pygame.Surface((120, 120), pygame.SRCALPHA)
        draw_impact_fx(surface, (60, 60), 1.0, 2.0)
        colors = [surface.get_at((x, y)) for y in range(120)
                  for x in range(120)]
        self.assertTrue(any(c.a and c.b > c.r + 40 for c in colors))

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

    def test_replay_duration_tracks_physics_time_without_event_extension(self):
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
        self.assertLessEqual(model.replay.duration, model.t)
        self.assertLessEqual(model.t - model.replay.duration,
                             model.replay.sample_interval + model.MAX_SUBSTEP)

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

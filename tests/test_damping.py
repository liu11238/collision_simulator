"""碰撞后转轴阻尼和耗散能量账本测试。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.ball_rod import BallHitsRod  # noqa: E402


class FrictionTest(unittest.TestCase):
    def make_model(self, **values):
        model = BallHitsRod()
        for key, value in values.items():
            model.set_control_value(key, value)
        model.reset()
        return model

    def run_after(self, model, duration=1.0):
        model.jump_to_collision()
        model.running = True
        steps = int(duration * 240)
        for _ in range(steps):
            model.step(1.0 / 240.0)

    def test_zero_friction_preserves_post_collision_energy(self):
        model = self.make_model(vc=3.0, h=0.72, tau0=0.0)
        model.jump_to_collision()
        initial = model.mechanical_energy()
        self.run_after(model, 1.5)
        self.assertAlmostEqual(model.damping_energy, 0.0, places=12)
        self.assertAlmostEqual(model.mechanical_energy(), initial, places=8)

    def test_constant_friction_reduces_energy_and_records_loss(self):
        model = self.make_model(vc=3.0, h=0.72, tau0=0.05)
        model.jump_to_collision()
        initial = model.mechanical_energy()
        self.run_after(model, 2.0)
        final = model.mechanical_energy()

        self.assertGreater(model.damping_energy, 0.0)
        self.assertLess(final, initial)
        self.assertAlmostEqual(initial - final, model.damping_energy, places=7)

    def test_energy_account_closes_after_friction_motion(self):
        model = self.make_model(vc=3.0, h=0.72, e=0.6, tau0=0.05)
        model.jump_to_collision()
        for _ in range(480):
            model.step(1.0 / 240.0)

        account = model.energy_breakdown()
        self.assertAlmostEqual(
            account["initial"],
            account["mechanical"] + account["collision"] + account["damping"],
            places=7,
        )
        self.assertAlmostEqual(
            account["collision"], model.last_result["collision_energy_loss"], places=12
        )

    def test_friction_does_not_change_instantaneous_collision(self):
        no_friction = self.make_model(vc=3.0, h=0.72, tau0=0.0)
        friction = self.make_model(vc=3.0, h=0.72, tau0=0.05)
        no_friction.jump_to_collision()
        friction.jump_to_collision()

        for key in ("v_after", "omega_after", "impulse", "energy_after"):
            self.assertAlmostEqual(no_friction.last_result[key], friction.last_result[key], places=12)

    def test_collision_explanation_freezes_physics_until_complete(self):
        model = self.make_model(vc=3.0, h=0.72, tau0=0.02)
        model.phase = "swinging"
        model.running = True
        model.begin_collision(explain=True)
        self.assertEqual(model.phase, "impact_explain")
        self.assertTrue(model.collided)
        snapshot = model.last_result
        frozen = (model.theta, model.omega, model.ball_v, model.t)

        model.step(0.5)
        self.assertEqual((model.theta, model.omega, model.ball_v, model.t), frozen)
        self.assertIs(model.last_result, snapshot)
        self.assertEqual(snapshot["contact_before"], snapshot.contact_before)
        self.assertIn("collision_energy_loss", snapshot.keys())

        model.skip_explanation()
        self.assertEqual(model.phase, "after")
        self.assertAlmostEqual(model.omega, snapshot["omega_after"], places=12)

    def test_collision_explanation_auto_commits(self):
        model = self.make_model(vc=3.0, h=0.72, tau0=0.02)
        model.begin_collision(explain=True)
        duration = model.impact_explainer.total_duration
        model.running = True
        model.step(duration + 0.01)
        self.assertEqual(model.phase, "after")
        self.assertIsNone(model.impact_explainer)


if __name__ == "__main__":
    unittest.main()

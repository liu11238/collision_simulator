"""守恒量、能量账本和回放细分字段的回归测试。"""

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

import pygame  # noqa: E402

from models.ball_rod import BallHitsRod  # noqa: E402
from render.energy import EnergyState, draw_energy_flow  # noqa: E402
from render.replay_fx import draw_friction_heat_fx  # noqa: E402


class EnergyRefactorTest(unittest.TestCase):
    def make_model(self, **values):
        model = BallHitsRod()
        for key, value in values.items():
            model.set_control_value(key, value)
        model.reset()
        return model

    def test_collision_report_separates_angular_conservation_from_energy_loss(self):
        model = self.make_model(vc=3.0, h=0.72, e=0.6)
        model.jump_to_collision()
        result = model.last_result
        report = result.conservation_report()

        self.assertAlmostEqual(report["angular_momentum_error"], 0.0, places=10)
        self.assertAlmostEqual(report["energy_dissipation"], result.collision_energy_loss)
        self.assertAlmostEqual(report["energy_change"], -result.collision_energy_loss)
        self.assertAlmostEqual(report["energy_residual"], 0.0, places=10)
        self.assertNotAlmostEqual(report["energy_change"], 0.0, places=8)

    def test_energy_state_keeps_legacy_account_access(self):
        model = self.make_model(vc=3.0, h=0.72, e=0.6, tau0=0.05)
        model.jump_to_collision()
        model.running = True
        for _ in range(240):
            model.step(1.0 / 240.0)
        account = model.energy_breakdown()

        self.assertIsInstance(account, EnergyState)
        self.assertAlmostEqual(account["collision"], account.collision_loss)
        self.assertAlmostEqual(account["damping"], account.friction_heat)
        self.assertAlmostEqual(
            account.initial,
            account.mechanical + account.collision_loss
            + account.friction_heat + account.residual,
            places=7,
        )

    def test_replay_frames_record_energy_and_angular_momentum_components(self):
        model = self.make_model(vc=3.0, h=0.72, e=0.6)
        model.jump_to_collision()
        before, after = model.replay.frames[-2:]
        result = model.last_result

        self.assertAlmostEqual(before.rod_kinetic_energy, result.rod_ke_before)
        self.assertAlmostEqual(before.ball_kinetic_energy, result.ball_ke_before)
        self.assertAlmostEqual(after.rod_kinetic_energy, result.rod_ke_after)
        self.assertAlmostEqual(after.ball_kinetic_energy, result.ball_ke_after)
        self.assertAlmostEqual(after.collision_energy_loss, result.collision_energy_loss)
        self.assertAlmostEqual(before.angular_momentum, result.total_L_before)
        self.assertAlmostEqual(after.angular_momentum, result.total_L_after)

    def test_energy_and_heat_effects_are_deterministic(self):
        state = EnergyState(
            initial=8.0, mechanical=5.0, rod_kinetic=2.0,
            ball_kinetic=1.0, potential=2.0,
            collision_loss=2.0, friction_heat=1.0, residual=0.0,
        )
        first = pygame.Surface((400, 160), pygame.SRCALPHA)
        second = pygame.Surface((400, 160), pygame.SRCALPHA)
        draw_energy_flow(first, pygame.Rect(0, 0, 400, 126), state)
        draw_energy_flow(second, pygame.Rect(0, 0, 400, 126), state)
        self.assertEqual(pygame.image.tobytes(first, "RGBA"),
                         pygame.image.tobytes(second, "RGBA"))

        first.fill((0, 0, 0, 0))
        second.fill((0, 0, 0, 0))
        draw_friction_heat_fx(first, (200, 80), 1.25)
        draw_friction_heat_fx(second, (200, 80), 1.25)
        self.assertEqual(pygame.image.tobytes(first, "RGBA"),
                         pygame.image.tobytes(second, "RGBA"))


if __name__ == "__main__":
    unittest.main()
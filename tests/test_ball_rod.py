"""质点—细杆模型的无头回归测试。"""

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

from models.ball_rod import BallHitsRod  # noqa: E402
from models.ball_ball import BallBallCollision  # noqa: E402


class BallRodTest(unittest.TestCase):
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

    def run_to_collision(self, model):
        model.phase = "swinging"
        model.running = True
        for _ in range(3000):
            model.step(1.0 / 240.0)
            if model.collided:
                return
        self.fail("模型未在测试时间内到达碰撞位置")

    def test_target_collision_point_speed(self):
        model = self.make_model(vc=4.2, h=0.8)
        self.run_to_collision(model)
        result = model.last_result
        self.assertAlmostEqual(result["contact_before"], 4.2, places=9)
        self.assertAlmostEqual(model.collision_point_speed(),
                               abs(result["contact_after"]), places=9)

    def test_gravity_release_angle_and_energy(self):
        model = self.make_model(vc=2.0, h=0.8, g=9.8)
        self.assertFalse(model.uses_initial_speed)
        self.assertGreater(model.initial_angle_deg, 0.0)
        self.assertLess(model.initial_angle_deg, 90.0)

        expected = model.sliders["M"].value * model.sliders["g"].value
        expected *= model.sliders["L"].value / 2.0
        expected *= 1.0 - math.sin(model.initial_theta)
        self.assertAlmostEqual(model.initial_energy, expected, places=10)

        model.phase = "swinging"
        model.running = True
        for _ in range(200):
            model.step(1.0 / 240.0)
            if model.collided:
                break
        self.assertTrue(model.collided)
        self.assertLess(
            abs(model.last_result["energy_before"] - model.initial_energy),
            1e-9,
        )

    def test_potential_zero_and_percussion_center(self):
        model = self.make_model(g=9.8, L=1.2)
        self.assertAlmostEqual(model.gravity_potential(math.pi / 2.0), 0.0, places=12)
        self.assertGreater(model.gravity_potential(0.0), 0.0)
        self.assertAlmostEqual(model.percussion_center(), 2.0 * 1.2 / 3.0, places=12)

    def test_friction_torque_is_constant_and_opposes_rotation(self):
        model = self.make_model(tau0=0.04)
        self.assertAlmostEqual(model.friction_torque(2.5), -0.04, places=12)
        self.assertAlmostEqual(model.friction_torque(0.25), -0.04, places=12)
        self.assertAlmostEqual(model.friction_torque(-2.5), 0.04, places=12)
        self.assertAlmostEqual(model.friction_torque(0.0), 0.0, places=12)

    def test_legacy_b_parameter_maps_to_constant_friction(self):
        model = self.make_model(b=0.04)
        self.assertAlmostEqual(model.friction_moment(), 0.04, places=12)
        self.assertAlmostEqual(model.damping_torque(2.5), -0.04, places=12)

    def test_static_friction_only_locks_when_gravity_torque_is_small(self):
        model = self.make_model(tau0=0.04, g=0.0)
        self.assertTrue(model._can_stick(math.pi / 2.0, 1.0e-4))

        model.set_control_value("g", 9.8)
        model.set_control_value("tau0", 0.04)
        self.assertFalse(model._can_stick(0.0, 1.0e-4))

    def test_percussion_center_has_zero_pivot_impulse(self):
        model = self.make_model(vc=3.0, h=2.0 / 3.0)
        model.jump_to_collision()
        self.assertAlmostEqual(model.last_result.pivot_impulse, 0.0, places=10)

    def test_both_models_keep_physical_substeps_under_limit(self):
        rod = self.make_model(anim_speed=2.5)
        rod.jump_to_collision()
        rod_steps = []
        original_rod_step = rod._advance_simulation_substep

        def record_rod_step(sub):
            rod_steps.append(sub)
            original_rod_step(sub)

        rod._advance_simulation_substep = record_rod_step
        rod.step(1.0 / 240.0)
        self.assertEqual(len(rod_steps), 5)
        self.assertLessEqual(max(rod_steps), rod.MAX_SUBSTEP)

        balls = BallBallCollision()
        balls.set_control_value("anim_speed", 2.5)
        balls.reset()
        balls.phase = "moving"
        balls.running = True
        ball_steps = []
        original_ball_step = balls._advance_simulation_substep

        def record_ball_step(sub):
            ball_steps.append(sub)
            original_ball_step(sub)

        balls._advance_simulation_substep = record_ball_step
        balls.step(1.0 / 240.0)
        self.assertEqual(len(ball_steps), 5)
        self.assertLessEqual(max(ball_steps), balls.MAX_SUBSTEP)

    def test_excess_speed_uses_90_degree_plus_initial_speed(self):
        model = self.make_model(vc=10.0, h=0.8, g=9.8)
        self.assertTrue(model.uses_initial_speed)
        self.assertAlmostEqual(model.initial_angle_deg, 90.0, places=12)
        self.assertGreater(model.initial_omega, 0.0)
        self.assertAlmostEqual(model._swing_speed(math.pi / 2.0),
                               model.target_omega, places=10)

    def test_zero_gravity_uses_initial_speed(self):
        model = self.make_model(vc=4.0, h=0.8, g=0.0)
        self.assertTrue(model.uses_initial_speed)
        self.assertAlmostEqual(model.initial_angle_deg, 90.0, places=12)
        self.assertAlmostEqual(model.initial_omega, model.target_omega, places=12)
        self.run_to_collision(model)
        self.assertAlmostEqual(model.last_result["contact_before"], 4.0, places=9)

    def test_collision_angular_momentum_and_elastic_energy(self):
        model = self.make_model(vc=3.0, h=0.72)
        model.jump_to_collision()
        result = model.last_result
        self.assertAlmostEqual(result["total_L_before"],
                               result["total_L_after"], places=10)
        self.assertAlmostEqual(result["ke_before"], result["ke_after"], places=10)
        self.assertAlmostEqual(result["relative_after"],
                               -result["relative_before"], places=10)
        self.assertAlmostEqual(result.angular_momentum_error, 0.0, places=10)
        self.assertAlmostEqual(result.restitution_error, 0.0, places=10)
        self.assertAlmostEqual(result.energy_residual, 0.0, places=10)
        self.assertAlmostEqual(result.collision_loss_error, 0.0, places=10)

    def test_restitution_coefficient(self):
        model = self.make_model(vc=3.0, h=0.72, e=0.5)
        model.jump_to_collision()
        result = model.last_result
        self.assertAlmostEqual(result["e"], 0.5, places=12)
        self.assertAlmostEqual(
            result["relative_after"],
            -0.5 * result["relative_before"],
            places=10,
        )
        self.assertAlmostEqual(result["total_L_before"],
                               result["total_L_after"], places=10)
        self.assertLess(result["energy_after"], result["energy_before"])

    def test_zero_target_speed_stays_at_collision_position(self):
        model = self.make_model(vc=0.0, g=0.0)
        self.assertAlmostEqual(model.initial_angle_deg, 0.0, places=12)
        self.assertEqual(model.initial_omega, 0.0)
        model.jump_to_collision()
        self.assertTrue(model.collided)
        self.assertAlmostEqual(model.last_result["contact_before"], 0.0, places=12)

    def test_replay_seek_is_read_only_and_playback_ends_cleanly(self):
        model = self.make_model(vc=3.0, h=0.72, e=0.6)
        model.jump_to_collision()
        model.step(0.20)
        self.assertGreater(model.replay.duration, 0.0)
        physical_state = (model.theta, model.omega, model.ball_x,
                          model.ball_v, model.t)
        frames = tuple(model.replay.frames)

        model.seek_replay(model.replay.duration * 0.5)
        self.assertEqual((model.theta, model.omega, model.ball_x,
                          model.ball_v, model.t), physical_state)
        self.assertEqual(tuple(model.replay.frames), frames)

        model.replay.playing = True
        model.replay_playback_step(model.replay.duration + 1.0)
        self.assertFalse(model.replay.playing)
        self.assertAlmostEqual(model.replay.cursor, model.replay.duration)
        self.assertEqual(model.replay_frame().event, "collision_after" if
                         model.replay.duration == 0.0 else None)

    def test_rod_trail_has_age_and_fades_after_motion_stops(self):
        model = self.make_model(vc=3.0, h=0.72, e=0.6)
        model.explain_enabled = False
        model.jump_to_collision()
        model.step(1.0 / 60.0)
        self.assertTrue(model.rod_trail)
        self.assertTrue(all(hasattr(point, "age") for point in model.rod_trail))
        model.running = False
        for _ in range(60):
            model.step(model.TRAIL_LIFETIME / 60.0)
        self.assertFalse(model.rod_trail)


    def test_target_control_is_angular_velocity(self):
        model = self.make_model(h=0.8, omega_c=5.0)
        self.assertAlmostEqual(model.target_angular_speed(), 5.0, places=12)
        self.assertAlmostEqual(model.target_collision_speed(), 4.0, places=12)

        # h 改变时角速度不变，碰撞点线速度按 h 缩放。
        model.set_control_value("h", 0.4)
        self.assertAlmostEqual(model.target_angular_speed(), 5.0, places=12)
        self.assertAlmostEqual(model.target_collision_speed(), 2.0, places=12)

        # 旧参数名 vc（碰撞点线速度）按当前 h 换算成角速度。
        model.set_control_value("vc", 3.0)
        self.assertAlmostEqual(model.target_angular_speed(), 7.5, places=12)
        self.assertAlmostEqual(model.target_collision_speed(), 3.0, places=12)

if __name__ == "__main__":
    unittest.main()

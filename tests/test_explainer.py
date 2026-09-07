"""碰撞讲解器的插值、守恒和无头绘制测试。"""

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

from main import App  # noqa: E402
from models.ball_rod import BallHitsRod  # noqa: E402
from presentation.collision_explainer import CollisionExplainer  # noqa: E402


class ExplainerTest(unittest.TestCase):
    def make_model(self):
        model = BallHitsRod()
        model.set_control_value("h", 0.72)
        model.set_control_value("omega_c", 3.0 / 0.72)
        model.set_control_value("e", 0.6)
        model.reset()
        model.phase = "swinging"
        model.theta = math.pi / 2.0
        model.omega = model.target_omega
        model.begin_collision(explain=True)
        return model

    def test_interpolation_endpoints(self):
        model = self.make_model()
        explainer = model.impact_explainer
        snapshot = model.last_result

        self.assertEqual(explainer.PHASE_DURATION, 2.2)
        self.assertEqual(explainer.phase, "velocity")
        self.assertAlmostEqual(explainer.ball_v_display(), snapshot.u_before)
        self.assertAlmostEqual(explainer.contact_speed_display(), snapshot.contact_before)

        explainer.elapsed = explainer.total_duration
        self.assertEqual(explainer.phase, "energy")
        self.assertTrue(explainer.complete)
        self.assertAlmostEqual(explainer.ball_v_display(), snapshot.v_after)
        self.assertAlmostEqual(explainer.contact_speed_display(), snapshot.contact_after)
        self.assertAlmostEqual(explainer.rod_L_display(), snapshot.rod_L_after)
        self.assertAlmostEqual(explainer.ball_MRV_display(), snapshot.ball_MRV_after)
        self.assertAlmostEqual(explainer.impulse_display(), snapshot.impulse)

    def test_momentum_display_remains_conserved(self):
        model = self.make_model()
        explainer = model.impact_explainer
        snapshot = model.last_result

        for elapsed in (0.0, 0.25, 1.1, 2.2, 2.8, 3.9, 4.4, 5.5, 6.6):
            explainer.elapsed = elapsed
            self.assertAlmostEqual(
                explainer.rod_L_display() + explainer.ball_MRV_display(),
                snapshot.total_L_before,
                places=10,
            )

    def test_momentum_bar_scales_are_fixed_at_initialization(self):
        model = self.make_model()
        explainer = model.impact_explainer
        scales = (explainer.L_scale, explainer.rod_L_scale, explainer.ball_L_scale)
        explainer.elapsed = 1.0
        self.assertEqual(scales, (explainer.L_scale, explainer.rod_L_scale,
                                  explainer.ball_L_scale))

    def test_display_speed_is_continuous_at_stage_boundaries(self):
        model = self.make_model()
        explainer = model.impact_explainer
        for boundary in (explainer.PHASE_DURATION, 2.0 * explainer.PHASE_DURATION):
            before = boundary - 1e-9
            after = boundary + 1e-9
            explainer.elapsed = before
            values_before = (
                explainer.ball_v_display(),
                explainer.contact_speed_display(),
                explainer.rod_omega_display(),
                explainer.ball_x_display(),
            )
            explainer.elapsed = after
            values_after = (
                explainer.ball_v_display(),
                explainer.contact_speed_display(),
                explainer.rod_omega_display(),
                explainer.ball_x_display(),
            )
            for left, right in zip(values_before, values_after):
                self.assertAlmostEqual(left, right, places=6)

    def test_energy_display_closes_at_every_intermediate_time(self):
        model = self.make_model()
        explainer = model.impact_explainer
        for elapsed in (0.0, 2.2, 3.0, 4.4, 5.1, 6.6):
            explainer.elapsed = elapsed
            parts = explainer.energy_parts_display()
            self.assertAlmostEqual(
                parts["rod"] + parts["ball"] + parts["loss"],
                parts["total"],
                places=10,
            )

    def test_focus_strength_has_a_stable_platform(self):
        model = self.make_model()
        explainer = model.impact_explainer
        explainer.elapsed = 0.5 * explainer.total_duration
        self.assertAlmostEqual(explainer.focus_strength(), 1.0, places=12)
        explainer.elapsed = 0.65 * explainer.total_duration
        self.assertAlmostEqual(explainer.focus_strength(), 1.0, places=12)

    def test_energy_display_parts_have_expected_endpoints(self):
        model = self.make_model()
        explainer = model.impact_explainer
        snapshot = model.last_result

        start = explainer.energy_parts_display()
        self.assertAlmostEqual(start["rod"], snapshot.rod_ke_before)
        self.assertAlmostEqual(start["ball"], snapshot.ball_ke_before)
        self.assertAlmostEqual(start["loss"], 0.0)
        explainer.elapsed = explainer.total_duration
        end = explainer.energy_parts_display()
        self.assertAlmostEqual(end["rod"], snapshot.rod_ke_after)
        self.assertAlmostEqual(end["ball"], snapshot.ball_ke_after)
        self.assertAlmostEqual(end["loss"], snapshot.collision_energy_loss)

    def test_stage_update_and_physics_freeze(self):
        model = self.make_model()
        frozen = (model.theta, model.omega, model.ball_v, model.t)
        explainer = model.impact_explainer

        self.assertFalse(explainer.update(1.0))
        self.assertEqual(explainer.phase, "velocity")
        self.assertFalse(explainer.update(1.3))
        self.assertEqual(explainer.phase, "momentum")
        self.assertTrue(explainer.update(explainer.total_duration))
        self.assertEqual((model.theta, model.omega, model.ball_v, model.t), frozen)

    def test_impact_effects_spawn_once_across_skip_and_auto_commit(self):
        model = self.make_model()
        effect_count = (len(model.particles), len(model.shockwaves))
        model.skip_explanation()
        self.assertEqual((len(model.particles), len(model.shockwaves)), effect_count)

        model = self.make_model()
        effect_count = (len(model.particles), len(model.shockwaves))
        model.running = True
        model.impact_explainer.elapsed = model.impact_explainer.total_duration - 0.001
        model.step(0.002)
        self.assertEqual(model.phase, "after")
        self.assertEqual((len(model.particles), len(model.shockwaves)), effect_count)

    def test_headless_scene_and_explainer_draw(self):
        app = App()
        model = app.models[1]
        model.set_control_value("h", 0.72)
        model.set_control_value("omega_c", 3.0 / 0.72)
        model.reset()
        model.phase = "swinging"
        model.theta = math.pi / 2.0
        model.omega = model.target_omega
        model.begin_collision(explain=True)
        surface = pygame.Surface((1280, 960), pygame.SRCALPHA)

        for elapsed in (0.0, 2.2, 4.4, 6.6):
            model.impact_explainer.elapsed = elapsed
            model.draw_scene()
            model.draw_ui()
            model.impact_explainer.draw(surface, pygame.Rect(38, 376, 730, 228))


    def make_ready_model(self):
        model = BallHitsRod()
        model.set_control_value("h", 0.72)
        model.set_control_value("omega_c", 3.0 / 0.72)
        model.set_control_value("e", 0.6)
        model.reset()
        model.phase = "swinging"
        model.theta = math.pi / 2.0
        model.omega = model.target_omega
        return model

    def test_panel_toggle_defaults_off(self):
        model = self.make_ready_model()
        self.assertFalse(model.toggles["explain"].value)
        self.assertFalse(model.explain_enabled)

    def test_panel_toggle_click_enables_explanation(self):
        model = self.make_ready_model()
        toggle = model.toggles["explain"]
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                   pos=toggle.rect.center, button=1)

        self.assertTrue(model.handle_toggles(event))
        self.assertTrue(toggle.value)
        self.assertTrue(model.explain_enabled)

        # 开关开启后碰撞进入讲解冻结阶段。
        model.begin_collision()
        self.assertIsNotNone(model.impact_explainer)
        self.assertEqual(model.phase, "impact_explain")

        # 再次点击关闭；重新初始化后碰撞直接提交。
        self.assertTrue(model.handle_toggles(event))
        self.assertFalse(model.explain_enabled)
        model.reset()
        model.phase = "swinging"
        model.theta = math.pi / 2.0
        model.omega = model.target_omega
        model.begin_collision()
        self.assertIsNone(model.impact_explainer)
        self.assertEqual(model.phase, "after")

    def test_toggle_stays_in_sync_with_e_key(self):
        model = self.make_ready_model()
        model.toggle_explanation()
        self.assertTrue(model.toggles["explain"].value)
        self.assertTrue(model.explain_enabled)
        model.toggle_explanation()
        self.assertFalse(model.toggles["explain"].value)
        self.assertFalse(model.explain_enabled)

        # 面板开关开启后按 E 重新关闭，两边状态始终保持一致。
        toggle = model.toggles["explain"]
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                   pos=toggle.rect.center, button=1)
        model.handle_toggles(event)
        self.assertTrue(model.explain_enabled)
        model.toggle_explanation()
        self.assertFalse(model.explain_enabled)
        self.assertFalse(toggle.value)


if __name__ == "__main__":
    unittest.main()

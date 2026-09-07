"""Regression gates for real motion, camera framing and physical isolation."""
import math
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from config import BALL1_COLOR, LAYOUT, ROD_COLOR
from core import display
from main import App
from models.ball_rod import BallHitsRod
from presentation import impact_panel


class ImpactMotionTests(unittest.TestCase):
    def setUp(self):
        self.size = (LAYOUT.width, LAYOUT.height)

    def tearDown(self):
        LAYOUT.apply(*self.size)
        display.resize_display(*self.size)

    def rod(self, **values):
        model = BallHitsRod()
        for key, value in values.items():
            model.set_control_value(key, value)
        model.reset()
        model.theta = math.pi / 2
        model.omega = model.target_omega
        model.begin_collision(explain=True)
        model.running = True
        return model

    def test_camera_zooms_and_returns_without_clipping_subjects(self):
        for width, height in ((1280, 720), (1600, 900), (1920, 1080)):
            LAYOUT.apply(width, height)
            for length in (.25, 1.0, 2.0):
                for ratio in (0.0, .72, 1.0):
                    model = self.rod(L=length, h=length * ratio)
                    explainer = model.impact_explainer
                    base = model.scene_camera()
                    cameras = []
                    for i in range(41):
                        explainer.elapsed = explainer.total_duration * i / 40
                        camera = model.scene_camera(explainer)
                        cameras.append(camera)
                        scene = pygame.Rect(LAYOUT.scene)
                        pivot = camera.point(0, 0)
                        tip = camera.point(0, length)
                        radius = max(12, int(model.ball_radius_world() * camera.scale))
                        bx, by = camera.point(explainer.ball_x_display(), model.current_h())
                        sphere = pygame.Rect(bx, by-radius, 2*radius+8, 2*radius)
                        self.assertTrue(scene.contains(sphere), (width, length, ratio, i))
                        self.assertGreaterEqual(pivot[1] - 38, scene.top)
                        self.assertLessEqual(tip[1] + 10, scene.bottom)
                    self.assertGreater(max(c.zoom for c in cameras), 1.05)
                    self.assertEqual(cameras[0], base)
                    self.assertEqual(cameras[-1], base)
                    # Camera motion has no discontinuous translation between
                    # neighboring samples (even when constrained at the edge).
                    for a, b in zip(cameras, cameras[1:]):
                        self.assertLess(math.dist(a.origin, b.origin), 25)

    def test_rendered_ball_remains_tangent_during_zoom(self):
        model = self.rod()
        from render.primitives import draw_matte_ball
        real_line = pygame.draw.line
        for elapsed in (0.0, .4, 1.4, 2.19):
            balls, rods = [], []
            def sphere(surface, center, radius, color):
                if surface is display.screen and color == BALL1_COLOR:
                    balls.append((center, radius))
                return draw_matte_ball(surface, center, radius, color)
            def line(surface, color, start, end, width=1):
                if surface is display.screen and color == ROD_COLOR:
                    rods.append((start, end, width))
                return real_line(surface, color, start, end, width)
            model.impact_explainer.elapsed = elapsed
            with patch('models.ball_rod.draw_matte_ball', sphere), patch('pygame.draw.line', line):
                display.begin_frame()
                model.draw_scene()
            center, radius = balls[-1]
            start, end, width = rods[-1]
            self.assertEqual(start[0], end[0])
            self.assertLessEqual(abs(center[0] - radius - (start[0] + width / 2)), 1)

    def test_each_stage_moves_in_scene_and_panel_including_elastic_energy(self):
        LAYOUT.apply(1280, 720)
        display.resize_display(1280, 720)
        app = App()
        for index, model in enumerate(app.models):
            app.switch_mode(index)
            model.toggle_explanation()
            model.start_pause()
            for _ in range(1000):
                model.step(1 / 60)
                if model.phase == 'impact_explain':
                    break
            self.assertEqual(model.phase, 'impact_explain')
            for stage in range(3):
                frames = []
                for offset in (.25, .75):
                    if index == 0:
                        model.explain_elapsed = 3 * (stage + offset)
                    else:
                        model.impact_explainer.elapsed = 2.2 * (stage + offset)
                    display.begin_frame()
                    model.draw_scene()
                    model.draw_interface()
                    # Ignore progress badges: the subject/diagram must move.
                    scene = pygame.Rect(LAYOUT.scene)
                    scene.y += 80
                    scene.h -= 80
                    panel = pygame.Rect(LAYOUT.replay_panel).inflate(-32, -20)
                    panel.y += 90
                    panel.h -= 115
                    frames.append(tuple(pygame.image.tobytes(display.screen.subsurface(r), 'RGB')
                                        for r in (scene, panel)))
                for a, b in zip(frames[0], frames[1]):
                    changed = sum(x != y for x, y in zip(a, b))
                    self.assertGreater(changed, 200, (index, stage))

    def test_panel_text_does_not_overlap_or_escape(self):
        LAYOUT.apply(1280, 720)
        model = self.rod()
        surface = pygame.Surface((800, 400))
        rect = pygame.Rect(20, 20, 380, 220)
        real_draw = impact_panel.draw_text
        for elapsed in (.5, 2.7, 4.9):
            labels = []
            def draw(*args, **kwargs):
                result = real_draw(*args, **kwargs)
                labels.append((args[1], result))
                return result
            model.impact_explainer.elapsed = elapsed
            with patch.object(impact_panel, 'draw_text', draw):
                model.impact_explainer.draw(surface, rect)
            for index, (text, bounds) in enumerate(labels):
                self.assertTrue(rect.contains(bounds), (elapsed, text, bounds))
                for other, box in labels[index+1:]:
                    self.assertFalse(bounds.colliderect(box), (elapsed, text, other))

    def test_animation_does_not_advance_physics_or_replay(self):
        model = self.rod(e=.6, tau0=.1)
        frozen = (model.theta, model.omega, model.ball_x, model.ball_v, model.t,
                  model.damping_energy, tuple(model.replay.frames))
        for _ in range(60):
            model.step(.1)
            model.draw_scene()
            model.draw_analysis_panel(pygame.Rect(20, 20, 380, 220))
        self.assertEqual(frozen, (model.theta, model.omega, model.ball_x,
                         model.ball_v, model.t, model.damping_energy, tuple(model.replay.frames)))
        snapshot = model.collision_snapshot
        model.step(1)
        self.assertEqual(model.phase, 'after')
        self.assertEqual(model.omega, snapshot.omega_after)
        self.assertEqual(model.ball_v, snapshot.v_after)
        self.assertEqual(model.camera_zoom, 1.0)

    def test_same_elapsed_time_draws_the_same_panel(self):
        model = self.rod()
        for elapsed in (.8, 3.1, 5.7):
            model.impact_explainer.elapsed = elapsed
            buffers = []
            for _ in range(2):
                surface = pygame.Surface((380, 220))
                model.impact_explainer.draw(surface, surface.get_rect())
                buffers.append(pygame.image.tobytes(surface, 'RGB'))
            self.assertEqual(*buffers)

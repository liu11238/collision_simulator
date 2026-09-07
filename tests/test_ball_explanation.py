import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest
from models.ball_ball import BallBallCollision
from models.ball_rod import BallHitsRod
from core.fonts import font_covers, get_font


class ExplanationTests(unittest.TestCase):
    def test_chinese_font(self):
        self.assertTrue(font_covers(get_font(16), '碰撞慢放讲解速度变化'))

    def test_freeze_and_resume(self):
        model = BallBallCollision()
        model.toggle_explanation()
        model.jump_to_collision()
        state = (model.x1, model.x2, model.v1, model.v2, model.t)
        self.assertEqual(model.phase, 'impact_explain')
        model.step(1)
        self.assertEqual(state, (model.x1, model.x2, model.v1, model.v2, model.t))
        model.step(8)
        self.assertEqual(model.phase, 'after')
        model.step(.01)
        self.assertGreater(model.t, state[-1])

    def test_disabled_same_result(self):
        a, b = BallBallCollision(), BallBallCollision()
        b.toggle_explanation()
        a.jump_to_collision()
        b.jump_to_collision()
        self.assertEqual(a.last_result, b.last_result)
        self.assertEqual(a.phase, 'after')
        self.assertEqual(b.phase, 'impact_explain')
        b.toggle_explanation()
        self.assertEqual(b.phase, 'after')

    def test_rod_disable_commits(self):
        model = BallHitsRod()
        model.toggle_explanation()
        model.begin_collision()
        model.toggle_explanation()
        self.assertEqual(model.phase, 'after')

    def test_explanation_defaults_off_for_both_models(self):
        for model in (BallBallCollision(), BallHitsRod()):
            self.assertFalse(model.toggles['explain'].value)

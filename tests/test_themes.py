import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest
import pygame
import theme
from main import App
from core import display
from config import LAYOUT

class ThemeTests(unittest.TestCase):
    def test_default_theme_is_blue(self):
        self.assertEqual(theme.current, 'blue')

    def test_switch_preserves_simulation_and_renders_both_models(self):
        app = App()
        for size in ((1280,720), (1600,900)):
            LAYOUT.apply(*size)
            for key in theme.NAMES:
                before = [(m.t, m.running) for m in app.models]
                app.set_theme(key)
                self.assertEqual(before, [(m.t, m.running) for m in app.models])
                for index, model in enumerate(app.models):
                    app.switch_mode(index)
                    display.begin_frame()
                    model.draw_scene()
                    model.draw_interface()
                for _, button in app.theme_buttons:
                    self.assertFalse(button.rect.colliderect(app.btn_sound.rect))
        app.set_theme('dark')

if __name__ == '__main__':
    unittest.main()

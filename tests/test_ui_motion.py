"""Small deterministic checks for alpha shadows and UI easing state."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest
from unittest.mock import patch

import pygame

from render.primitives import draw_soft_shadow
from ui.widgets import Button, Toggle


class UIMotionTests(unittest.TestCase):
    def test_shadow_contains_only_translucent_pixels(self):
        surface = pygame.Surface((100, 60), pygame.SRCALPHA)
        draw_soft_shadow(surface, (20, 20, 60, 12))
        alphas = [surface.get_at((x, y)).a
                  for y in range(surface.get_height())
                  for x in range(surface.get_width())]
        self.assertGreater(max(alphas), 0)
        self.assertLess(max(alphas), 255)

    def test_button_hover_and_press_ease(self):
        button = Button('测试', pygame.Rect(10, 10, 100, 32))
        surface = pygame.Surface((140, 60))
        with patch('pygame.mouse.get_pos', return_value=button.rect.center):
            button.draw(surface)
        self.assertGreater(button._hover_t, 0)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                   pos=button.rect.center, button=1)
        self.assertTrue(button.clicked(event))
        self.assertEqual(button._press_t, 1.0)

    def test_toggle_knob_uses_intermediate_position(self):
        toggle = Toggle(10, 10, False)
        toggle.value = True
        surface = pygame.Surface((80, 45))
        toggle.draw(surface)
        self.assertGreater(toggle._position, 0.0)
        self.assertLess(toggle._position, 1.0)


if __name__ == '__main__':
    unittest.main()

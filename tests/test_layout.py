"""1280×720 统一布局和旧控件接口的回归测试。"""

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
pygame.init()

from config import (BOTTOM_ACTION_H, BOTTOM_ACTION_Y, BOTTOM_CARD_H,
                    BOTTOM_CARD_Y, BOTTOM_FORMULA_H, BOTTOM_FORMULA_Y,
                    HEIGHT, LAYOUT, SIM_H, UI_H, WIDTH, build_layout)  # noqa: E402
from ui.widgets import TimelineSlider  # noqa: E402


class LayoutTest(unittest.TestCase):
    def rect(self, values):
        return pygame.Rect(values)

    def test_default_canvas_is_16_by_9_and_regions_are_inside(self):
        self.assertEqual((WIDTH, HEIGHT), (1280, 720))
        self.assertEqual(WIDTH / HEIGHT, 16 / 9)
        layout = build_layout()
        canvas = pygame.Rect(0, 0, WIDTH, HEIGHT)

        for name in ("scene_rect", "info_rect", "timeline_rect",
                     "analysis_rect", "controls_rect", "formula_rect",
                     "action_rect"):
            self.assertTrue(
                canvas.contains(self.rect(getattr(layout, name))),
                msg=f"{name} 超出画布边界",
            )

        self.assertFalse(
            self.rect(layout.analysis_rect).colliderect(
                self.rect(layout.controls_rect)
            )
        )
        self.assertFalse(
            self.rect(layout.scene_rect).colliderect(
                self.rect(layout.info_rect)
            )
        )

    def test_legacy_bottom_constants_still_form_valid_vertical_order(self):
        self.assertLess(BOTTOM_FORMULA_Y + BOTTOM_FORMULA_H, BOTTOM_ACTION_Y)
        self.assertLess(BOTTOM_ACTION_Y + BOTTOM_ACTION_H, BOTTOM_CARD_Y)
        self.assertLess(BOTTOM_CARD_Y + BOTTOM_CARD_H, SIM_H + UI_H)

    def test_layout_scales_for_another_canvas_without_negative_regions(self):
        layout = build_layout(1600, 900)
        canvas = pygame.Rect(0, 0, 1600, 900)
        for name in ("scene_rect", "info_rect", "timeline_rect",
                     "analysis_rect", "controls_rect"):
            rect = self.rect(getattr(layout, name))
            self.assertGreater(rect.w, 0)
            self.assertGreater(rect.h, 0)
            self.assertTrue(canvas.contains(rect))

    def test_timeline_slider_keeps_legacy_constructor(self):
        slider = TimelineSlider(24, SIM_H - 38, 858)
        self.assertEqual(slider.rect, pygame.Rect(24, SIM_H - 38, 858, 28))


if __name__ == "__main__":
    unittest.main()
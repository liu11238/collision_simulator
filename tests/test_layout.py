"""响应式布局回归：分辨率矩阵、区域包含/不重叠与旧接口兼容。"""

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

from config import (BAND_DEFAULT, BAND_MINIMUM, DEFAULT_HEIGHT, DEFAULT_WIDTH,
                    LAYOUT, MIN_HEIGHT, MIN_WIDTH, build_layout,
                    build_metrics)  # noqa: E402
from ui.widgets import TimelineSlider  # noqa: E402
from core.fonts import get_font  # noqa: E402
from render.text import draw_text_box  # noqa: E402

MATRIX = [
    (1280, 720),
    (1366, 768),
    (1440, 900),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
]

REGIONS = ("header", "tabs", "scene", "inspector", "timeline",
           "replay_panel", "parameter_panel", "energy_panel", "footer",
           "formula", "action")


class LayoutTest(unittest.TestCase):
    def check_layout(self, layout):
        canvas = pygame.Rect(0, 0, layout.width, layout.height)
        rects = {name: pygame.Rect(getattr(layout, name)) for name in REGIONS}
        for name, rect in rects.items():
            self.assertTrue(canvas.contains(rect),
                            msg=f"{name} 超出窗口边界: {rect}")
            self.assertGreater(rect.w, 0, msg=f"{name} 宽度非正")
            self.assertGreater(rect.h, 0, msg=f"{name} 高度非正")

        # 同层区域互不重叠。
        self.assertFalse(rects["scene"].colliderect(rects["inspector"]))
        bottom = ("replay_panel", "parameter_panel", "energy_panel")
        for i, left in enumerate(bottom):
            for right in bottom[i + 1:]:
                self.assertFalse(rects[left].colliderect(rects[right]),
                                 msg=f"{left} 与 {right} 重叠")
        # footer 子区域。
        self.assertTrue(rects["footer"].contains(rects["formula"]))
        self.assertTrue(rects["footer"].contains(rects["action"]))
        self.assertFalse(rects["formula"].colliderect(rects["action"]))
        # 垂直五带恰好铺满窗口。
        self.assertEqual(layout.header[1] + layout.header[3], layout.scene[1])
        self.assertEqual(layout.scene[1] + layout.scene[3], layout.timeline[1])
        self.assertEqual(layout.timeline[1] + layout.timeline[3],
                         layout.replay_panel[1])
        self.assertEqual(layout.replay_panel[1] + layout.replay_panel[3],
                         layout.footer[1])
        self.assertEqual(layout.footer[1] + layout.footer[3], layout.height)

    def test_default_window_is_1600_by_900(self):
        self.assertEqual((DEFAULT_WIDTH, DEFAULT_HEIGHT), (1600, 900))
        self.assertEqual((MIN_WIDTH, MIN_HEIGHT), (1280, 720))
        self.assertEqual(DEFAULT_WIDTH / DEFAULT_HEIGHT, 16 / 9)

    def test_resolution_matrix_regions_stay_inside_and_disjoint(self):
        for width, height in MATRIX:
            with self.subTest(size=(width, height)):
                layout = build_layout(width, height)
                self.assertEqual((layout.width, layout.height), (width, height))
                self.check_layout(layout)

    def test_default_layout_uses_reference_band_heights(self):
        layout = build_layout()
        self.assertEqual(layout.header[3], BAND_DEFAULT["header"])
        self.assertEqual(layout.scene[3], BAND_DEFAULT["scene"])
        self.assertEqual(layout.timeline[3], BAND_DEFAULT["timeline"])
        self.assertEqual(layout.replay_panel[3], BAND_DEFAULT["bottom"])
        self.assertEqual(layout.footer[3], BAND_DEFAULT["footer"])

    def test_minimum_window_uses_minimum_band_heights(self):
        layout = build_layout(MIN_WIDTH, MIN_HEIGHT)
        self.assertEqual(layout.header[3], BAND_MINIMUM["header"])
        self.assertEqual(layout.scene[3], BAND_MINIMUM["scene"])
        self.assertEqual(layout.timeline[3], BAND_MINIMUM["timeline"])
        self.assertEqual(layout.replay_panel[3], BAND_MINIMUM["bottom"])
        self.assertEqual(layout.footer[3], BAND_MINIMUM["footer"])

    def test_bottom_panel_widths_follow_density_proportions(self):
        layout = build_layout(1600, 900)
        total = (layout.replay_panel[2] + layout.parameter_panel[2]
                 + layout.energy_panel[2])
        self.assertEqual(total, 1600 - 2 * 16 - 2 * 16)
        for rect, frac in ((layout.replay_panel, 0.34),
                           (layout.parameter_panel, 0.36),
                           (layout.energy_panel, 0.30)):
            self.assertAlmostEqual(rect[2] / total, frac, delta=0.01)

    def test_inspector_width_clamped(self):
        self.assertEqual(build_layout(1600, 900).inspector[2], 408)
        self.assertLessEqual(build_layout(2560, 1440).inspector[2], 480)
        self.assertGreaterEqual(build_layout(1280, 720).inspector[2], 300)

    def test_density_tiers(self):
        self.assertEqual(build_metrics(1280, 720).density, "compact")
        self.assertEqual(build_metrics(1440, 900).density, "normal")
        self.assertEqual(build_metrics(1800, 1000).density, "spacious")
        self.assertLess(build_metrics(1280, 720).parameter_row_height,
                        build_metrics(1600, 900).parameter_row_height)

    def test_scale_stays_within_bounds(self):
        for width, height in MATRIX + [(2000, 600), (1000, 500)]:
            with self.subTest(size=(width, height)):
                metrics = build_metrics(width, height)
                self.assertGreaterEqual(metrics.scale, 0.80)
                self.assertLessEqual(metrics.scale, 1.25)

    def test_live_layout_apply_updates_in_place(self):
        handle = LAYOUT
        before = LAYOUT.scene
        LAYOUT.apply(1280, 720)
        try:
            self.assertIs(LAYOUT, handle)  # 句柄身份不变，导入方无需重绑
            self.assertIsInstance(LAYOUT.layout, type(before and handle.layout))
            self.assertNotEqual(LAYOUT.scene, before)
            self.assertEqual(LAYOUT.width, 1280)
            self.assertEqual(LAYOUT.scene_h, BAND_MINIMUM["scene"])
            self.assertEqual(LAYOUT.metrics.parameter_row_height,
                             build_metrics(1280, 720).parameter_row_height)
        finally:
            LAYOUT.apply(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        self.assertEqual(LAYOUT.scene_h, BAND_DEFAULT["scene"])

    def test_timeline_slider_keeps_legacy_constructor(self):
        slider = TimelineSlider(24, 40, 858)
        self.assertEqual(slider.rect, pygame.Rect(24, 40, 858, 28))

    def test_parameter_rows_have_two_line_minimum_height(self):
        for width, height in MATRIX:
            with self.subTest(size=(width, height)):
                self.assertGreaterEqual(
                    build_metrics(width, height).parameter_row_height, 44
                )

    def test_text_box_restores_parent_clip(self):
        surface = pygame.Surface((300, 180))
        parent = pygame.Rect(20, 20, 180, 100)
        surface.set_clip(parent)
        draw_text_box(surface, pygame.Rect(30, 30, 80, 40),
                      ["一段需要裁剪的文字"], get_font(14), (255, 255, 255))
        self.assertEqual(surface.get_clip(), parent)

    def test_rod_height_input_stays_in_parameter_panel(self):
        from models.ball_rod import BallHitsRod
        model = BallHitsRod()
        panel = pygame.Rect(LAYOUT.parameter_panel)
        self.assertTrue(panel.contains(model.input_boxes["h"].rect))
        height_slider = model.sliders["height_ratio"]
        self.assertEqual(model.input_boxes["h"].rect.y,
                         height_slider.y - min(29, LAYOUT.metrics.parameter_row_height - 13))


if __name__ == "__main__":
    unittest.main()

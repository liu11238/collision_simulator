"""字体回退渲染测试：缺字形检测、分段、复合渲染与宽度一致性。"""

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

from core.fonts import (BASE_DIR, font_covers, get_font,  # noqa: E402
                        get_symbol_font, render_text, split_font_runs,
                        text_width)
from render.primitives import draw_text  # noqa: E402
from render.text import measure_text  # noqa: E402

SYMBOLS = "✓✔√→≤≥²·ωΩψ"


class FontFallbackTest(unittest.TestCase):
    def test_base_dir_points_at_project_root(self):
        self.assertTrue((BASE_DIR / "core").is_dir())
        self.assertTrue((BASE_DIR / "tests").is_dir())

    @unittest.skipUnless(os.name == "nt", "Segoe UI Symbol 仅 Windows 提供")
    def test_symbol_fallback_font_available_on_windows(self):
        fallback = get_symbol_font(16)
        self.assertIsNotNone(fallback)
        self.assertTrue(font_covers(fallback, "✓√→"))

    def test_plain_text_stays_in_primary_font(self):
        font = get_font(16)
        runs = split_font_runs("中文 abc 123", font)
        self.assertEqual(len(runs), 1)
        self.assertIs(runs[0][0], font)

    def test_missing_glyphs_routed_to_fallback(self):
        font = get_font(16)
        for ch in SYMBOLS:
            text = f"a{ch}b"
            runs = split_font_runs(text, font)
            fallback_chars = ""
            for target, part in runs:
                self.assertTrue(font_covers(target, part))
                if target is not font:
                    fallback_chars += part
            missing = "".join(ch for ch in text
                              if not font_covers(font, ch))
            self.assertEqual(fallback_chars, missing)

    def test_metrics_false_positive_detected_as_missing(self):
        # 微软雅黑等字体对部分符号（如 ✓）的 metrics 返回非 None，
        # 但实际渲染为 .notdef 方框；覆盖检测必须识别这种情况。
        font = get_font(16)
        tofu = font.render("\u0378", True, (255, 255, 255))
        image = font.render("✓", True, (255, 255, 255))
        is_tofu = (image.get_size() == tofu.get_size()
                   and pygame.image.tobytes(image, "RGBA")
                   == pygame.image.tobytes(tofu, "RGBA"))
        if is_tofu:
            self.assertFalse(font_covers(font, "✓"))
        else:
            self.assertTrue(font_covers(font, "✓"))

    @unittest.skipUnless(os.name == "nt", "Segoe UI Symbol 仅 Windows 提供")
    def test_check_mark_routes_to_symbol_fallback_on_windows(self):
        font = get_font(16)
        if font_covers(font, "✓"):
            self.skipTest("当前主字体确实拥有 ✓ 字形")
        runs = split_font_runs("完成 ✓", font)
        fallback_parts = "".join(part for target, part in runs
                                 if target is not font)
        self.assertIn("✓", fallback_parts)

    def test_render_text_plain_matches_native_render(self):
        font = get_font(16)
        img = render_text("中文 abc 3.0", font, (255, 255, 255))
        self.assertEqual(img.get_width(), font.size("中文 abc 3.0")[0])

    def test_render_text_mixed_width_equals_run_widths(self):
        font = get_font(16)
        text = "ω=3.0 ✓"
        width = sum(target.size(part)[0]
                    for target, part in split_font_runs(text, font))
        img = render_text(text, font, (255, 255, 255))
        self.assertEqual(img.get_width(), width)

    def test_measure_text_uses_fallback_widths(self):
        font = get_font(16)
        text = "高度 h=1.0 m ✓"
        width, height = measure_text(text, font)
        self.assertEqual(width, text_width(text, font))
        self.assertEqual(height, font.get_height())

    def test_headless_draw_text_with_symbols(self):
        surface = pygame.Surface((400, 60), pygame.SRCALPHA)
        rect = draw_text(surface, "√ω² ≤ 3.0 ✓→", (10, 10),
                         get_font(16), (255, 255, 255))
        self.assertGreater(rect.width, 0)


if __name__ == "__main__":
    unittest.main()

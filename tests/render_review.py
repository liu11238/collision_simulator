"""Headless visual QA: python tests/render_review.py /absolute/output/dir."""
import os
import sys
from pathlib import Path
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pygame
from main import App
from config import LAYOUT
from core import display


def render_review(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    app = App()
    for width, height in ((1280, 720), (1600, 900)):
        LAYOUT.apply(width, height)
        display.resize_display(width, height)
        app.relayout()
        for index, model in enumerate(app.models):
            app.switch_mode(index)
            model.reset()
            if model.toggles["explain"].value:
                model.toggle_explanation()
            model.update_inputs(1.0)
            display.begin_frame()
            model.draw_scene()
            model.draw_interface()
            pygame.image.save(
                display.screen,
                str(destination / f'{width}_model{index}_default.png'),
            )
            model.toggle_explanation()
            model.start_pause()
            for _ in range(2000):
                model.step(1 / 60)
                if model.phase == 'impact_explain':
                    break
            assert model.phase == 'impact_explain'
            for stage in range(3):
                if index == 0:
                    model.explain_elapsed = stage * 3 + .5
                else:
                    model.impact_explainer.elapsed = stage * 2.2 + .5
                display.begin_frame()
                model.draw_scene()
                model.draw_interface()
                pygame.image.save(display.screen, str(destination / f'{width}_model{index}_stage{stage}.png'))


if __name__ == '__main__':
    render_review(sys.argv[1])

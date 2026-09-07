"""Render both models at the instant collision event for visual QA."""
import os
import sys
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame

from config import LAYOUT
from core import display
from main import App


def render_replay_review(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    LAYOUT.apply(1600, 900)
    display.resize_display(1600, 900)
    app = App()
    app.relayout()
    for index, model in enumerate(app.models):
        app.switch_mode(index)
        model.reset()
        model.jump_to_collision()
        impact_time = model.last_result['impact_time']
        model.step(0.3)
        for suffix, offset in (('impact', 0.0), ('decay', 0.055)):
            model.seek_replay(impact_time + offset, side='after')
            model.update_inputs(1.0)
            display.begin_frame()
            model.draw_scene()
            model.draw_interface()
            pygame.image.save(
                display.screen,
                str(destination / f'model{index}_{suffix}.png'),
            )


if __name__ == '__main__':
    render_replay_review(sys.argv[1])

"""Record an actual, stepped demonstration: python tests/render_motion.py out.mp4.

Requires ffmpeg on PATH. This is a visual review helper, not a unit test.
"""
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame

from config import LAYOUT
from core import display
from main import App


def render_motion(destination, fps=30):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    LAYOUT.apply(1280, 720)
    display.resize_display(1280, 720)
    app = App()
    command = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', '1280x720', '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
               '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p', '-movflags',
               '+faststart', str(destination)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for index in (1, 0):
            app.switch_mode(index)
            model = app.model
            model.reset()
            if not model.toggles["explain"].value:
                model.toggle_explanation()
            # Include normal view, the full explanation, and automatic resume.
            for _ in range(fps // 2):
                model.update_inputs(1 / fps)
                display.advance_ambience(1 / fps)
                display.begin_frame()
                model.draw_scene()
                model.draw_interface()
                process.stdin.write(pygame.image.tobytes(display.screen, 'RGB'))
            model.start_pause()
            after_frames = 0
            for _ in range(20 * fps):
                model.update_inputs(1 / fps)
                model.step(1 / fps)
                display.advance_ambience(1 / fps)
                display.begin_frame()
                model.draw_scene()
                model.draw_interface()
                process.stdin.write(pygame.image.tobytes(display.screen, 'RGB'))
                if model.phase == 'after':
                    after_frames += 1
                    if after_frames >= fps:
                        break
    finally:
        process.stdin.close()
        status = process.wait()
    if status:
        raise RuntimeError(f'ffmpeg exited with status {status}')
    print(destination)


if __name__ == '__main__':
    render_motion(sys.argv[1])

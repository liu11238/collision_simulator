"""应用程序入口、模型切换和 pygame 事件循环。"""

from __future__ import annotations

import sys

import pygame

from config import FPS, SIM_H
from core.display import clock, screen
from models.ball_ball import BallBallCollision
from models.ball_rod import BallHitsRod
from ui.widgets import Button

class App:
    def __init__(self):
        self.models = [BallBallCollision(), BallHitsRod()]
        for model in self.models:
            model.app = self
        self.mode_index = 0

        self.btn_start = Button("开始 / 暂停  Space", pygame.Rect(38, SIM_H + 286, 180, 38))
        self.btn_reset = Button("重置  R", pygame.Rect(236, SIM_H + 286, 110, 38))
        self.btn_snap = Button("直接到碰撞  C", pygame.Rect(364, SIM_H + 286, 150, 38))
        self.mode_buttons = [
            Button("1  两自由质点弹性碰撞仿真", pygame.Rect(38, 118, 280, 36)),
            Button("2  质点‑定轴细杆碰撞仿真", pygame.Rect(330, 118, 280, 36)),
        ]

    @property
    def model(self):
        return self.models[self.mode_index]

    def switch_mode(self, index):
        if 0 <= index < len(self.models) and index != self.mode_index:
            for box in self.model.input_boxes.values():
                box.active = False

                box.dragging = False
            self.model.running = False
            self.mode_index = index
            for box in self.model.input_boxes.values():
                box.active = False
                box.dragging = False

            self.model.running = False

    def draw_mode_tabs(self):
        for i, button in enumerate(self.mode_buttons):
            button.draw(screen, active=(i == self.mode_index))

    def run(self):
        running_app = True
        while running_app:
            dt = clock.tick(FPS) / 1000.0
            model = self.model

            model.update_inputs(dt)
            need_reset = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running_app = False
                    continue

                switched = False

                for i, button in enumerate(self.mode_buttons):
                    if button.clicked(event):
                        self.switch_mode(i)
                        switched = True
                        break
                if switched:
                    continue

                model = self.model

                input_was_active, input_consumed, input_changed = model.handle_input_event(event)
                if input_changed:
                    need_reset = True

                if event.type == pygame.KEYDOWN and not model.any_input_active():
                    if event.key == pygame.K_ESCAPE:
                        running_app = False
                    elif event.key == pygame.K_1:
                        self.switch_mode(0)
                    elif event.key == pygame.K_2:
                        self.switch_mode(1)
                    elif event.key == pygame.K_SPACE:
                        model.start_pause()
                    elif event.key == pygame.K_e and hasattr(model, "toggle_explanation"):
                        model.toggle_explanation()
                    elif event.key == pygame.K_r:
                        model.reset()
                    elif event.key == pygame.K_c:
                        model.jump_to_collision()

                if input_consumed or input_was_active:
                    continue

                if self.btn_start.clicked(event):
                    model.start_pause()
                if self.btn_reset.clicked(event):
                    model.reset()

                if self.btn_snap.clicked(event):
                    model.jump_to_collision()

                if model.handle_sliders(event):
                    need_reset = True

            model = self.model
            if need_reset:
                model.reset(keep_running=False)
                model.sync_inputs(force=False)


            model.step(dt)
            model.draw_scene()
            model.draw_ui()
            pygame.display.flip()

        pygame.quit()

        sys.exit()


def main():
    App().run()


if __name__ == "__main__":
    main()

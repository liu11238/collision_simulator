"""应用程序入口、模型切换、响应式缩放和 pygame 事件循环。"""

from __future__ import annotations

import sys

import pygame

from config import (DEFAULT_HEIGHT, DEFAULT_WIDTH, FPS, LAYOUT, MIN_HEIGHT,
                    MIN_WIDTH)
from core import display
from models.ball_ball import BallBallCollision
from models.ball_rod import BallHitsRod
from ui.widgets import Button


def _event_size(event):
    """从 VIDEORESIZE / WINDOWSIZECHANGED 事件中提取新窗口尺寸。"""
    for w_attr, h_attr in (("w", "h"), ("width", "height"), ("x", "y")):
        w = getattr(event, w_attr, None)
        h = getattr(event, h_attr, None)
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            return w, h
    return None


class App:
    def __init__(self):
        self.models = [BallBallCollision(), BallHitsRod()]
        for model in self.models:
            model.app = self
        self.mode_index = 0
        self._build_buttons()

    def _build_buttons(self):
        action = pygame.Rect(LAYOUT.action)
        tabs = pygame.Rect(LAYOUT.tabs)

        snap_w, reset_w, start_w, gap = 112, 64, 132, 8
        x = action.right - (start_w + gap + reset_w + gap + snap_w)
        self.btn_start = Button("开始 / 暂停",
                                pygame.Rect(x, action.y, start_w, action.h))
        self.btn_reset = Button(
            "重置", pygame.Rect(x + start_w + gap, action.y, reset_w, action.h))
        self.btn_snap = Button(
            "直接到碰撞",
            pygame.Rect(x + start_w + gap + reset_w + gap, action.y,
                        snap_w, action.h))

        tab_w = min(240, (tabs.w - 12) // 2)
        self.mode_buttons = [
            Button("1  双球一维碰撞仿真",
                   pygame.Rect(tabs.x, tabs.y, tab_w, tabs.h)),
            Button("2  质点‑定轴细杆碰撞仿真",
                   pygame.Rect(tabs.x + tab_w + 12, tabs.y, tab_w, tabs.h)),
        ]

    def relayout(self):
        """窗口缩放后重排按钮和模型控件。"""
        self._build_buttons()
        for model in self.models:
            model.relayout()

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
            button.draw(display.screen, active=(i == self.mode_index))

    def handle_resize_event(self, event):
        """应用窗口缩放：更新布局几何并重建图层，绝不拉伸旧位图。"""
        size = _event_size(event)
        if not size:
            return False
        width = max(MIN_WIDTH, size[0])
        height = max(MIN_HEIGHT, size[1])
        if width == LAYOUT.width and height == LAYOUT.height:
            return False
        LAYOUT.apply(width, height)
        display.resize_display(width, height)
        self.relayout()
        return True

    def run(self):
        running_app = True
        while running_app:
            dt = display.clock.tick(FPS) / 1000.0
            model = self.model

            model.update_inputs(dt)
            need_reset = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running_app = False
                    continue

                if event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                    self.handle_resize_event(event)
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

                if model.handle_timeline(event):
                    continue

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
                    elif event.key == pygame.K_p and hasattr(model, "leave_replay"):
                        model.leave_replay()
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and getattr(
                            model, "replay_mode", False):
                        direction = -1.0 if event.key == pygame.K_LEFT else 1.0
                        model.seek_replay(
                            model.replay.cursor + direction * model.replay.sample_interval,
                            side="after",
                        )

                if input_consumed or input_was_active:
                    continue

                if model.handle_panel_scroll(event):
                    continue

                if self.btn_start.clicked(event):
                    model.start_pause()
                if self.btn_reset.clicked(event):
                    model.reset()

                if self.btn_snap.clicked(event):
                    model.jump_to_collision()

                if model.handle_toggles(event):
                    # 开关只影响展示选项，不需要重置仿真。
                    continue

                if model.handle_sliders(event):
                    need_reset = True

            model = self.model
            if need_reset:
                model.reset(keep_running=False)
                model.sync_inputs(force=False)

            model.step(dt)
            # 标题、时间与 FPS 每帧都可能变短；必须先重绘完整背景，
            # 否则旧字形会残留。背景同时覆盖顶栏和整个场景宽度。
            display.begin_frame()
            model.draw_scene()
            model.draw_interface()
            pygame.display.flip()

        pygame.quit()

        sys.exit()


def main():
    App().run()


if __name__ == "__main__":
    main()

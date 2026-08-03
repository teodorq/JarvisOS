"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations
import time

from app.vision2.activity_detector import ActivityDetector
from app.vision2.change_detector import ChangeDetector
from app.vision2.context_detector import ContextDetector
from app.vision2.screen_state import ScreenState


class Vision2:

    def __init__(self, screen_vision=None):
        self.screen_vision = screen_vision
        self.context_detector = ContextDetector()
        self.change_detector = ChangeDetector()
        self.activity_detector = ActivityDetector()

    def read_screen(self) -> ScreenState:
        screenshot_path = None
        window_title = ""
        screen_width = 0
        screen_height = 0
        mouse_x = 0
        mouse_y = 0

        if self.screen_vision:
            try:
                screenshot_path = self.screen_vision.take_screenshot()
            except Exception:
                screenshot_path = None

            try:
                window_title = self.screen_vision.get_active_window_title()
            except Exception:
                window_title = ""

            try:
                screen_size = self.screen_vision.get_screen_size()
                screen_width = screen_size.get("width", 0)
                screen_height = screen_size.get("height", 0)
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")

            try:
                mouse = self.screen_vision.get_mouse_position()
                mouse_x = mouse.get("x", 0)
                mouse_y = mouse.get("y", 0)
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")

        app_name = self.context_detector.detect_app(window_title)
        page_context = self.context_detector.detect_page_context(window_title)

        activity = self.activity_detector.detect(
            app_name=app_name,
            page_context=page_context,
            window_title=window_title
        )

        state = ScreenState(
            window_title=window_title,
            app_name=app_name,
            page_context=page_context,
            screenshot_path=screenshot_path,
            timestamp=time.time(),
            screen_width=screen_width,
            screen_height=screen_height,
            mouse_x=mouse_x,
            mouse_y=mouse_y
        )

        state.activity = activity

        return state

    def analyze_screen(self) -> dict:
        state = self.read_screen()
        change = self.change_detector.analyze(state)

        return {
            "state": state,
            "app": state.app_name,
            "page": state.page_context,
            "activity": getattr(state, "activity", "unknown"),
            "change": change
        }

    def should_ask_user(self, analysis: dict) -> bool:
        importance = analysis.get("change", {}).get("importance", "low")
        return importance == "high"

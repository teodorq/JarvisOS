from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pyautogui

from app.core.storage_retention import enforce_screenshot_retention

try:
    import win32gui
except ImportError:
    win32gui = None


class ScreenVision:
    """Capture bounded, compact screen evidence for local vision tasks."""

    def __init__(self, screenshot_dir: str | Path = "data/screenshots") -> None:
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        enforce_screenshot_retention(self.screenshot_dir)

    def take_screenshot(self) -> str:
        filename = datetime.now().strftime(
            "screen_%Y-%m-%d_%H-%M-%S.webp"
        )
        path = self.screenshot_dir / filename
        screenshot = pyautogui.screenshot()
        path = self._save_compact(screenshot, path)
        enforce_screenshot_retention(self.screenshot_dir)
        return str(path)

    def take_region_screenshot(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        prefix: str = "region"
    ) -> str:
        filename = datetime.now().strftime(
            f"{prefix}_%Y-%m-%d_%H-%M-%S.webp"
        )
        path = self.screenshot_dir / filename
        screenshot = pyautogui.screenshot(
            region=(left, top, width, height)
        )
        path = self._save_compact(screenshot, path)
        enforce_screenshot_retention(self.screenshot_dir)
        return str(path)

    @staticmethod
    def _save_compact(screenshot: Any, path: Path) -> Path:
        try:
            screenshot.save(path, format="WEBP", quality=82, method=1)
            return path
        except (OSError, ValueError):
            fallback = path.with_suffix(".png")
            screenshot.save(fallback, format="PNG")
            return fallback

    def get_screen_size(self):
        width, height = pyautogui.size()

        return {
            "width": width,
            "height": height
        }

    def get_mouse_position(self):
        x, y = pyautogui.position()

        return {
            "x": x,
            "y": y
        }

    def get_active_window_title(self):
        if win32gui is None:
            return ""

        try:
            hwnd = win32gui.GetForegroundWindow()

            if hwnd == 0:
                return ""

            return win32gui.GetWindowText(hwnd)

        except Exception:
            return ""

    def get_screen_info(self):
        return {
            "window_title": self.get_active_window_title(),
            "screen_size": self.get_screen_size(),
            "mouse_position": self.get_mouse_position()
        }

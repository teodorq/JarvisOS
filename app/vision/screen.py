from datetime import datetime
from pathlib import Path

import pyautogui

try:
    import win32gui
except ImportError:
    win32gui = None


class ScreenVision:

    def __init__(self):
        self.screenshot_dir = Path("data/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def take_screenshot(self) -> str:
        filename = datetime.now().strftime(
            "screen_%Y-%m-%d_%H-%M-%S.png"
        )

        path = self.screenshot_dir / filename

        screenshot = pyautogui.screenshot()
        screenshot.save(path)

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
            f"{prefix}_%Y-%m-%d_%H-%M-%S.png"
        )

        path = self.screenshot_dir / filename

        screenshot = pyautogui.screenshot(
            region=(left, top, width, height)
        )
        screenshot.save(path)

        return str(path)

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
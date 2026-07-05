import pyautogui
from datetime import datetime
from pathlib import Path


class ScreenVision:
    def __init__(self):
        self.screenshot_dir = Path("data/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def take_screenshot(self) -> str:
        filename = datetime.now().strftime("screen_%Y-%m-%d_%H-%M-%S.png")
        path = self.screenshot_dir / filename

        screenshot = pyautogui.screenshot()
        screenshot.save(path)

        return str(path)
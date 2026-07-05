from app.vision.screen import ScreenVision
from app.vision.window_scanner import WindowScanner
from app.vision.qwen_vision import QwenVision


class VisionAI:

    def __init__(self):
        self.screen = ScreenVision()
        self.window_scanner = WindowScanner()
        self.qwen = QwenVision()

    def analyze_screen(self):
        screenshot = self.screen.take_screenshot()

        windows = self.window_scanner.describe_windows()

        qwen = self.qwen.analyze_image(screenshot)

        result = f"""
Analiza ekranu przez JARVIS Vision

==============================
OTWARTE OKNA
==============================

{windows}

==============================
QWEN VISION
==============================

{qwen}

==============================
SCREENSHOT
==============================

{screenshot}
"""

        return result.strip()

    def ask(self, question):
        screenshot = self.screen.take_screenshot()

        answer = self.qwen.ask_about_image(
            screenshot,
            question
        )

        return answer
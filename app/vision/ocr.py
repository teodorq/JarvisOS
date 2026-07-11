from app.vision.screen import ScreenVision
from app.vision.qwen_vision import QwenVision


class OCR:

    def __init__(self):
        self.screen = ScreenVision()
        self.qwen = QwenVision()

    def read_screen(self):
        screenshot = self.screen.take_screenshot()

        prompt = """
Odczytaj cały tekst widoczny na ekranie.

Zwróć wyłącznie tekst.
Nie opisuj obrazu.
Nie dodawaj komentarzy.
"""

        text = self.qwen.ask_about_image(
            screenshot,
            prompt
        )

        return {
            "screenshot": screenshot,
            "text": text
        }

    def read_region(self, image_path):
        prompt = """
Odczytaj cały tekst z obrazu.

Zwróć wyłącznie tekst.
"""

        text = self.qwen.ask_about_image(
            image_path,
            prompt
        )

        return {
            "text": text
        }
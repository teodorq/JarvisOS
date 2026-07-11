from app.vision.screen import ScreenVision
from app.vision.qwen_vision import QwenVision


class VisionFeedback:
    """
    Moduł sprawdza, czy wykonany krok prawdopodobnie się udał.
    Na razie działa opisowo, później będzie zwracał decyzję dla Agent Loop.
    """

    def __init__(self):
        self.screen = ScreenVision()
        self.qwen = QwenVision()

    def check_step(self, step_instruction: str, action_result: str) -> dict:
        screenshot = self.screen.take_screenshot()

        prompt = f"""
Jesteś modułem Vision Feedback dla JARVIS OS.

Sprawdź screenshot po wykonaniu kroku.

KROK:
{step_instruction}

WYNIK AKCJI:
{action_result}

Oceń, czy krok prawdopodobnie się udał.

Odpowiedz WYŁĄCZNIE JSON-em:
{{
  "success": true,
  "confidence": 0.85,
  "reason": "krótkie wyjaśnienie",
  "next_hint": "co zrobić dalej"
}}
"""

        response = self.qwen.ask_about_image(screenshot, prompt)

        return {
            "screenshot": screenshot,
            "raw_response": response,
            "success": self._guess_success(response),
            "summary": response
        }

    def _guess_success(self, text: str) -> bool:
        text = text.lower()

        bad_words = [
            "nie udało",
            "nie widzę",
            "błąd",
            "failed",
            "false",
            "nie znaleziono"
        ]

        for word in bad_words:
            if word in text:
                return False

        return True
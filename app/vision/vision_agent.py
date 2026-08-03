"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations
import json

from app.vision.screen import ScreenVision
from app.vision.qwen_vision import QwenVision
from app.vision.gui_detector import GuiDetector


class VisionAgent:
    def __init__(self):
        self.screen = ScreenVision()
        self.qwen = QwenVision()
        self.gui = GuiDetector()

    def describe_screen(self) -> str:
        screenshot = self.screen.take_screenshot()
        return self.qwen.analyze_image(screenshot)

    def scan_gui(self) -> dict:
        return self.gui.scan()

    def find_gui_element(self, description: str) -> dict:
        return self.gui.find(description)

    def find_element(self, description: str) -> dict:
        desc = description.lower().strip()

        if "pierwszy film" in desc or "pierwsze video" in desc:
            return self.find_first_youtube_video()

        gui_result = self.find_gui_element(description)

        if gui_result.get("found") and gui_result.get("element"):
            element = gui_result["element"]

            return {
                "found": True,
                "x": int(element.get("x", 0)),
                "y": int(element.get("y", 0)),
                "description": element.get("text", description),
                "type": element.get("type", ""),
                "confidence": element.get("confidence", 0),
                "score": gui_result.get("score", 0),
                "screenshot": gui_result.get("screenshot", ""),
                "summary": gui_result.get("summary", ""),
                "source": "gui_detector"
            }

        return self.find_element_direct(description)

    def find_first_youtube_video(self) -> dict:
        screenshot = self.screen.take_screenshot()

        prompt = """
Jesteś modułem Vision Agent dla JARVIS OS.

Na screenshocie jest YouTube.

Znajdź PIERWSZY FILM na liście wyników lub stronie głównej YouTube.

BARDZO WAŻNE:
- NIE wybieraj logo YouTube.
- NIE wybieraj przycisku menu.
- NIE wybieraj pola wyszukiwania.
- NIE wybieraj filtrów typu Wszystko, Shorts, Filmy.
- NIE wybieraj górnego paska.
- Wybierz pierwszy realny film: miniaturę albo tytuł filmu.
- Punkt kliknięcia ma być w środku miniatury lub na tytule filmu.
- Zwykle pierwszy film jest poniżej górnego paska, nie na samej górze ekranu.

Odpowiedz WYŁĄCZNIE JSON-em:

{
  "found": true,
  "x": 123,
  "y": 456,
  "description": "pierwszy film na YouTube"
}

Jeśli nie widzisz filmu:

{
  "found": false,
  "x": 0,
  "y": 0,
  "description": "nie znaleziono pierwszego filmu"
}
"""

        response = self.qwen.ask_about_image(screenshot, prompt)
        data = self._extract_json(response)

        data["screenshot"] = screenshot
        data["raw_response"] = response
        data["source"] = "youtube_first_video_qwen"

        try:
            y = int(data.get("y", 0))
            if data.get("found") and y < 220:
                data["found"] = False
                data["description"] = "Vision wskazał element za wysoko, prawdopodobnie pasek YouTube zamiast filmu."
        except Exception:
            raise RuntimeError("AutoDev: przechwycony wyjątek")

        return data

    def find_element_direct(self, description: str) -> dict:
        screenshot = self.screen.take_screenshot()

        prompt = f"""
Jesteś modułem Vision Agent dla JARVIS OS.

Masz znaleźć na screenshocie element opisany tak:
"{description}"

Odpowiedz WYŁĄCZNIE JSON-em:

{{
  "found": true,
  "x": 123,
  "y": 456,
  "description": "krótki opis elementu"
}}

Jeśli nie widzisz elementu:

{{
  "found": false,
  "x": 0,
  "y": 0,
  "description": "nie znaleziono"
}}

Podaj współrzędne środka elementu na ekranie.
"""

        response = self.qwen.ask_about_image(screenshot, prompt)
        data = self._extract_json(response)

        data["screenshot"] = screenshot
        data["raw_response"] = response
        data["source"] = "direct_qwen"
        return data

    def _extract_json(self, text: str) -> dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end <= 0:
                return {
                    "found": False,
                    "x": 0,
                    "y": 0,
                    "description": "Vision nie zwrócił JSON."
                }

            raw = text[start:end]
            data = json.loads(raw)

            if "found" not in data:
                data["found"] = False

            if "x" not in data:
                data["x"] = 0

            if "y" not in data:
                data["y"] = 0

            if "description" not in data:
                data["description"] = ""

            return data

        except Exception:
            return {
                "found": False,
                "x": 0,
                "y": 0,
                "description": "Nie udało się odczytać odpowiedzi Vision."
            }

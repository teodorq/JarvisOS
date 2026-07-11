import json
from difflib import SequenceMatcher

from app.vision.screen import ScreenVision
from app.vision.qwen_vision import QwenVision
from app.vision.window_scanner import WindowScanner


class GuiDetector:
    def __init__(self):
        self.screen = ScreenVision()
        self.qwen = QwenVision()
        self.windows = WindowScanner()
        self.last_scan = None

    def scan(self) -> dict:
        scan_window = self._get_scan_window()
        screenshot = self._take_scan_screenshot(scan_window)

        prompt = """
Jesteś modułem GUI Detector 2.2 dla JARVIS OS.

Analizujesz screenshot JEDNEGO OKNA aplikacji, nie całego monitora.

Znajdź klikalne elementy GUI.

Typy:
- video
- thumbnail
- title
- menu
- button
- input
- link
- icon
- tab
- checkbox
- window_button
- result
- player

Jeśli to YouTube:
- pierwszy realny film oznacz jako type: "video", text: "pierwszy film"
- miniaturę filmu oznacz jako "thumbnail"
- tytuł filmu oznacz jako "title"
- pole wyszukiwania oznacz jako "input"
- menu boczne oznacz jako "menu"
- NIE wybieraj logo, menu, filtrów ani pola wyszukiwania jako filmu
- x/y podaj względem TEGO SCREENSHOTA OKNA

Odpowiedz WYŁĄCZNIE JSON-em:

{
  "summary": "krótki opis ekranu",
  "elements": [
    {
      "id": 1,
      "type": "video",
      "text": "pierwszy film",
      "x": 900,
      "y": 420,
      "confidence": 0.90
    }
  ]
}
"""

        response = self.qwen.ask_about_image(screenshot, prompt)
        data = self._extract_json(response)

        data["screenshot"] = screenshot
        data["raw_response"] = response
        data["scan_window"] = scan_window

        elements = data.get("elements", [])
        elements = self._filter_elements(elements)
        elements = self._offset_elements(elements, scan_window)

        data["elements"] = elements

        self.last_scan = data
        return data

    def find(self, query: str) -> dict:
        scan = self.scan()
        elements = scan.get("elements", [])

        query_lower = query.lower().strip()
        wanted_types = self._wanted_types(query_lower)

        best = None
        best_score = 0

        for element in elements:
            score = self._score_element(element, query_lower, wanted_types)

            if score > best_score:
                best_score = score
                best = element

        if best and best_score >= 35:
            return {
                "found": True,
                "element": best,
                "score": best_score,
                "screenshot": scan.get("screenshot", ""),
                "summary": scan.get("summary", ""),
                "scan_window": scan.get("scan_window")
            }

        return {
            "found": False,
            "element": None,
            "score": best_score,
            "screenshot": scan.get("screenshot", ""),
            "summary": scan.get("summary", ""),
            "scan_window": scan.get("scan_window")
        }

    def _get_scan_window(self):
        active = self.windows.get_active_window()

        if active:
            title = active.get("title", "").lower()

            if any(name in title for name in [
                "youtube",
                "opera",
                "chrome",
                "edge",
                "firefox"
            ]):
                return active

        for keyword in ["youtube", "opera", "chrome", "edge", "firefox"]:
            window = self.windows.find_window(keyword)
            if window:
                return window

        return None

    def _take_scan_screenshot(self, scan_window):
        if not scan_window:
            return self.screen.take_screenshot()

        left = max(0, int(scan_window.get("left", 0)))
        top = max(0, int(scan_window.get("top", 0)))
        width = max(1, int(scan_window.get("width", 1)))
        height = max(1, int(scan_window.get("height", 1)))

        return self.screen.take_region_screenshot(
            left=left,
            top=top,
            width=width,
            height=height,
            prefix="window"
        )

    def _offset_elements(self, elements: list, scan_window):
        if not scan_window:
            return elements

        left = int(scan_window.get("left", 0))
        top = int(scan_window.get("top", 0))

        for element in elements:
            try:
                element["local_x"] = int(element.get("x", 0))
                element["local_y"] = int(element.get("y", 0))
                element["x"] = element["local_x"] + left
                element["y"] = element["local_y"] + top
            except Exception:
                pass

        return elements

    def _filter_elements(self, elements: list) -> list:
        filtered = []

        for element in elements:
            if not isinstance(element, dict):
                continue

            element_type = str(element.get("type", "")).lower().strip()
            text = str(element.get("text", "")).lower().strip()

            if not element_type:
                continue

            bad_texts = [
                "jarvis",
                "brain",
                "memory",
                "trading",
                "dashboard",
                "wyślij",
                "wyslij",
                "napisz polecenie"
            ]

            if any(bad in text for bad in bad_texts):
                continue

            filtered.append(element)

        return filtered

    def _wanted_types(self, query: str) -> list[str]:
        if "pierwszy film" in query or "film" in query or "video" in query:
            return ["video", "thumbnail", "title"]

        if "pierwszy wynik" in query or "wynik" in query:
            return ["result", "link", "title"]

        if "odtwarzacz" in query or "player" in query:
            return ["player", "video"]

        if "subskrypcje" in query or "shorts" in query or "historia" in query or "menu" in query:
            return ["menu", "button", "link"]

        if "pole" in query or "wyszukiwania" in query or "szukaj" in query:
            return ["input", "textbox", "text_field", "search"]

        if "zaloguj" in query or "akcept" in query or "dalej" in query or "subskrybuj" in query:
            return ["button"]

        if "ikona" in query or "logo" in query:
            return ["icon"]

        if "zamknij" in query or query == "x":
            return ["window_button", "button", "icon"]

        return []

    def _score_element(self, element: dict, query: str, wanted_types: list[str]) -> int:
        score = 0

        text = str(element.get("text", "")).lower().strip()
        element_type = str(element.get("type", "")).lower().strip()

        try:
            x = int(element.get("local_x", element.get("x", 0)))
            y = int(element.get("local_y", element.get("y", 0)))
        except Exception:
            x = 0
            y = 0

        if wanted_types:
            if element_type in wanted_types:
                score += 120
            else:
                score -= 100

        if "pierwszy film" in query:
            if element_type in ["video", "thumbnail", "title"]:
                score += 200

            if "pierwszy film" in text:
                score += 220

            if "film" in text or "video" in text or "miniatura" in text:
                score += 90

            if y < 180:
                score -= 250

            if x < 180:
                score -= 250

            if element_type in ["menu", "button", "input", "icon", "tab", "window_button"]:
                score -= 250

            bad_video_words = [
                "subskrypcje",
                "shorts",
                "strona główna",
                "strona glowna",
                "historia",
                "biblioteka",
                "youtube",
                "szukaj",
                "wyszukaj",
                "zaloguj",
                "subskrybuj",
                "menu"
            ]

            if any(bad in text for bad in bad_video_words):
                score -= 300

        aliases = {
            "pierwszy film": ["pierwszy film", "film", "video", "miniatura", "thumbnail"],
            "pierwszy wynik": ["pierwszy wynik", "wynik", "result", "link"],
            "zaloguj": ["zaloguj", "login", "sign in"],
            "subskrypcje": ["subskrypcje", "subscriptions"],
            "shorts": ["shorts"],
            "akceptuję": ["akceptuję", "akceptuje", "accept", "zgadzam", "cookies"],
            "dalej": ["dalej", "next", "continue"],
            "zamknij": ["zamknij", "x", "close"],
            "x": ["x", "zamknij", "close"],
            "szukaj": ["szukaj", "wyszukaj", "search", "pole wyszukiwania"],
            "pole wyszukiwania": ["pole wyszukiwania", "search box", "search", "szukaj"],
        }

        if query in text:
            score += 120

        if text and text in query:
            score += 80

        for word in query.split():
            if word in text:
                score += 30
            if word in element_type:
                score += 15

        for key, values in aliases.items():
            if key in query:
                for value in values:
                    if value in text or value in element_type:
                        score += 80

        similarity = SequenceMatcher(None, query, text).ratio()
        score += int(similarity * 40)

        try:
            score += int(float(element.get("confidence", 0)) * 20)
        except Exception:
            pass

        return score

    def _extract_json(self, text: str) -> dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end <= 0:
                return {
                    "summary": "Nie udało się odczytać JSON.",
                    "elements": []
                }

            raw = text[start:end]
            data = json.loads(raw)

            if "elements" not in data:
                data["elements"] = []

            if "summary" not in data:
                data["summary"] = ""

            return data

        except Exception as error:
            return {
                "summary": f"Błąd parsowania GUI JSON: {error}",
                "elements": []
            }
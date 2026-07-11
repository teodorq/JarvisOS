import json
from app.ai.llm import LocalLLM


class PlannerLLM:
    def __init__(self):
        self.llm = LocalLLM()

    def create_plan(self, user_command: str) -> dict:
        original = user_command.strip()
        command = original.lower()

        # ===== VISION =====
        if (
            "co widzisz" in command
            or "przeanalizuj ekran" in command
            or "analiza ekranu" in command
            or "jakie okna" in command
            or "co jest na ekranie" in command
        ):
            return {
                "goal": "Przeanalizować ekran",
                "steps": [
                    "Sprawdzić otwarte okna",
                    "Zrobić screenshot",
                    "Zwrócić analizę"
                ],
                "execute": True,
                "action_type": "vision_analyze",
                "target": "",
                "text": "",
                "url": "",
                "query": ""
            }

        # ===== GOOGLE =====
        if "wyszukaj w google" in command or "szukaj w google" in command:
            query = original.lower()
            query = query.replace("wyszukaj w google", "").replace("szukaj w google", "").strip()

            return {
                "goal": f"Wyszukać w Google: {query}",
                "steps": [
                    "Otworzyć Google",
                    f"Wyszukać: {query}"
                ],
                "execute": True,
                "action_type": "google_search",
                "target": "",
                "text": "",
                "url": "",
                "query": query
            }

        # ===== YOUTUBE =====
        if "wyszukaj na youtube" in command or "szukaj na youtube" in command:
            query = original.lower()
            query = query.replace("wyszukaj na youtube", "").replace("szukaj na youtube", "").strip()

            return {
                "goal": f"Wyszukać na YouTube: {query}",
                "steps": [
                    "Otworzyć YouTube",
                    f"Wyszukać: {query}"
                ],
                "execute": True,
                "action_type": "youtube_search",
                "target": "",
                "text": "",
                "url": "",
                "query": query
            }

        prompt = f"""
Jesteś Plannerem JARVIS OS.

Odpowiadaj WYŁĄCZNIE poprawnym JSON.

Polecenie:

{original}
"""

        response = self.llm.ask(prompt)

        try:
            start = response.find("{")
            end = response.rfind("}") + 1

            if start == -1:
                raise Exception()

            return json.loads(response[start:end])

        except Exception:
            return {
                "goal": "Nie rozpoznano polecenia.",
                "steps": [
                    "Brak poprawnej odpowiedzi AI."
                ],
                "execute": False,
                "action_type": "unknown",
                "target": "",
                "text": "",
                "url": "",
                "query": ""
            }
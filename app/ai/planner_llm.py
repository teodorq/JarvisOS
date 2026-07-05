import json
from app.ai.llm import LocalLLM


class PlannerLLM:
    def __init__(self):
        self.llm = LocalLLM()

    def create_plan(self, user_command: str) -> dict:
        original = user_command.strip()
        command = original.lower()

        # Szybkie, pewne reguły przed AI
        if "wyszukaj w google" in command or "szukaj w google" in command:
            query = original.lower()
            query = query.replace("wyszukaj w google", "").replace("szukaj w google", "").strip()
            return {
                "goal": f"Wyszukać w Google: {query}",
                "steps": ["Otworzyć Google z gotowym wyszukiwaniem", f"Wyszukać: {query}"],
                "execute": True,
                "action_type": "google_search",
                "target": "",
                "text": "",
                "url": "",
                "query": query
            }

        if "wyszukaj na youtube" in command or "szukaj na youtube" in command:
            query = original.lower()
            query = query.replace("wyszukaj na youtube", "").replace("szukaj na youtube", "").strip()
            return {
                "goal": f"Wyszukać na YouTube: {query}",
                "steps": ["Otworzyć YouTube z gotowym wyszukiwaniem", f"Wyszukać: {query}"],
                "execute": True,
                "action_type": "youtube_search",
                "target": "",
                "text": "",
                "url": "",
                "query": query
            }

        prompt = f"""
Jesteś modułem planowania JARVIS OS.
Zamień polecenie użytkownika na JEDNĄ akcję.

Zwróć WYŁĄCZNIE poprawny JSON.

Format:
{{
    "goal": "...",
    "steps": ["...", "..."],
    "execute": true,
    "action_type": "",
    "target": "",
    "text": "",
    "url": "",
    "query": ""
}}

Dostępne action_type:
open_website, open_app, click, type_text, screenshot, remember, task,
memory_summary, google_search, youtube_search, open_url, press_enter, unknown

Zasady:
- Dla wyszukiwania w Google użyj google_search i wpisz frazę w query.
- Dla wyszukiwania na YouTube użyj youtube_search i wpisz frazę w query.
- Nie używaj open_website dla wyszukiwania.
- open_website służy tylko do otwierania strony głównej.

Polecenie użytkownika:
{original}
"""

        response = self.llm.ask(prompt)

        try:
            start = response.find("{")
            end = response.rfind("}") + 1

            if start == -1 or end == 0:
                raise Exception("Brak JSON")

            return json.loads(response[start:end])

        except Exception:
            return {
                "goal": "Nie udało się utworzyć planu.",
                "steps": ["Model zwrócił niepoprawną odpowiedź."],
                "execute": False,
                "action_type": "unknown",
                "target": "",
                "text": "",
                "url": "",
                "query": ""
            }
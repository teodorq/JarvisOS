from app.ai.actions import Action, ActionTypes
from app.ai.llm import LocalLLM


class Planner:
    def __init__(self):
        self.llm = LocalLLM()

    def create_action(self, command: str) -> Action:
        original = command.strip()
        command_lower = command.lower().strip()

        # Najpierw szybkie lokalne komendy
        if command_lower.startswith("zapamiętaj "):
            text = original.replace("zapamiętaj", "", 1).strip()
            return Action(ActionTypes.REMEMBER, text=text)

        if command_lower.startswith("zadanie "):
            text = original.replace("zadanie", "", 1).strip()
            return Action(ActionTypes.ADD_TASK, text=text)

        if "pamięć" in command_lower or "co pamiętasz" in command_lower:
            return Action(ActionTypes.MEMORY_SUMMARY)

        if "patrz na ekran" in command_lower or "zrób screen" in command_lower or "zrzut ekranu" in command_lower:
            return Action(ActionTypes.SCREENSHOT)

        # Potem pytamy lokalne AI
        prompt = f"""
Jesteś mózgiem asystenta JARVIS OS po polsku.
Masz zamienić polecenie użytkownika na jedną prostą akcję.

Dostępne akcje:
- open_website: youtube, google
- open_app: chrome, notatnik, steam, discord
- type_text
- click
- screenshot
- unknown

Odpowiedz WYŁĄCZNIE w formacie JSON, bez komentarza.

Polecenie użytkownika:
{original}

Przykłady:
{{"action_type":"open_website","target":"youtube","text":""}}
{{"action_type":"open_app","target":"notatnik","text":""}}
{{"action_type":"type_text","target":"","text":"siema"}}
{{"action_type":"screenshot","target":"","text":""}}
{{"action_type":"unknown","target":"","text":""}}
"""

        response = self.llm.ask(prompt)
        return self._parse_ai_response(response)

    def _parse_ai_response(self, response: str) -> Action:
        try:
            import json

            start = response.find("{")
            end = response.rfind("}") + 1

            if start == -1 or end == 0:
                return Action(ActionTypes.UNKNOWN)

            data = json.loads(response[start:end])

            return Action(
                data.get("action_type", ActionTypes.UNKNOWN),
                data.get("target", ""),
                data.get("text", "")
            )

        except Exception:
            return Action(ActionTypes.UNKNOWN)

    def create_plan(self, action: Action) -> list[str]:
        if action.action_type == ActionTypes.OPEN_WEBSITE:
            return [
                "Zinterpretować polecenie przez lokalny model AI",
                f"Otworzyć stronę: {action.target}",
                "Potwierdzić wykonanie"
            ]

        if action.action_type == ActionTypes.OPEN_APP:
            return [
                "Zinterpretować polecenie przez lokalny model AI",
                f"Uruchomić aplikację: {action.target}",
                "Potwierdzić wykonanie"
            ]

        if action.action_type == ActionTypes.TYPE_TEXT:
            return [
                "Przygotować klawiaturę",
                f"Wpisać tekst: {action.text}"
            ]

        if action.action_type == ActionTypes.CLICK:
            return ["Wykonać kliknięcie myszką"]

        if action.action_type == ActionTypes.SCREENSHOT:
            return [
                "Zrobić zrzut ekranu",
                "Zapisać plik w data/screenshots",
                "Podać lokalizację pliku"
            ]

        if action.action_type == ActionTypes.REMEMBER:
            return [
                "Zapisać informację w pamięci",
                "Potwierdzić zapis"
            ]

        if action.action_type == ActionTypes.ADD_TASK:
            return [
                "Dodać zadanie do pamięci",
                "Ustawić status jako aktywne"
            ]

        if action.action_type == ActionTypes.MEMORY_SUMMARY:
            return [
                "Odczytać pamięć",
                "Pokazać podsumowanie"
            ]

        return [
            "Nie rozpoznano polecenia",
            "Nie wykonywać akcji"
        ]
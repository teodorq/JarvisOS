from __future__ import annotations

from typing import Any

from app.ai.actions import ActionTypes
from app.ai.commands.registry import CommandRegistry


class PlannerLLM:

    SOFTWARE_ENGINEER_PHRASES = (
        "autonomous software engineer",
        "autonomiczny software engineer",
        "autonomiczny programista",
        "zaimplementuj autonomicznie",
        "zbuduj funkcję autonomicznie",
        "zbuduj funkcje autonomicznie",
        "napisz funkcję autonomicznie",
        "napisz funkcje autonomicznie",
        "stwórz funkcjonalność autonomicznie",
        "stworz funkcjonalnosc autonomicznie",
    )

    ARCHITECT_PHRASES = (
        "autonomous architect",
        "architect ai",
        "analizuj architekturę",
        "analizuj architekture",
        "przeanalizuj architekturę",
        "przeanalizuj architekture",
        "przeanalizuj architekturę projektu",
        "przeanalizuj architekture projektu",
        "zaplanuj refaktoryzację",
        "zaplanuj refaktoryzacje",
        "zaplanuj przebudowę architektury",
        "zaplanuj przebudowe architektury",
    )

    REASONER_PHRASES = (
        "rozumuj",
        "przeanalizuj cel",
        "wybierz najlepsze rozwiązanie",
        "wybierz najlepsze rozwiazanie",
        "oceń opcje",
        "ocen opcje",
        "oceń ryzyko",
        "ocen ryzyko",
        "zbuduj strategię",
        "zbuduj strategie",
        "podejmij decyzję",
        "podejmij decyzje",
        "porównaj rozwiązania",
        "porownaj rozwiazania",
        "porównaj opcje",
        "porownaj opcje",
        "najbezpieczniejsze rozwiązanie",
        "najbezpieczniejsze rozwiazanie",
        "reasoner",
        "reasoning",
    )

    RESEARCH_PHRASES = (
        "research",
        "przeanalizuj projekt",
        "przeskanuj projekt",
        "zbadaj projekt",
        "audyt projektu",
        "znajdź problemy w projekcie",
        "znajdz problemy w projekcie",
        "wykryj problemy w projekcie",
    )

    AUTODEV_PHRASES = (
        "autodev",
        "developer controller",
        "developercontroller",
        "przygotuj patch",
        "wygeneruj patch",
        "pokaż patch",
        "pokaz patch",
        "patch preview",
        "wykonaj patch",
        "rollback",
    )

    def __init__(
        self,
    ) -> None:

        self.registry = CommandRegistry()

    def create_plan(
        self,
        user_command: str,
    ) -> dict[str, Any]:

        command = self._normalize_command(
            user_command
        )

        if not command:
            return self._plan(
                goal="Puste polecenie",
                actions=[],
                handler_hint="standard",
            )

        handler_hint = self.detect_handler(
            command
        )

        if handler_hint == "software_engineer":
            return self._special_plan(
                command=command,
                goal=(
                    "Zaplanować i wykonać funkcjonalność "
                    "przez Autonomous Software Engineer"
                ),
                steps=[
                    "Rozbić cel na zadania implementacyjne",
                    "Zbudować zależności i kolejność wykonania",
                    "Wybrać najlepsze gotowe zadanie",
                    "Przygotować kod przez Developer Agent",
                    "Uruchomić walidację i testy",
                    "Ponowić próbę albo wykonać rollback",
                    "Wygenerować raport końcowy",
                ],
                handler_hint="software_engineer",
            )

        if handler_hint == "architect":
            return self._special_plan(
                command=command,
                goal=(
                    "Przeanalizować architekturę projektu "
                    "przez Autonomous Architect"
                ),
                steps=[
                    "Zbudować mapę modułów i zależności",
                    "Ocenić coupling oraz cohesion",
                    "Wykryć naruszenia architektury",
                    "Przygotować blueprinty refaktoryzacji",
                    "Uszeregować zmiany według ROI i ryzyka",
                ],
                handler_hint="architect",
            )

        if handler_hint == "reasoner":
            return self._special_plan(
                command=command,
                goal=(
                    "Przeprowadzić analizę celu "
                    "przez AI Reasoner"
                ),
                steps=[
                    "Rozpoznać rzeczywisty cel użytkownika",
                    "Zbudować graf decyzji",
                    "Wygenerować możliwe rozwiązania",
                    "Ocenić ryzyko każdej opcji",
                    "Wybrać najlepszą strategię",
                ],
                handler_hint="reasoner",
            )

        if handler_hint == "research":
            return self._special_plan(
                command=command,
                goal=(
                    "Przeprowadzić analizę projektu "
                    "przez Research Agent"
                ),
                steps=[
                    "Rozpoznać zakres analizy",
                    "Uruchomić Research Workflow",
                    "Przeskanować kod i zależności",
                    "Wykryć problemy i możliwości poprawy",
                    "Przygotować raport",
                ],
                handler_hint="research",
            )

        if handler_hint == "autodev":
            return self._special_plan(
                command=command,
                goal=(
                    "Obsłużyć polecenie przez AutoDev"
                ),
                steps=[
                    "Przeanalizować polecenie AutoDev",
                    "Przygotować operację",
                    "Wygenerować preview lub raport",
                ],
                handler_hint="autodev",
            )

        normalized_command = self._replace_aliases(
            command
        )

        actions: list[dict[str, Any]] = []
        parsed_parts: list[str] = []
        unrecognized_parts: list[str] = []

        for part in self._split_command(
            normalized_command
        ):
            action = self.registry.parse(
                part
            )

            if action:
                actions.append(action)
                parsed_parts.append(part)
            else:
                unrecognized_parts.append(part)

        if actions:
            plan = self._plan(
                goal="Wykonać polecenie",
                actions=actions,
                handler_hint="standard",
            )
            plan["parsed_parts"] = parsed_parts
            plan["unrecognized_parts"] = unrecognized_parts
            return plan

        plan = self._plan(
            goal="Nie rozpoznano polecenia",
            actions=[],
            handler_hint="standard",
        )
        plan["parsed_parts"] = []
        plan["unrecognized_parts"] = unrecognized_parts
        return plan

    def detect_handler(
        self,
        user_command: str,
    ) -> str:

        command = self._normalize_command(
            user_command
        )

        if not command:
            return "standard"

        scores = {
            "software_engineer": self._phrase_score(
                command,
                self.SOFTWARE_ENGINEER_PHRASES,
            ),
            "architect": self._phrase_score(
                command,
                self.ARCHITECT_PHRASES,
            ),
            "reasoner": self._phrase_score(
                command,
                self.REASONER_PHRASES,
            ),
            "research": self._phrase_score(
                command,
                self.RESEARCH_PHRASES,
            ),
            "autodev": self._phrase_score(
                command,
                self.AUTODEV_PHRASES,
            ),
        }

        best_score = max(scores.values())

        if best_score == 0:
            return "standard"

        # AutoDev ma pierwszeństwo przy remisie, ponieważ
        # komendy developerskie mogą zawierać słowa takie jak
        # "przeanalizuj" albo "projekt".
        for handler in (
            "software_engineer",
            "architect",
            "autodev",
            "research",
            "reasoner",
        ):
            if scores[handler] == best_score:
                return handler

        return "standard"

    def _plan(
        self,
        goal: str,
        actions: list[dict[str, Any]],
        handler_hint: str = "standard",
    ) -> dict[str, Any]:

        contextual_actions = self._contextual_actions(
            actions
        )

        cleaned_actions = self._cleanup_actions(
            contextual_actions
        )

        cleaned_actions = self._deduplicate_actions(
            cleaned_actions
        )

        first_action = (
            cleaned_actions[0]
            if cleaned_actions
            else {}
        )

        return {
            "goal": goal,
            "steps": [
                self._step_text(action)
                for action in cleaned_actions
            ],
            "execute": len(
                cleaned_actions
            ) > 0,
            "action_type": first_action.get(
                "action_type",
                ActionTypes.UNKNOWN,
            ),
            "target": first_action.get(
                "target",
                "",
            ),
            "text": first_action.get(
                "text",
                "",
            ),
            "url": first_action.get(
                "url",
                "",
            ),
            "query": first_action.get(
                "query",
                "",
            ),
            "actions": cleaned_actions,
            "handler_hint": handler_hint,
            "planner_version": "2.3.0",
        }

    def _special_plan(
        self,
        command: str,
        goal: str,
        steps: list[str],
        handler_hint: str,
    ) -> dict[str, Any]:

        return {
            "command": command,
            "goal": goal,
            "steps": steps,
            "execute": True,
            "action_type": ActionTypes.UNKNOWN,
            "target": "",
            "text": "",
            "url": "",
            "query": "",
            "actions": [],
            "handler_hint": handler_hint,
            "planner_version": "2.3.0",
        }

    def _normalize_command(
        self,
        user_command: str,
    ) -> str:

        if not isinstance(
            user_command,
            str,
        ):
            return ""

        return " ".join(
            user_command
            .strip()
            .lower()
            .split()
        )

    def _replace_aliases(
        self,
        command: str,
    ) -> str:

        normalized = command

        replacements = {
            "operę": "opera",
            "przeglądarkę": "opera",
            "przegladarke": "opera",
        }

        for old_value, new_value in replacements.items():
            normalized = normalized.replace(
                old_value,
                new_value,
            )

        return normalized

    def _split_command(
        self,
        command: str,
    ) -> list[str]:

        normalized = command

        separators = (
            " oraz ",
            " potem ",
            " następnie ",
            " nastepnie ",
            " i ",
        )

        for separator in separators:
            normalized = normalized.replace(
                separator,
                ",",
            )

        return [
            part.strip()
            for part in normalized.split(",")
            if part.strip()
        ]

    def _contextual_actions(
        self,
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        contextual_actions = [
            dict(action)
            for action in actions
            if isinstance(
                action,
                dict,
            )
        ]

        last_website = ""

        for action in contextual_actions:
            action_type = action.get(
                "action_type"
            )

            if action_type == ActionTypes.OPEN_WEBSITE:
                last_website = str(
                    action.get(
                        "target",
                        "",
                    )
                ).lower()

            if action_type == ActionTypes.TYPE_TEXT:
                text = str(
                    action.get(
                        "text",
                        "",
                    )
                ).strip()

                if last_website == "youtube":
                    action["action_type"] = (
                        ActionTypes.YOUTUBE_SEARCH
                    )
                    action["query"] = text
                    action["text"] = ""

                elif last_website == "google":
                    action["action_type"] = (
                        ActionTypes.GOOGLE_SEARCH
                    )
                    action["query"] = text
                    action["text"] = ""

        return contextual_actions

    def _cleanup_actions(
        self,
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        cleaned: list[
            dict[str, Any]
        ] = []

        for index, action in enumerate(
            actions
        ):
            action_type = action.get(
                "action_type"
            )

            target = str(
                action.get(
                    "target",
                    "",
                )
            ).lower()

            next_action = (
                actions[index + 1]
                if index + 1 < len(actions)
                else None
            )

            if (
                action_type
                == ActionTypes.OPEN_WEBSITE
                and target == "youtube"
                and next_action
                and next_action.get(
                    "action_type"
                )
                == ActionTypes.YOUTUBE_SEARCH
            ):
                continue

            if (
                action_type
                == ActionTypes.OPEN_WEBSITE
                and target == "google"
                and next_action
                and next_action.get(
                    "action_type"
                )
                == ActionTypes.GOOGLE_SEARCH
            ):
                continue

            cleaned.append(action)

        has_browser_action = any(
            action.get(
                "action_type"
            )
            in {
                ActionTypes.OPEN_WEBSITE,
                ActionTypes.YOUTUBE_SEARCH,
                ActionTypes.GOOGLE_SEARCH,
                ActionTypes.YOUTUBE_FIRST_VIDEO,
            }
            for action in cleaned
        )

        if has_browser_action:
            cleaned = [
                action
                for action in cleaned
                if not (
                    action.get(
                        "action_type"
                    )
                    == ActionTypes.OPEN_APP
                    and str(
                        action.get(
                            "target",
                            "",
                        )
                    ).lower()
                    in {
                        "opera",
                        "chrome",
                    }
                )
            ]

        return cleaned

    def _step_text(
        self,
        action: dict[str, Any],
    ) -> str:

        action_type = action.get(
            "action_type"
        )

        target = action.get(
            "target",
            "",
        )

        text = action.get(
            "text",
            "",
        )

        query = action.get(
            "query",
            "",
        )

        steps = {
            "SYSTEM_STATUS": (
                "Sprawdzić status systemu"
            ),
            "DESKTOP_HISTORY": (
                "Pokazać historię akcji pulpitu"
            ),
            "SCROLL_DOWN": (
                "Przewinąć w dół"
            ),
            "SCROLL_UP": (
                "Przewinąć w górę"
            ),
            "COPY": (
                "Skopiować"
            ),
            "PASTE": (
                "Wkleić"
            ),
            "CUT": (
                "Wyciąć"
            ),
            "SELECT_ALL": (
                "Zaznaczyć wszystko"
            ),
            "CLOSE_WINDOW": (
                "Zamknąć okno"
            ),
            "SWITCH_WINDOW": (
                "Przełączyć okno"
            ),
            "MINIMIZE_WINDOW": (
                "Zminimalizować okno"
            ),
            "MAXIMIZE_WINDOW": (
                "Zmaksymalizować okno"
            ),
            "OPEN_START_MENU": (
                "Otworzyć menu Start"
            ),
            "WINDOWS_LIST": (
                "Pokazać listę okien"
            ),
            "WINDOW_FOCUS": (
                f"Aktywować okno: {target}"
            ),
            "WINDOW_CLOSE": (
                f"Zamknąć okno: {target}"
            ),
            "FILE_LIST": (
                f"Pokazać folder: {target}"
            ),
            "FOLDER_CREATE": (
                f"Utworzyć folder: {target}"
            ),
            "APP_OPEN": (
                f"Uruchomić aplikację: {target}"
            ),
        }

        if action_type in steps:
            return steps[action_type]

        if action_type == ActionTypes.OPEN_APP:
            return (
                f"Otworzyć aplikację: {target}"
            )

        if action_type == ActionTypes.OPEN_WEBSITE:
            return (
                f"Otworzyć stronę: {target}"
            )

        if action_type == ActionTypes.TYPE_TEXT:
            return (
                f"Wpisać tekst: {text}"
            )

        if action_type == ActionTypes.PRESS_ENTER:
            return "Nacisnąć Enter"

        if action_type == ActionTypes.VISION_CLICK:
            return (
                f"Kliknąć element: {target}"
            )

        if action_type == ActionTypes.GOOGLE_SEARCH:
            return (
                f"Wyszukać w Google: {query}"
            )

        if action_type == ActionTypes.YOUTUBE_SEARCH:
            return (
                f"Wyszukać na YouTube: {query}"
            )

        if (
            action_type
            == ActionTypes.YOUTUBE_FIRST_VIDEO
        ):
            return (
                "Kliknąć pierwszy film "
                "na YouTube"
            )

        if action_type == ActionTypes.VISION_ANALYZE:
            return "Przeanalizować ekran"

        if action_type == ActionTypes.SCREENSHOT:
            return "Zrobić screenshot"

        if action_type == ActionTypes.REMEMBER:
            return "Zapisać w pamięci"

        if action_type == ActionTypes.ADD_TASK:
            return "Dodać zadanie"

        if action_type == ActionTypes.MEMORY_SUMMARY:
            return "Pokazać pamięć"

        return (
            f"Wykonać akcję: {action_type}"
        )

    def _deduplicate_actions(
        self,
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        unique_actions: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()

        for action in actions:
            signature = (
                action.get("action_type"),
                str(action.get("target", "")).strip().lower(),
                str(action.get("text", "")).strip(),
                str(action.get("url", "")).strip().lower(),
                str(action.get("query", "")).strip().lower(),
            )

            if signature in seen:
                continue

            seen.add(signature)
            unique_actions.append(action)

        return unique_actions

    def _phrase_score(
        self,
        text: str,
        phrases: tuple[str, ...],
    ) -> int:

        return sum(
            1
            for phrase in phrases
            if phrase in text
        )

    def _contains_any(
        self,
        text: str,
        phrases: tuple[str, ...],
    ) -> bool:

        return any(
            phrase in text
            for phrase in phrases
        )
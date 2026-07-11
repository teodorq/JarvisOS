from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_workflow import (
    ResearchWorkflow
)


class ResearchRouter:

    RESEARCH_ACTIONS = [
        "przeanalizuj",
        "analizuj",
        "zbadaj",
        "przejrzyj",
        "oceń",
        "ocen",
        "sprawdź",
        "sprawdz",
        "znajdź problem",
        "znajdz problem",
        "wykryj problem",
        "wykryj problemy",
        "znajdź błędy",
        "znajdz bledy",
        "wykryj błędy",
        "wykryj bledy",
        "zaproponuj poprawki",
        "zaplanuj poprawki",
        "zaplanuj refaktoryzację",
        "zaplanuj refaktoryzacje",
        "przygotuj refaktoryzację",
        "przygotuj refaktoryzacje",
        "refaktoryzuj",
        "ulepsz kod",
        "usprawnij kod",
        "research"
    ]

    PROJECT_CONTEXT = [
        "jarvis",
        "jarvis os",
        "projekt",
        "kod",
        "kodu",
        "moduł",
        "modul",
        "plik",
        "klasa",
        "funkcja",
        "metoda",
        "import",
        "zależność",
        "zaleznosc",
        "architektura",
        "refaktoryzacja",
        "autodev",
        "research agent",
        "brain",
        "vision",
        "memory",
        "voice",
        "browser",
        "desktop",
        "gui",
        "planner",
        "plannerllm",
        "developercontroller",
        "developer controller"
    ]

    EXPLICIT_RESEARCH_PHRASES = [
        "przeanalizuj moduł",
        "przeanalizuj modul",
        "przeanalizuj projekt",
        "przeanalizuj kod",
        "zbadaj moduł",
        "zbadaj modul",
        "zbadaj projekt",
        "oceń jakość kodu",
        "ocen jakosc kodu",
        "sprawdź jakość kodu",
        "sprawdz jakosc kodu",
        "znajdź problemy w kodzie",
        "znajdz problemy w kodzie",
        "wykryj problemy w projekcie",
        "zaplanuj refaktoryzację",
        "zaplanuj refaktoryzacje",
        "przygotuj plan refaktoryzacji",
        "zaproponuj poprawki w kodzie",
        "research projektu",
        "uruchom research"
    ]

    EXCLUDED_CONTEXTS = [
        "pogoda",
        "temperatura",
        "godzina",
        "czas",
        "kurs walut",
        "waluta",
        "bitcoin cena",
        "wiadomości",
        "wiadomosci",
        "youtube film",
        "film na youtube",
        "muzyka",
        "piosenka",
        "lokalizacja",
        "mapa",
        "kalendarz",
        "email",
        "mail",
        "gmail"
    ]

    def __init__(
        self,
        project_root: str = "C:/JarvisAI"
    ):
        self.project_root = project_root

        self.workflow = ResearchWorkflow(
            project_root=project_root
        )

        self.last_prompt = ""
        self.last_response = None

    def can_handle(
        self,
        prompt: str
    ) -> bool:
        normalized = self._normalize(
            prompt
        )

        if not normalized:
            return False

        if self._contains_any(
            normalized,
            self.EXCLUDED_CONTEXTS
        ):
            return False

        if self._contains_any(
            normalized,
            self.EXPLICIT_RESEARCH_PHRASES
        ):
            return True

        has_action = self._contains_any(
            normalized,
            self.RESEARCH_ACTIONS
        )

        has_project_context = (
            self._contains_any(
                normalized,
                self.PROJECT_CONTEXT
            )
        )

        return (
            has_action
            and has_project_context
        )

    def handle(
        self,
        prompt: str
    ) -> dict:
        self.last_prompt = prompt

        if not self.can_handle(
            prompt
        ):
            response = {
                "handler": "research",
                "success": False,
                "goal": prompt,
                "report": "",
                "error": (
                    "Polecenie nie zostało "
                    "rozpoznane jako Research."
                )
            }

            self.last_response = response
            return response

        try:
            result = self.workflow.run(
                prompt
            )

            response = {
                "handler": "research",
                "success": result.success,
                "goal": prompt,
                "report": (
                    self.workflow.report()
                ),
                "error": "",
                "findings_count": (
                    result.count()
                )
            }

        except Exception as error:
            response = {
                "handler": "research",
                "success": False,
                "goal": prompt,
                "report": "",
                "error": str(
                    error
                ),
                "findings_count": 0
            }

        self.last_response = response

        return response

    def build_query(
        self,
        goal: str
    ) -> ResearchQuery:
        return ResearchQuery(
            goal=goal,
            metadata={
                "source": "research_router"
            }
        )

    def status(
        self
    ) -> dict:
        return {
            "ready": True,
            "project_root": self.project_root,
            "last_prompt": self.last_prompt,
            "has_response": (
                self.last_response is not None
            ),
            "last_success": (
                self.last_response.get(
                    "success",
                    False
                )
                if self.last_response
                else False
            )
        }

    def reset(
        self
    ):
        self.workflow.reset()

        self.last_prompt = ""
        self.last_response = None

    def _normalize(
        self,
        text: str
    ) -> str:
        return (
            str(text)
            .lower()
            .strip()
        )

    def _contains_any(
        self,
        text: str,
        phrases: list[str]
    ) -> bool:
        return any(
            phrase in text
            for phrase in phrases
        )
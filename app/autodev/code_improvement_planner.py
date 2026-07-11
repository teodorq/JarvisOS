from __future__ import annotations

from typing import Any


class CodeImprovementPlanner:

    def __init__(
        self,
    ) -> None:

        self.last_plan: dict[str, Any] | None = None

    def build_plan(
        self,
        *,
        target: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:

        path = str(
            target.get(
                "path",
                "",
            )
        ).strip()

        issues = analysis.get(
            "issues",
            [],
        )

        if not isinstance(
            issues,
            list,
        ):
            issues = []

        if not path:
            plan = {
                "success": False,
                "status": "MISSING_TARGET",
                "path": "",
                "issue": None,
                "strategy": "",
                "requires_code_generation": False,
            }

            self.last_plan = plan
            return plan

        if not issues:
            plan = {
                "success": True,
                "status": "NO_ISSUES",
                "path": path,
                "issue": None,
                "strategy": (
                    "Brak wykrytych problemów "
                    "w wybranym pliku."
                ),
                "requires_code_generation": False,
            }

            self.last_plan = plan
            return plan

        selected_issue = dict(
            issues[0]
        )

        issue_type = str(
            selected_issue.get(
                "type",
                "UNKNOWN",
            )
        ).upper()

        strategy = self._strategy_for(
            issue_type
        )

        plan = {
            "success": True,
            "status": "PLAN_READY",
            "path": path,
            "issue": selected_issue,
            "issue_type": issue_type,
            "severity": str(
                selected_issue.get(
                    "severity",
                    "UNKNOWN",
                )
            ),
            "line": int(
                selected_issue.get(
                    "line",
                    0,
                )
                or 0
            ),
            "strategy": strategy,
            "requires_code_generation": True,
            "requires_approval": True,
            "safe_execution": True,
            "auto_rollback": True,
            "goal": self._build_goal(
                path=path,
                issue=selected_issue,
                strategy=strategy,
            ),
        }

        self.last_plan = dict(
            plan
        )

        return plan

    def _strategy_for(
        self,
        issue_type: str,
    ) -> str:

        strategies = {
            "SYNTAX_ERROR": (
                "Napraw błąd składni bez zmiany "
                "publicznego zachowania modułu."
            ),
            "EMPTY_BLOCK": (
                "Zastąp pusty blok bezpieczną "
                "implementacją albo jawnym wyjątkiem."
            ),
            "TODO": (
                "Zrealizuj brakującą funkcjonalność "
                "zgodnie z kontekstem pliku."
            ),
            "LONG_FUNCTION": (
                "Podziel długą funkcję na mniejsze "
                "metody bez zmiany jej wyniku."
            ),
            "LARGE_CLASS": (
                "Wydziel odpowiedzialności klasy "
                "bez naruszania jej publicznego API."
            ),
            "TOO_MANY_ARGUMENTS": (
                "Ogranicz liczbę argumentów przez "
                "obiekt danych lub konfigurację."
            ),
            "BROAD_EXCEPTION": (
                "Zastąp szeroki wyjątek bardziej "
                "precyzyjną obsługą błędów."
            ),
        }

        return strategies.get(
            issue_type,
            (
                "Przeanalizuj problem i przygotuj "
                "minimalną bezpieczną poprawkę."
            ),
        )

    def _build_goal(
        self,
        *,
        path: str,
        issue: dict[str, Any],
        strategy: str,
    ) -> str:

        message = str(
            issue.get(
                "message",
                "Wykryto problem w kodzie.",
            )
        ).strip()

        line = int(
            issue.get(
                "line",
                0,
            )
            or 0
        )

        location = (
            f" linia {line}"
            if line > 0
            else ""
        )

        return (
            f"Ulepsz plik {path},{location}. "
            f"Problem: {message} "
            f"Strategia: {strategy}"
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_plan": self.last_plan,
        }
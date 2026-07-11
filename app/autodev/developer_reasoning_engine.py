from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class DeveloperReasoningResult:
    success: bool
    status: str
    goal: str = ""
    path: str = ""
    issue_type: str = ""
    strategy: str = ""
    constraints: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeveloperReasoningEngine:
    """
    Buduje bezpieczny plan pracy dla generatora kodu.

    Silnik nie zapisuje plików i nie uruchamia zmian.
    Jego zadaniem jest przygotowanie jednoznacznego,
    ograniczonego planu dla kolejnego etapu.
    """

    SUPPORTED_ISSUES = {
        "EMPTY_BLOCK",
        "TODO",
        "BROAD_EXCEPTION",
        "LONG_FUNCTION",
        "LARGE_CLASS",
        "TOO_MANY_ARGUMENTS",
    }

    def __init__(
        self,
    ) -> None:
        self.last_result: DeveloperReasoningResult | None = None

    def reason(
        self,
        plan: dict[str, Any],
    ) -> DeveloperReasoningResult:

        if not isinstance(plan, dict):
            return self._finish(
                DeveloperReasoningResult(
                    success=False,
                    status="INVALID_PLAN",
                    risks=[
                        "Plan wejściowy nie jest słownikiem."
                    ],
                )
            )

        path = str(
            plan.get(
                "path",
                "",
            )
        ).strip()

        goal = str(
            plan.get(
                "goal",
                "",
            )
        ).strip()

        issue = plan.get(
            "issue",
            {},
        )

        if not isinstance(issue, dict):
            issue = {}

        issue_type = str(
            plan.get(
                "issue_type",
                issue.get(
                    "type",
                    "",
                ),
            )
        ).strip().upper()

        if not path:
            return self._finish(
                DeveloperReasoningResult(
                    success=False,
                    status="MISSING_PATH",
                    goal=goal,
                    issue_type=issue_type,
                    risks=[
                        "Brak pliku docelowego."
                    ],
                )
            )

        if issue_type not in self.SUPPORTED_ISSUES:
            return self._finish(
                DeveloperReasoningResult(
                    success=False,
                    status="UNSUPPORTED_ISSUE",
                    goal=goal,
                    path=path,
                    issue_type=issue_type,
                    risks=[
                        (
                            "Typ problemu nie jest obsługiwany "
                            "przez DeveloperReasoningEngine."
                        )
                    ],
                )
            )

        strategy = self._strategy_for(
            issue_type
        )

        constraints = [
            "Nie zmieniaj publicznego API bez potrzeby.",
            "Nie zapisuj zmian bez walidacji.",
            "Nie używaj eval, exec ani shell=True.",
            "Zachowaj zgodność z istniejącymi testami.",
            "Przygotuj minimalną zmianę.",
            "Wymagaj akceptacji przed zapisem.",
        ]

        risks = self._risks_for(
            issue_type
        )

        return self._finish(
            DeveloperReasoningResult(
                success=True,
                status="REASONING_READY",
                goal=goal,
                path=path,
                issue_type=issue_type,
                strategy=strategy,
                constraints=constraints,
                risks=risks,
                metadata={
                    "requires_approval": True,
                    "safe_execution": True,
                    "auto_rollback": True,
                },
            )
        )

    def _strategy_for(
        self,
        issue_type: str,
    ) -> str:

        strategies = {
            "EMPTY_BLOCK": (
                "Zastąp pusty blok jawną i bezpieczną "
                "implementacją albo NotImplementedError."
            ),
            "TODO": (
                "Uzupełnij brakującą funkcjonalność "
                "w minimalnym zakresie."
            ),
            "BROAD_EXCEPTION": (
                "Zawęź obsługiwany wyjątek albo dodaj "
                "bezpieczną diagnostykę."
            ),
            "LONG_FUNCTION": (
                "Wydziel małe metody bez zmiany wyniku."
            ),
            "LARGE_CLASS": (
                "Wydziel jedną odpowiedzialność do "
                "osobnego komponentu."
            ),
            "TOO_MANY_ARGUMENTS": (
                "Zastąp grupę argumentów obiektem danych "
                "bez naruszania zachowania."
            ),
        }

        return strategies[
            issue_type
        ]

    def _risks_for(
        self,
        issue_type: str,
    ) -> list[str]:

        common = [
            "Możliwa regresja zachowania.",
            "Możliwa zmiana importów.",
        ]

        if issue_type in {
            "LONG_FUNCTION",
            "LARGE_CLASS",
            "TOO_MANY_ARGUMENTS",
        }:
            common.append(
                "Refaktoryzacja może wpłynąć na wiele wywołań."
            )

        if issue_type == "BROAD_EXCEPTION":
            common.append(
                "Zbyt wąski wyjątek może ujawnić wcześniej ukryte błędy."
            )

        return common

    def _finish(
        self,
        result: DeveloperReasoningResult,
    ) -> DeveloperReasoningResult:

        self.last_result = result
        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }

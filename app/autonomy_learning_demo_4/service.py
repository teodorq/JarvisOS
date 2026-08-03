from __future__ import annotations

"""Logika biznesowa funkcjonalności AutonomyLearningDemo4."""

from .models import (
    AutonomyLearningDemo4Request,
    AutonomyLearningDemo4Result,
)
from .repository import AutonomyLearningDemo4Repository


class AutonomyLearningDemo4Service:
    """Realizuje cel: Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\autonomy_learning_demo_4 składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu"""

    def __init__(
        self,
        repository: AutonomyLearningDemo4Repository | None = None,
    ) -> None:
        self.repository = (
            repository
            or AutonomyLearningDemo4Repository()
        )

    def execute(
        self,
        request: AutonomyLearningDemo4Request,
    ) -> AutonomyLearningDemo4Result:
        if not isinstance(
            request,
            AutonomyLearningDemo4Request,
        ):
            return AutonomyLearningDemo4Result(
                success=False,
                status="INVALID_REQUEST",
                errors=[
                    "Nieprawidłowy typ żądania.",
                ],
            )

        payload = dict(
            request.payload
        )
        self.repository.save(
            "last_payload",
            payload,
        )

        return AutonomyLearningDemo4Result(
            success=True,
            status="COMPLETED",
            data={
                "feature": "AutonomyLearningDemo4",
                "objective": 'Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\\autonomy_learning_demo_4 składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu',
                "payload": payload,
            },
        )

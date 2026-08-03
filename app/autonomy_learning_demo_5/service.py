from __future__ import annotations

"""Logika biznesowa funkcjonalności AutonomyLearningDemo5."""

from .models import (
    AutonomyLearningDemo5Request,
    AutonomyLearningDemo5Result,
)
from .repository import AutonomyLearningDemo5Repository


class AutonomyLearningDemo5Service:
    """Realizuje cel: Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\autonomy_learning_demo_5 składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu"""

    def __init__(
        self,
        repository: AutonomyLearningDemo5Repository | None = None,
    ) -> None:
        self.repository = (
            repository
            or AutonomyLearningDemo5Repository()
        )

    def execute(
        self,
        request: AutonomyLearningDemo5Request,
    ) -> AutonomyLearningDemo5Result:
        if not isinstance(
            request,
            AutonomyLearningDemo5Request,
        ):
            return AutonomyLearningDemo5Result(
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

        return AutonomyLearningDemo5Result(
            success=True,
            status="COMPLETED",
            data={
                "feature": "AutonomyLearningDemo5",
                "objective": 'Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\\autonomy_learning_demo_5 składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu',
                "payload": payload,
            },
        )

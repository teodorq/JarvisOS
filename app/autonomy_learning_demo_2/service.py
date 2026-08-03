from __future__ import annotations

"""Logika biznesowa funkcjonalności AutonomyLearningDemo2."""

from .models import (
    AutonomyLearningDemo2Request,
    AutonomyLearningDemo2Result,
)
from .repository import AutonomyLearningDemo2Repository


class AutonomyLearningDemo2Service:
    """Realizuje cel: Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\autonomy_learning_demo_2 składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu"""

    def __init__(
        self,
        repository: AutonomyLearningDemo2Repository | None = None,
    ) -> None:
        self.repository = (
            repository
            or AutonomyLearningDemo2Repository()
        )

    def execute(
        self,
        request: AutonomyLearningDemo2Request,
    ) -> AutonomyLearningDemo2Result:
        if not isinstance(
            request,
            AutonomyLearningDemo2Request,
        ):
            return AutonomyLearningDemo2Result(
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

        return AutonomyLearningDemo2Result(
            success=True,
            status="COMPLETED",
            data={
                "feature": "AutonomyLearningDemo2",
                "objective": 'Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\\autonomy_learning_demo_2 składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu',
                "payload": payload,
            },
        )

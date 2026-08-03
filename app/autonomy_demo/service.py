from __future__ import annotations

"""Logika biznesowa funkcjonalności AutonomyDemo."""

from .models import (
    AutonomyDemoRequest,
    AutonomyDemoResult,
)
from .repository import AutonomyDemoRepository


class AutonomyDemoService:
    """Realizuje cel: Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\autonomy_demo składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu"""

    def __init__(
        self,
        repository: AutonomyDemoRepository | None = None,
    ) -> None:
        self.repository = (
            repository
            or AutonomyDemoRepository()
        )

    def execute(
        self,
        request: AutonomyDemoRequest,
    ) -> AutonomyDemoResult:
        if not isinstance(
            request,
            AutonomyDemoRequest,
        ):
            return AutonomyDemoResult(
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

        return AutonomyDemoResult(
            success=True,
            status="COMPLETED",
            data={
                "feature": "AutonomyDemo",
                "objective": 'Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\\autonomy_demo składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu',
                "payload": payload,
            },
        )

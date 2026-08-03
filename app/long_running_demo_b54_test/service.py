from __future__ import annotations

"""Logika biznesowa funkcjonalności LongRunningDemoB54Test."""

from .models import (
    LongRunningDemoB54TestRequest,
    LongRunningDemoB54TestResult,
)
from .repository import LongRunningDemoB54TestRepository


class LongRunningDemoB54TestService:
    r"""Realizuje cel: utwórz bezpieczny demonstracyjny moduł app\long_running_demo_b54_test składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu"""

    def __init__(
        self,
        repository: LongRunningDemoB54TestRepository | None = None,
    ) -> None:
        self.repository = (
            repository
            or LongRunningDemoB54TestRepository()
        )

    def execute(
        self,
        request: LongRunningDemoB54TestRequest,
    ) -> LongRunningDemoB54TestResult:
        if not isinstance(
            request,
            LongRunningDemoB54TestRequest,
        ):
            return LongRunningDemoB54TestResult(
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

        return LongRunningDemoB54TestResult(
            success=True,
            status="COMPLETED",
            data={
                "feature": "LongRunningDemoB54Test",
                "objective": 'utwórz bezpieczny demonstracyjny moduł app\\long_running_demo_b54_test składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu',
                "payload": payload,
            },
        )

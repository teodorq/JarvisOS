from __future__ import annotations

"""Logika biznesowa funkcjonalności LongRunningDemo."""

from .models import (
    LongRunningDemoRequest,
    LongRunningDemoResult,
)
from .repository import LongRunningDemoRepository


class LongRunningDemoService:
    r"""Realizuje cel: utwórz bezpieczny demonstracyjny moduł app\long_running_demo składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu"""

    def __init__(
        self,
        repository: LongRunningDemoRepository | None = None,
    ) -> None:
        self.repository = (
            repository
            or LongRunningDemoRepository()
        )

    def execute(
        self,
        request: LongRunningDemoRequest,
    ) -> LongRunningDemoResult:
        if not isinstance(
            request,
            LongRunningDemoRequest,
        ):
            return LongRunningDemoResult(
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

        return LongRunningDemoResult(
            success=True,
            status="COMPLETED",
            data={
                "feature": "LongRunningDemo",
                "objective": 'utwórz bezpieczny demonstracyjny moduł app\\long_running_demo składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu',
                "payload": payload,
            },
        )

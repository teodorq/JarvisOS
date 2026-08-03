from __future__ import annotations

"""Modele danych dla funkcjonalności LongRunningDemoB54Test."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LongRunningDemoB54TestRequest:
    """Wejście funkcjonalności LongRunningDemoB54Test."""

    payload: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class LongRunningDemoB54TestResult:
    """Ustrukturyzowany wynik funkcjonalności LongRunningDemoB54Test."""

    success: bool
    status: str
    data: dict[str, Any] = field(
        default_factory=dict
    )
    errors: list[str] = field(
        default_factory=list
    )


FEATURE_OBJECTIVE = 'utwórz bezpieczny demonstracyjny moduł app\\long_running_demo_b54_test składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu'

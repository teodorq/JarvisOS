from __future__ import annotations

"""Modele danych dla funkcjonalności LongRunningDemo."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LongRunningDemoRequest:
    """Wejście funkcjonalności LongRunningDemo."""

    payload: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class LongRunningDemoResult:
    """Ustrukturyzowany wynik funkcjonalności LongRunningDemo."""

    success: bool
    status: str
    data: dict[str, Any] = field(
        default_factory=dict
    )
    errors: list[str] = field(
        default_factory=list
    )


FEATURE_OBJECTIVE = 'utwórz bezpieczny demonstracyjny moduł app\\long_running_demo składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu'

from __future__ import annotations

"""Modele danych dla funkcjonalności AutonomyDemo."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AutonomyDemoRequest:
    """Wejście funkcjonalności AutonomyDemo."""

    payload: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class AutonomyDemoResult:
    """Ustrukturyzowany wynik funkcjonalności AutonomyDemo."""

    success: bool
    status: str
    data: dict[str, Any] = field(
        default_factory=dict
    )
    errors: list[str] = field(
        default_factory=list
    )


FEATURE_OBJECTIVE = 'Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\\autonomy_demo składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu'

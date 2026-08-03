from __future__ import annotations

"""Modele danych dla funkcjonalności AutonomyLearningDemo."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AutonomyLearningDemoRequest:
    """Wejście funkcjonalności AutonomyLearningDemo."""

    payload: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class AutonomyLearningDemoResult:
    """Ustrukturyzowany wynik funkcjonalności AutonomyLearningDemo."""

    success: bool
    status: str
    data: dict[str, Any] = field(
        default_factory=dict
    )
    errors: list[str] = field(
        default_factory=list
    )


FEATURE_OBJECTIVE = 'Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\\autonomy_learning_demo składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu'

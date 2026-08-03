from __future__ import annotations

"""Modele danych dla funkcjonalności AutonomyLearningDemo2."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AutonomyLearningDemo2Request:
    """Wejście funkcjonalności AutonomyLearningDemo2."""

    payload: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class AutonomyLearningDemo2Result:
    """Ustrukturyzowany wynik funkcjonalności AutonomyLearningDemo2."""

    success: bool
    status: str
    data: dict[str, Any] = field(
        default_factory=dict
    )
    errors: list[str] = field(
        default_factory=list
    )


FEATURE_OBJECTIVE = 'Zaplanuj dla dużego celu: utwórz bezpieczny demonstracyjny moduł app\\autonomy_learning_demo_2 składający się z modelu, repozytorium, serwisu, kontrolera oraz testów, bez modyfikowania istniejących modułów projektu'

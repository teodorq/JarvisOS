from __future__ import annotations

import unicodedata
from typing import Any

from .project_intelligence_scanner import ProjectOpportunityScanner


_SAFE_PREVIEW_MARKERS = (
    "niczego nie zmieniaj",
    "nic nie zmieniaj",
    "bez wprowadzania zmian",
    "bez zmiany plików",
    "bez zmiany plikow",
    "tylko zaproponuj",
    "tylko propozycja",
    "jedną bezpieczną poprawę",
    "jedna bezpieczna poprawe",
    "bezpieczny podgląd",
    "bezpieczny podglad",
    "safe autodev preview",
)
_PROJECT_ANALYSIS_MARKERS = (
    "przeanalizuj projekt",
    "przeanalizuj kod",
    "przeskanuj projekt",
    "sprawdź projekt",
    "sprawdz projekt",
    "autodev preview",
)


def plan_safe_autodev_preview(brain: Any, command: str) -> dict[str, Any] | None:
    """Return a read-only thought for one concrete project improvement."""
    if not _matches(command):
        return None
    return {
        "command": str(command),
        "goal": "Zaproponować jedną bezpieczną poprawę bez zmiany plików",
        "plan": [
            "Przeskanować kod projektu wyłącznie do odczytu",
            "Wybrać jedną poprawę o najlepszym stosunku wartości do ryzyka",
            "Pokazać plik, problem, zakres, ryzyko i sposób sprawdzenia",
        ],
        "actions": [],
        "can_execute": True,
        "handler": "safe_autodev_preview",
        "read_only": True,
        "requires_confirmation": False,
    }


def execute_safe_autodev_preview(brain: Any, thought: dict[str, Any]) -> str:
    """Scan project read-only and format exactly one bounded proposal."""
    command = str(thought.get("command", "")).strip()
    try:
        root = getattr(brain, "project_root", None)
        scanner = ProjectOpportunityScanner(
            root,
            max_files=500,
            max_opportunities=30,
        )
        cycle = scanner.run_cycle()
        selected = _selected(cycle)
        result = _format_result(cycle, selected)
        setattr(brain, "last_safe_autodev_preview", selected or {})
    except Exception:
        result = (
            "Nie udało mi się bezpiecznie przygotować podglądu. "
            "Nie zmieniłem żadnego pliku."
        )
    remember = getattr(brain, "_remember_execution", None)
    if callable(remember):
        remember(command, result)
    return result


def _selected(cycle: dict[str, Any]) -> dict[str, Any]:
    prioritization = dict(cycle.get("prioritization", {}) or {})
    selected = prioritization.get("selected")
    return dict(selected) if isinstance(selected, dict) else {}


def _format_result(cycle: dict[str, Any], selected: dict[str, Any]) -> str:
    scanned = int(cycle.get("files_scanned", 0) or 0)
    if not selected:
        return (
            f"Przeskanowałem {scanned} plików i nie znalazłem teraz "
            "jednej poprawy, którą mógłbym uczciwie uznać za bezpieczną. "
            "Nic nie zmieniłem."
        )
    task = dict(selected.get("task", {}) or {})
    title = str(task.get("title", "Bezpieczna poprawa")).strip()
    target = str(task.get("target", "")).strip() or "nieustalony plik"
    description = str(task.get("description", "")).strip()
    recommendation = str(task.get("recommendation", "")).strip()
    metadata = dict(task.get("metadata", {}) or {})
    risk = round(float(selected.get("predicted_risk", 0.0) or 0.0))
    effort = round(float(selected.get("effort_score", 0.0) or 0.0))
    confidence = round(float(metadata.get("confidence", 0.0) or 0.0) * 100)
    lines = [
        f"Przeskanowałem {scanned} plików i znalazłem jedną bezpieczną poprawę.",
        f"Propozycja: {title}",
        f"Plik: {target}",
    ]
    if description:
        lines.append(f"Problem: {description}")
    if recommendation:
        lines.append(f"Zakres: {recommendation}")
    lines.extend([
        f"Ocena: ryzyko {risk}/100, pewność {confidence}%, nakład {effort}/100.",
        "Nic nie zmieniłem, nie utworzyłem patcha i niczego nie uruchomiłem.",
    ])
    return "\n".join(lines)


def _matches(command: str) -> bool:
    normalized = _normalize(command)
    return (
        any(marker in normalized for marker in _PROJECT_ANALYSIS_MARKERS)
        and any(marker in normalized for marker in _SAFE_PREVIEW_MARKERS)
    )


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold())
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char)).split()
    )

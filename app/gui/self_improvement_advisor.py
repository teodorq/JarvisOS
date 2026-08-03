from __future__ import annotations

import re
import unicodedata
from typing import Any


_QUESTIONS = (
    "co bys w sobie zmienil",
    "co bys w sobie poprawil",
    "co powinienes w sobie poprawic",
    "jak mozesz sie ulepszyc",
    "jak moglbys sie ulepszyc",
    "jak bys sie ulepszyl",
    "jakie masz pomysly na swoj rozwoj",
    "co chcesz w sobie zmienic",
)


def self_improvement_advice(
    window: Any,
    command: object | None = None,
) -> str | None:
    """Oceń bieżący projekt i wybierz jedno własne usprawnienie."""
    if command is None:
        command = window
        window = None
    folded = _fold(command)
    if not any(question in folded for question in _QUESTIONS):
        return None

    assessment = _fresh_project_assessment(window)
    if assessment is None:
        return (
            "Chcę odpowiedzieć na podstawie mojego rzeczywistego stanu, a nie "
            "zgadywać. Nie mam teraz dostępu do świeżej oceny projektu, więc "
            "nie będę podawał gotowej listy. Gdy odczyt będzie dostępny, "
            "sam wybiorę najważniejsze usprawnienie i wyjaśnię powód."
        )

    selected = dict(assessment.get("selected", {}) or {})
    if not selected:
        return (
            "Właśnie sprawdziłem swój aktualny stan. Nie znalazłem teraz "
            "usprawnienia, które uczciwie mógłbym uznać za ważniejsze od "
            "pozostałych. Niczego nie zmieniłem i przy kolejnym sprawdzeniu "
            "ocenię projekt ponownie."
        )

    title = str(selected.get("title", "usprawnić działanie")).strip()
    reason = _natural_reason(selected)
    confidence = _confidence_text(selected.get("confidence", 0.0))
    risk = _risk_text(selected.get("risk_score", 0.0))
    found = int(assessment.get("found", 0) or 0)
    scope = (
        f" Po świeżym sprawdzeniu porównałem {found} wykrytych obszarów."
        if found > 1
        else ""
    )
    return (
        f"Sprawdziłem teraz swój rzeczywisty stan.{scope} "
        f"Najbardziej zmieniłbym teraz to: {title.rstrip('.').lower()}. "
        f"{reason} Wybrałem właśnie ten kierunek, ponieważ ma obecnie najlepszy "
        f"stosunek korzyści do ryzyka; {confidence}, a {risk}. "
        "Najpierw przygotowałbym małą zmianę i sprawdził, czy naprawdę poprawia "
        "działanie. Na razie niczego sam nie zmieniłem. Jeśli powiesz: "
        "„zacznij samorozwój”, sam wybiorę jedną bezpieczną zmianę, przygotuję "
        "ją i przetestuję na izolowanej kopii, ale nie wdrożę bez Twojej decyzji."
    )


def _fresh_project_assessment(window: Any) -> dict[str, Any] | None:
    brain = getattr(window, "brain", None)
    service = getattr(brain, "project_intelligence_service", None)
    if service is None:
        return None
    try:
        intelligence = getattr(service, "intelligence", None)
        run_cycle = getattr(intelligence, "run_cycle", None)
        if callable(run_cycle):
            cycle = run_cycle()
            prioritization = dict(cycle.get("prioritization", {}) or {})
            candidates = list(prioritization.get("candidates", []) or [])
            raw_selected = prioritization.get("selected", {}) or {}
            return {
                "selected": _normalize_scanner_candidate(raw_selected),
                "found": len(candidates),
            }
        scan = service.scan_project()
        if not isinstance(scan, dict) or not scan.get("success", False):
            return None
        selection = service.select_best()
        selected = (
            dict(selection.get("selected", {}) or {})
            if isinstance(selection, dict)
            else {}
        )
        opportunities = list(scan.get("opportunities", []) or [])
        if not selected and opportunities:
            candidates = [
                dict(item)
                for item in opportunities
                if isinstance(item, dict)
            ]
            if candidates:
                selected = max(
                    candidates,
                    key=lambda item: float(item.get("final_score", 0.0) or 0.0),
                )
        return {
            "selected": selected,
            "found": int(scan.get("scanned", len(opportunities)) or 0),
        }
    except Exception:
        return None


def _normalize_scanner_candidate(value: object) -> dict[str, Any]:
    candidate = dict(value or {}) if isinstance(value, dict) else {}
    task = candidate.get("task", candidate)
    if not isinstance(task, dict):
        return {}
    metadata = dict(task.get("metadata", {}) or {})
    return {
        "title": task.get("title", "usprawnić działanie"),
        "target": task.get("target", ""),
        "severity": task.get("severity", "MEDIUM"),
        "issue_type": metadata.get(
            "issue_type", task.get("issue_type", "PROJECT_IMPROVEMENT")
        ),
        "confidence": metadata.get("confidence", 0.0),
        "risk_score": candidate.get(
            "predicted_risk", metadata.get("risk", 0.0)
        ),
        "effort_score": candidate.get(
            "effort_score", metadata.get("estimated_effort", 0.0)
        ),
        "final_score": candidate.get("final_score", 0.0),
        "metadata": metadata,
    }


def _natural_reason(selected: dict[str, Any]) -> str:
    issue = str(selected.get("issue_type", "")).upper()
    metadata = dict(selected.get("metadata", {}) or {})
    area = _natural_area(selected.get("target", ""))
    if issue == "LARGE_MODULE":
        lines = int(metadata.get("line_count", 0) or 0)
        detail = f" ma obecnie {lines} linii" if lines else " jest zbyt rozbudowana"
        return (
            f"{area.capitalize()}{detail}, dlatego nawet niewielkie poprawki są "
            "tam wolniejsze do sprawdzenia i łatwiej o niezamierzony skutek."
        )
    if issue == "LONG_FUNCTION":
        lines = int(metadata.get("function_lines", 0) or 0)
        detail = f" liczy {lines} linii" if lines else " jest zbyt długa"
        return (
            f"Jedna operacja w obszarze: {area}{detail}. Jej uproszczenie "
            "ułatwi sprawdzanie działania i zmniejszy ryzyko zacięć po zmianach."
        )
    if issue == "BROAD_EXCEPTION":
        count = int(metadata.get("broad_exception_count", 0) or 0)
        return (
            f"{area.capitalize()} ukrywa zbyt wiele różnych niepowodzeń"
            f" ({count}, według bieżącej analizy). Dokładniejsze rozpoznawanie "
            "przyczyn ułatwi stabilne odzyskiwanie działania."
        )
    if issue == "HIGH_BRANCH_COMPLEXITY":
        return (
            f"{area.capitalize()} podejmuje zbyt wiele zależnych od siebie "
            "decyzji. Uproszczenie tej logiki zwiększy przewidywalność."
        )
    if issue == "TODO_DEBT":
        return (
            f"W obszarze: {area} pozostały niedokończone decyzje. Najpierw "
            "ustaliłbym, które nadal są potrzebne, zamiast dopisywać nowe funkcje."
        )
    if issue == "SYNTAX_ERROR":
        return (
            f"{area.capitalize()} zawiera błąd, który może całkowicie blokować "
            "jej uruchomienie, więc to ma pierwszeństwo przed nowymi funkcjami."
        )
    return (
        f"Bieżąca analiza wskazała obszar: {area} jako najlepszy kandydat do "
        "usprawnienia pod względem wpływu, pewności i kosztu zmiany."
    )


def _natural_area(target: object) -> str:
    value = str(target or "").casefold().replace("\\", "/")
    if "brain_response_formatter" in value or "response_formatter" in value:
        return "część odpowiedzialna za przygotowywanie odpowiedzi"
    if "voice" in value or "speech" in value or "tts" in value:
        return "obsługa głosu"
    if "client" in value or "/gui/" in value:
        return "widok rozmowy i obsługa poleceń"
    if "memory" in value:
        return "pamięć rozmowy"
    if "calendar" in value:
        return "obsługa kalendarza"
    if "mail" in value or "gmail" in value:
        return "obsługa poczty"
    return "jedna z głównych części systemu"


def _confidence_text(value: object) -> str:
    confidence = float(value or 0.0)
    if confidence >= 0.8:
        return "mam wysoką pewność tej oceny"
    if confidence >= 0.55:
        return "mam umiarkowaną pewność tej oceny"
    return "ta ocena wymaga jeszcze potwierdzenia"


def _risk_text(value: object) -> str:
    risk = float(value or 0.0)
    if risk <= 30:
        return "ryzyko zmiany jest niskie"
    if risk <= 60:
        return "ryzyko zmiany jest umiarkowane"
    return "ryzyko zmiany jest wysokie"


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    plain = "".join(char for char in text if not unicodedata.combining(char))
    plain = plain.translate(str.maketrans({"ł": "l"}))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


__all__ = ["self_improvement_advice"]

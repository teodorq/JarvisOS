"""Plain-language owner summary of the latest Forex PAPER decision."""

from __future__ import annotations


_REASONS = {
    "NO_NEW_CROSSOVER": "brak nowego przecięcia średnich",
    "LONG_TREND_INTACT": "trend wzrostowy trwa, bez nowego wejścia",
    "SHORT_TREND_INTACT": "trend spadkowy trwa, bez nowego wejścia",
    "CURRENT_OBSERVATION_BLOCKED": "bieżąca obserwacja została zablokowana",
    "SECOND_SOURCE_UNAVAILABLE": "brak potwierdzenia z drugiego źródła",
    "HIGH_IMPACT_EVENT_WINDOW": "okno ważnego wydarzenia gospodarczego",
}


def _count(value: object) -> int:
    try:
        return max(0, min(int(value or 0), 1_000_000))
    except (TypeError, ValueError):
        return 0


def _reason_text(value: object) -> str:
    reasons = dict(value) if isinstance(value, dict) else {}
    visible: list[str] = []
    other = 0
    for code, raw_count in list(reasons.items())[:12]:
        count = _count(raw_count)
        if count <= 0:
            continue
        label = _REASONS.get(str(code))
        if label:
            visible.append(f"{label}: {count}")
        else:
            other += count
    if other:
        visible.append(f"inne warunki bezpieczeństwa: {other}")
    return "; ".join(visible[:4])


def forex_runtime_cycle_text(value: object) -> str:
    cycle = dict(value) if isinstance(value, dict) else {}
    if cycle.get("available") is not True:
        return "Ostatnia decyzja: brak zapisanego cyklu PAPER."
    if cycle.get("status") == "SAFETY_VIOLATION":
        return (
            "Ostatnia decyzja: wynik odrzucony przez kontrolę bezpieczeństwa; "
            "LIVE pozostaje wyłączony."
        )
    decision = str(cycle.get("decision", ""))
    if decision == "PAPER_EXECUTED":
        return (
            "Ostatnia decyzja: wykonano "
            f"{_count(cycle.get('execution_count'))} lokalnych operacji PAPER."
        )
    reasons = _reason_text(cycle.get("reason_codes"))
    if decision == "NO_ENTRY_SIGNAL":
        base = (
            "Ostatnia decyzja: brak nowego sygnału wejścia; dane gotowe dla "
            f"{_count(cycle.get('ready_pair_count'))}/7 par."
        )
        return f"{base} Powody: {reasons}." if reasons else base
    if decision in {"DATA_BLOCKED", "PAIR_DATA_BLOCKED"}:
        if cycle.get("high_impact_event_window") is True:
            return (
                "Ostatnia decyzja: nowe wejścia wstrzymane przez okno ważnego "
                "wydarzenia; obsługa istniejących pozycji nadal działa."
            )
        base = "Ostatnia decyzja: cykl bez wejścia z powodu blokady danych."
        return f"{base} Powody: {reasons}." if reasons else base
    return "Ostatnia decyzja: cykl zakończony bez transakcji."


__all__ = ["forex_runtime_cycle_text"]

"""Polish, owner-facing labels for the immutable Forex PAPER review packet."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _count(value: object) -> int:
    try:
        return max(0, min(int(value or 0), 1_000_000))
    except (TypeError, ValueError):
        return 0


def _number(value: object, places: int) -> str | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or abs(number) > Decimal("1000000"):
        return None
    return f"{number:.{places}f}"


def _risk_detail(value: object) -> str:
    performance = dict(value) if isinstance(value, dict) else {}
    raw = performance.get("risk_diagnostics")
    risk = dict(raw) if isinstance(raw, dict) else {}
    count = _count(risk.get("closed_trade_count"))
    observed = _count(risk.get("risk_observed_trade_count"))
    missing = _count(risk.get("risk_missing_trade_count"))
    if count == 0:
        return " Dane R pojawią się po zamknięciu nowej pozycji."
    if observed > count or missing != count - observed:
        return " Dane R są chwilowo niedostępne; brakujące wartości nie są szacowane."
    if observed == 0:
        return (
            f" Dane R: 0/{count}; starsze zamknięcia nie miały zapisanego "
            "ryzyka, więc JARVIS niczego nie szacuje."
        )
    coverage = _number(risk.get("risk_coverage_pct"), 2)
    average = _number(risk.get("average_r_multiple"), 4)
    net = _number(risk.get("net_r_multiple"), 4)
    drawdown = _number(risk.get("maximum_observed_drawdown_r"), 4)
    loss_streak = _count(risk.get("maximum_observed_consecutive_losses"))
    if (
        coverage is None
        or average is None
        or net is None
        or drawdown is None
    ):
        return " Dane R są chwilowo niedostępne; brakujące wartości nie są szacowane."
    completeness = (
        "Zapis ryzyka jest pełny."
        if observed == count
        else "Brakujących wartości JARVIS nie szacuje."
    )
    return (
        f" Dane R: {observed}/{count} ({coverage}%); suma {net} R, "
        f"średnia {average} R, maksymalne obserwowane obsunięcie {drawdown} R, "
        f"najdłuższa seria strat {loss_streak}. "
        f"1 R oznacza początkowe ryzyko pozycji. "
        f"{completeness}"
    )


def forex_performance_review_view(
    value: object,
    performance: object = None,
) -> tuple[str, str, str]:
    review = dict(value) if isinstance(value, dict) else {}
    status = str(review.get("status", ""))
    source_valid = review.get("source_valid") is True
    persisted = review.get("packet_persisted") is True
    frozen = review.get("review_snapshot_frozen") is True
    if (
        status == "READY_FOR_OWNER_REVIEW"
        and source_valid
        and persisted
        and frozen
    ):
        return (
            "PRÓBKA: ZAMROŻONA",
            "healthy",
            "Pakiet wyniku PAPER jest niezmiennie zapisany i gotowy "
            "wyłącznie do ręcznego przeglądu."
            + _risk_detail(performance),
        )
    if status == "WAITING_FOR_PAPER_SAMPLE" and source_valid:
        count = _count(review.get("valid_closed_trade_count"))
        required = _count(review.get("minimum_closed_trades_for_review"))
        return (
            f"PRÓBKA: {count}/{required}",
            "accent",
            f"Pakiet wyniku PAPER: {count}/{required}; po ukończeniu próbki "
            "zostanie zapisany jako niezmienny materiał do przeglądu."
            + _risk_detail(performance),
        )
    return (
        "PRÓBKA: BLOKADA",
        "danger",
        "Pakiet wyniku PAPER jest zablokowany przez niespójne dowody; "
        "handel LIVE pozostaje wyłączony.",
    )


__all__ = ["forex_performance_review_view"]

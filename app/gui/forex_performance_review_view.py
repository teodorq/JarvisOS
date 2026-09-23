"""Polish, owner-facing labels for the immutable Forex PAPER review packet."""

from __future__ import annotations

from typing import Any


def _count(value: object) -> int:
    try:
        return max(0, min(int(value or 0), 1_000_000))
    except (TypeError, ValueError):
        return 0


def forex_performance_review_view(
    value: object,
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
            "wyłącznie do ręcznego przeglądu.",
        )
    if status == "WAITING_FOR_PAPER_SAMPLE" and source_valid:
        count = _count(review.get("valid_closed_trade_count"))
        required = _count(review.get("minimum_closed_trades_for_review"))
        return (
            f"PRÓBKA: {count}/{required}",
            "accent",
            f"Pakiet wyniku PAPER: {count}/{required}; po ukończeniu próbki "
            "zostanie zapisany jako niezmienny materiał do przeglądu.",
        )
    return (
        "PRÓBKA: BLOKADA",
        "danger",
        "Pakiet wyniku PAPER jest zablokowany przez niespójne dowody; "
        "handel LIVE pozostaje wyłączony.",
    )


__all__ = ["forex_performance_review_view"]

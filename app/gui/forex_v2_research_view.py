"""Plain-language summary of the verified Forex V2 signal sample."""

from __future__ import annotations


def _count(value: object) -> int:
    try:
        return max(0, min(int(value or 0), 1_000_000))
    except (TypeError, ValueError):
        return 0


def forex_v2_research_text(value: object) -> str:
    review = dict(value) if isinstance(value, dict) else {}
    status = str(review.get("status", ""))
    if review.get("source_valid") is not True:
        return (
            "Badanie V2: dowody są niespójne lub niedostępne. "
            "Strategia nie zostanie zmieniona, a LIVE pozostaje wyłączony."
        )
    cycles = _count(review.get("accepted_cycle_count"))
    required_cycles = _count(review.get("minimum_accepted_cycle_count"))
    days = _count(review.get("accepted_market_day_count"))
    required_days = _count(review.get("minimum_market_day_count"))
    if status == "WAITING_FOR_FORWARD_SAMPLE":
        return (
            f"Badanie V2: zbieranie sygnałów — {cycles}/{required_cycles} "
            f"cykli i {days}/{required_days} dni rynkowych. "
            "Nie jest to ocena skuteczności."
        )
    if status == "PENDING_IMMUTABLE_REVIEW_PACKET":
        return (
            "Badanie V2: próbka jest kompletna, ale czeka na niezmienny "
            "zapis. Nie daje to zgody na zmianę strategii ani LIVE."
        )
    if (
        status == "READY_FOR_OWNER_REVIEW"
        and review.get("packet_persisted") is True
        and review.get("review_snapshot_frozen") is True
    ):
        base = _count(review.get("base_entry_signal_count"))
        retained = _count(review.get("retained_entry_signal_count"))
        filtered = _count(review.get("filtered_entry_signal_count"))
        return (
            f"Badanie V2 zamrożone: {cycles} cykli / {days} dni; sygnały "
            f"bazowe {base}, pozostawione {retained}, odfiltrowane {filtered}. "
            "To tylko próbka zachowania sygnałów — nie wynik ani "
            "potwierdzenie skuteczności."
        )
    return (
        "Badanie V2: pakiet nie przeszedł pełnej kontroli. "
        "Strategia nie zostanie zmieniona, a LIVE pozostaje wyłączony."
    )


__all__ = ["forex_v2_research_text"]

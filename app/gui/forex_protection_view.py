"""Non-technical visual state for the local Forex PAPER position guard."""

from __future__ import annotations

from typing import Any


def forex_protection_view(value: object) -> tuple[str, str, str]:
    item = dict(value) if isinstance(value, dict) else {}
    status = str(item.get("status", "NO_HEARTBEAT"))
    failures = _count(item.get("consecutive_failure_count"))
    reason = " ".join(str(item.get("reason", "")).split())[:100]
    if not item.get("available"):
        return (
            "OCHRONA: BRAK STATUSU",
            "neutral",
            "Ochrona SL/TP oczekuje na heartbeat obserwatora.",
        )
    if item.get("attention_required") or status == "SAFETY_VIOLATION":
        detail = reason or "kolejne kontrole nie przeszły"
        return (
            "OCHRONA: UWAGA",
            "danger",
            f"Ochrona SL/TP wymaga uwagi: {detail} (licznik {failures}).",
        )
    if item.get("stale"):
        return (
            "OCHRONA: NIEAKTUALNA",
            "accent",
            "Heartbeat ochrony jest nieaktualny; observer spróbuje się odtworzyć.",
        )
    if not item.get("market_window_open"):
        return (
            "OCHRONA: RYNEK ZAMKNIĘTY",
            "neutral",
            "Ochrona wznowi kontrole po otwarciu rynku Forex.",
        )
    if status == "PAPER_PROTECTION_BLOCKED":
        return (
            "OCHRONA: PONOWI PRÓBĘ",
            "accent",
            "Pojedyncza kontrola została bezpiecznie pominięta; ponowię ją za minutę.",
        )
    if status == "PAPER_PROTECTION_APPLIED":
        return (
            "OCHRONA: ZADZIAŁAŁA",
            "healthy",
            "Ochrona zastosowała SL lub TP wyłącznie w lokalnym PAPER.",
        )
    if (
        item.get("recent_recovery")
        and status in {"NO_PROTECTION_TRIGGER", "NO_OPEN_POSITIONS"}
    ):
        gap = _duration(item.get("last_recovery_gap_seconds"))
        return (
            "OCHRONA: WZNOWIONA",
            "healthy",
            f"Po przerwie {gap} ochrona sprawdziła pozycje przed nowym cyklem.",
        )
    if status in {"NO_PROTECTION_TRIGGER", "NO_OPEN_POSITIONS"}:
        return (
            "OCHRONA: DZIAŁA",
            "healthy",
            "Ochrona SL/TP działa; brak działania do wykonania.",
        )
    return (
        "OCHRONA: OCZEKUJE",
        "neutral",
        "Ochrona SL/TP oczekuje na pierwszą kontrolę minutową.",
    )


def _count(value: object) -> int:
    try:
        return max(0, min(1_000, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def _duration(value: object) -> str:
    try:
        seconds = max(0, min(604_800, int(value or 0)))
    except (TypeError, ValueError):
        seconds = 0
    minutes = max(1, seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, remainder = divmod(minutes, 60)
    if remainder:
        return f"{hours} godz. {remainder} min"
    return f"{hours} godz."


__all__ = ["forex_protection_view"]

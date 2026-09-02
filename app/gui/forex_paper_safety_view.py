"""Small presentation helper for the read-only Forex PAPER safety banner."""

from __future__ import annotations

from typing import Any, Mapping


def forex_paper_safety_view(
    snapshot: Mapping[str, Any],
) -> tuple[str, str, str]:
    ready = snapshot.get("status") == "READY"
    raw = snapshot.get("loss_streak_safety")
    safety = dict(raw) if isinstance(raw, dict) else {}
    raw_weekly = snapshot.get("weekly_loss_safety")
    weekly = dict(raw_weekly) if isinstance(raw_weekly, dict) else {}
    weekly_paused = weekly.get("active") is True
    paused = safety.get("active") is True or weekly_paused
    label = (
        "PAPER — PRZERWA"
        if ready and paused
        else "PAPER AKTYWNY" if ready else "WYMAGA UWAGI"
    )
    tone = "neutral" if ready and paused else "healthy" if ready else "danger"
    current = _count(safety.get("current_consecutive_losses"), 0)
    threshold = max(2, _count(safety.get("threshold"), 3))
    if weekly_paused:
        entry_state = "NOWE WEJŚCIA: PRZERWA (LIMIT TYGODNIOWY)"
    elif paused:
        entry_state = "NOWE WEJŚCIA: PRZERWA"
    else:
        entry_state = f"SERIA STRAT: {current}/{threshold}"
    banner = (
        "● PAPER ONLY   ● BROKER: BRAK ZLECEŃ   "
        "● PRAWDZIWE PIENIĄDZE: BRAK DOSTĘPU   ● " + entry_state
    )
    return label, tone, banner


def _count(value: object, fallback: int) -> int:
    try:
        return max(0, min(int(value), 1_000_000))
    except (TypeError, ValueError):
        return fallback


__all__ = ["forex_paper_safety_view"]

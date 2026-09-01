"""Read-only lifecycle diagnostics for closed Forex PAPER trades."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from app.trading.forex_models import MAJOR_FOREX_PAIRS


_PAIR_SYMBOLS = frozenset(pair.symbol for pair in MAJOR_FOREX_PAIRS)
_MINUTES = Decimal("0.01")
_MAX_HOLDING_SECONDS = 10 * 366 * 24 * 60 * 60


def _timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _minutes(seconds: Decimal) -> str:
    return str(
        (seconds / Decimal("60")).quantize(
            _MINUTES,
            rounding=ROUND_HALF_UP,
        )
    )


def _reason(item: Mapping[str, Any]) -> str:
    raw = item.get("reason_codes")
    values = list(raw) if isinstance(raw, (list, tuple)) else []
    codes = {
        str(value).strip().upper()[:80]
        for value in values[:8]
        if str(value).strip()
    }
    if "STOP_LOSS_TRIGGERED" in codes:
        return "stop_loss"
    if "TAKE_PROFIT_TRIGGERED" in codes:
        return "take_profit"
    if codes:
        return "strategy"
    return "unspecified"


def build_forex_trade_diagnostics(
    closed_fills: Iterable[Mapping[str, Any] | object],
) -> dict[str, Any]:
    """Summarize observed lifecycles without changing trading decisions."""

    durations: list[Decimal] = []
    reasons = {
        "stop_loss": 0,
        "take_profit": 0,
        "strategy": 0,
        "unspecified": 0,
    }
    closed_count = 0
    for raw in tuple(closed_fills):
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        if (
            not str(item.get("action", "")).strip().upper().startswith("CLOSE_")
            or str(item.get("pair", "")).strip().upper() not in _PAIR_SYMBOLS
        ):
            continue
        closed_count += 1
        reasons[_reason(item)] += 1
        opened = _timestamp(item.get("opened_at"))
        closed = _timestamp(item.get("closed_at") or item.get("filled_at"))
        if opened is None or closed is None:
            continue
        seconds = Decimal(str((closed - opened).total_seconds()))
        if seconds < 0 or seconds > _MAX_HOLDING_SECONDS:
            continue
        durations.append(seconds)

    ordered = sorted(durations)
    if ordered:
        middle = len(ordered) // 2
        median = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / Decimal("2")
        )
        average = sum(ordered, Decimal("0")) / Decimal(len(ordered))
        average_minutes: str | None = _minutes(average)
        median_minutes: str | None = _minutes(median)
        shortest_minutes: str | None = _minutes(ordered[0])
        longest_minutes: str | None = _minutes(ordered[-1])
    else:
        average_minutes = None
        median_minutes = None
        shortest_minutes = None
        longest_minutes = None
    holding_complete = len(durations) == closed_count
    reason_complete = reasons["unspecified"] == 0
    if closed_count == 0:
        status = "NO_CLOSED_TRADES"
    elif holding_complete and reason_complete:
        status = "COMPLETE"
    else:
        status = "INCOMPLETE"
    return {
        "status": status,
        "mode": "FOREX_PAPER_TRADE_DIAGNOSTICS_READ_ONLY",
        "closed_trade_count": closed_count,
        "holding_time_observed_count": len(durations),
        "holding_time_missing_count": closed_count - len(durations),
        "average_holding_minutes": average_minutes,
        "median_holding_minutes": median_minutes,
        "shortest_holding_minutes": shortest_minutes,
        "longest_holding_minutes": longest_minutes,
        "exit_reason_counts": {
            "stop_loss": reasons["stop_loss"],
            "take_profit": reasons["take_profit"],
            "strategy": reasons["strategy"],
            "unspecified": reasons["unspecified"],
        },
        "holding_time_coverage_complete": holding_complete,
        "exit_reason_coverage_complete": reason_complete,
        "diagnostics_complete": holding_complete and reason_complete,
        "performance_validated": False,
        "automatic_strategy_change": False,
        "live_promotion_ready": False,
    }


__all__ = ["build_forex_trade_diagnostics"]

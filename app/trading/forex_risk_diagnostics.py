"""Read-only risk-normalized diagnostics for closed Forex PAPER trades."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from app.trading.forex_models import MAJOR_FOREX_PAIRS


_PAIR_SYMBOLS = frozenset(pair.symbol for pair in MAJOR_FOREX_PAIRS)
_RATIO = Decimal("0.0001")
_PERCENT = Decimal("0.01")
_MAX_ABSOLUTE_VALUE = Decimal("1000000000000")
_MAX_ABSOLUTE_R_MULTIPLE = Decimal("1000000")


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite() or abs(result) > _MAX_ABSOLUTE_VALUE:
        return None
    return result


def _text(value: Decimal, quantum: Decimal) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


def build_forex_risk_diagnostics(
    closed_fills: Iterable[Mapping[str, Any] | object],
) -> dict[str, Any]:
    """Summarize realized P/L per recorded initial risk without taking action."""

    closed_count = 0
    multiples: list[Decimal] = []
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
        pnl = _decimal(item.get("realized_pnl_pln"))
        risk = _decimal(item.get("initial_risk_pln"))
        if pnl is None or risk is None or risk <= 0:
            continue
        multiple = pnl / risk
        if (
            not multiple.is_finite()
            or abs(multiple) > _MAX_ABSOLUTE_R_MULTIPLE
        ):
            continue
        multiples.append(multiple)

    observed_count = len(multiples)
    missing_count = closed_count - observed_count
    coverage = (
        Decimal(observed_count) * Decimal("100") / Decimal(closed_count)
        if closed_count
        else Decimal("0")
    )
    ordered = sorted(multiples)
    if ordered:
        winning_count = sum(value > 0 for value in multiples)
        losing_count = sum(value < 0 for value in multiples)
        breakeven_count = len(multiples) - winning_count - losing_count
        cumulative = Decimal("0")
        peak = Decimal("0")
        maximum_drawdown = Decimal("0")
        current_loss_streak = 0
        maximum_loss_streak = 0
        for value in multiples:
            cumulative += value
            peak = max(peak, cumulative)
            maximum_drawdown = max(maximum_drawdown, peak - cumulative)
            if value < 0:
                current_loss_streak += 1
                maximum_loss_streak = max(
                    maximum_loss_streak,
                    current_loss_streak,
                )
            else:
                current_loss_streak = 0
        middle = len(ordered) // 2
        median = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / Decimal("2")
        )
        net: str | None = _text(sum(ordered, Decimal("0")), _RATIO)
        average: str | None = _text(
            sum(ordered, Decimal("0")) / Decimal(len(ordered)),
            _RATIO,
        )
        median_value: str | None = _text(median, _RATIO)
        best: str | None = _text(ordered[-1], _RATIO)
        worst: str | None = _text(ordered[0], _RATIO)
        maximum_drawdown_r: str | None = _text(
            maximum_drawdown,
            _RATIO,
        )
    else:
        winning_count = 0
        losing_count = 0
        breakeven_count = 0
        current_loss_streak = 0
        maximum_loss_streak = 0
        net = None
        average = None
        median_value = None
        best = None
        worst = None
        maximum_drawdown_r = None

    if closed_count == 0:
        status = "NO_CLOSED_TRADES"
    elif observed_count == 0:
        status = "NO_RISK_TELEMETRY"
    elif missing_count == 0:
        status = "COMPLETE"
    else:
        status = "PARTIAL"
    return {
        "status": status,
        "mode": "FOREX_PAPER_RISK_DIAGNOSTICS_READ_ONLY",
        "closed_trade_count": closed_count,
        "risk_observed_trade_count": observed_count,
        "risk_missing_trade_count": missing_count,
        "risk_coverage_pct": _text(coverage, _PERCENT),
        "net_r_multiple": net,
        "average_r_multiple": average,
        "median_r_multiple": median_value,
        "best_r_multiple": best,
        "worst_r_multiple": worst,
        "winning_r_trade_count": winning_count,
        "losing_r_trade_count": losing_count,
        "breakeven_r_trade_count": breakeven_count,
        "maximum_observed_drawdown_r": maximum_drawdown_r,
        "maximum_observed_consecutive_losses": maximum_loss_streak,
        "current_observed_consecutive_losses": current_loss_streak,
        "risk_coverage_complete": closed_count == observed_count,
        "performance_validated": False,
        "automatic_strategy_change": False,
        "live_promotion_ready": False,
    }


__all__ = ["build_forex_risk_diagnostics"]

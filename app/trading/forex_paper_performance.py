"""Read-only performance evidence derived from the local Forex PAPER ledger."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from app.trading.forex_models import MAJOR_FOREX_PAIRS
from app.trading.models import TradingValidationError


_MONEY = Decimal("0.01")
_PERCENT = Decimal("0.01")
_RATIO = Decimal("0.0001")
_MAX_ABSOLUTE_VALUE = Decimal("1000000000000")


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


def _text(value: Decimal, quantum: Decimal = _MONEY) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class ForexPaperPerformancePolicy:
    """A sample threshold for manual review, never for automatic promotion."""

    minimum_closed_trades_for_review: int = 20

    def __post_init__(self) -> None:
        value = self.minimum_closed_trades_for_review
        if type(value) is not int or not 1 <= value <= 10_000:
            raise TradingValidationError(
                "forex_paper_performance: invalid_sample_threshold"
            )


def build_forex_paper_performance_review(
    closed_fills: Iterable[Mapping[str, Any] | object],
    *,
    initial_balance_pln: object,
    current_balance_pln: object,
    audit_chain_valid: bool,
    execution_audit_matches_ledger: bool,
    policy: ForexPaperPerformancePolicy | None = None,
) -> dict[str, Any]:
    """Summarize immutable PAPER evidence without changing trading state."""

    selected_policy = policy or ForexPaperPerformancePolicy()
    values: list[Decimal] = []
    pair_values: dict[str, list[Decimal]] = {
        pair.symbol: [] for pair in MAJOR_FOREX_PAIRS
    }
    invalid_fill_count = 0
    for raw in tuple(closed_fills):
        if not isinstance(raw, Mapping):
            invalid_fill_count += 1
            continue
        item = dict(raw)
        action = str(item.get("action", "")).strip().upper()
        pair = str(item.get("pair", "")).strip().upper()
        pnl = _decimal(item.get("realized_pnl_pln"))
        if (
            not action.startswith("CLOSE_")
            or pair not in pair_values
            or pnl is None
        ):
            invalid_fill_count += 1
            continue
        values.append(pnl)
        pair_values[pair].append(pnl)

    initial_balance = _decimal(initial_balance_pln)
    current_balance = _decimal(current_balance_pln)
    balance_values_valid = bool(
        initial_balance is not None
        and current_balance is not None
        and initial_balance > 0
        and current_balance >= 0
    )
    initial = initial_balance or Decimal("0")
    current = current_balance or Decimal("0")
    net = sum(values, Decimal("0"))
    reconciliation_delta = current - (initial + net)
    balance_reconciled = bool(
        balance_values_valid and abs(reconciliation_delta) <= _MONEY
    )

    profits = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    breakeven_count = len(values) - len(profits) - len(losses)
    gross_profit = sum(profits, Decimal("0"))
    gross_loss_abs = abs(sum(losses, Decimal("0")))
    average = net / Decimal(len(values)) if values else Decimal("0")
    average_win = (
        gross_profit / Decimal(len(profits)) if profits else Decimal("0")
    )
    average_loss = (
        -gross_loss_abs / Decimal(len(losses)) if losses else Decimal("0")
    )
    win_rate = (
        Decimal(len(profits)) * Decimal("100") / Decimal(len(values))
        if values
        else Decimal("0")
    )

    equity = initial
    peak = initial
    maximum_drawdown = Decimal("0")
    maximum_drawdown_pct = Decimal("0")
    current_loss_streak = 0
    maximum_loss_streak = 0
    for pnl in values:
        equity += pnl
        peak = max(peak, equity)
        drawdown = max(Decimal("0"), peak - equity)
        drawdown_pct = (
            drawdown * Decimal("100") / peak
            if peak > 0
            else Decimal("0")
        )
        maximum_drawdown = max(maximum_drawdown, drawdown)
        maximum_drawdown_pct = max(maximum_drawdown_pct, drawdown_pct)
        if pnl < 0:
            current_loss_streak += 1
            maximum_loss_streak = max(
                maximum_loss_streak, current_loss_streak
            )
        else:
            current_loss_streak = 0

    if gross_loss_abs > 0:
        profit_factor = _text(gross_profit / gross_loss_abs, _RATIO)
        profit_factor_status = "CALCULATED"
    elif values:
        profit_factor = None
        profit_factor_status = "NO_GROSS_LOSS"
    else:
        profit_factor = None
        profit_factor_status = "NO_CLOSED_TRADES"

    evidence_valid = bool(
        audit_chain_valid is True
        and execution_audit_matches_ledger is True
        and invalid_fill_count == 0
        and balance_reconciled
    )
    required = selected_policy.minimum_closed_trades_for_review
    remaining = max(0, required - len(values))
    sample_ready = bool(evidence_valid and len(values) >= required)
    if not evidence_valid:
        status = "BLOCKED_INVALID_EVIDENCE"
    elif sample_ready:
        status = "READY_FOR_MANUAL_REVIEW"
    else:
        status = "COLLECTING_PAPER_SAMPLE"

    pair_breakdown: dict[str, dict[str, Any]] = {}
    ready_pairs: list[str] = []
    collecting_pairs: list[str] = []
    unobserved_pairs: list[str] = []
    blocked_pairs: list[str] = []
    for pair, outcomes in pair_values.items():
        pair_profits = [value for value in outcomes if value > 0]
        pair_losses = [value for value in outcomes if value < 0]
        pair_net = sum(outcomes, Decimal("0"))
        pair_gross_profit = sum(pair_profits, Decimal("0"))
        pair_gross_loss = abs(sum(pair_losses, Decimal("0")))
        pair_average = (
            pair_net / Decimal(len(outcomes))
            if outcomes
            else Decimal("0")
        )
        pair_win_rate = (
            Decimal(len(pair_profits)) * 100 / Decimal(len(outcomes))
            if outcomes
            else Decimal("0")
        )
        pair_loss_streak = 0
        pair_maximum_loss_streak = 0
        for outcome in outcomes:
            if outcome < 0:
                pair_loss_streak += 1
                pair_maximum_loss_streak = max(
                    pair_maximum_loss_streak, pair_loss_streak
                )
            else:
                pair_loss_streak = 0
        pair_remaining = max(0, required - len(outcomes))
        pair_sample_ready = bool(evidence_valid and len(outcomes) >= required)
        if not evidence_valid:
            pair_review_status = "BLOCKED_INVALID_EVIDENCE"
            blocked_pairs.append(pair)
        elif not outcomes:
            pair_review_status = "NO_CLOSED_TRADES"
            unobserved_pairs.append(pair)
        elif pair_sample_ready:
            pair_review_status = "READY_FOR_MANUAL_REVIEW"
            ready_pairs.append(pair)
        else:
            pair_review_status = "COLLECTING_PAIR_SAMPLE"
            collecting_pairs.append(pair)
        pair_breakdown[pair] = {
            "closed_trade_count": len(outcomes),
            "winning_trade_count": len(pair_profits),
            "losing_trade_count": len(pair_losses),
            "breakeven_trade_count": (
                len(outcomes) - len(pair_profits) - len(pair_losses)
            ),
            "win_rate_pct": _text(pair_win_rate, _PERCENT),
            "net_realized_pnl_pln": _text(pair_net),
            "average_trade_pnl_pln": _text(pair_average),
            "profit_factor": (
                _text(pair_gross_profit / pair_gross_loss, _RATIO)
                if pair_gross_loss > 0
                else None
            ),
            "maximum_consecutive_losses": pair_maximum_loss_streak,
            "minimum_closed_trades_for_review": required,
            "remaining_closed_trades_for_review": pair_remaining,
            "sample_progress_pct": _text(
                min(
                    Decimal("100"),
                    Decimal(len(outcomes)) * 100 / Decimal(required),
                ),
                _PERCENT,
            ),
            "sample_size_sufficient_for_review": pair_sample_ready,
            "review_status": pair_review_status,
            "performance_validated": False,
            "automatic_pair_selection": False,
        }

    pair_review_status = (
        "BLOCKED_INVALID_EVIDENCE"
        if blocked_pairs
        else (
            "READY_FOR_MANUAL_REVIEW"
            if len(ready_pairs) == len(pair_values)
            else "COLLECTING_PAIR_SAMPLES"
        )
    )
    pair_review = {
        "status": pair_review_status,
        "mode": "FOREX_PAIR_REVIEW_READ_ONLY",
        "pair_count": len(pair_values),
        "minimum_closed_trades_per_pair_for_review": required,
        "ready_pair_count": len(ready_pairs),
        "collecting_pair_count": len(collecting_pairs),
        "unobserved_pair_count": len(unobserved_pairs),
        "blocked_pair_count": len(blocked_pairs),
        "ready_pairs": ready_pairs,
        "collecting_pairs": collecting_pairs,
        "unobserved_pairs": unobserved_pairs,
        "blocked_pairs": blocked_pairs,
        "all_pairs_ready_for_manual_review": len(ready_pairs) == len(pair_values),
        "automatic_pair_selection": False,
        "automatic_pair_disable": False,
        "live_promotion_ready": False,
    }

    return {
        "status": status,
        "mode": "FOREX_PAPER_PERFORMANCE_READ_ONLY",
        "minimum_closed_trades_for_review": required,
        "valid_closed_trade_count": len(values),
        "remaining_closed_trades_for_review": remaining,
        "sample_progress_pct": _text(
            min(Decimal("100"), Decimal(len(values)) * 100 / Decimal(required)),
            _PERCENT,
        ),
        "sample_size_sufficient_for_review": sample_ready,
        "winning_trade_count": len(profits),
        "losing_trade_count": len(losses),
        "breakeven_trade_count": breakeven_count,
        "win_rate_pct": _text(win_rate, _PERCENT),
        "net_realized_pnl_pln": _text(net),
        "gross_profit_pln": _text(gross_profit),
        "gross_loss_abs_pln": _text(gross_loss_abs),
        "average_trade_pnl_pln": _text(average),
        "average_win_pnl_pln": _text(average_win),
        "average_loss_pnl_pln": _text(average_loss),
        "profit_factor": profit_factor,
        "profit_factor_status": profit_factor_status,
        "maximum_closed_trade_drawdown_pln": _text(maximum_drawdown),
        "maximum_closed_trade_drawdown_pct": _text(
            maximum_drawdown_pct, _PERCENT
        ),
        "maximum_consecutive_losses": maximum_loss_streak,
        "current_consecutive_losses": current_loss_streak,
        "pair_breakdown": pair_breakdown,
        "pair_review": pair_review,
        "integrity": {
            "evidence_valid": evidence_valid,
            "audit_chain_valid": audit_chain_valid is True,
            "execution_audit_matches_ledger": (
                execution_audit_matches_ledger is True
            ),
            "balance_reconciled": balance_reconciled,
            "balance_reconciliation_delta_pln": _text(
                reconciliation_delta
            ),
            "invalid_closed_fill_count": invalid_fill_count,
        },
        "performance_validated": False,
        "automatic_paper_strategy_change": False,
        "live_promotion_ready": False,
        "automatic_live_promotion": False,
    }


__all__ = [
    "ForexPaperPerformancePolicy",
    "build_forex_paper_performance_review",
]

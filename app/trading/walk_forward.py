"""Chronological holdout and rolling walk-forward paper research."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from app.trading.backtest import HistoricalPaperBacktester
from app.trading.models import MarketBar, StrategySignal, TradingValidationError
from app.trading.policy import PaperTradingPolicy


_PERCENT = Decimal("0.0001")
_MAX_BARS = 500_000
_MAX_SIGNALS = 500_000
_MAX_WINDOWS = 1_000


def _percent(value: Decimal) -> str:
    return str(value.quantize(_PERCENT, rounding=ROUND_HALF_UP))


def _validated_bars(
    values: Iterable[MarketBar],
    *,
    field: str,
) -> tuple[MarketBar, ...]:
    bars = tuple(values)
    if any(not isinstance(bar, MarketBar) for bar in bars):
        raise TradingValidationError(f"walk_forward: {field}_bar_required")
    if len(bars) < 2:
        raise TradingValidationError(f"walk_forward: {field}_requires_two_bars")
    if len(bars) > _MAX_BARS:
        raise TradingValidationError(f"walk_forward: {field}_bar_limit_exceeded")
    if any(
        right.timestamp <= left.timestamp
        for left, right in zip(bars, bars[1:])
    ):
        raise TradingValidationError(
            f"walk_forward: {field}_not_strictly_chronological"
        )
    if len({bar.symbol for bar in bars}) != 1:
        raise TradingValidationError(f"walk_forward: {field}_symbol_mismatch")
    if len({bar.currency for bar in bars}) != 1:
        raise TradingValidationError(f"walk_forward: {field}_currency_mismatch")
    return bars


def _validated_signals(
    values: Iterable[StrategySignal],
    *,
    bars: tuple[MarketBar, ...],
    field: str,
) -> tuple[StrategySignal, ...]:
    raw_signals = tuple(values)
    if any(not isinstance(signal, StrategySignal) for signal in raw_signals):
        raise TradingValidationError(f"walk_forward: {field}_signal_required")
    signals = tuple(sorted(raw_signals, key=lambda item: item.timestamp))
    if len(signals) > _MAX_SIGNALS:
        raise TradingValidationError(f"walk_forward: {field}_signal_limit_exceeded")
    identifiers = [signal.signal_id for signal in signals]
    if len(identifiers) != len(set(identifiers)):
        raise TradingValidationError(f"walk_forward: {field}_duplicate_signal_id")
    if any(signal.symbol != bars[0].symbol for signal in signals):
        raise TradingValidationError(f"walk_forward: {field}_signal_symbol_mismatch")
    if any(
        signal.timestamp < bars[0].timestamp
        or signal.timestamp > bars[-1].timestamp
        for signal in signals
    ):
        raise TradingValidationError(f"walk_forward: {field}_signal_outside_window")
    return signals


class ChronologicalHoldoutValidator:
    """Compare an earlier training period with a later isolated test period."""

    def __init__(self, policy: PaperTradingPolicy | None = None) -> None:
        self.policy = policy or PaperTradingPolicy()
        self.backtester = HistoricalPaperBacktester(self.policy)

    def run(
        self,
        *,
        training_bars: Iterable[MarketBar],
        testing_bars: Iterable[MarketBar],
        training_signals: Iterable[StrategySignal] = (),
        testing_signals: Iterable[StrategySignal] = (),
    ) -> dict[str, Any]:
        training = _validated_bars(training_bars, field="training")
        testing = _validated_bars(testing_bars, field="testing")
        if training[-1].timestamp >= testing[0].timestamp:
            raise TradingValidationError("walk_forward: periods_overlap")
        if training[0].symbol != testing[0].symbol:
            raise TradingValidationError("walk_forward: period_symbol_mismatch")
        if training[0].currency != testing[0].currency:
            raise TradingValidationError("walk_forward: period_currency_mismatch")
        selected_training_signals = _validated_signals(
            training_signals,
            bars=training,
            field="training",
        )
        selected_testing_signals = _validated_signals(
            testing_signals,
            bars=testing,
            field="testing",
        )
        identifiers = {
            signal.signal_id for signal in selected_training_signals
        }
        if identifiers.intersection(
            signal.signal_id for signal in selected_testing_signals
        ):
            raise TradingValidationError("walk_forward: signal_reused_across_periods")

        training_result = self.backtester.run(
            training,
            selected_training_signals,
        )
        testing_result = self.backtester.run(
            testing,
            selected_testing_signals,
        )
        training_return = Decimal(training_result["total_return_pct"])
        testing_return = Decimal(testing_result["total_return_pct"])
        return {
            "status": "CHRONOLOGICAL_HOLDOUT_COMPLETED",
            "mode": "HISTORICAL_RESEARCH_ONLY",
            "symbol": training[0].symbol,
            "currency": training[0].currency,
            "training_started_at": training[0].timestamp.isoformat(),
            "training_ended_at": training[-1].timestamp.isoformat(),
            "testing_started_at": testing[0].timestamp.isoformat(),
            "testing_ended_at": testing[-1].timestamp.isoformat(),
            "training_bar_count": len(training),
            "testing_bar_count": len(testing),
            "training_signal_count": len(selected_training_signals),
            "testing_signal_count": len(selected_testing_signals),
            "training": training_result,
            "testing": testing_result,
            "generalization_gap_pct": _percent(
                testing_return - training_return
            ),
            "chronological_split_valid": True,
            "period_overlap_detected": False,
            "test_account_isolated": True,
            "same_bar_execution_blocked": True,
            "external_signal_generation_audited": False,
            "parameter_optimization_performed_by_validator": False,
            "automatic_paper_promotion": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }


@dataclass(frozen=True, slots=True)
class WalkForwardPolicy:
    training_bar_count: int = 120
    testing_bar_count: int = 40
    step_bar_count: int = 40
    minimum_window_count: int = 2

    def __post_init__(self) -> None:
        for name, value in (
            ("training_bar_count", self.training_bar_count),
            ("testing_bar_count", self.testing_bar_count),
            ("step_bar_count", self.step_bar_count),
            ("minimum_window_count", self.minimum_window_count),
        ):
            if type(value) is not int:
                raise TradingValidationError(f"walk_forward: {name}_must_be_integer")
        if not 2 <= self.training_bar_count <= 250_000:
            raise TradingValidationError("walk_forward: invalid_training_bar_count")
        if not 2 <= self.testing_bar_count <= 250_000:
            raise TradingValidationError("walk_forward: invalid_testing_bar_count")
        if not self.testing_bar_count <= self.step_bar_count <= 250_000:
            raise TradingValidationError("walk_forward: overlapping_test_windows")
        if not 1 <= self.minimum_window_count <= 1_000:
            raise TradingValidationError("walk_forward: invalid_minimum_window_count")


class HistoricalWalkForwardValidator:
    """Run fixed strategy signals through non-overlapping future test windows."""

    def __init__(
        self,
        policy: PaperTradingPolicy | None = None,
        *,
        walk_forward_policy: WalkForwardPolicy | None = None,
    ) -> None:
        self.policy = policy or PaperTradingPolicy()
        self.walk_forward_policy = walk_forward_policy or WalkForwardPolicy()
        self.holdout = ChronologicalHoldoutValidator(self.policy)

    def run(
        self,
        bars: Iterable[MarketBar],
        signals: Iterable[StrategySignal],
    ) -> dict[str, Any]:
        history = _validated_bars(bars, field="history")
        ordered_signals = _validated_signals(
            signals,
            bars=history,
            field="history",
        )

        config = self.walk_forward_policy
        required = config.training_bar_count + config.testing_bar_count
        windows: list[dict[str, Any]] = []
        maximum_start = len(history) - required
        expected_windows = (
            maximum_start // config.step_bar_count + 1
            if maximum_start >= 0
            else 0
        )
        if expected_windows > _MAX_WINDOWS:
            raise TradingValidationError("walk_forward: window_limit_exceeded")
        for start in range(0, maximum_start + 1, config.step_bar_count):
            training_end = start + config.training_bar_count
            testing_end = training_end + config.testing_bar_count
            training = history[start:training_end]
            testing = history[training_end:testing_end]
            training_signals = self._signals_for(ordered_signals, training)
            testing_signals = self._signals_for(ordered_signals, testing)
            result = self.holdout.run(
                training_bars=training,
                testing_bars=testing,
                training_signals=training_signals,
                testing_signals=testing_signals,
            )
            result["window"] = len(windows) + 1
            windows.append(result)
        if len(windows) < config.minimum_window_count:
            raise TradingValidationError("walk_forward: insufficient_window_count")

        testing_returns = [
            Decimal(window["testing"]["total_return_pct"])
            for window in windows
        ]
        testing_drawdowns = [
            Decimal(window["testing"]["max_drawdown_pct"])
            for window in windows
        ]
        gaps = [Decimal(window["generalization_gap_pct"]) for window in windows]
        count = Decimal(len(windows))
        return {
            "status": "WALK_FORWARD_COMPLETED",
            "mode": "HISTORICAL_RESEARCH_ONLY",
            "symbol": history[0].symbol,
            "currency": history[0].currency,
            "source_bar_count": len(history),
            "source_signal_count": len(ordered_signals),
            "window_count": len(windows),
            "minimum_window_count": config.minimum_window_count,
            "training_bar_count_per_window": config.training_bar_count,
            "testing_bar_count_per_window": config.testing_bar_count,
            "step_bar_count": config.step_bar_count,
            "out_of_sample_started_at": windows[0]["testing_started_at"],
            "out_of_sample_ended_at": windows[-1]["testing_ended_at"],
            "out_of_sample_fill_count": sum(
                int(window["testing"]["fill_count"]) for window in windows
            ),
            "out_of_sample_rejection_count": sum(
                int(window["testing"]["rejection_count"]) for window in windows
            ),
            "profitable_out_of_sample_window_count": sum(
                value > 0 for value in testing_returns
            ),
            "average_out_of_sample_return_pct": _percent(
                sum(testing_returns, Decimal("0")) / count
            ),
            "worst_out_of_sample_return_pct": _percent(min(testing_returns)),
            "best_out_of_sample_return_pct": _percent(max(testing_returns)),
            "maximum_out_of_sample_drawdown_pct": _percent(
                max(testing_drawdowns)
            ),
            "average_generalization_gap_pct": _percent(
                sum(gaps, Decimal("0")) / count
            ),
            "windows": windows,
            "chronological_splits_valid": True,
            "out_of_sample_windows_non_overlapping": True,
            "same_bar_execution_blocked": True,
            "external_signal_generation_audited": False,
            "parameter_optimization_performed_by_validator": False,
            "research_only": True,
            "automatic_paper_promotion": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }

    @staticmethod
    def _signals_for(
        signals: tuple[StrategySignal, ...],
        bars: tuple[MarketBar, ...],
    ) -> tuple[StrategySignal, ...]:
        return tuple(
            signal for signal in signals
            if bars[0].timestamp <= signal.timestamp <= bars[-1].timestamp
        )


__all__ = [
    "ChronologicalHoldoutValidator",
    "HistoricalWalkForwardValidator",
    "WalkForwardPolicy",
]

"""Audited, bidirectional Forex research on closed historical bars."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Iterable

from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_models import ForexPair, major_pair
from app.trading.models import (
    MarketBar,
    TradingValidationError,
    aware_utc,
    decimal_value,
    normalized_symbol,
)


_SIGNAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MONEY = Decimal("0.01")
_PERCENT = Decimal("0.0001")
_PRICE = Decimal("0.000001")
_MAX_BARS = 500_000
_MAX_SIGNALS = 50_000
_MAX_WINDOWS = 1_000


def _text(value: Decimal, quantum: Decimal = _MONEY) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _validated_bars(
    values: Iterable[MarketBar],
    *,
    minimum: int,
) -> tuple[ForexPair, tuple[MarketBar, ...]]:
    bars = tuple(values)
    if len(bars) < minimum:
        raise TradingValidationError("forex_history: insufficient_bars")
    if len(bars) > _MAX_BARS:
        raise TradingValidationError("forex_history: bar_limit_exceeded")
    if any(not isinstance(bar, MarketBar) for bar in bars):
        raise TradingValidationError("forex_history: market_bar_required")
    if any(
        right.timestamp <= left.timestamp
        for left, right in zip(bars, bars[1:])
    ):
        raise TradingValidationError("forex_history: bars_not_strictly_ordered")
    if len({bar.symbol for bar in bars}) != 1:
        raise TradingValidationError("forex_history: one_pair_per_run")
    pair = major_pair(bars[0].symbol)
    if {bar.currency for bar in bars} != {pair.quote_currency}:
        raise TradingValidationError("forex_history: quote_currency_mismatch")
    return pair, bars


@dataclass(frozen=True, slots=True)
class ForexHistoricalPolicy:
    """Fixed research assumptions; never controls a broker account."""

    fast_window: int = 10
    slow_window: int = 30
    initial_equity_quote: Decimal = Decimal("100000")
    position_notional_pct: Decimal = Decimal("0.10")
    assumed_spread_pips: Decimal = Decimal("1.5")
    assumed_slippage_pips: Decimal = Decimal("0.2")
    minimum_stop_pips: Decimal = ForexPaperCoordinator.MINIMUM_STOP_PIPS
    maximum_stop_pips: Decimal = ForexPaperCoordinator.MAXIMUM_STOP_PIPS
    take_profit_reward_risk: Decimal = Decimal("2")

    def __post_init__(self) -> None:
        if type(self.fast_window) is not int or type(self.slow_window) is not int:
            raise TradingValidationError("forex_history: windows_must_be_integer")
        if not 2 <= self.fast_window < self.slow_window <= 200:
            raise TradingValidationError("forex_history: invalid_windows")
        equity = decimal_value(self.initial_equity_quote, "initial_equity_quote")
        notional = decimal_value(self.position_notional_pct, "position_notional_pct")
        spread = decimal_value(
            self.assumed_spread_pips,
            "assumed_spread_pips",
            allow_zero=True,
        )
        slippage = decimal_value(
            self.assumed_slippage_pips,
            "assumed_slippage_pips",
            allow_zero=True,
        )
        minimum_stop = decimal_value(self.minimum_stop_pips, "minimum_stop_pips")
        maximum_stop = decimal_value(self.maximum_stop_pips, "maximum_stop_pips")
        reward_risk = decimal_value(
            self.take_profit_reward_risk,
            "take_profit_reward_risk",
        )
        if equity < Decimal("1000") or equity > Decimal("100000000"):
            raise TradingValidationError("forex_history: invalid_initial_equity")
        if not Decimal("0.01") <= notional <= Decimal("0.50"):
            raise TradingValidationError("forex_history: unsafe_notional_pct")
        if spread > Decimal("10") or slippage > Decimal("5"):
            raise TradingValidationError("forex_history: unsafe_cost_assumption")
        if not Decimal("5") <= minimum_stop <= maximum_stop <= Decimal("200"):
            raise TradingValidationError("forex_history: unsafe_stop_range")
        if not Decimal("1") <= reward_risk <= Decimal("5"):
            raise TradingValidationError("forex_history: unsafe_reward_risk")
        object.__setattr__(self, "initial_equity_quote", equity)
        object.__setattr__(self, "position_notional_pct", notional)
        object.__setattr__(self, "assumed_spread_pips", spread)
        object.__setattr__(self, "assumed_slippage_pips", slippage)
        object.__setattr__(self, "minimum_stop_pips", minimum_stop)
        object.__setattr__(self, "maximum_stop_pips", maximum_stop)
        object.__setattr__(self, "take_profit_reward_risk", reward_risk)


@dataclass(frozen=True, slots=True)
class ForexHistoricalSignal:
    signal_id: str
    symbol: str
    action: str
    timestamp: object
    fast_average: Decimal
    slow_average: Decimal
    volatility_pct: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        identifier = str(self.signal_id or "").strip()
        action = str(self.action or "").strip().upper()
        if not _SIGNAL_ID.fullmatch(identifier):
            raise TradingValidationError("forex_history: invalid_signal_id")
        if action not in {"OPEN_LONG", "OPEN_SHORT"}:
            raise TradingValidationError("forex_history: invalid_signal_action")
        object.__setattr__(self, "signal_id", identifier)
        object.__setattr__(self, "symbol", normalized_symbol(self.symbol))
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "timestamp", aware_utc(self.timestamp, "timestamp"))
        object.__setattr__(
            self,
            "fast_average",
            decimal_value(self.fast_average, "fast_average"),
        )
        object.__setattr__(
            self,
            "slow_average",
            decimal_value(self.slow_average, "slow_average"),
        )
        object.__setattr__(
            self,
            "volatility_pct",
            decimal_value(
                self.volatility_pct,
                "volatility_pct",
                allow_zero=True,
            ),
        )


class FixedForexCrossoverSignalGenerator:
    """Mirror the live 10/30 scanner using only current and earlier closes."""

    def __init__(self, policy: ForexHistoricalPolicy | None = None) -> None:
        self.policy = policy or ForexHistoricalPolicy()

    def generate(
        self,
        values: Iterable[MarketBar],
    ) -> tuple[ForexHistoricalSignal, ...]:
        pair, bars = _validated_bars(
            values,
            minimum=self.policy.slow_window + 1,
        )
        closes = tuple(bar.close for bar in bars)
        signals: list[ForexHistoricalSignal] = []
        for index in range(self.policy.slow_window, len(bars)):
            window = closes[index - self.policy.slow_window:index + 1]
            fast = self._mean(window[-self.policy.fast_window:])
            slow = self._mean(window[-self.policy.slow_window:])
            previous_fast = self._mean(
                window[-self.policy.fast_window - 1:-1]
            )
            previous_slow = self._mean(
                window[-self.policy.slow_window - 1:-1]
            )
            returns = tuple(
                abs(current / previous - Decimal("1"))
                for previous, current in zip(window, window[1:])
            )
            volatility_pct = self._mean(returns) * Decimal("100")
            action = ""
            if previous_fast <= previous_slow and fast > slow:
                action = "OPEN_LONG"
            elif previous_fast >= previous_slow and fast < slow:
                action = "OPEN_SHORT"
            if action:
                timestamp = bars[index].timestamp
                signals.append(ForexHistoricalSignal(
                    signal_id=(
                        f"fx-{pair.symbol.lower()}-"
                        f"{timestamp.strftime('%Y%m%dT%H%M%S')}-"
                        f"{action.lower()}"
                    ),
                    symbol=pair.symbol,
                    action=action,
                    timestamp=timestamp,
                    fast_average=fast,
                    slow_average=slow,
                    volatility_pct=volatility_pct,
                ))
        if len(signals) > _MAX_SIGNALS:
            raise TradingValidationError("forex_history: signal_limit_exceeded")
        return tuple(signals)

    def audit(self) -> dict[str, Any]:
        return {
            "strategy": "FIXED_SMA_CROSSOVER",
            "fast_window": self.policy.fast_window,
            "slow_window": self.policy.slow_window,
            "closed_bars_only": True,
            "current_or_past_bars_only": True,
            "future_bar_access": False,
            "volatility_uses_same_closed_window_as_live_scanner": True,
            "parameter_optimization_performed": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }

    @staticmethod
    def _mean(values: tuple[Decimal, ...]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values))


@dataclass(slots=True)
class _Position:
    side: str
    units: Decimal
    entry_execution_price: Decimal
    entry_reference_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    signal_id: str
    signal_at: object
    filled_at: object


class BidirectionalForexHistoricalBacktester:
    """Evaluate LONG and SHORT reversals with next-bar fills and synthetic costs."""

    def __init__(self, policy: ForexHistoricalPolicy | None = None) -> None:
        self.policy = policy or ForexHistoricalPolicy()

    def run(
        self,
        values: Iterable[MarketBar],
        signals: Iterable[ForexHistoricalSignal],
    ) -> dict[str, Any]:
        pair, bars = _validated_bars(values, minimum=2)
        raw_signals = tuple(signals)
        if any(not isinstance(item, ForexHistoricalSignal) for item in raw_signals):
            raise TradingValidationError("forex_history: historical_signal_required")
        ordered = tuple(sorted(raw_signals, key=lambda item: item.timestamp))
        if len(ordered) > _MAX_SIGNALS:
            raise TradingValidationError("forex_history: signal_limit_exceeded")
        identifiers = [item.signal_id for item in ordered]
        if len(identifiers) != len(set(identifiers)):
            raise TradingValidationError("forex_history: duplicate_signal_id")
        signal_timestamps = [item.timestamp for item in ordered]
        if len(signal_timestamps) != len(set(signal_timestamps)):
            raise TradingValidationError("forex_history: duplicate_signal_timestamp")
        if any(item.symbol != pair.symbol for item in ordered):
            raise TradingValidationError("forex_history: signal_pair_mismatch")

        timestamps = [bar.timestamp for bar in bars]
        timestamp_set = set(timestamps)
        scheduled: dict[int, list[ForexHistoricalSignal]] = {}
        rejections: list[dict[str, str]] = []
        for item in ordered:
            if item.timestamp < timestamps[0] or item.timestamp > timestamps[-1]:
                rejections.append({
                    "signal_id": item.signal_id,
                    "code": "SIGNAL_OUTSIDE_WINDOW",
                })
                continue
            if item.timestamp not in timestamp_set:
                rejections.append({
                    "signal_id": item.signal_id,
                    "code": "SIGNAL_NOT_ON_CLOSED_BAR",
                })
                continue
            index = bisect_right(timestamps, item.timestamp)
            if index >= len(bars):
                rejections.append({"signal_id": item.signal_id, "code": "NO_NEXT_BAR"})
            else:
                scheduled.setdefault(index, []).append(item)

        balance = self.policy.initial_equity_quote
        position: _Position | None = None
        trades: list[dict[str, str | bool]] = []
        fills: list[dict[str, str]] = []
        equity_curve: list[Decimal] = []
        peak = balance
        maximum_drawdown = Decimal("0")
        estimated_cost = Decimal("0")

        def close_active(
            *,
            reference_price: Decimal,
            closed_at: object,
            reason: str,
            trigger_signal_id: str = "",
        ) -> None:
            nonlocal balance, estimated_cost, position
            if position is None:
                raise TradingValidationError(
                    "forex_history: close_without_position"
                )
            closing_position = position
            closed, cost = self._close_position(
                pair=pair,
                position=closing_position,
                reference_price=reference_price,
                closed_at=closed_at,
                reason=reason,
            )
            balance += Decimal(str(closed["net_pnl_quote"]))
            estimated_cost += cost
            trades.append(closed)
            fills.append({
                "signal_id": trigger_signal_id or closing_position.signal_id,
                "action": f"CLOSE_{closing_position.side}",
                "filled_at": aware_utc(closed_at, "closed_at").isoformat(),
                "price": str(closed["exit_execution_price"]),
                "reason": reason,
            })
            position = None

        for index, bar in enumerate(bars):
            risk_exit_at_open = False
            if position is not None:
                opening_exit = self._risk_exit(
                    pair=pair,
                    position=position,
                    bar=bar,
                    opening_gap_only=True,
                )
                if opening_exit is not None:
                    reference_price, reason = opening_exit
                    close_active(
                        reference_price=reference_price,
                        closed_at=bar.timestamp,
                        reason=reason,
                    )
                    risk_exit_at_open = True

            for signal in scheduled.get(index, []):
                if risk_exit_at_open:
                    rejections.append({
                        "signal_id": signal.signal_id,
                        "code": "RISK_EXIT_PRIORITY",
                    })
                    continue
                target_side = "LONG" if signal.action == "OPEN_LONG" else "SHORT"
                if position is not None and position.side == target_side:
                    rejections.append({
                        "signal_id": signal.signal_id,
                        "code": "POSITION_ALREADY_ALIGNED",
                    })
                    continue
                if position is not None:
                    close_active(
                        reference_price=bar.open,
                        closed_at=bar.timestamp,
                        reason="OPPOSITE_CROSSOVER",
                        trigger_signal_id=signal.signal_id,
                    )
                    continue
                position = self._open_position(
                    pair=pair,
                    side=target_side,
                    balance=balance,
                    reference_price=bar.open,
                    signal=signal,
                    filled_at=bar.timestamp,
                )
                estimated_cost += self._one_way_cost(pair, position.units)
                fills.append({
                    "signal_id": signal.signal_id,
                    "action": f"OPEN_{target_side}",
                    "filled_at": bar.timestamp.isoformat(),
                    "price": _text(position.entry_execution_price, _PRICE),
                })

            if position is not None:
                intrabar_exit = self._risk_exit(
                    pair=pair,
                    position=position,
                    bar=bar,
                    opening_gap_only=False,
                )
                if intrabar_exit is not None:
                    reference_price, reason = intrabar_exit
                    close_active(
                        reference_price=reference_price,
                        closed_at=bar.timestamp,
                        reason=reason,
                    )

            equity = balance
            if position is not None:
                marked = self._exit_price(pair, position.side, bar.close)
                equity += self._pnl(position, marked)
            equity_curve.append(equity)
            peak = max(peak, equity)
            if peak > 0:
                maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak)

        if position is not None:
            close_active(
                reference_price=bars[-1].close,
                closed_at=bars[-1].timestamp,
                reason="FORCED_WINDOW_CLOSE",
            )
            equity_curve[-1] = balance

        net_profit = balance - self.policy.initial_equity_quote
        winning = sum(Decimal(str(item["net_pnl_quote"])) > 0 for item in trades)
        win_rate = Decimal(winning) / Decimal(len(trades)) if trades else Decimal("0")
        stop_loss_exit_count = sum(
            str(item["exit_reason"]).startswith("STOP_LOSS")
            for item in trades
        )
        take_profit_exit_count = sum(
            str(item["exit_reason"]).startswith("TAKE_PROFIT")
            for item in trades
        )
        ambiguous_bar_count = sum(
            item["exit_reason"] == "STOP_LOSS_AMBIGUOUS_BAR"
            for item in trades
        )
        return {
            "status": "FOREX_HISTORICAL_BACKTEST_COMPLETED",
            "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
            "symbol": pair.symbol,
            "quote_currency": pair.quote_currency,
            "bar_count": len(bars),
            "signal_count": len(ordered),
            "fill_count": len(fills),
            "trade_count": len(trades),
            "rejection_count": len(rejections),
            "initial_equity_quote": _text(self.policy.initial_equity_quote),
            "final_equity_quote": _text(balance),
            "net_profit_quote": _text(net_profit),
            "estimated_spread_slippage_cost_quote": _text(estimated_cost),
            "total_return_pct": _text(
                net_profit / self.policy.initial_equity_quote * Decimal("100"),
                _PERCENT,
            ),
            "max_drawdown_pct": _text(maximum_drawdown * Decimal("100"), _PERCENT),
            "win_rate_pct": _text(win_rate * Decimal("100"), _PERCENT),
            "stop_loss_exit_count": stop_loss_exit_count,
            "take_profit_exit_count": take_profit_exit_count,
            "ambiguous_bar_count": ambiguous_bar_count,
            "trades": trades,
            "fills": fills,
            "rejections": rejections,
            "long_and_short_supported": True,
            "same_bar_execution_blocked": True,
            "forced_window_liquidation": True,
            "historical_spread_available": False,
            "synthetic_cost_model": True,
            "assumed_spread_pips": str(self.policy.assumed_spread_pips),
            "assumed_slippage_pips": str(self.policy.assumed_slippage_pips),
            "stop_loss_enabled": True,
            "stop_loss_formula_matches_paper_coordinator": True,
            "position_sizing_matches_paper_coordinator": False,
            "minimum_stop_pips": str(self.policy.minimum_stop_pips),
            "maximum_stop_pips": str(self.policy.maximum_stop_pips),
            "take_profit_enabled": True,
            "take_profit_reward_risk": str(
                self.policy.take_profit_reward_risk
            ),
            "take_profit_research_only": True,
            "ambiguous_stop_target_bar_uses_stop_first": True,
            "portfolio_pln_aggregation_performed": False,
            "automatic_paper_promotion": False,
            "broker_connection_used": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }

    def _open_position(
        self,
        *,
        pair: ForexPair,
        side: str,
        balance: Decimal,
        reference_price: Decimal,
        signal: ForexHistoricalSignal,
        filled_at: object,
    ) -> _Position:
        execution = self._entry_price(pair, side, reference_price)
        notional = max(Decimal("0"), balance) * self.policy.position_notional_pct
        if execution <= 0 or notional <= 0:
            raise TradingValidationError("forex_history: nonpositive_execution_value")
        volatility_distance = (
            signal.volatility_pct / Decimal("100")
        ) * execution * Decimal("2")
        minimum = pair.pip_size * self.policy.minimum_stop_pips
        maximum = pair.pip_size * self.policy.maximum_stop_pips
        stop_distance = min(max(volatility_distance, minimum), maximum)
        stop_loss = (
            execution - stop_distance
            if side == "LONG"
            else execution + stop_distance
        )
        take_profit_distance = (
            stop_distance * self.policy.take_profit_reward_risk
        )
        take_profit = (
            execution + take_profit_distance
            if side == "LONG"
            else execution - take_profit_distance
        )
        if stop_loss <= 0 or take_profit <= 0:
            raise TradingValidationError("forex_history: invalid_exit_levels")
        return _Position(
            side=side,
            units=notional / execution,
            entry_execution_price=execution,
            entry_reference_price=reference_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            signal_id=signal.signal_id,
            signal_at=signal.timestamp,
            filled_at=aware_utc(filled_at, "filled_at"),
        )

    def _close_position(
        self,
        *,
        pair: ForexPair,
        position: _Position,
        reference_price: Decimal,
        closed_at: object,
        reason: str,
    ) -> tuple[dict[str, str | bool], Decimal]:
        execution = self._exit_price(pair, position.side, reference_price)
        net_pnl = self._pnl(position, execution)
        gross_pnl = (
            (reference_price - position.entry_reference_price) * position.units
            if position.side == "LONG"
            else (position.entry_reference_price - reference_price) * position.units
        )
        total_cost = max(Decimal("0"), gross_pnl - net_pnl)
        return ({
            "side": position.side,
            "entry_signal_id": position.signal_id,
            "signal_at": position.signal_at.isoformat(),
            "opened_at": position.filled_at.isoformat(),
            "closed_at": aware_utc(closed_at, "closed_at").isoformat(),
            "entry_execution_price": _text(position.entry_execution_price, _PRICE),
            "exit_execution_price": _text(execution, _PRICE),
            "stop_loss": _text(position.stop_loss, _PRICE),
            "take_profit": _text(position.take_profit, _PRICE),
            "units": _text(position.units, Decimal("0.01")),
            "gross_pnl_quote": _text(gross_pnl),
            "net_pnl_quote": _text(net_pnl),
            "estimated_cost_quote": _text(total_cost),
            "exit_reason": reason,
            "profitable": net_pnl > 0,
        }, self._one_way_cost(pair, position.units))

    def _risk_exit(
        self,
        *,
        pair: ForexPair,
        position: _Position,
        bar: MarketBar,
        opening_gap_only: bool,
    ) -> tuple[Decimal, str] | None:
        if opening_gap_only:
            executable_open = self._exit_price(pair, position.side, bar.open)
            if (
                position.side == "LONG"
                and executable_open <= position.stop_loss
            ) or (
                position.side == "SHORT"
                and executable_open >= position.stop_loss
            ):
                return bar.open, "STOP_LOSS_GAP"
            if (
                position.side == "LONG"
                and executable_open >= position.take_profit
            ) or (
                position.side == "SHORT"
                and executable_open <= position.take_profit
            ):
                return (
                    self._reference_for_exit_execution(
                        pair,
                        position.side,
                        position.take_profit,
                    ),
                    "TAKE_PROFIT_GAP",
                )
            return None

        executable_low = self._exit_price(pair, position.side, bar.low)
        executable_high = self._exit_price(pair, position.side, bar.high)
        if position.side == "LONG":
            stop_hit = executable_low <= position.stop_loss
            target_hit = executable_high >= position.take_profit
        else:
            stop_hit = executable_high >= position.stop_loss
            target_hit = executable_low <= position.take_profit
        if stop_hit:
            reason = (
                "STOP_LOSS_AMBIGUOUS_BAR"
                if target_hit
                else "STOP_LOSS_TRIGGERED"
            )
            return (
                self._reference_for_exit_execution(
                    pair,
                    position.side,
                    position.stop_loss,
                ),
                reason,
            )
        if target_hit:
            return (
                self._reference_for_exit_execution(
                    pair,
                    position.side,
                    position.take_profit,
                ),
                "TAKE_PROFIT_TRIGGERED",
            )
        return None

    def _cost_per_unit(self, pair: ForexPair) -> Decimal:
        return pair.pip_size * (
            self.policy.assumed_spread_pips / Decimal("2")
            + self.policy.assumed_slippage_pips
        )

    def _one_way_cost(self, pair: ForexPair, units: Decimal) -> Decimal:
        return self._cost_per_unit(pair) * units

    def _entry_price(self, pair: ForexPair, side: str, midpoint: Decimal) -> Decimal:
        cost = self._cost_per_unit(pair)
        return midpoint + cost if side == "LONG" else midpoint - cost

    def _exit_price(self, pair: ForexPair, side: str, midpoint: Decimal) -> Decimal:
        cost = self._cost_per_unit(pair)
        return midpoint - cost if side == "LONG" else midpoint + cost

    def _reference_for_exit_execution(
        self,
        pair: ForexPair,
        side: str,
        execution_price: Decimal,
    ) -> Decimal:
        cost = self._cost_per_unit(pair)
        return (
            execution_price + cost
            if side == "LONG"
            else execution_price - cost
        )

    @staticmethod
    def _pnl(position: _Position, exit_price: Decimal) -> Decimal:
        if position.side == "LONG":
            return (exit_price - position.entry_execution_price) * position.units
        return (position.entry_execution_price - exit_price) * position.units


@dataclass(frozen=True, slots=True)
class ForexWalkForwardPolicy:
    training_bar_count: int = 1_500
    testing_bar_count: int = 500
    step_bar_count: int = 500
    minimum_window_count: int = 2

    def __post_init__(self) -> None:
        for name, value in (
            ("training_bar_count", self.training_bar_count),
            ("testing_bar_count", self.testing_bar_count),
            ("step_bar_count", self.step_bar_count),
            ("minimum_window_count", self.minimum_window_count),
        ):
            if type(value) is not int:
                raise TradingValidationError(f"forex_history: {name}_must_be_integer")
        if not 50 <= self.training_bar_count <= 250_000:
            raise TradingValidationError("forex_history: invalid_training_bar_count")
        if not 10 <= self.testing_bar_count <= 250_000:
            raise TradingValidationError("forex_history: invalid_testing_bar_count")
        if not self.testing_bar_count <= self.step_bar_count <= 250_000:
            raise TradingValidationError("forex_history: overlapping_test_windows")
        if not 1 <= self.minimum_window_count <= _MAX_WINDOWS:
            raise TradingValidationError("forex_history: invalid_minimum_window_count")


class ForexHistoricalWalkForwardValidator:
    """Generate and test fixed signals inside chronological isolated windows."""

    def __init__(
        self,
        policy: ForexHistoricalPolicy | None = None,
        *,
        walk_forward_policy: ForexWalkForwardPolicy | None = None,
    ) -> None:
        self.policy = policy or ForexHistoricalPolicy()
        self.walk_forward_policy = walk_forward_policy or ForexWalkForwardPolicy()
        self.generator = FixedForexCrossoverSignalGenerator(self.policy)
        self.backtester = BidirectionalForexHistoricalBacktester(self.policy)

    def run(self, values: Iterable[MarketBar]) -> dict[str, Any]:
        pair, bars = _validated_bars(
            values,
            minimum=(
                self.walk_forward_policy.training_bar_count
                + self.walk_forward_policy.testing_bar_count
            ),
        )
        config = self.walk_forward_policy
        required = config.training_bar_count + config.testing_bar_count
        maximum_start = len(bars) - required
        expected = maximum_start // config.step_bar_count + 1
        if expected > _MAX_WINDOWS:
            raise TradingValidationError("forex_history: window_limit_exceeded")
        windows: list[dict[str, Any]] = []
        for start in range(0, maximum_start + 1, config.step_bar_count):
            training_end = start + config.training_bar_count
            testing_end = training_end + config.testing_bar_count
            training = bars[start:training_end]
            testing = bars[training_end:testing_end]
            training_signals = self.generator.generate(training)
            warmup = training[-self.policy.slow_window:] + testing
            testing_signals = tuple(
                signal
                for signal in self.generator.generate(warmup)
                if signal.timestamp >= testing[0].timestamp
            )
            windows.append({
                "window": len(windows) + 1,
                "training_started_at": training[0].timestamp.isoformat(),
                "training_ended_at": training[-1].timestamp.isoformat(),
                "testing_started_at": testing[0].timestamp.isoformat(),
                "testing_ended_at": testing[-1].timestamp.isoformat(),
                "training": self.backtester.run(training, training_signals),
                "testing": self.backtester.run(testing, testing_signals),
            })
        if len(windows) < config.minimum_window_count:
            raise TradingValidationError("forex_history: insufficient_window_count")

        returns = [Decimal(window["testing"]["total_return_pct"]) for window in windows]
        drawdowns = [Decimal(window["testing"]["max_drawdown_pct"]) for window in windows]
        count = Decimal(len(windows))
        compounded = Decimal("1")
        for value in returns:
            compounded *= Decimal("1") + value / Decimal("100")
        return {
            "status": "FOREX_WALK_FORWARD_COMPLETED",
            "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
            "symbol": pair.symbol,
            "quote_currency": pair.quote_currency,
            "source_bar_count": len(bars),
            "window_count": len(windows),
            "training_bar_count_per_window": config.training_bar_count,
            "testing_bar_count_per_window": config.testing_bar_count,
            "step_bar_count": config.step_bar_count,
            "out_of_sample_started_at": windows[0]["testing_started_at"],
            "out_of_sample_ended_at": windows[-1]["testing_ended_at"],
            "out_of_sample_trade_count": sum(
                int(window["testing"]["trade_count"]) for window in windows
            ),
            "out_of_sample_stop_loss_exit_count": sum(
                int(window["testing"]["stop_loss_exit_count"])
                for window in windows
            ),
            "out_of_sample_take_profit_exit_count": sum(
                int(window["testing"]["take_profit_exit_count"])
                for window in windows
            ),
            "out_of_sample_ambiguous_bar_count": sum(
                int(window["testing"]["ambiguous_bar_count"])
                for window in windows
            ),
            "profitable_out_of_sample_window_count": sum(value > 0 for value in returns),
            "average_out_of_sample_return_pct": _text(sum(returns) / count, _PERCENT),
            "compounded_out_of_sample_return_pct": _text(
                (compounded - Decimal("1")) * Decimal("100"),
                _PERCENT,
            ),
            "worst_out_of_sample_return_pct": _text(min(returns), _PERCENT),
            "best_out_of_sample_return_pct": _text(max(returns), _PERCENT),
            "maximum_out_of_sample_drawdown_pct": _text(max(drawdowns), _PERCENT),
            "windows": windows,
            "signal_generator_audit": self.generator.audit(),
            "chronological_splits_valid": True,
            "out_of_sample_windows_non_overlapping": True,
            "past_only_warmup_used": True,
            "same_bar_execution_blocked": True,
            "stop_loss_formula_matches_paper_coordinator": True,
            "position_sizing_matches_paper_coordinator": False,
            "take_profit_research_only": True,
            "ambiguous_stop_target_bar_uses_stop_first": True,
            "parameter_optimization_performed": False,
            "strategy_performance_validated": False,
            "research_only": True,
            "automatic_paper_promotion": False,
            "broker_connection_used": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }


__all__ = [
    "BidirectionalForexHistoricalBacktester",
    "FixedForexCrossoverSignalGenerator",
    "ForexHistoricalPolicy",
    "ForexHistoricalSignal",
    "ForexHistoricalWalkForwardValidator",
    "ForexWalkForwardPolicy",
]

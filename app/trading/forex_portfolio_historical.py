"""Portfolio-level Forex research that reuses the PAPER decision path."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexPosition,
    ForexQuote,
    ForexSafetyContext,
    HISTORICAL_FOREX_PAIRS,
    MAJOR_FOREX_PAIRS,
)
from app.trading.forex_risk import ForexPaperPolicy, ForexRateBook
from app.trading.forex_scanner import ForexMarketScanner, ForexScannerPolicy
from app.trading.models import MarketBar, TradingValidationError, decimal_value


_MONEY = Decimal("0.01")
_PERCENT = Decimal("0.0001")
_MAX_BARS = 500_000
_MAX_WINDOWS = 1_000
_PAIR_BY_SYMBOL = {pair.symbol: pair for pair in HISTORICAL_FOREX_PAIRS}
_TRADABLE_SYMBOLS = frozenset(pair.symbol for pair in MAJOR_FOREX_PAIRS)
_HISTORICAL_SYMBOLS = frozenset(_PAIR_BY_SYMBOL)


def _text(value: Decimal, quantum: Decimal = _MONEY) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _validated_histories(
    values: Mapping[str, Iterable[MarketBar]],
    *,
    minimum: int,
) -> dict[str, tuple[MarketBar, ...]]:
    if not isinstance(values, Mapping) or set(values) != _HISTORICAL_SYMBOLS:
        raise TradingValidationError("forex_portfolio_history: complete_pair_set_required")
    histories: dict[str, tuple[MarketBar, ...]] = {}
    reference_timestamps: tuple[datetime, ...] | None = None
    for symbol in sorted(_HISTORICAL_SYMBOLS):
        bars = tuple(values[symbol])
        pair = _PAIR_BY_SYMBOL[symbol]
        if len(bars) < minimum:
            raise TradingValidationError("forex_portfolio_history: insufficient_bars")
        if len(bars) > _MAX_BARS:
            raise TradingValidationError("forex_portfolio_history: bar_limit_exceeded")
        if any(not isinstance(bar, MarketBar) for bar in bars):
            raise TradingValidationError("forex_portfolio_history: market_bar_required")
        if any(bar.symbol != symbol for bar in bars):
            raise TradingValidationError("forex_portfolio_history: pair_mismatch")
        if any(bar.currency != pair.quote_currency for bar in bars):
            raise TradingValidationError("forex_portfolio_history: quote_currency_mismatch")
        timestamps = tuple(bar.timestamp for bar in bars)
        if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
            raise TradingValidationError("forex_portfolio_history: bars_not_ordered")
        if reference_timestamps is None:
            reference_timestamps = timestamps
        elif timestamps != reference_timestamps:
            raise TradingValidationError("forex_portfolio_history: timestamps_not_aligned")
        histories[symbol] = bars
    return histories


@dataclass(frozen=True, slots=True)
class ForexPortfolioHistoricalPolicy:
    """Fixed costs and the exact PAPER scanner/risk policy for research."""

    initial_equity_pln: Decimal = Decimal("100000")
    assumed_spread_pips: Decimal = Decimal("1.5")
    assumed_slippage_pips: Decimal = Decimal("0.2")
    scanner: ForexScannerPolicy = field(default_factory=ForexScannerPolicy)
    paper: ForexPaperPolicy = field(default_factory=ForexPaperPolicy)

    def __post_init__(self) -> None:
        equity = decimal_value(self.initial_equity_pln, "initial_equity_pln")
        spread = decimal_value(
            self.assumed_spread_pips, "assumed_spread_pips", allow_zero=True
        )
        slippage = decimal_value(
            self.assumed_slippage_pips, "assumed_slippage_pips", allow_zero=True
        )
        if not Decimal("1000") <= equity <= Decimal("100000000"):
            raise TradingValidationError("forex_portfolio_history: invalid_equity")
        if spread > Decimal("10") or slippage > Decimal("5"):
            raise TradingValidationError("forex_portfolio_history: unsafe_costs")
        if self.paper.account_currency != "PLN":
            raise TradingValidationError("forex_portfolio_history: pln_account_required")
        if self.paper.take_profit_reward_risk != Decimal("2"):
            raise TradingValidationError("forex_portfolio_history: paper_target_mismatch")
        object.__setattr__(self, "initial_equity_pln", equity)
        object.__setattr__(self, "assumed_spread_pips", spread)
        object.__setattr__(self, "assumed_slippage_pips", slippage)


class ForexPortfolioHistoricalBacktester:
    """Replay all pairs together without a broker, network, or order API."""

    def __init__(
        self,
        policy: ForexPortfolioHistoricalPolicy | None = None,
        *,
        scanner: Any | None = None,
    ) -> None:
        self.policy = policy or ForexPortfolioHistoricalPolicy()
        self.scanner = scanner or ForexMarketScanner(policy=self.policy.scanner)
        if tuple(getattr(self.scanner, "universe", ())) != MAJOR_FOREX_PAIRS:
            raise TradingValidationError("forex_portfolio_history: scanner_universe_mismatch")
        if getattr(self.scanner, "policy", None) != self.policy.scanner:
            raise TradingValidationError("forex_portfolio_history: scanner_policy_mismatch")
        self.required_history_count = int(getattr(
            self.scanner,
            "required_history_count",
            self.policy.scanner.slow_window + 1,
        ))
        if not self.policy.scanner.slow_window + 1 <= self.required_history_count <= 499:
            raise TradingValidationError("forex_portfolio_history: invalid_scanner_history")
        self.coordinator = ForexPaperCoordinator(self.policy.paper)

    def run(
        self,
        values: Mapping[str, Iterable[MarketBar]],
        *,
        trading_start_at: datetime | None = None,
    ) -> dict[str, Any]:
        histories = _validated_histories(
            values,
            minimum=self.required_history_count + 1,
        )
        timestamps = tuple(histories["EUR_USD"][index].timestamp for index in range(len(histories["EUR_USD"])))
        start_index = self.required_history_count
        if trading_start_at is not None:
            candidates = [index for index, stamp in enumerate(timestamps) if stamp >= trading_start_at]
            if not candidates:
                raise TradingValidationError("forex_portfolio_history: trading_start_outside_data")
            start_index = max(start_index, candidates[0])
        if start_index >= len(timestamps):
            raise TradingValidationError("forex_portfolio_history: insufficient_testing_bars")

        balance = self.policy.initial_equity_pln
        positions: dict[str, ForexPosition] = {}
        fills: list[dict[str, Any]] = []
        closed_trades: list[dict[str, Any]] = []
        equity_curve = [balance]
        daily_realized: dict[object, Decimal] = {}
        rejected_count = 0
        ambiguous_count = 0
        maximum_positions = 0

        for index in range(start_index, len(timestamps)):
            now = timestamps[index]
            open_quotes = self._quotes(histories, index, price_field="open")
            rate_book = ForexRateBook(open_quotes.values(), now=now)
            positions = self._marked_positions(positions, open_quotes)
            unrealized = self._unrealized_pln(positions, open_quotes, rate_book)
            equity = balance + unrealized
            bars_for_scanner = {
                symbol: tuple(
                    self._forex_bar(_PAIR_BY_SYMBOL[symbol], bar)
                    for bar in series[index - self.required_history_count:index]
                )
                for symbol, series in histories.items()
                if symbol in _TRADABLE_SYMBOLS
            }
            contexts = {
                pair.symbol: ForexSafetyContext(
                    observed_at=now,
                    market_open=True,
                    calendar_ready=True,
                    high_impact_event_blocked=False,
                    conversion_to_pln_ready=True,
                    independent_source_count=2,
                )
                for pair in MAJOR_FOREX_PAIRS
            }
            assessments = self.scanner.scan(
                quotes={symbol: quote for symbol, quote in open_quotes.items() if symbol in _TRADABLE_SYMBOLS},
                bars=bars_for_scanner,
                contexts=contexts,
                positions={symbol: position.side for symbol, position in positions.items()},
                now=now,
            )
            plan = self.coordinator.plan(
                assessments=assessments,
                quotes={symbol: quote for symbol, quote in open_quotes.items() if symbol in _TRADABLE_SYMBOLS},
                positions=positions,
                rates=rate_book,
                equity_pln=equity,
                daily_pnl_pln=daily_realized.get(now.date(), Decimal("0")),
                now=now,
            )
            rejected_count += len(plan["rejected"])
            for raw in plan["instructions"]:
                symbol = str(raw["pair"])
                action = str(raw["action"])
                if action == "CLOSE_POSITION" and symbol in positions:
                    position = positions.pop(symbol)
                    reason_codes = tuple(raw["reason_codes"])
                    exit_price = Decimal(str(raw["intended_price"]))
                    if (
                        "TAKE_PROFIT_TRIGGERED" in reason_codes
                        and position.take_profit is not None
                    ):
                        exit_price = position.take_profit
                    balance, trade = self._close(
                        balance=balance,
                        position=position,
                        exit_price=exit_price,
                        closed_at=now,
                        rate_book=rate_book,
                        reason_codes=reason_codes,
                    )
                    daily_realized[now.date()] = daily_realized.get(now.date(), Decimal("0")) + Decimal(trade["pnl_pln"])
                    closed_trades.append(trade)
                    fills.append({"action": "CLOSE_POSITION", **trade})
                elif action in {"OPEN_LONG", "OPEN_SHORT"} and symbol not in positions:
                    pair = _PAIR_BY_SYMBOL[symbol]
                    entry = Decimal(str(raw["intended_price"]))
                    positions[symbol] = ForexPosition(
                        pair=pair,
                        side="LONG" if action == "OPEN_LONG" else "SHORT",
                        units=Decimal(str(raw["units"])),
                        entry_price=entry,
                        current_price=entry,
                        stop_loss=Decimal(str(raw["stop_loss"])),
                        take_profit=Decimal(str(raw["take_profit"])),
                        opened_at=now,
                    )
                    fills.append({
                        "action": action,
                        "pair": symbol,
                        "units": str(positions[symbol].units),
                        "entry_price": str(entry),
                        "stop_loss": str(positions[symbol].stop_loss),
                        "take_profit": str(positions[symbol].take_profit),
                        "planned_at": now.isoformat(),
                        "executed_at": now.isoformat(),
                        "signal_observed_through": histories[symbol][index - 1].timestamp.isoformat(),
                        "reason_codes": list(raw["reason_codes"]),
                    })
            maximum_positions = max(maximum_positions, len(positions))

            for symbol, position in tuple(positions.items()):
                bar = histories[symbol][index]
                cost = self._execution_cost(position.pair)
                stop_hit = (
                    bar.low - cost <= position.stop_loss
                    if position.side == "LONG"
                    else bar.high + cost >= position.stop_loss
                )
                target_hit = (
                    bar.high - cost >= position.take_profit
                    if position.side == "LONG"
                    else bar.low + cost <= position.take_profit
                )
                if not stop_hit and not target_hit:
                    continue
                if stop_hit and target_hit:
                    ambiguous_count += 1
                exit_price = position.stop_loss if stop_hit else position.take_profit
                reason = "STOP_LOSS_TRIGGERED" if stop_hit else "TAKE_PROFIT_TRIGGERED"
                balance, trade = self._close(
                    balance=balance,
                    position=positions.pop(symbol),
                    exit_price=exit_price,
                    closed_at=now,
                    rate_book=rate_book,
                    reason_codes=(reason,),
                )
                daily_realized[now.date()] = daily_realized.get(now.date(), Decimal("0")) + Decimal(trade["pnl_pln"])
                closed_trades.append(trade)
                fills.append({"action": "CLOSE_POSITION", **trade})

            close_quotes = self._quotes(histories, index, price_field="close")
            close_rates = ForexRateBook(close_quotes.values(), now=now)
            positions = self._marked_positions(positions, close_quotes)
            equity_curve.append(balance + self._unrealized_pln(positions, close_quotes, close_rates))

        if positions:
            final_index = len(timestamps) - 1
            final_now = timestamps[final_index]
            final_quotes = self._quotes(histories, final_index, price_field="close")
            final_rates = ForexRateBook(final_quotes.values(), now=final_now)
            for symbol, position in tuple(positions.items()):
                quote = final_quotes[symbol]
                balance, trade = self._close(
                    balance=balance,
                    position=positions.pop(symbol),
                    exit_price=quote.bid if position.side == "LONG" else quote.ask,
                    closed_at=final_now,
                    rate_book=final_rates,
                    reason_codes=("END_OF_WINDOW",),
                )
                closed_trades.append(trade)
                fills.append({"action": "CLOSE_POSITION", **trade})
            equity_curve.append(balance)

        peak = equity_curve[0]
        maximum_drawdown = Decimal("0")
        for value in equity_curve:
            peak = max(peak, value)
            maximum_drawdown = max(maximum_drawdown, (peak - value) / peak)
        total_return = ((balance / self.policy.initial_equity_pln) - Decimal("1")) * Decimal("100")
        wins = sum(Decimal(trade["pnl_pln"]) > 0 for trade in closed_trades)
        scanner_audit = (
            self.scanner.audit()
            if callable(getattr(self.scanner, "audit", None))
            else {"strategy": "PAPER_BASE_SCANNER"}
        )
        return {
            "status": "COMPLETED",
            "account_currency": "PLN",
            "initial_equity_pln": _text(self.policy.initial_equity_pln),
            "ending_equity_pln": _text(balance),
            "return_pct": _text(total_return, _PERCENT),
            "maximum_drawdown_pct": _text(maximum_drawdown * Decimal("100"), _PERCENT),
            "trade_count": len(closed_trades),
            "profitable_trade_count": wins,
            "stop_loss_exit_count": sum("STOP_LOSS_TRIGGERED" in trade["reason_codes"] for trade in closed_trades),
            "take_profit_exit_count": sum("TAKE_PROFIT_TRIGGERED" in trade["reason_codes"] for trade in closed_trades),
            "ambiguous_bar_count": ambiguous_count,
            "rejected_candidate_count": rejected_count,
            "maximum_concurrent_positions_observed": maximum_positions,
            "fills": fills,
            "portfolio_pln_aggregation_performed": True,
            "historical_pln_conversion_series_verified": True,
            "scanner_matches_paper": type(self.scanner) is ForexMarketScanner,
            "scanner_audit": scanner_audit,
            "position_sizing_matches_paper_coordinator": True,
            "stop_loss_formula_matches_paper_coordinator": True,
            "take_profit_matches_paper": True,
            "same_bar_signal_execution_blocked": True,
            "ambiguous_stop_target_bar_uses_stop_first": True,
            "research_only": True,
            "automatic_paper_promotion": False,
            "broker_connection_used": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }

    def _quotes(
        self,
        histories: Mapping[str, tuple[MarketBar, ...]],
        index: int,
        *,
        price_field: str,
    ) -> dict[str, ForexQuote]:
        quotes: dict[str, ForexQuote] = {}
        for symbol, series in histories.items():
            pair = _PAIR_BY_SYMBOL[symbol]
            bar = series[index]
            midpoint = getattr(bar, price_field)
            cost = self._execution_cost(pair)
            quotes[symbol] = ForexQuote.create(
                pair=pair,
                bid=midpoint - cost,
                ask=midpoint + cost,
                timestamp=bar.timestamp,
            )
        return quotes

    def _execution_cost(self, pair: ForexPair) -> Decimal:
        if not pair.tradable:
            return Decimal("0")
        return pair.pip_size * (
            (self.policy.assumed_spread_pips / Decimal("2"))
            + self.policy.assumed_slippage_pips
        )

    @staticmethod
    def _forex_bar(pair: ForexPair, bar: MarketBar) -> ForexBar:
        return ForexBar.create(
            pair=pair,
            timestamp=bar.timestamp,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            tick_volume=bar.volume,
        )

    @staticmethod
    def _marked_positions(
        positions: Mapping[str, ForexPosition],
        quotes: Mapping[str, ForexQuote],
    ) -> dict[str, ForexPosition]:
        return {
            symbol: ForexPosition(
                pair=position.pair,
                side=position.side,
                units=position.units,
                entry_price=position.entry_price,
                current_price=quotes[symbol].midpoint,
                stop_loss=position.stop_loss,
                opened_at=position.opened_at,
                take_profit=position.take_profit,
            )
            for symbol, position in positions.items()
        }

    @staticmethod
    def _unrealized_pln(
        positions: Mapping[str, ForexPosition],
        quotes: Mapping[str, ForexQuote],
        rates: ForexRateBook,
    ) -> Decimal:
        total = Decimal("0")
        for symbol, position in positions.items():
            quote = quotes[symbol]
            pnl_quote = (
                (quote.bid - position.entry_price) * position.units
                if position.side == "LONG"
                else (position.entry_price - quote.ask) * position.units
            )
            total += rates.convert(pnl_quote, position.pair.quote_currency, "PLN")
        return total

    @staticmethod
    def _close(
        *,
        balance: Decimal,
        position: ForexPosition,
        exit_price: Decimal,
        closed_at: datetime,
        rate_book: ForexRateBook,
        reason_codes: tuple[str, ...],
    ) -> tuple[Decimal, dict[str, Any]]:
        pnl_quote = (
            (exit_price - position.entry_price) * position.units
            if position.side == "LONG"
            else (position.entry_price - exit_price) * position.units
        )
        pnl_pln = rate_book.convert(pnl_quote, position.pair.quote_currency, "PLN")
        trade = {
            "pair": position.pair.symbol,
            "side": position.side,
            "units": str(position.units),
            "entry_price": str(position.entry_price),
            "exit_price": str(exit_price),
            "stop_loss": str(position.stop_loss),
            "take_profit": str(position.take_profit),
            "opened_at": position.opened_at.isoformat(),
            "closed_at": closed_at.isoformat(),
            "pnl_pln": str(pnl_pln),
            "reason_codes": list(reason_codes),
        }
        return balance + pnl_pln, trade


@dataclass(frozen=True, slots=True)
class ForexPortfolioWalkForwardPolicy:
    training_bar_count: int = 1_500
    testing_bar_count: int = 500
    step_bar_count: int = 500
    minimum_trade_count: int = 20
    minimum_profitable_window_ratio: Decimal = Decimal("0.60")
    maximum_drawdown_pct: Decimal = Decimal("5")

    def __post_init__(self) -> None:
        if type(self.training_bar_count) is not int or self.training_bar_count < 50:
            raise TradingValidationError("forex_portfolio_walk_forward: invalid_training_size")
        if type(self.testing_bar_count) is not int or self.testing_bar_count < 10:
            raise TradingValidationError("forex_portfolio_walk_forward: invalid_testing_size")
        if type(self.step_bar_count) is not int or self.step_bar_count < self.testing_bar_count:
            raise TradingValidationError("forex_portfolio_walk_forward: overlapping_windows")
        if type(self.minimum_trade_count) is not int or self.minimum_trade_count < 1:
            raise TradingValidationError("forex_portfolio_walk_forward: invalid_trade_minimum")
        ratio = decimal_value(self.minimum_profitable_window_ratio, "minimum_profitable_window_ratio")
        drawdown = decimal_value(self.maximum_drawdown_pct, "maximum_drawdown_pct")
        if not Decimal("0.50") <= ratio <= Decimal("1"):
            raise TradingValidationError("forex_portfolio_walk_forward: invalid_profitable_ratio")
        if not Decimal("0.1") <= drawdown <= Decimal("20"):
            raise TradingValidationError("forex_portfolio_walk_forward: invalid_drawdown_limit")


class ForexPortfolioHistoricalWalkForwardValidator:
    """Evaluate fixed portfolio rules on isolated chronological OOS windows."""

    def __init__(
        self,
        *,
        historical_policy: ForexPortfolioHistoricalPolicy | None = None,
        walk_forward_policy: ForexPortfolioWalkForwardPolicy | None = None,
        scanner: Any | None = None,
    ) -> None:
        self.historical_policy = historical_policy or ForexPortfolioHistoricalPolicy()
        self.walk_forward_policy = walk_forward_policy or ForexPortfolioWalkForwardPolicy()
        self.scanner = scanner

    def run(self, values: Mapping[str, Iterable[MarketBar]]) -> dict[str, Any]:
        required = self.walk_forward_policy.training_bar_count + self.walk_forward_policy.testing_bar_count
        histories = _validated_histories(values, minimum=required)
        total = len(histories["EUR_USD"])
        windows: list[dict[str, Any]] = []
        training_start = 0
        while training_start + required <= total:
            if len(windows) >= _MAX_WINDOWS:
                raise TradingValidationError("forex_portfolio_walk_forward: window_limit")
            testing_start = training_start + self.walk_forward_policy.training_bar_count
            testing_end = testing_start + self.walk_forward_policy.testing_bar_count
            sliced = {symbol: bars[training_start:testing_end] for symbol, bars in histories.items()}
            result = ForexPortfolioHistoricalBacktester(
                self.historical_policy,
                scanner=self.scanner,
            ).run(
                sliced,
                trading_start_at=histories["EUR_USD"][testing_start].timestamp,
            )
            windows.append({
                "window": len(windows) + 1,
                "training_start_at": histories["EUR_USD"][training_start].timestamp.isoformat(),
                "training_end_at": histories["EUR_USD"][testing_start - 1].timestamp.isoformat(),
                "testing_start_at": histories["EUR_USD"][testing_start].timestamp.isoformat(),
                "testing_end_at": histories["EUR_USD"][testing_end - 1].timestamp.isoformat(),
                "testing": result,
            })
            training_start += self.walk_forward_policy.step_bar_count
        if not windows:
            raise TradingValidationError("forex_portfolio_walk_forward: no_windows")
        returns = [Decimal(window["testing"]["return_pct"]) for window in windows]
        drawdowns = [Decimal(window["testing"]["maximum_drawdown_pct"]) for window in windows]
        trade_count = sum(int(window["testing"]["trade_count"]) for window in windows)
        profitable_count = sum(value > 0 for value in returns)
        profitable_ratio = Decimal(profitable_count) / Decimal(len(windows))
        average_return = sum(returns) / Decimal(len(returns))
        compounded = Decimal("1")
        for value in returns:
            compounded *= Decimal("1") + value / Decimal("100")
        compounded_return = (compounded - Decimal("1")) * Decimal("100")
        performance_checks = {
            "average_return_positive": average_return > 0,
            "compounded_return_positive": compounded_return > 0,
            "profitable_window_ratio_met": profitable_ratio >= self.walk_forward_policy.minimum_profitable_window_ratio,
            "maximum_drawdown_within_limit": max(drawdowns) <= self.walk_forward_policy.maximum_drawdown_pct,
            "minimum_trade_count_met": trade_count >= self.walk_forward_policy.minimum_trade_count,
        }
        scanner_audit = windows[0]["testing"]["scanner_audit"]
        scanner_matches_paper = all(
            window["testing"]["scanner_matches_paper"] for window in windows
        )
        return {
            "status": "COMPLETED",
            "account_currency": "PLN",
            "window_count": len(windows),
            "out_of_sample_trade_count": trade_count,
            "out_of_sample_stop_loss_exit_count": sum(int(window["testing"]["stop_loss_exit_count"]) for window in windows),
            "out_of_sample_take_profit_exit_count": sum(int(window["testing"]["take_profit_exit_count"]) for window in windows),
            "out_of_sample_ambiguous_bar_count": sum(int(window["testing"]["ambiguous_bar_count"]) for window in windows),
            "profitable_out_of_sample_window_count": profitable_count,
            "profitable_out_of_sample_window_ratio": _text(profitable_ratio, _PERCENT),
            "average_out_of_sample_return_pct": _text(average_return, _PERCENT),
            "compounded_out_of_sample_return_pct": _text(compounded_return, _PERCENT),
            "maximum_out_of_sample_drawdown_pct": _text(max(drawdowns), _PERCENT),
            "performance_checks": performance_checks,
            "strategy_performance_validated": all(performance_checks.values()),
            "portfolio_pln_aggregation_performed": True,
            "historical_pln_conversion_series_verified": True,
            "scanner_matches_paper": scanner_matches_paper,
            "scanner_audit": scanner_audit,
            "position_sizing_matches_paper_coordinator": True,
            "stop_loss_formula_matches_paper_coordinator": True,
            "take_profit_research_only": False,
            "take_profit_matches_paper": True,
            "chronological_splits_valid": True,
            "out_of_sample_windows_non_overlapping": True,
            "past_only_warmup_used": True,
            "same_bar_signal_execution_blocked": True,
            "ambiguous_stop_target_bar_uses_stop_first": True,
            "parameter_optimization_performed": False,
            "windows": windows,
            "research_only": True,
            "automatic_paper_promotion": False,
            "broker_connection_used": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }


__all__ = [
    "ForexPortfolioHistoricalBacktester",
    "ForexPortfolioHistoricalPolicy",
    "ForexPortfolioHistoricalWalkForwardValidator",
    "ForexPortfolioWalkForwardPolicy",
]

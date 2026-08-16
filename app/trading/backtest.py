"""Deterministic backtester that executes signals on the next bar."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from app.trading.models import MarketBar, StrategySignal, TradingValidationError
from app.trading.policy import PaperTradingPolicy


_MONEY = Decimal("0.01")
_PERCENT = Decimal("0.0001")


def _text(value: Decimal, quantum: Decimal = _MONEY) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


class HistoricalPaperBacktester:
    """Evaluate explicit signals without same-bar look-ahead."""

    def __init__(self, policy: PaperTradingPolicy | None = None) -> None:
        self.policy = policy or PaperTradingPolicy()

    def run(
        self,
        bars: Iterable[MarketBar],
        signals: Iterable[StrategySignal],
    ) -> dict[str, Any]:
        ordered_bars = sorted(list(bars), key=lambda item: item.timestamp)
        ordered_signals = sorted(list(signals), key=lambda item: item.timestamp)
        if len(ordered_bars) < 2:
            raise TradingValidationError("backtest: at_least_two_bars_required")
        symbols = {bar.symbol for bar in ordered_bars}
        currencies = {bar.currency for bar in ordered_bars}
        if len(symbols) != 1:
            raise TradingValidationError("backtest: one_symbol_per_run")
        if currencies != {self.policy.base_currency}:
            raise TradingValidationError("backtest: currency_mismatch")
        symbol = next(iter(symbols))
        timestamps = [bar.timestamp for bar in ordered_bars]
        if len(timestamps) != len(set(timestamps)):
            raise TradingValidationError("backtest: duplicate_bar_timestamp")
        signal_ids = [signal.signal_id for signal in ordered_signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise TradingValidationError("backtest: duplicate_signal_id")
        if any(signal.symbol != symbol for signal in ordered_signals):
            raise TradingValidationError("backtest: signal_symbol_mismatch")

        scheduled: dict[int, list[StrategySignal]] = defaultdict(list)
        rejected: list[dict[str, str]] = []
        for signal in ordered_signals:
            index = bisect_right(timestamps, signal.timestamp)
            if index >= len(ordered_bars):
                rejected.append({"signal_id": signal.signal_id, "code": "NO_NEXT_BAR"})
            else:
                scheduled[index].append(signal)

        cash = self.policy.initial_cash
        quantity = Decimal("0")
        average_cost = Decimal("0")
        realized_pnl = Decimal("0")
        commissions = Decimal("0")
        fills: list[dict[str, str]] = []
        equity_curve: list[Decimal] = []
        peak = self.policy.initial_cash
        max_drawdown = Decimal("0")
        orders_by_day: dict[str, int] = defaultdict(int)
        day_start_equity: dict[str, Decimal] = {}
        winning_sells = 0
        sell_count = 0
        slippage = self.policy.slippage_bps / Decimal("10000")

        for index, bar in enumerate(ordered_bars):
            day = bar.timestamp.date().isoformat()
            marked_equity = cash + quantity * bar.open
            day_start_equity.setdefault(day, marked_equity)
            for signal in scheduled.get(index, []):
                if orders_by_day[day] >= self.policy.max_orders_per_day:
                    rejected.append(
                        {"signal_id": signal.signal_id, "code": "DAILY_ORDER_LIMIT"}
                    )
                    continue
                execution_price = (
                    bar.open * (Decimal("1") + slippage)
                    if signal.side == "BUY"
                    else bar.open * (Decimal("1") - slippage)
                )
                notional = execution_price * signal.quantity
                fee = max(
                    self.policy.minimum_commission,
                    notional * self.policy.commission_bps / Decimal("10000"),
                )
                equity = cash + quantity * bar.open
                daily_loss = max(Decimal("0"), day_start_equity[day] - equity)
                code = ""
                if notional > equity * self.policy.max_order_notional_pct:
                    code = "ORDER_NOTIONAL_LIMIT"
                elif signal.side == "BUY" and daily_loss >= (
                    day_start_equity[day] * self.policy.max_daily_loss_pct
                ):
                    code = "DAILY_LOSS_LIMIT"
                elif signal.side == "BUY" and (
                    (quantity * bar.open) + notional
                    > equity * self.policy.max_position_pct
                ):
                    code = "POSITION_LIMIT"
                elif signal.side == "BUY" and notional + fee > cash:
                    code = "INSUFFICIENT_PAPER_CASH"
                elif signal.side == "SELL" and signal.quantity > quantity:
                    code = "SHORT_SELLING_BLOCKED"
                if code:
                    rejected.append({"signal_id": signal.signal_id, "code": code})
                    continue

                fill_realized = Decimal("0")
                if signal.side == "BUY":
                    new_quantity = quantity + signal.quantity
                    average_cost = (
                        quantity * average_cost + notional + fee
                    ) / new_quantity
                    quantity = new_quantity
                    cash -= notional + fee
                else:
                    fill_realized = (
                        execution_price - average_cost
                    ) * signal.quantity - fee
                    sell_count += 1
                    winning_sells += int(fill_realized > 0)
                    realized_pnl += fill_realized
                    quantity -= signal.quantity
                    cash += notional - fee
                    if quantity == 0:
                        average_cost = Decimal("0")
                commissions += fee
                orders_by_day[day] += 1
                fills.append({
                    "signal_id": signal.signal_id,
                    "side": signal.side,
                    "quantity": str(signal.quantity),
                    "signal_at": signal.timestamp.isoformat(),
                    "filled_at": bar.timestamp.isoformat(),
                    "price": _text(execution_price, Decimal("0.0001")),
                    "fee": _text(fee),
                    "realized_pnl": _text(fill_realized),
                })

            equity = cash + quantity * bar.close
            equity_curve.append(equity)
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak)

        final_equity = equity_curve[-1]
        net_profit = final_equity - self.policy.initial_cash
        total_return = net_profit / self.policy.initial_cash
        unrealized = quantity * (ordered_bars[-1].close - average_cost)
        win_rate = (
            Decimal(winning_sells) / Decimal(sell_count)
            if sell_count
            else Decimal("0")
        )
        return {
            "status": "BACKTEST_COMPLETED",
            "mode": "HISTORICAL_PAPER_ONLY",
            "symbol": symbol,
            "currency": self.policy.base_currency,
            "bar_count": len(ordered_bars),
            "signal_count": len(ordered_signals),
            "fill_count": len(fills),
            "rejection_count": len(rejected),
            "initial_cash": _text(self.policy.initial_cash),
            "final_cash": _text(cash),
            "final_equity": _text(final_equity),
            "net_profit": _text(net_profit),
            "realized_pnl": _text(realized_pnl),
            "unrealized_pnl": _text(unrealized),
            "commissions": _text(commissions),
            "total_return_pct": _text(total_return * Decimal("100"), _PERCENT),
            "max_drawdown_pct": _text(max_drawdown * Decimal("100"), _PERCENT),
            "win_rate_pct": _text(win_rate * Decimal("100"), _PERCENT),
            "open_quantity": str(quantity),
            "fills": fills,
            "rejections": rejected,
            "look_ahead_blocked": True,
            "live_order_sent": False,
        }


__all__ = ["HistoricalPaperBacktester"]

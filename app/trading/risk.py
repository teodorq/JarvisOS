"""Deterministic pre-trade risk checks for paper orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.trading.models import MarketQuote, PaperOrder, aware_utc
from app.trading.policy import PaperTradingPolicy


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception:
        return Decimal("0")
    return result if result.is_finite() else Decimal("0")


def account_metrics(
    state: dict[str, Any],
    *,
    current_quote: MarketQuote | None = None,
) -> dict[str, Decimal]:
    cash = _decimal(state.get("cash"))
    gross = Decimal("0")
    market_value = Decimal("0")
    for symbol, raw in dict(state.get("positions", {}) or {}).items():
        position = dict(raw or {})
        quantity = max(Decimal("0"), _decimal(position.get("quantity")))
        last_price = _decimal(position.get("last_price"))
        if current_quote is not None and symbol == current_quote.symbol:
            last_price = current_quote.midpoint
        value = quantity * max(Decimal("0"), last_price)
        market_value += value
        gross += abs(value)
    equity = cash + market_value
    return {
        "cash": cash,
        "market_value": market_value,
        "gross_exposure": gross,
        "equity": equity,
    }


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allowed: bool
    code: str
    reason: str
    estimated_price: Decimal = Decimal("0")
    estimated_notional: Decimal = Decimal("0")
    estimated_fee: Decimal = Decimal("0")


class PreTradeRiskEngine:
    """Apply all paper risk limits before a simulated order can be filled."""

    def __init__(self, policy: PaperTradingPolicy | None = None) -> None:
        self.policy = policy or PaperTradingPolicy()

    def evaluate(
        self,
        order: PaperOrder,
        quote: MarketQuote,
        state: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> RiskDecision:
        if str(state.get("mode", "")).upper() != "PAPER_ONLY":
            return self._deny("MODE_NOT_PAPER", "Silnik nie jest w trybie PAPER_ONLY.")
        if bool(dict(state.get("kill_switch", {}) or {}).get("active")):
            return self._deny("KILL_SWITCH_ACTIVE", "Wyłącznik awaryjny jest aktywny.")
        if order.symbol != quote.symbol:
            return self._deny("SYMBOL_MISMATCH", "Zlecenie i kwotowanie dotyczą różnych symboli.")
        if quote.currency != self.policy.base_currency:
            return self._deny("CURRENCY_MISMATCH", "Brak bezpiecznego przelicznika waluty.")

        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        age = (selected_now - quote.timestamp).total_seconds()
        if age < -5:
            return self._deny("QUOTE_FROM_FUTURE", "Kwotowanie ma nieprawidłowy czas.")
        if age > self.policy.max_quote_age_seconds:
            return self._deny("STALE_QUOTE", "Kwotowanie jest zbyt stare.")
        if quote.midpoint <= 0:
            return self._deny("INVALID_QUOTE", "Kwotowanie nie ma dodatniej ceny.")
        spread = (quote.ask - quote.bid) / quote.midpoint
        if spread > self.policy.max_spread_pct:
            return self._deny("SPREAD_TOO_WIDE", "Spread przekracza bezpieczny limit.")
        if int(state.get("orders_today", 0) or 0) >= self.policy.max_orders_per_day:
            return self._deny("DAILY_ORDER_LIMIT", "Osiągnięto dzienny limit zleceń.")

        metrics = account_metrics(state, current_quote=quote)
        equity = metrics["equity"]
        if equity <= 0:
            return self._deny("NO_EQUITY", "Kapitał paper tradingu nie jest dodatni.")
        day_start = _decimal(state.get("day_start_equity")) or equity
        daily_loss = max(Decimal("0"), day_start - equity)
        if (
            order.side == "BUY"
            and daily_loss >= day_start * self.policy.max_daily_loss_pct
        ):
            return self._deny("DAILY_LOSS_LIMIT", "Osiągnięto limit dziennej straty.")

        slippage = self.policy.slippage_bps / Decimal("10000")
        estimated_price = (
            quote.ask * (Decimal("1") + slippage)
            if order.side == "BUY"
            else quote.bid * (Decimal("1") - slippage)
        )
        notional = estimated_price * order.quantity
        fee = max(
            self.policy.minimum_commission,
            notional * self.policy.commission_bps / Decimal("10000"),
        )
        if notional > equity * self.policy.max_order_notional_pct:
            return self._deny(
                "ORDER_NOTIONAL_LIMIT",
                "Wartość zlecenia przekracza limit pojedynczego zlecenia.",
                estimated_price,
                notional,
                fee,
            )

        positions = dict(state.get("positions", {}) or {})
        position = dict(positions.get(order.symbol, {}) or {})
        held_quantity = max(Decimal("0"), _decimal(position.get("quantity")))
        current_value = held_quantity * quote.midpoint
        if order.side == "SELL":
            if order.quantity > held_quantity:
                return self._deny(
                    "SHORT_SELLING_BLOCKED",
                    "Sprzedaż przekracza posiadaną ilość; short selling jest wyłączony.",
                    estimated_price,
                    notional,
                    fee,
                )
            return RiskDecision(True, "ALLOWED", "Zlecenie zmniejsza ekspozycję.", estimated_price, notional, fee)

        if current_value + notional > equity * self.policy.max_position_pct:
            return self._deny(
                "POSITION_LIMIT",
                "Pozycja po zleceniu przekroczyłaby limit symbolu.",
                estimated_price,
                notional,
                fee,
            )
        if (
            metrics["gross_exposure"] + notional
            > equity * self.policy.max_gross_exposure_pct
        ):
            return self._deny(
                "GROSS_EXPOSURE_LIMIT",
                "Łączna ekspozycja przekroczyłaby limit portfela.",
                estimated_price,
                notional,
                fee,
            )
        if notional + fee > metrics["cash"]:
            return self._deny(
                "INSUFFICIENT_PAPER_CASH",
                "Brak wystarczającej gotówki paper; dźwignia jest wyłączona.",
                estimated_price,
                notional,
                fee,
            )
        return RiskDecision(
            True,
            "ALLOWED",
            "Wszystkie limity pre-trade zostały spełnione.",
            estimated_price,
            notional,
            fee,
        )

    @staticmethod
    def _deny(
        code: str,
        reason: str,
        price: Decimal = Decimal("0"),
        notional: Decimal = Decimal("0"),
        fee: Decimal = Decimal("0"),
    ) -> RiskDecision:
        return RiskDecision(False, code, reason, price, notional, fee)


__all__ = ["PreTradeRiskEngine", "RiskDecision", "account_metrics"]

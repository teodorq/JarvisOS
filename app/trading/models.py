"""Strict value objects used by the local paper-trading engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re


_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")
_ORDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,79}$")
_STRATEGY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


class TradingValidationError(ValueError):
    """Raised when market or order data is ambiguous or unsafe."""


def decimal_value(
    value: object,
    field: str,
    *,
    allow_zero: bool = False,
) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise TradingValidationError(f"{field}: invalid_decimal") from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise TradingValidationError(f"{field}: non_positive")
    return result


def aware_utc(value: datetime, field: str = "timestamp") -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise TradingValidationError(f"{field}: timezone_required")
    return value.astimezone(timezone.utc)


def normalized_symbol(value: object) -> str:
    symbol = str(value or "").strip().upper()
    if not _SYMBOL.fullmatch(symbol):
        raise TradingValidationError("symbol: invalid")
    return symbol


def normalized_currency(value: object) -> str:
    currency = str(value or "").strip().upper()
    if not _CURRENCY.fullmatch(currency):
        raise TradingValidationError("currency: invalid")
    return currency


@dataclass(frozen=True, slots=True)
class MarketQuote:
    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: datetime
    currency: str = "PLN"

    def __post_init__(self) -> None:
        symbol = normalized_symbol(self.symbol)
        bid = decimal_value(self.bid, "bid")
        ask = decimal_value(self.ask, "ask")
        if ask < bid:
            raise TradingValidationError("quote: crossed_market")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)
        object.__setattr__(self, "timestamp", aware_utc(self.timestamp))
        object.__setattr__(self, "currency", normalized_currency(self.currency))

    @classmethod
    def create(
        cls,
        *,
        symbol: object,
        bid: object,
        ask: object,
        timestamp: datetime,
        currency: object = "PLN",
    ) -> "MarketQuote":
        normalized_bid = decimal_value(bid, "bid")
        normalized_ask = decimal_value(ask, "ask")
        if normalized_ask < normalized_bid:
            raise TradingValidationError("quote: crossed_market")
        return cls(
            symbol=normalized_symbol(symbol),
            bid=normalized_bid,
            ask=normalized_ask,
            timestamp=aware_utc(timestamp),
            currency=normalized_currency(currency),
        )

    @property
    def midpoint(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")


@dataclass(frozen=True, slots=True)
class PaperOrder:
    client_order_id: str
    symbol: str
    side: str
    quantity: Decimal
    created_at: datetime
    strategy_id: str = "MANUAL_PAPER"

    def __post_init__(self) -> None:
        order_id = str(self.client_order_id or "").strip()
        if not _ORDER_ID.fullmatch(order_id):
            raise TradingValidationError("client_order_id: invalid")
        side = str(self.side or "").strip().upper()
        if side not in {"BUY", "SELL"}:
            raise TradingValidationError("side: buy_or_sell_required")
        strategy = str(self.strategy_id or "").strip().upper()
        if not _STRATEGY_ID.fullmatch(strategy):
            raise TradingValidationError("strategy_id: invalid")
        object.__setattr__(self, "client_order_id", order_id)
        object.__setattr__(self, "symbol", normalized_symbol(self.symbol))
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "quantity", decimal_value(self.quantity, "quantity"))
        object.__setattr__(self, "created_at", aware_utc(self.created_at, "created_at"))
        object.__setattr__(self, "strategy_id", strategy)

    @classmethod
    def create(
        cls,
        *,
        client_order_id: object,
        symbol: object,
        side: object,
        quantity: object,
        created_at: datetime,
        strategy_id: object = "MANUAL_PAPER",
    ) -> "PaperOrder":
        order_id = str(client_order_id or "").strip()
        if not _ORDER_ID.fullmatch(order_id):
            raise TradingValidationError("client_order_id: invalid")
        normalized_side = str(side or "").strip().upper()
        if normalized_side not in {"BUY", "SELL"}:
            raise TradingValidationError("side: buy_or_sell_required")
        normalized_strategy = str(strategy_id or "").strip().upper()
        if not _STRATEGY_ID.fullmatch(normalized_strategy):
            raise TradingValidationError("strategy_id: invalid")
        return cls(
            client_order_id=order_id,
            symbol=normalized_symbol(symbol),
            side=normalized_side,
            quantity=decimal_value(quantity, "quantity"),
            created_at=aware_utc(created_at, "created_at"),
            strategy_id=normalized_strategy,
        )


@dataclass(frozen=True, slots=True)
class MarketBar:
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    currency: str = "PLN"

    def __post_init__(self) -> None:
        open_price = decimal_value(self.open, "open")
        high_price = decimal_value(self.high, "high")
        low_price = decimal_value(self.low, "low")
        close_price = decimal_value(self.close, "close")
        volume = decimal_value(self.volume, "volume", allow_zero=True)
        if high_price < max(open_price, low_price, close_price):
            raise TradingValidationError("bar: high_inconsistent")
        if low_price > min(open_price, high_price, close_price):
            raise TradingValidationError("bar: low_inconsistent")
        object.__setattr__(self, "symbol", normalized_symbol(self.symbol))
        object.__setattr__(self, "timestamp", aware_utc(self.timestamp))
        object.__setattr__(self, "open", open_price)
        object.__setattr__(self, "high", high_price)
        object.__setattr__(self, "low", low_price)
        object.__setattr__(self, "close", close_price)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "currency", normalized_currency(self.currency))

    @classmethod
    def create(
        cls,
        *,
        symbol: object,
        timestamp: datetime,
        open: object,
        high: object,
        low: object,
        close: object,
        volume: object,
        currency: object = "PLN",
    ) -> "MarketBar":
        open_price = decimal_value(open, "open")
        high_price = decimal_value(high, "high")
        low_price = decimal_value(low, "low")
        close_price = decimal_value(close, "close")
        normalized_volume = decimal_value(volume, "volume", allow_zero=True)
        if high_price < max(open_price, low_price, close_price):
            raise TradingValidationError("bar: high_inconsistent")
        if low_price > min(open_price, high_price, close_price):
            raise TradingValidationError("bar: low_inconsistent")
        return cls(
            symbol=normalized_symbol(symbol),
            timestamp=aware_utc(timestamp),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=normalized_volume,
            currency=normalized_currency(currency),
        )


@dataclass(frozen=True, slots=True)
class StrategySignal:
    signal_id: str
    symbol: str
    side: str
    quantity: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        order = PaperOrder(
            client_order_id=self.signal_id,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            created_at=self.timestamp,
            strategy_id="BACKTEST",
        )
        object.__setattr__(self, "signal_id", order.client_order_id)
        object.__setattr__(self, "symbol", order.symbol)
        object.__setattr__(self, "side", order.side)
        object.__setattr__(self, "quantity", order.quantity)
        object.__setattr__(self, "timestamp", order.created_at)

    @classmethod
    def create(
        cls,
        *,
        signal_id: object,
        symbol: object,
        side: object,
        quantity: object,
        timestamp: datetime,
    ) -> "StrategySignal":
        order = PaperOrder.create(
            client_order_id=signal_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            created_at=timestamp,
            strategy_id="BACKTEST",
        )
        return cls(
            signal_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            timestamp=order.created_at,
        )


__all__ = [
    "MarketBar",
    "MarketQuote",
    "PaperOrder",
    "StrategySignal",
    "TradingValidationError",
    "aware_utc",
    "decimal_value",
    "normalized_currency",
    "normalized_symbol",
]

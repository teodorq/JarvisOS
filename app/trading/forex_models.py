"""Strict value objects for broker-neutral, paper-only Forex research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re

from app.trading.models import (
    TradingValidationError,
    aware_utc,
    decimal_value,
    normalized_currency,
)


_PAIR = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


def normalized_pair(value: object) -> str:
    symbol = str(value or "").strip().upper().replace("/", "_")
    if not _PAIR.fullmatch(symbol):
        raise TradingValidationError("forex_pair: invalid")
    base, quote = symbol.split("_", 1)
    if base == quote:
        raise TradingValidationError("forex_pair: currencies_must_differ")
    normalized_currency(base)
    normalized_currency(quote)
    return symbol


@dataclass(frozen=True, slots=True)
class ForexPair:
    symbol: str
    base_currency: str
    quote_currency: str
    pip_size: Decimal
    tradable: bool = True

    @classmethod
    def create(cls, symbol: object, *, tradable: bool = True) -> "ForexPair":
        normalized = normalized_pair(symbol)
        base, quote = normalized.split("_", 1)
        return cls(
            symbol=normalized,
            base_currency=base,
            quote_currency=quote,
            pip_size=Decimal("0.01") if quote == "JPY" else Decimal("0.0001"),
            tradable=bool(tradable),
        )

    def __post_init__(self) -> None:
        symbol = normalized_pair(self.symbol)
        base, quote = symbol.split("_", 1)
        expected_pip = Decimal("0.01") if quote == "JPY" else Decimal("0.0001")
        if self.base_currency != base or self.quote_currency != quote:
            raise TradingValidationError("forex_pair: currency_mismatch")
        if self.pip_size != expected_pip:
            raise TradingValidationError("forex_pair: invalid_pip_size")


MAJOR_FOREX_PAIRS: tuple[ForexPair, ...] = tuple(
    ForexPair.create(symbol)
    for symbol in (
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "AUD_USD",
        "USD_CAD",
        "NZD_USD",
    )
)
USD_PLN_CONVERSION_PAIR = ForexPair.create("USD_PLN", tradable=False)


def major_pair(symbol: object) -> ForexPair:
    normalized = normalized_pair(symbol)
    for pair in MAJOR_FOREX_PAIRS:
        if pair.symbol == normalized:
            return pair
    raise TradingValidationError("forex_pair: outside_major_universe")


@dataclass(frozen=True, slots=True)
class ForexQuote:
    pair: ForexPair
    bid: Decimal
    ask: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.pair, ForexPair):
            raise TradingValidationError("forex_quote: pair_required")
        bid = decimal_value(self.bid, "bid")
        ask = decimal_value(self.ask, "ask")
        if ask < bid:
            raise TradingValidationError("forex_quote: crossed_market")
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)
        object.__setattr__(self, "timestamp", aware_utc(self.timestamp))

    @classmethod
    def create(
        cls,
        *,
        pair: ForexPair,
        bid: object,
        ask: object,
        timestamp: datetime,
    ) -> "ForexQuote":
        return cls(pair=pair, bid=bid, ask=ask, timestamp=timestamp)

    @property
    def midpoint(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread_pips(self) -> Decimal:
        return (self.ask - self.bid) / self.pair.pip_size


@dataclass(frozen=True, slots=True)
class ForexBar:
    pair: ForexPair
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.pair, ForexPair):
            raise TradingValidationError("forex_bar: pair_required")
        open_price = decimal_value(self.open, "open")
        high_price = decimal_value(self.high, "high")
        low_price = decimal_value(self.low, "low")
        close_price = decimal_value(self.close, "close")
        volume = decimal_value(self.tick_volume, "tick_volume", allow_zero=True)
        if high_price < max(open_price, low_price, close_price):
            raise TradingValidationError("forex_bar: high_inconsistent")
        if low_price > min(open_price, high_price, close_price):
            raise TradingValidationError("forex_bar: low_inconsistent")
        object.__setattr__(self, "timestamp", aware_utc(self.timestamp))
        object.__setattr__(self, "open", open_price)
        object.__setattr__(self, "high", high_price)
        object.__setattr__(self, "low", low_price)
        object.__setattr__(self, "close", close_price)
        object.__setattr__(self, "tick_volume", volume)

    @classmethod
    def create(
        cls,
        *,
        pair: ForexPair,
        timestamp: datetime,
        open: object,
        high: object,
        low: object,
        close: object,
        tick_volume: object,
    ) -> "ForexBar":
        return cls(
            pair=pair,
            timestamp=timestamp,
            open=open,
            high=high,
            low=low,
            close=close,
            tick_volume=tick_volume,
        )


@dataclass(frozen=True, slots=True)
class ForexPosition:
    pair: ForexPair
    side: str
    units: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Decimal
    opened_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.pair, ForexPair):
            raise TradingValidationError("forex_position: pair_required")
        side = str(self.side or "").strip().upper()
        if side not in {"LONG", "SHORT"}:
            raise TradingValidationError("forex_position: long_or_short_required")
        units = decimal_value(self.units, "units")
        entry = decimal_value(self.entry_price, "entry_price")
        current = decimal_value(self.current_price, "current_price")
        stop = decimal_value(self.stop_loss, "stop_loss")
        if side == "LONG" and stop >= entry:
            raise TradingValidationError("forex_position: long_stop_must_be_lower")
        if side == "SHORT" and stop <= entry:
            raise TradingValidationError("forex_position: short_stop_must_be_higher")
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "units", units)
        object.__setattr__(self, "entry_price", entry)
        object.__setattr__(self, "current_price", current)
        object.__setattr__(self, "stop_loss", stop)
        object.__setattr__(self, "opened_at", aware_utc(self.opened_at, "opened_at"))


@dataclass(frozen=True, slots=True)
class ForexSafetyContext:
    observed_at: datetime
    market_open: bool
    calendar_ready: bool
    high_impact_event_blocked: bool
    conversion_to_pln_ready: bool
    independent_source_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", aware_utc(self.observed_at))
        if any(type(value) is not bool for value in (
            self.market_open,
            self.calendar_ready,
            self.high_impact_event_blocked,
            self.conversion_to_pln_ready,
        )):
            raise TradingValidationError("forex_context: boolean_required")
        if type(self.independent_source_count) is not int or not (
            1 <= self.independent_source_count <= 5
        ):
            raise TradingValidationError("forex_context: invalid_source_count")

    @property
    def opening_blocks(self) -> tuple[str, ...]:
        blocks: list[str] = []
        if not self.market_open:
            blocks.append("MARKET_CLOSED")
        if not self.calendar_ready:
            blocks.append("ECONOMIC_CALENDAR_UNAVAILABLE")
        if self.high_impact_event_blocked:
            blocks.append("HIGH_IMPACT_EVENT_WINDOW")
        if not self.conversion_to_pln_ready:
            blocks.append("PLN_CONVERSION_UNAVAILABLE")
        if self.independent_source_count < 2:
            blocks.append("SECOND_SOURCE_UNAVAILABLE")
        return tuple(blocks)


__all__ = [
    "ForexBar",
    "ForexPair",
    "ForexPosition",
    "ForexQuote",
    "ForexSafetyContext",
    "MAJOR_FOREX_PAIRS",
    "USD_PLN_CONVERSION_PAIR",
    "major_pair",
    "normalized_pair",
]

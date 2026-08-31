"""Strict values exchanged across the read-only Forex data boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Mapping

from app.trading.forex_models import ForexBar, ForexPair, ForexQuote, ForexSafetyContext
from app.trading.models import TradingValidationError, aware_utc, decimal_value, normalized_currency


@dataclass(frozen=True, slots=True)
class IndependentRate:
    pair: ForexPair
    midpoint: Decimal
    timestamp: datetime
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.pair, ForexPair) or not self.pair.tradable:
            raise TradingValidationError("forex_data: tradable_pair_required")
        object.__setattr__(self, "midpoint", decimal_value(self.midpoint, "midpoint"))
        object.__setattr__(self, "timestamp", aware_utc(self.timestamp))
        source = str(self.source or "").strip().upper()
        if not source or len(source) > 40:
            raise TradingValidationError("forex_data: invalid_source")
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True)
class PlnReferenceRate:
    currency: str
    midpoint_pln: Decimal
    effective_date: date
    fetched_at: datetime
    source: str = "NBP"

    def __post_init__(self) -> None:
        currency = normalized_currency(self.currency)
        if currency == "PLN":
            raise TradingValidationError("forex_data: foreign_currency_required")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(
            self, "midpoint_pln", decimal_value(self.midpoint_pln, "midpoint_pln")
        )
        if not isinstance(self.effective_date, date):
            raise TradingValidationError("forex_data: effective_date_required")
        object.__setattr__(self, "fetched_at", aware_utc(self.fetched_at))


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    event_at: datetime
    title: str
    currencies: tuple[str, ...]
    importance: int
    block_start_at: datetime | None = None
    block_end_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_at", aware_utc(self.event_at))
        title = " ".join(str(self.title or "").split())
        if not title or len(title) > 240:
            raise TradingValidationError("forex_calendar: invalid_title")
        object.__setattr__(self, "title", title)
        currencies = tuple(
            dict.fromkeys(normalized_currency(item) for item in self.currencies)
        )
        if not currencies or len(currencies) > 4:
            raise TradingValidationError("forex_calendar: invalid_currencies")
        object.__setattr__(self, "currencies", currencies)
        if type(self.importance) is not int or not 1 <= self.importance <= 3:
            raise TradingValidationError("forex_calendar: invalid_importance")
        start = self.block_start_at
        end = self.block_end_at
        if (start is None) != (end is None):
            raise TradingValidationError("forex_calendar: incomplete_block_window")
        if start is not None and end is not None:
            start = aware_utc(start)
            end = aware_utc(end)
            if (
                self.importance != 3
                or end <= start
                or end - start > timedelta(days=2)
            ):
                raise TradingValidationError("forex_calendar: invalid_block_window")
            object.__setattr__(self, "block_start_at", start)
            object.__setattr__(self, "block_end_at", end)


@dataclass(frozen=True, slots=True)
class EconomicCalendarSnapshot:
    provider: str
    fetched_at: datetime
    coverage_start: datetime
    coverage_end: datetime
    events: tuple[EconomicEvent, ...]

    def __post_init__(self) -> None:
        provider = str(self.provider or "").strip().upper()
        if not provider or len(provider) > 40:
            raise TradingValidationError("forex_calendar: invalid_provider")
        object.__setattr__(self, "provider", provider)
        fetched = aware_utc(self.fetched_at)
        start = aware_utc(self.coverage_start)
        end = aware_utc(self.coverage_end)
        if end <= start:
            raise TradingValidationError("forex_calendar: invalid_coverage")
        object.__setattr__(self, "fetched_at", fetched)
        object.__setattr__(self, "coverage_start", start)
        object.__setattr__(self, "coverage_end", end)
        object.__setattr__(self, "events", tuple(self.events))


@dataclass(frozen=True, slots=True)
class ForexDataBundle:
    quotes: Mapping[str, ForexQuote]
    bars: Mapping[str, tuple[ForexBar, ...]]
    contexts: Mapping[str, ForexSafetyContext]
    conversion_quotes: tuple[ForexQuote, ...]
    diagnostics: Mapping[str, object]


__all__ = [
    "EconomicCalendarSnapshot",
    "EconomicEvent",
    "ForexDataBundle",
    "IndependentRate",
    "PlnReferenceRate",
]

"""Fail-closed composition of approved read-only Forex data sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

from app.market_data.forex_environment import ForexDataSettings
from app.market_data.forex_models import EconomicCalendarSnapshot, ForexDataBundle, IndependentRate
from app.market_data.forex_sources import (
    FmpEconomicCalendarReadOnlySource,
    JsonTransport,
    NbpPlnReadOnlySource,
    OandaPracticeReadOnlySource,
    TwelveDataReadOnlySource,
)
from app.trading.forex_models import (
    ForexPair,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.models import TradingValidationError, aware_utc


@dataclass(frozen=True, slots=True)
class ForexDataGatePolicy:
    max_primary_age_seconds: int = 10
    max_independent_age_seconds: int = 90
    max_source_deviation_pct: Decimal = Decimal("0.002")
    max_calendar_age_seconds: int = 900
    max_nbp_business_age_days: int = 4
    event_block_before_minutes: int = 30
    event_block_after_minutes: int = 30

    def __post_init__(self) -> None:
        if not 1 <= self.max_primary_age_seconds <= 30:
            raise TradingValidationError("forex_data_gate: unsafe_primary_age")
        if not 5 <= self.max_independent_age_seconds <= 300:
            raise TradingValidationError("forex_data_gate: unsafe_independent_age")
        if not Decimal("0.0001") <= self.max_source_deviation_pct <= Decimal("0.005"):
            raise TradingValidationError("forex_data_gate: unsafe_deviation")
        if not 60 <= self.max_calendar_age_seconds <= 3600:
            raise TradingValidationError("forex_data_gate: unsafe_calendar_age")
        if not 1 <= self.max_nbp_business_age_days <= 4:
            raise TradingValidationError("forex_data_gate: unsafe_nbp_age")
        if not 5 <= self.event_block_before_minutes <= 120:
            raise TradingValidationError("forex_data_gate: unsafe_event_window")
        if not 5 <= self.event_block_after_minutes <= 120:
            raise TradingValidationError("forex_data_gate: unsafe_event_window")


class ForexReadOnlyDataGateway:
    """Collect a complete PAPER input bundle without exposing order endpoints."""

    def __init__(
        self,
        settings: ForexDataSettings,
        *,
        transport: JsonTransport | None = None,
        policy: ForexDataGatePolicy | None = None,
        universe: Iterable[ForexPair] = MAJOR_FOREX_PAIRS,
    ) -> None:
        self.settings = settings
        self.policy = policy or ForexDataGatePolicy()
        self.universe = tuple(universe)
        if self.universe != MAJOR_FOREX_PAIRS:
            raise TradingValidationError("forex_data_gate: unsupported_universe")
        self._transport = transport

    def status(self) -> dict[str, object]:
        return {
            "mode": "READ_ONLY_PAPER_INPUT",
            "configured": self.settings.readiness(),
            "providers": {
                "primary": "OANDA_PRACTICE",
                "independent": "TWELVE_DATA",
                "pln_reference": "NBP",
                "economic_calendar": "FMP",
            },
            "live_order_surface": False,
            "real_money_access": False,
        }

    def collect(self, *, now: datetime | None = None) -> ForexDataBundle:
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        if not self.settings.readiness()["complete"]:
            raise TradingValidationError("forex_data_gate: configuration_incomplete")
        primary_source = OandaPracticeReadOnlySource(
            account_id=self.settings.oanda_practice_account_id,
            token=self.settings.oanda_practice_token,
            transport=self._transport,
        )
        independent_source = TwelveDataReadOnlySource(
            self.settings.twelve_data_api_key, self._transport
        )
        calendar_source = FmpEconomicCalendarReadOnlySource(
            self.settings.fmp_api_key, self._transport
        )
        nbp_source = NbpPlnReadOnlySource(self._transport)

        quotes = primary_source.fetch_quotes(self.universe)
        bars = {
            pair.symbol: primary_source.fetch_bars(pair)
            for pair in self.universe
        }
        independent = independent_source.fetch_rates(self.universe)
        pln_reference = nbp_source.fetch_usd_pln(fetched_at=selected_now)
        calendar = calendar_source.fetch_calendar(now=selected_now)

        conversion_ready = self._pln_reference_ready(
            pln_reference.effective_date, selected_now
        )
        conversion_quotes: tuple[ForexQuote, ...] = ()
        if conversion_ready:
            conversion_quotes = (ForexQuote.create(
                pair=USD_PLN_CONVERSION_PAIR,
                bid=pln_reference.midpoint_pln,
                ask=pln_reference.midpoint_pln,
                timestamp=pln_reference.fetched_at,
            ),)
        calendar_ready = self._calendar_ready(calendar, selected_now)
        contexts: dict[str, ForexSafetyContext] = {}
        cross_checked: list[str] = []
        for pair in self.universe:
            source_count = 1
            if self._sources_agree(
                quotes[pair.symbol], independent.get(pair.symbol), selected_now
            ):
                source_count = 2
                cross_checked.append(pair.symbol)
            contexts[pair.symbol] = ForexSafetyContext(
                observed_at=selected_now,
                market_open=self.market_open(selected_now),
                calendar_ready=calendar_ready,
                high_impact_event_blocked=(
                    self._event_blocked(pair, calendar, selected_now)
                    if calendar_ready else True
                ),
                conversion_to_pln_ready=conversion_ready,
                independent_source_count=source_count,
            )
        return ForexDataBundle(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            conversion_quotes=conversion_quotes,
            diagnostics={
                "mode": "READ_ONLY_PAPER_INPUT",
                "collected_at": selected_now.isoformat(),
                "primary_pair_count": len(quotes),
                "cross_checked_pairs": tuple(cross_checked),
                "calendar_ready": calendar_ready,
                "high_impact_event_count": sum(
                    event.importance == 3 for event in calendar.events
                ),
                "nbp_effective_date": pln_reference.effective_date.isoformat(),
                "pln_conversion_ready": conversion_ready,
                "live_orders_sent": False,
            },
        )

    def _sources_agree(
        self,
        primary: ForexQuote,
        independent: IndependentRate | None,
        now: datetime,
    ) -> bool:
        if independent is None or independent.pair != primary.pair:
            return False
        primary_age = (now - primary.timestamp).total_seconds()
        independent_age = (now - independent.timestamp).total_seconds()
        if not -2 <= primary_age <= self.policy.max_primary_age_seconds:
            return False
        if not -2 <= independent_age <= self.policy.max_independent_age_seconds:
            return False
        deviation = abs(primary.midpoint - independent.midpoint) / primary.midpoint
        return deviation <= self.policy.max_source_deviation_pct

    def _calendar_ready(
        self, snapshot: EconomicCalendarSnapshot, now: datetime
    ) -> bool:
        age = (now - snapshot.fetched_at).total_seconds()
        return (
            -2 <= age <= self.policy.max_calendar_age_seconds
            and snapshot.coverage_start <= now <= snapshot.coverage_end
        )

    def _pln_reference_ready(self, effective_date: date, now: datetime) -> bool:
        age_days = (now.date() - effective_date).days
        return 0 <= age_days <= self.policy.max_nbp_business_age_days

    def _event_blocked(
        self,
        pair: ForexPair,
        snapshot: EconomicCalendarSnapshot,
        now: datetime,
    ) -> bool:
        start = now - timedelta(minutes=self.policy.event_block_after_minutes)
        end = now + timedelta(minutes=self.policy.event_block_before_minutes)
        affected = {pair.base_currency, pair.quote_currency}
        return any(
            event.importance == 3
            and start <= event.event_at <= end
            and bool(affected.intersection(event.currencies))
            for event in snapshot.events
        )

    @staticmethod
    def market_open(now: datetime) -> bool:
        selected = aware_utc(now)
        weekday = selected.weekday()
        if weekday <= 3:
            return True
        if weekday == 4:
            return selected.hour < 21
        if weekday == 5:
            return False
        return selected.hour >= 22


__all__ = ["ForexDataGatePolicy", "ForexReadOnlyDataGateway"]

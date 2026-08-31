"""Fixed-host, GET-only Forex data adapters; no broker order surface."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import re
from typing import Any, Callable, Iterable, Mapping

from app.market_data.forex_models import (
    EconomicCalendarSnapshot,
    EconomicEvent,
    IndependentRate,
    PlnReferenceRate,
)
from app.market_data.http_json import JsonHttpTransport, MarketDataTransportError, PreparedJsonRequest
from app.trading.forex_models import ForexBar, ForexPair, ForexQuote, major_pair
from app.trading.models import TradingValidationError, aware_utc


JsonTransport = Callable[[PreparedJsonRequest], Any]
_ACCOUNT_ID = re.compile(r"^[A-Za-z0-9-]{3,80}$")
_MAJOR_CURRENCIES = frozenset({"AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NZD", "USD"})
_COUNTRY_CURRENCY = {
    "australia": "AUD",
    "canada": "CAD",
    "euro area": "EUR",
    "eurozone": "EUR",
    "france": "EUR",
    "germany": "EUR",
    "italy": "EUR",
    "japan": "JPY",
    "new zealand": "NZD",
    "switzerland": "CHF",
    "united kingdom": "GBP",
    "united states": "USD",
}


def _source_datetime(value: object, code: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise TradingValidationError(code) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _utc_datetime(value: object, code: str) -> datetime:
    return aware_utc(_source_datetime(value, code))


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TradingValidationError(code)
    return value


class OandaPracticeReadOnlySource:
    HOST = "api-fxpractice.oanda.com"

    def __init__(
        self,
        *,
        account_id: str,
        token: str,
        transport: JsonTransport | None = None,
    ) -> None:
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise TradingValidationError("oanda_practice: invalid_account_id")
        if not token or len(token) > 4096 or any(char.isspace() for char in token):
            raise TradingValidationError("oanda_practice: invalid_token")
        self.account_id = account_id
        self._token = token
        self._transport = transport or JsonHttpTransport()

    def _request(
        self, path: str, query: Iterable[tuple[str, str]] = ()
    ) -> PreparedJsonRequest:
        return PreparedJsonRequest.build(
            host=self.HOST,
            path=path,
            query=query,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
        )

    def fetch_quotes(self, pairs: Iterable[ForexPair]) -> dict[str, ForexQuote]:
        selected = tuple(pairs)
        symbols = tuple(pair.symbol for pair in selected)
        if not symbols or len(set(symbols)) != len(symbols):
            raise TradingValidationError("oanda_practice: invalid_universe")
        request = self._request(
            f"/v3/accounts/{self.account_id}/pricing",
            (("instruments", ",".join(symbols)), ("includeHomeConversions", "false")),
        )
        payload = _mapping(self._transport(request), "oanda_practice: invalid_response")
        rows = payload.get("prices")
        if not isinstance(rows, list):
            raise TradingValidationError("oanda_practice: prices_missing")
        quotes: dict[str, ForexQuote] = {}
        for raw in rows:
            row = _mapping(raw, "oanda_practice: invalid_price")
            symbol = str(row.get("instrument", "")).upper()
            if symbol not in symbols or row.get("status") != "tradeable":
                continue
            bids, asks = row.get("bids"), row.get("asks")
            if not isinstance(bids, list) or not bids or not isinstance(asks, list) or not asks:
                raise TradingValidationError("oanda_practice: liquidity_missing")
            bid = max(Decimal(str(_mapping(item, "oanda_practice: invalid_bid")["price"])) for item in bids)
            ask = min(Decimal(str(_mapping(item, "oanda_practice: invalid_ask")["price"])) for item in asks)
            quotes[symbol] = ForexQuote.create(
                pair=major_pair(symbol),
                bid=bid,
                ask=ask,
                timestamp=_utc_datetime(row.get("time"), "oanda_practice: invalid_time"),
            )
        if set(quotes) != set(symbols):
            raise TradingValidationError("oanda_practice: incomplete_prices")
        return quotes

    def fetch_bars(self, pair: ForexPair, *, count: int = 31) -> tuple[ForexBar, ...]:
        if not pair.tradable or not 31 <= count <= 499:
            raise TradingValidationError("oanda_practice: invalid_candle_request")
        request = self._request(
            f"/v3/accounts/{self.account_id}/instruments/{pair.symbol}/candles",
            (("price", "M"), ("granularity", "M15"), ("count", str(count + 1))),
        )
        payload = _mapping(self._transport(request), "oanda_practice: invalid_response")
        rows = payload.get("candles")
        if not isinstance(rows, list):
            raise TradingValidationError("oanda_practice: candles_missing")
        bars: list[ForexBar] = []
        for raw in rows:
            row = _mapping(raw, "oanda_practice: invalid_candle")
            if row.get("complete") is not True:
                continue
            mid = _mapping(row.get("mid"), "oanda_practice: midpoint_missing")
            bars.append(ForexBar.create(
                pair=pair,
                timestamp=_utc_datetime(row.get("time"), "oanda_practice: invalid_time"),
                open=mid.get("o"),
                high=mid.get("h"),
                low=mid.get("l"),
                close=mid.get("c"),
                tick_volume=row.get("volume"),
            ))
        bars.sort(key=lambda item: item.timestamp)
        if len(bars) < count:
            raise TradingValidationError("oanda_practice: incomplete_candles")
        return tuple(bars[-count:])


class TwelveDataReadOnlySource:
    HOST = "api.twelvedata.com"

    def __init__(self, api_key: str, transport: JsonTransport | None = None) -> None:
        if not api_key or len(api_key) > 4096 or any(char.isspace() for char in api_key):
            raise TradingValidationError("twelve_data: invalid_api_key")
        self._api_key = api_key
        self._transport = transport or JsonHttpTransport()

    def fetch_rates(self, pairs: Iterable[ForexPair]) -> dict[str, IndependentRate]:
        rates: dict[str, IndependentRate] = {}
        for pair in tuple(pairs):
            request = PreparedJsonRequest.build(
                host=self.HOST,
                path="/exchange_rate",
                query=(("symbol", pair.symbol.replace("_", "/")), ("timezone", "UTC")),
                headers={"Accept": "application/json", "Authorization": f"apikey {self._api_key}"},
            )
            payload = _mapping(self._transport(request), "twelve_data: invalid_response")
            returned = str(payload.get("symbol", "")).replace("/", "_").upper()
            if returned != pair.symbol:
                raise TradingValidationError("twelve_data: pair_mismatch")
            try:
                timestamp = datetime.fromtimestamp(int(payload["timestamp"]), tz=timezone.utc)
            except (KeyError, TypeError, ValueError, OSError) as error:
                raise TradingValidationError("twelve_data: invalid_timestamp") from error
            rates[pair.symbol] = IndependentRate(
                pair=pair,
                midpoint=payload.get("rate"),
                timestamp=timestamp,
                source="TWELVE_DATA",
            )
        return rates


class NbpPlnReadOnlySource:
    HOST = "api.nbp.pl"

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self._transport = transport or JsonHttpTransport()

    def fetch_usd_pln(self, *, fetched_at: datetime) -> PlnReferenceRate:
        request = PreparedJsonRequest.build(
            host=self.HOST,
            path="/api/exchangerates/rates/a/usd/",
            headers={"Accept": "application/json"},
        )
        payload = _mapping(self._transport(request), "nbp: invalid_response")
        rows = payload.get("rates")
        if not isinstance(rows, list) or len(rows) != 1:
            raise TradingValidationError("nbp: rate_missing")
        rate = _mapping(rows[0], "nbp: invalid_rate")
        try:
            effective = date.fromisoformat(str(rate["effectiveDate"]))
        except (KeyError, ValueError) as error:
            raise TradingValidationError("nbp: invalid_effective_date") from error
        return PlnReferenceRate(
            currency="USD",
            midpoint_pln=rate.get("mid"),
            effective_date=effective,
            fetched_at=fetched_at,
        )


class ForexFactoryEconomicCalendarReadOnlySource:
    """Read the public weekly Forex Factory JSON export without credentials."""

    HOST = "nfs.faireconomy.media"
    PATH = "/ff_calendar_thisweek.json"

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self._transport = transport or JsonHttpTransport()

    def fetch_calendar(self, *, now: datetime) -> EconomicCalendarSnapshot:
        selected_now = aware_utc(now)
        request = PreparedJsonRequest.build(
            host=self.HOST,
            path=self.PATH,
            headers={"Accept": "application/json"},
        )
        payload = self._transport(request)
        if not isinstance(payload, list) or not 1 <= len(payload) <= 1_000:
            raise TradingValidationError("forex_factory_calendar: invalid_response")
        events: list[EconomicEvent] = []
        for raw in payload:
            row = _mapping(raw, "forex_factory_calendar: invalid_event")
            currency = str(row.get("country", "")).strip().upper()
            if currency not in _MAJOR_CURRENCIES:
                continue
            impact = str(row.get("impact", "")).strip().casefold()
            importance = {
                "low": 1,
                "medium": 2,
                "high": 3,
                "holiday": 3,
            }.get(impact)
            if importance is None:
                raise TradingValidationError(
                    "forex_factory_calendar: invalid_importance"
                )
            source_time = _source_datetime(
                row.get("date"), "forex_factory_calendar: invalid_time"
            )
            block_start = None
            block_end = None
            if impact == "holiday":
                block_start = datetime.combine(
                    source_time.date(), time.min, tzinfo=source_time.tzinfo
                )
                block_end = block_start + timedelta(days=1)
            events.append(EconomicEvent(
                event_at=source_time,
                title=row.get("title"),
                currencies=(currency,),
                importance=importance,
                block_start_at=block_start,
                block_end_at=block_end,
            ))
        events.sort(key=lambda item: item.event_at)
        if not events:
            raise TradingValidationError("forex_factory_calendar: coverage_missing")
        anchor = events[0].event_at
        start_day = anchor.date() - timedelta(days=(anchor.weekday() + 1) % 7)
        coverage_start = datetime.combine(start_day, time.min, tzinfo=timezone.utc)
        coverage_end = coverage_start + timedelta(days=7)
        if any(
            not coverage_start <= event.event_at < coverage_end for event in events
        ):
            raise TradingValidationError("forex_factory_calendar: invalid_coverage")
        return EconomicCalendarSnapshot(
            provider="FOREX_FACTORY",
            fetched_at=selected_now,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            events=tuple(events),
        )


class FmpEconomicCalendarReadOnlySource:
    HOST = "financialmodelingprep.com"

    def __init__(self, api_key: str, transport: JsonTransport | None = None) -> None:
        if not api_key or len(api_key) > 4096 or any(char.isspace() for char in api_key):
            raise TradingValidationError("fmp_calendar: invalid_api_key")
        self._api_key = api_key
        self._transport = transport or JsonHttpTransport()

    def fetch_calendar(self, *, now: datetime) -> EconomicCalendarSnapshot:
        selected_now = aware_utc(now)
        start_day, end_day = selected_now.date() - timedelta(days=1), selected_now.date() + timedelta(days=1)
        request = PreparedJsonRequest.build(
            host=self.HOST,
            path="/stable/economic-calendar",
            query=(("from", start_day.isoformat()), ("to", end_day.isoformat())),
            headers={"Accept": "application/json", "apikey": self._api_key},
        )
        payload = self._transport(request)
        if not isinstance(payload, list):
            raise TradingValidationError("fmp_calendar: invalid_response")
        events: list[EconomicEvent] = []
        for raw in payload:
            row = _mapping(raw, "fmp_calendar: invalid_event")
            currency = self._currency(row)
            if currency is None:
                continue
            importance = self._importance(row.get("impact"))
            if importance is None:
                raise TradingValidationError("fmp_calendar: invalid_importance")
            events.append(EconomicEvent(
                event_at=_utc_datetime(row.get("date"), "fmp_calendar: invalid_time"),
                title=row.get("event") or row.get("name"),
                currencies=(currency,),
                importance=importance,
            ))
        return EconomicCalendarSnapshot(
            provider="FMP",
            fetched_at=selected_now,
            coverage_start=datetime.combine(start_day, time.min, tzinfo=timezone.utc),
            coverage_end=datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=timezone.utc),
            events=tuple(sorted(events, key=lambda item: item.event_at)),
        )

    @staticmethod
    def _currency(row: Mapping[str, Any]) -> str | None:
        direct = str(row.get("currency", "")).strip().upper()
        if direct in _MAJOR_CURRENCIES:
            return direct
        return _COUNTRY_CURRENCY.get(str(row.get("country", "")).strip().casefold())

    @staticmethod
    def _importance(value: object) -> int | None:
        if type(value) is int and 1 <= value <= 3:
            return value
        return {"low": 1, "medium": 2, "high": 3}.get(str(value or "").strip().casefold())


__all__ = [
    "FmpEconomicCalendarReadOnlySource",
    "ForexFactoryEconomicCalendarReadOnlySource",
    "JsonTransport",
    "MarketDataTransportError",
    "NbpPlnReadOnlySource",
    "OandaPracticeReadOnlySource",
    "TwelveDataReadOnlySource",
]

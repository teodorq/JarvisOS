from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from app.market_data.forex_environment import ForexDataSettings, load_forex_environment
from app.market_data.forex_gateway import ForexReadOnlyDataGateway
from app.market_data.forex_sources import (
    ForexFactoryEconomicCalendarReadOnlySource,
    NbpPlnReadOnlySource,
    OandaPracticeReadOnlySource,
    TwelveDataReadOnlySource,
)
from app.market_data.http_json import MarketDataTransportError, PreparedJsonRequest
from app.market_data.mt5_demo import Mt5DemoReadOnlySource
from app.trading.forex_autopilot import ForexPaperAutopilot
from app.trading.forex_models import MAJOR_FOREX_PAIRS, major_pair
from app.trading.models import TradingValidationError


UTC = timezone.utc
NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
PRICES = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
}


class FakeForexTransport:
    def __init__(
        self,
        *,
        divergent_pair: str = "",
        event_currency: str = "",
        nbp_age_days: int = 0,
    ) -> None:
        self.calls: list[PreparedJsonRequest] = []
        self.divergent_pair = divergent_pair
        self.event_currency = event_currency
        self.nbp_age_days = nbp_age_days

    def __call__(self, request: PreparedJsonRequest) -> object:
        self.calls.append(request)
        parsed = urlsplit(request.url)
        query = parse_qs(parsed.query)
        if parsed.hostname == OandaPracticeReadOnlySource.HOST:
            if parsed.path.endswith("/pricing"):
                return {"prices": [self._oanda_price(pair) for pair in MAJOR_FOREX_PAIRS]}
            if parsed.path.endswith("/candles"):
                symbol = parsed.path.split("/")[-2]
                requested = self.assert_requested_candle(query)
                return {"candles": self._candles(symbol, requested)}
        if parsed.hostname == TwelveDataReadOnlySource.HOST:
            symbol = query["symbol"][0].replace("/", "_")
            rate = PRICES[symbol]
            if symbol == self.divergent_pair:
                rate *= Decimal("1.01")
            return {
                "symbol": symbol.replace("_", "/"),
                "rate": str(rate),
                "timestamp": int(NOW.timestamp()),
            }
        if parsed.hostname == NbpPlnReadOnlySource.HOST:
            return {
                "table": "A",
                "currency": "dolar amerykański",
                "code": "USD",
                "rates": [{
                    "no": "150/A/NBP/2026",
                    "effectiveDate": (NOW.date() - timedelta(days=self.nbp_age_days)).isoformat(),
                    "mid": 3.75,
                }],
            }
        if parsed.hostname == ForexFactoryEconomicCalendarReadOnlySource.HOST:
            currency = self.event_currency or "EUR"
            return [{
                "date": (
                    NOW if self.event_currency else NOW + timedelta(hours=12)
                ).isoformat(),
                "country": currency,
                "title": "Test economic release",
                "impact": "High" if self.event_currency else "Low",
            }]
        raise AssertionError(request.public_summary())

    @staticmethod
    def assert_requested_candle(query: dict[str, list[str]]) -> int:
        if query.get("price") != ["M"] or query.get("granularity") != ["M15"]:
            raise AssertionError(query)
        try:
            requested = int(query.get("count", [""])[0])
        except ValueError as error:
            raise AssertionError(query) from error
        if not 32 <= requested <= 500:
            raise AssertionError(query)
        return requested

    @staticmethod
    def _oanda_price(pair: object) -> dict[str, object]:
        symbol = pair.symbol
        price = PRICES[symbol]
        half = pair.pip_size / Decimal("2")
        return {
            "instrument": symbol,
            "status": "tradeable",
            "time": NOW.isoformat().replace("+00:00", "Z"),
            "bids": [{"price": str(price - half), "liquidity": 1_000_000}],
            "asks": [{"price": str(price + half), "liquidity": 1_000_000}],
        }

    @staticmethod
    def _candles(symbol: str, count: int) -> list[dict[str, object]]:
        pair = major_pair(symbol)
        price = PRICES[symbol]
        return [{
            "complete": True,
            "time": (NOW - timedelta(minutes=(count - 1 - index) * 15)).isoformat().replace("+00:00", "Z"),
            "volume": 100,
            "mid": {
                "o": str(price),
                "h": str(price + pair.pip_size),
                "l": str(price - pair.pip_size),
                "c": str(price),
            },
        } for index in range(count)]


def ready_settings() -> ForexDataSettings:
    return ForexDataSettings(
        enabled=True,
        primary_provider="OANDA_PRACTICE",
        oanda_practice_account_id="001-001-1234567-001",
        oanda_practice_token="practice-secret",
        twelve_data_api_key="twelve-secret",
        fmp_api_key="fmp-secret",
    )


def mt5_settings() -> ForexDataSettings:
    return ForexDataSettings(
        enabled=True,
        primary_provider="MT5_DEMO",
        twelve_data_api_key="twelve-secret",
        fmp_api_key="fmp-secret",
    )


class FakeMt5Module:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    TIMEFRAME_M15 = 15

    def __init__(
        self,
        *,
        trade_mode: int = 0,
        connected: bool = True,
        unready_once: bool = False,
    ) -> None:
        self.trade_mode = trade_mode
        self.connected = connected
        self.unready_once = unready_once
        self._tick_calls: dict[str, int] = {}
        self.calls: list[tuple[object, ...]] = []

    def initialize(self, *, timeout: int) -> bool:
        self.calls.append(("initialize", timeout))
        return True

    def terminal_info(self) -> object:
        self.calls.append(("terminal_info",))
        return SimpleNamespace(connected=self.connected)

    def account_info(self) -> object:
        self.calls.append(("account_info",))
        return SimpleNamespace(login=123456, trade_mode=self.trade_mode)

    def symbol_select(self, symbol: str, selected: bool) -> bool:
        self.calls.append(("symbol_select", symbol, selected))
        return True

    def symbol_info_tick(self, symbol: str) -> object:
        self.calls.append(("symbol_info_tick", symbol))
        self._tick_calls[symbol] = self._tick_calls.get(symbol, 0) + 1
        pair = next(pair for pair in MAJOR_FOREX_PAIRS if pair.symbol.replace("_", "") == symbol)
        price = PRICES[pair.symbol]
        return SimpleNamespace(
            bid=float(price - pair.pip_size / Decimal("2")),
            ask=float(price + pair.pip_size / Decimal("2")),
            time_msc=(
                0
                if self.unready_once and self._tick_calls[symbol] == 1
                else int(NOW.timestamp() * 1000)
            ),
        )

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> list[dict[str, object]]:
        self.calls.append(("copy_rates_from_pos", symbol, timeframe, start_pos, count))
        pair = next(pair for pair in MAJOR_FOREX_PAIRS if pair.symbol.replace("_", "") == symbol)
        price = PRICES[pair.symbol]
        return [{
            "time": int((NOW - timedelta(minutes=(count - index) * 15)).timestamp()),
            "open": float(price),
            "high": float(price + pair.pip_size),
            "low": float(price - pair.pip_size),
            "close": float(price),
            "tick_volume": 100,
        } for index in range(count)]

    def shutdown(self) -> None:
        self.calls.append(("shutdown",))


class RequestBoundaryTests(unittest.TestCase):
    def test_request_requires_https_exact_host_and_hides_headers(self) -> None:
        request = PreparedJsonRequest.build(
            host="api.example.test",
            path="/read-only",
            headers={"Authorization": "Bearer top-secret"},
        )
        self.assertNotIn("top-secret", repr(request))
        self.assertNotIn("top-secret", request.url)
        self.assertEqual(request.public_summary()["method"], "GET")
        with self.assertRaisesRegex(MarketDataTransportError, "unsafe_url"):
            PreparedJsonRequest(
                url="http://api.example.test/read-only",
                allowed_host="api.example.test",
            )
        with self.assertRaisesRegex(MarketDataTransportError, "unsafe_url"):
            PreparedJsonRequest(
                url="https://api.example.test:invalid/read-only",
                allowed_host="api.example.test",
            )

    def test_settings_repr_and_status_never_disclose_secrets(self) -> None:
        settings = ready_settings()
        rendered = repr(settings) + repr(ForexReadOnlyDataGateway(settings).status())
        for secret in (
            "001-001-1234567-001",
            "practice-secret",
            "twelve-secret",
            "fmp-secret",
        ):
            self.assertNotIn(secret, rendered)
        self.assertTrue(settings.readiness()["complete"])
        self.assertFalse(ForexReadOnlyDataGateway(settings).status()["live_order_surface"])

    def test_local_environment_loader_is_allowlisted_and_does_not_override(self) -> None:
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            config = Path(directory) / "config"
            config.mkdir()
            (config / "forex.env").write_text(
                "JARVIS_OS_FOREX_DATA_ENABLED=true\n"
                "JARVIS_OS_TWELVE_DATA_API_KEY=file-key\n"
                "UNREVIEWED_KEY=blocked\n",
                encoding="utf-8",
            )
            os.environ["JARVIS_OS_TWELVE_DATA_API_KEY"] = "process-key"
            loaded = load_forex_environment(directory)
            self.assertEqual(loaded, ("JARVIS_OS_FOREX_DATA_ENABLED",))
            self.assertEqual(os.environ["JARVIS_OS_TWELVE_DATA_API_KEY"], "process-key")
            self.assertNotIn("UNREVIEWED_KEY", os.environ)


class ProviderParserTests(unittest.TestCase):
    def test_mt5_demo_reads_quotes_and_only_closed_m15_bars(self) -> None:
        fake = FakeMt5Module()
        quotes, bars = Mt5DemoReadOnlySource(module=fake).fetch_market(MAJOR_FOREX_PAIRS)
        self.assertEqual(len(quotes), 7)
        self.assertEqual(len(bars), 7)
        self.assertTrue(all(len(series) == 31 for series in bars.values()))
        rate_calls = [call for call in fake.calls if call[0] == "copy_rates_from_pos"]
        self.assertTrue(all(call[2:] == (15, 1, 31) for call in rate_calls))
        self.assertEqual(fake.calls[:3], [
            ("initialize", 10_000),
            ("terminal_info",),
            ("account_info",),
        ])
        self.assertEqual(fake.calls[-1], ("shutdown",))

    def test_mt5_demo_reads_bounded_closed_m15_history(self) -> None:
        fake = FakeMt5Module()
        history = Mt5DemoReadOnlySource(module=fake).fetch_history(
            (major_pair("EUR_USD"),),
            bar_count=200,
            now=NOW,
        )

        self.assertEqual(tuple(history), ("EUR_USD",))
        self.assertEqual(len(history["EUR_USD"]), 200)
        rate_calls = [call for call in fake.calls if call[0] == "copy_rates_from_pos"]
        self.assertEqual(rate_calls, [("copy_rates_from_pos", "EURUSD", 15, 1, 200)])
        self.assertEqual(fake.calls[-1], ("shutdown",))

    def test_mt5_history_blocks_real_account_before_market_read(self) -> None:
        fake = FakeMt5Module(trade_mode=FakeMt5Module.ACCOUNT_TRADE_MODE_REAL)
        with self.assertRaisesRegex(TradingValidationError, "non_demo_account_blocked"):
            Mt5DemoReadOnlySource(module=fake).fetch_history(
                (major_pair("EUR_USD"),),
                bar_count=200,
                now=NOW,
            )
        self.assertFalse(any(call[0] == "copy_rates_from_pos" for call in fake.calls))
        self.assertEqual(fake.calls[-1], ("shutdown",))

    def test_mt5_blocks_real_account_before_any_market_read(self) -> None:
        fake = FakeMt5Module(trade_mode=FakeMt5Module.ACCOUNT_TRADE_MODE_REAL)
        with self.assertRaisesRegex(TradingValidationError, "non_demo_account_blocked"):
            Mt5DemoReadOnlySource(module=fake).fetch_market((major_pair("EUR_USD"),))
        self.assertFalse(any(call[0] == "symbol_info_tick" for call in fake.calls))
        self.assertFalse(any(call[0] == "copy_rates_from_pos" for call in fake.calls))
        self.assertEqual(fake.calls[-1], ("shutdown",))

    def test_mt5_blocks_disconnected_terminal_and_always_shuts_down(self) -> None:
        fake = FakeMt5Module(connected=False)
        with self.assertRaisesRegex(TradingValidationError, "terminal_disconnected"):
            Mt5DemoReadOnlySource(module=fake).fetch_market((major_pair("EUR_USD"),))
        self.assertEqual(fake.calls[-1], ("shutdown",))

    def test_mt5_waits_for_newly_selected_symbols_to_synchronize(self) -> None:
        fake = FakeMt5Module(unready_once=True)
        with patch("app.market_data.mt5_demo.time.sleep") as sleep:
            quotes, bars = Mt5DemoReadOnlySource(module=fake).fetch_market(
                (major_pair("EUR_USD"),)
            )
        self.assertEqual(tuple(quotes), ("EUR_USD",))
        self.assertEqual(len(bars["EUR_USD"]), 31)
        sleep.assert_called_once_with(0.2)

    def test_oanda_practice_quotes_and_complete_candles(self) -> None:
        fake = FakeForexTransport()
        source = OandaPracticeReadOnlySource(
            account_id=ready_settings().oanda_practice_account_id,
            token="secret",
            transport=fake,
        )
        pair = major_pair("EUR_USD")
        quote = source.fetch_quotes((pair,))[pair.symbol]
        bars = source.fetch_bars(pair)
        self.assertEqual(quote.midpoint, PRICES[pair.symbol])
        self.assertEqual(len(bars), 31)
        self.assertLess(bars[0].timestamp, bars[-1].timestamp)
        self.assertTrue(all(call.public_summary()["method"] == "GET" for call in fake.calls))

    def test_twelve_data_nbp_and_forex_factory_parsers(self) -> None:
        fake = FakeForexTransport(event_currency="EUR")
        pair = major_pair("EUR_USD")
        independent = TwelveDataReadOnlySource("key", fake).fetch_rates((pair,))
        reference = NbpPlnReadOnlySource(fake).fetch_usd_pln(fetched_at=NOW)
        calendar = ForexFactoryEconomicCalendarReadOnlySource(fake).fetch_calendar(now=NOW)
        self.assertEqual(independent[pair.symbol].midpoint, PRICES[pair.symbol])
        self.assertEqual(reference.midpoint_pln, Decimal("3.75"))
        self.assertEqual(calendar.events[0].currencies, ("EUR",))
        self.assertEqual(calendar.events[0].importance, 3)
        self.assertEqual(calendar.provider, "FOREX_FACTORY")

    def test_forex_factory_calendar_fails_closed_on_empty_feed(self) -> None:
        source = ForexFactoryEconomicCalendarReadOnlySource(lambda request: [])
        with self.assertRaisesRegex(TradingValidationError, "invalid_response"):
            source.fetch_calendar(now=NOW)

    def test_oanda_rejects_non_practice_credentials_shape(self) -> None:
        with self.assertRaisesRegex(TradingValidationError, "invalid_account_id"):
            OandaPracticeReadOnlySource(account_id="https://live.example", token="x")


class ForexDataGatewayTests(unittest.TestCase):
    def test_mt5_demo_can_be_selected_as_primary_source(self) -> None:
        fake_mt5 = FakeMt5Module()
        bundle = ForexReadOnlyDataGateway(
            mt5_settings(),
            transport=FakeForexTransport(),
            mt5_module=fake_mt5,
        ).collect(now=NOW)
        self.assertEqual(bundle.diagnostics["primary_provider"], "MT5_DEMO")
        self.assertEqual(len(bundle.quotes), 7)
        self.assertTrue(all(context.independent_source_count == 2 for context in bundle.contexts.values()))

    def test_complete_bundle_feeds_existing_paper_autopilot(self) -> None:
        fake = FakeForexTransport()
        bundle = ForexReadOnlyDataGateway(ready_settings(), transport=fake).collect(now=NOW)
        self.assertEqual(len(bundle.quotes), 7)
        self.assertEqual(len(bundle.bars), 7)
        self.assertTrue(all(len(series) == 211 for series in bundle.bars.values()))
        self.assertEqual(len(bundle.conversion_quotes), 1)
        self.assertTrue(all(context.independent_source_count == 2 for context in bundle.contexts.values()))
        self.assertTrue(all(not context.opening_blocks for context in bundle.contexts.values()))
        with TemporaryDirectory() as directory:
            result = ForexPaperAutopilot(directory).run_cycle(
                quotes=bundle.quotes,
                bars=bundle.bars,
                contexts=bundle.contexts,
                conversion_quotes=bundle.conversion_quotes,
                cycle_id="read-only-data-cycle",
                now=NOW,
            )
        self.assertEqual(result["status"], "CYCLE_COMPLETED")
        self.assertFalse(result["live_orders_sent"])

    def test_divergent_second_source_blocks_only_affected_pair(self) -> None:
        bundle = ForexReadOnlyDataGateway(
            ready_settings(), transport=FakeForexTransport(divergent_pair="EUR_USD")
        ).collect(now=NOW)
        self.assertIn("SECOND_SOURCE_UNAVAILABLE", bundle.contexts["EUR_USD"].opening_blocks)
        self.assertEqual(bundle.contexts["GBP_USD"].independent_source_count, 2)

    def test_high_impact_event_blocks_affected_currency_only(self) -> None:
        bundle = ForexReadOnlyDataGateway(
            ready_settings(), transport=FakeForexTransport(event_currency="EUR")
        ).collect(now=NOW)
        self.assertIn("HIGH_IMPACT_EVENT_WINDOW", bundle.contexts["EUR_USD"].opening_blocks)
        self.assertNotIn("HIGH_IMPACT_EVENT_WINDOW", bundle.contexts["GBP_USD"].opening_blocks)

    def test_stale_nbp_reference_removes_conversion_and_blocks_opening(self) -> None:
        bundle = ForexReadOnlyDataGateway(
            ready_settings(), transport=FakeForexTransport(nbp_age_days=5)
        ).collect(now=NOW)
        self.assertEqual(bundle.conversion_quotes, ())
        self.assertTrue(all(
            "PLN_CONVERSION_UNAVAILABLE" in context.opening_blocks
            for context in bundle.contexts.values()
        ))

    def test_incomplete_configuration_and_closed_market_fail_closed(self) -> None:
        with self.assertRaisesRegex(TradingValidationError, "configuration_incomplete"):
            ForexReadOnlyDataGateway(ForexDataSettings(enabled=False)).collect(now=NOW)
        saturday = datetime(2026, 8, 15, 12, tzinfo=UTC)
        self.assertFalse(ForexReadOnlyDataGateway.market_open(saturday))
        self.assertTrue(ForexReadOnlyDataGateway.market_open(NOW))

    def test_sources_contain_no_live_oanda_or_order_route(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app" / "market_data" / "forex_sources.py"
        ).read_text(encoding="utf-8").casefold()
        self.assertNotIn("api-fxtrade.oanda.com", source)
        self.assertNotIn("/orders", source)
        self.assertNotIn("post(", source)
        market_data_root = (
            Path(__file__).resolve().parents[1] / "app" / "market_data"
        )
        mt5_source = "\n".join(
            (market_data_root / name).read_text(encoding="utf-8").casefold()
            for name in ("mt5_demo.py", "mt5_history.py")
        )
        self.assertNotIn("order_send", mt5_source)
        self.assertNotIn("positions_get", mt5_source)
        self.assertNotIn("history_deals_get", mt5_source)


if __name__ == "__main__":
    unittest.main()

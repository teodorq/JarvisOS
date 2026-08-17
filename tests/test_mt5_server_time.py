from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest

from app.market_data.mt5_demo import Mt5DemoReadOnlySource
from app.trading.forex_models import major_pair
from app.trading.models import TradingValidationError


UTC = timezone.utc
NOW = datetime(2026, 8, 17, 16, 30, tzinfo=UTC)
PAIR = major_pair("EUR_USD")


class OffsetMt5Module:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M15 = 15

    def __init__(self, *, server: str, offset_seconds: int) -> None:
        self.server = server
        self.offset_seconds = offset_seconds
        self.shutdown_called = False

    def initialize(self, *, timeout: int) -> bool:
        return timeout == 10_000

    @staticmethod
    def terminal_info() -> object:
        return SimpleNamespace(connected=True)

    def account_info(self) -> object:
        return SimpleNamespace(
            login=123456,
            trade_mode=self.ACCOUNT_TRADE_MODE_DEMO,
            server=self.server,
        )

    @staticmethod
    def symbol_select(symbol: str, selected: bool) -> bool:
        return symbol == "EURUSD.pro" and selected

    def symbol_info_tick(self, symbol: str) -> object:
        timestamp = NOW + timedelta(seconds=self.offset_seconds)
        return SimpleNamespace(
            bid=1.09995,
            ask=1.10005,
            time_msc=int(timestamp.timestamp() * 1000),
        )

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> list[dict[str, object]]:
        return [{
            "time": int((
                NOW
                + timedelta(seconds=self.offset_seconds)
                - timedelta(minutes=(count - index) * 15)
            ).timestamp()),
            "open": 1.1,
            "high": 1.1001,
            "low": 1.0999,
            "close": 1.1,
            "tick_volume": Decimal("100"),
        } for index in range(count)]

    def shutdown(self) -> None:
        self.shutdown_called = True


class Mt5ServerTimeTests(unittest.TestCase):
    def test_oanda_tms_whole_hour_server_offset_is_normalized(self) -> None:
        fake = OffsetMt5Module(
            server="OANDATMS-MT5",
            offset_seconds=2 * 3600,
        )
        quotes, bars = Mt5DemoReadOnlySource(
            symbol_suffix=".pro",
            module=fake,
        ).fetch_market((PAIR,), now=NOW)

        self.assertEqual(quotes[PAIR.symbol].timestamp, NOW)
        self.assertEqual(bars[PAIR.symbol][-1].timestamp, NOW - timedelta(minutes=15))
        self.assertTrue(fake.shutdown_called)

    def test_utc_server_time_is_not_modified(self) -> None:
        fake = OffsetMt5Module(server="OTHER-DEMO", offset_seconds=0)
        quotes, _bars = Mt5DemoReadOnlySource(
            symbol_suffix=".pro",
            module=fake,
        ).fetch_market((PAIR,), now=NOW)
        self.assertEqual(quotes[PAIR.symbol].timestamp, NOW)

    def test_offset_is_rejected_for_an_unapproved_server(self) -> None:
        fake = OffsetMt5Module(server="OTHER-DEMO", offset_seconds=7200)
        with self.assertRaisesRegex(
            TradingValidationError,
            "unsupported_server_time_offset",
        ):
            Mt5DemoReadOnlySource(
                symbol_suffix=".pro",
                module=fake,
            ).fetch_market((PAIR,), now=NOW)
        self.assertTrue(fake.shutdown_called)

    def test_non_hour_offset_is_rejected_even_for_oanda_tms(self) -> None:
        fake = OffsetMt5Module(
            server="OANDATMS-MT5",
            offset_seconds=30 * 60,
        )
        with self.assertRaisesRegex(
            TradingValidationError,
            "unsupported_server_time_offset",
        ):
            Mt5DemoReadOnlySource(
                symbol_suffix=".pro",
                module=fake,
            ).fetch_market((PAIR,), now=NOW)

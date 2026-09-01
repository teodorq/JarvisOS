from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.market_data.forex_environment import ForexDataSettings
from app.market_data.forex_paper_protection import ForexPaperProtectionRuntime
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_risk import ForexRateBook


UTC = timezone.utc
NOW = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
EUR_USD = MAJOR_FOREX_PAIRS[0]


def _quote(pair, bid: object, ask: object, now: datetime) -> ForexQuote:
    return ForexQuote.create(pair=pair, bid=bid, ask=ask, timestamp=now)


def _bar(pair, price: object, now: datetime) -> ForexBar:
    value = Decimal(str(price))
    return ForexBar.create(
        pair=pair,
        timestamp=now - timedelta(minutes=15),
        open=value,
        high=value + pair.pip_size,
        low=value - pair.pip_size,
        close=value,
        tick_volume="100",
    )


class _Source:
    def __init__(self, *, bid: str, ask: str) -> None:
        self.bid = bid
        self.ask = ask
        self.calls = 0

    def fetch_market(self, pairs, *, bar_count=31, now=None):
        self.calls += 1
        selected_now = now or NOW
        quotes = {}
        bars = {}
        for pair in tuple(pairs):
            if pair.symbol == EUR_USD.symbol:
                quote = _quote(pair, self.bid, self.ask, selected_now)
                price = self.bid
            else:
                quote = _quote(pair, "3.999", "4.001", selected_now)
                price = "4.000"
            quotes[pair.symbol] = quote
            bars[pair.symbol] = (_bar(pair, price, selected_now),)
        return quotes, bars


def _settings(*, enabled: bool = True, provider: str = "MT5_DEMO"):
    return ForexDataSettings(
        enabled=True,
        paper_autopilot_enabled=enabled,
        primary_provider=provider,
    )


def _opened_executor(root: Path) -> ForexPaperExecutionEngine:
    executor = ForexPaperExecutionEngine(root)
    quotes = {
        EUR_USD.symbol: _quote(EUR_USD, "1.1000", "1.1002", NOW),
        USD_PLN_CONVERSION_PAIR.symbol: _quote(
            USD_PLN_CONVERSION_PAIR, "3.999", "4.001", NOW
        ),
    }
    rates = ForexRateBook(quotes.values(), now=NOW)
    plan = {
        "mode": "FOREX_PAPER_ONLY",
        "live_orders_sent": False,
        "sample_contract": executor.sample_contract,
        "instructions": [{
            "action": "OPEN_LONG",
            "pair": EUR_USD.symbol,
            "units": "100",
            "stop_loss": "1.0992",
            "take_profit": "1.1022",
        }],
    }
    result = executor.apply_plan(
        plan,
        quotes=quotes,
        rates=rates,
        cycle_id="paper-protection-open",
        now=NOW,
    )
    assert result["status"] == "APPLIED"
    return executor


def test_guard_closes_stop_loss_using_local_mt5_data_only() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        source = _Source(bid="1.0991", ask="1.0993")
        result = ForexPaperProtectionRuntime(
            root,
            settings=_settings(),
            source=source,
            executor=executor,
        ).run_once(
            cycle_id="paper-protection-stop-0001",
            now=NOW + timedelta(minutes=1),
        )

        assert result["status"] == "PAPER_PROTECTION_APPLIED"
        assert source.calls == 1
        fills = [item["fill"] for item in result["paper"]["execution"]["executions"]]
        assert [fill["action"] for fill in fills] == ["CLOSE_LONG"]
        assert fills[0]["reason_codes"] == ["STOP_LOSS_TRIGGERED"]
        assert result["paper"]["account"]["position_count"] == 0
        assert result["new_entries_allowed"] is False
        assert result["external_market_data_requests"] is False
        assert result["broker_orders_sent"] is False
        assert result["live_orders_sent"] is False
        assert result["real_money_access"] is False


def test_guard_does_not_read_market_without_an_open_position() -> None:
    with TemporaryDirectory() as temporary:
        source = _Source(bid="1.0991", ask="1.0993")
        result = ForexPaperProtectionRuntime(
            temporary,
            settings=_settings(),
            source=source,
        ).run_once(cycle_id="paper-protection-empty", now=NOW)

        assert result["status"] == "NO_OPEN_POSITIONS"
        assert source.calls == 0
        assert result["new_entries_allowed"] is False


def test_guard_keeps_position_when_no_stop_or_target_is_hit() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        result = ForexPaperProtectionRuntime(
            root,
            settings=_settings(),
            source=_Source(bid="1.1005", ask="1.1007"),
            executor=executor,
        ).run_once(
            cycle_id="paper-protection-watch",
            now=NOW + timedelta(minutes=1),
        )

        assert result["status"] == "NO_PROTECTION_TRIGGER"
        assert result["paper"]["account"]["position_count"] == 1
        assert result["paper"]["execution"]["executions"] == []


def test_guard_blocks_configuration_before_any_market_read() -> None:
    with TemporaryDirectory() as temporary:
        source = _Source(bid="1.0991", ask="1.0993")
        disabled = ForexPaperProtectionRuntime(
            temporary,
            settings=_settings(enabled=False),
            source=source,
        ).run_once(cycle_id="paper-protection-disabled", now=NOW)
        wrong_provider = ForexPaperProtectionRuntime(
            temporary,
            settings=_settings(provider="OANDA_PRACTICE"),
            source=source,
        ).run_once(cycle_id="paper-protection-provider", now=NOW)

        assert disabled["status"] == "PAPER_PROTECTION_BLOCKED"
        assert disabled["reason"] == "PAPER_AUTOPILOT_NOT_ENABLED"
        assert wrong_provider["reason"] == "MT5_DEMO_PRIMARY_REQUIRED"
        assert disabled["market_data_source"] == "LOCAL_MT5_DEMO"
        assert disabled["external_market_data_requests"] is False
        assert disabled["new_entries_allowed"] is False
        assert disabled["network_access"] is False
        assert source.calls == 0

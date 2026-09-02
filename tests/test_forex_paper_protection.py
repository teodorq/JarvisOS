from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.market_data.forex_environment import ForexDataSettings
from app.market_data.forex_paper_protection import ForexPaperProtectionRuntime
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_models import (
    ForexBar,
    ForexPosition,
    ForexQuote,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_risk import ForexRateBook
from app.trading.models import TradingValidationError


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


def _history_bar(
    pair,
    *,
    timestamp: datetime,
    open: object,
    high: object,
    low: object,
    close: object,
) -> ForexBar:
    return ForexBar.create(
        pair=pair,
        timestamp=timestamp,
        open=open,
        high=high,
        low=low,
        close=close,
        tick_volume="100",
    )


class _Source:
    def __init__(
        self,
        *,
        bid: str,
        ask: str,
        history: tuple[ForexBar, ...] = (),
    ) -> None:
        self.bid = bid
        self.ask = ask
        self.history = history
        self.calls = 0
        self.last_bar_count = 0
        self.last_timeframe_minutes = 0

    def fetch_market(
        self,
        pairs,
        *,
        bar_count=31,
        timeframe_minutes=15,
        now=None,
    ):
        self.calls += 1
        self.last_bar_count = bar_count
        self.last_timeframe_minutes = timeframe_minutes
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
            custom = {
                bar.timestamp: bar
                for bar in self.history
                if pair.symbol == EUR_USD.symbol
            }
            neutral = "1.1000" if pair.symbol == EUR_USD.symbol else price
            first_at = selected_now - timedelta(minutes=bar_count)
            series = []
            for index in range(bar_count):
                timestamp = first_at + timedelta(minutes=index)
                series.append(custom.get(timestamp) or _history_bar(
                    pair,
                    timestamp=timestamp,
                    open=neutral,
                    high=Decimal(str(neutral)) + pair.pip_size,
                    low=Decimal(str(neutral)) - pair.pip_size,
                    close=neutral,
                ))
            bars[pair.symbol] = tuple(series)
        return quotes, bars


class _IncompleteSource(_Source):
    def fetch_market(self, pairs, **kwargs):
        quotes, bars = super().fetch_market(pairs, **kwargs)
        bars[EUR_USD.symbol] = bars[EUR_USD.symbol][:-1]
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
        assert disabled["observed_at"] == NOW.isoformat()
        assert disabled["reason"] == "PAPER_AUTOPILOT_NOT_ENABLED"
        assert wrong_provider["reason"] == "MT5_DEMO_PRIMARY_REQUIRED"
        assert disabled["market_data_source"] == "LOCAL_MT5_DEMO"
        assert disabled["external_market_data_requests"] is False
        assert disabled["new_entries_allowed"] is False
        assert disabled["network_access"] is False
        assert source.calls == 0


def test_recovery_replay_closes_a_returned_target_at_the_target_level() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        source = _Source(
            bid="1.1005",
            ask="1.1007",
            history=(_history_bar(
                EUR_USD,
                timestamp=NOW + timedelta(minutes=2),
                open="1.1005",
                high="1.1023",
                low="1.1004",
                close="1.1008",
            ),),
        )

        result = ForexPaperProtectionRuntime(
            root,
            settings=_settings(),
            source=source,
            executor=executor,
        ).run_once(
            cycle_id="paper-protection-recovery-target",
            now=NOW + timedelta(minutes=20),
            recovery_since=NOW + timedelta(minutes=1),
        )

        fill = result["paper"]["execution"]["executions"][0]["fill"]
        replay = result["recovery_replay"]
        assert result["status"] == "PAPER_PROTECTION_APPLIED"
        assert fill["exit_price"] == "1.102200"
        assert fill["reason_codes"] == [
            "TAKE_PROFIT_TRIGGERED",
            "RECOVERY_M1_REPLAY",
        ]
        assert fill["protection_replay"] == {
            "timeframe": "M1_CLOSED_BARS",
            "bar_timestamp": (NOW + timedelta(minutes=2)).isoformat(),
            "trigger": "TAKE_PROFIT_TRIGGERED",
            "ambiguous_bar": False,
            "spread_policy": "CURRENT_MT5_SPREAD",
            "paper_only": True,
        }
        assert replay["status"] == "RECOVERY_REPLAY_APPLIED"
        assert replay["historical_exit_count"] == 1
        assert replay["ambiguous_bar_count"] == 0
        assert replay["evidence"][0]["trigger"] == "TAKE_PROFIT_TRIGGERED"
        assert source.last_timeframe_minutes == 1
        assert source.last_bar_count == 21
        assert replay["requested_bar_count"] == len(source.history) + 20
        assert result["broker_orders_sent"] is False
        assert result["live_orders_sent"] is False


def test_recovery_replay_chooses_stop_on_an_ambiguous_minute() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        source = _Source(
            bid="1.1005",
            ask="1.1007",
            history=(_history_bar(
                EUR_USD,
                timestamp=NOW + timedelta(minutes=2),
                open="1.1005",
                high="1.1023",
                low="1.0991",
                close="1.1008",
            ),),
        )

        result = ForexPaperProtectionRuntime(
            root,
            settings=_settings(),
            source=source,
            executor=executor,
        ).run_once(
            cycle_id="paper-protection-recovery-ambiguous",
            now=NOW + timedelta(minutes=20),
            recovery_since=NOW + timedelta(minutes=1),
        )

        fill = result["paper"]["execution"]["executions"][0]["fill"]
        replay = result["recovery_replay"]
        assert fill["exit_price"] == "1.099200"
        assert fill["reason_codes"] == [
            "STOP_LOSS_TRIGGERED",
            "STOP_LOSS_AMBIGUOUS_BAR",
            "RECOVERY_M1_REPLAY",
        ]
        assert fill["protection_replay"]["ambiguous_bar"] is True
        assert (
            fill["protection_replay"]["trigger"]
            == "STOP_LOSS_AMBIGUOUS_BAR"
        )
        assert replay["ambiguous_bar_count"] == 1
        assert replay["ambiguous_bar_policy"] == "STOP_FIRST_CONSERVATIVE"


def test_recovery_replay_uses_worse_open_price_for_a_stop_gap() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        source = _Source(
            bid="1.1005",
            ask="1.1007",
            history=(_history_bar(
                EUR_USD,
                timestamp=NOW + timedelta(minutes=2),
                open="1.0988",
                high="1.0990",
                low="1.0985",
                close="1.0989",
            ),),
        )

        result = ForexPaperProtectionRuntime(
            root,
            settings=_settings(),
            source=source,
            executor=executor,
        ).run_once(
            cycle_id="paper-protection-recovery-gap",
            now=NOW + timedelta(minutes=20),
            recovery_since=NOW + timedelta(minutes=1),
        )

        fill = result["paper"]["execution"]["executions"][0]["fill"]
        assert fill["exit_price"] == "1.098800"
        assert fill["reason_codes"] == [
            "STOP_LOSS_TRIGGERED",
            "STOP_LOSS_GAP",
            "RECOVERY_M1_REPLAY",
        ]


def test_recovery_replay_blocks_an_unbounded_history_request() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        source = _Source(bid="1.1005", ask="1.1007")

        result = ForexPaperProtectionRuntime(
            root,
            settings=_settings(),
            source=source,
            executor=executor,
        ).run_once(
            cycle_id="paper-protection-recovery-too-long",
            now=NOW + timedelta(days=8),
            recovery_since=NOW,
        )

        assert result["status"] == "PAPER_PROTECTION_BLOCKED"
        assert result["reason"] == "forex_protection: recovery_window_exceeded"
        assert result["new_entries_allowed"] is False
        assert result["real_money_access"] is False
        assert source.calls == 0


def test_recovery_replay_blocks_an_incomplete_m1_window() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        source = _IncompleteSource(bid="1.1005", ask="1.1007")

        result = ForexPaperProtectionRuntime(
            root,
            settings=_settings(),
            source=source,
            executor=executor,
        ).run_once(
            cycle_id="paper-protection-recovery-incomplete",
            now=NOW + timedelta(minutes=20),
            recovery_since=NOW + timedelta(minutes=1),
        )

        assert result["status"] == "PAPER_PROTECTION_BLOCKED"
        assert result["reason"] == "MT5_PROTECTION_HISTORY_INCOMPLETE"
        assert result["new_entries_allowed"] is False
        assert source.calls == 1
        assert tuple(executor.positions()) == (EUR_USD.symbol,)


def test_executor_rejects_tampered_recovery_evidence_atomically() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        executor = _opened_executor(root)
        observed_at = NOW + timedelta(minutes=20)
        quotes = {
            EUR_USD.symbol: _quote(EUR_USD, "1.0991", "1.0993", observed_at),
            USD_PLN_CONVERSION_PAIR.symbol: _quote(
                USD_PLN_CONVERSION_PAIR,
                "3.999",
                "4.001",
                observed_at,
            ),
        }
        rates = ForexRateBook(quotes.values(), now=observed_at)
        plan = {
            "mode": "FOREX_PAPER_ONLY",
            "live_orders_sent": False,
            "instructions": [{
                "action": "CLOSE_POSITION",
                "pair": EUR_USD.symbol,
                "reason_codes": ["STOP_LOSS_TRIGGERED", "RECOVERY_M1_REPLAY"],
                "protection_replay": {
                    "timeframe": "M1_CLOSED_BARS",
                    "bar_timestamp": (NOW + timedelta(minutes=2)).isoformat(),
                    "trigger": "STOP_LOSS_TRIGGERED",
                    "ambiguous_bar": False,
                    "spread_policy": "CURRENT_MT5_SPREAD",
                },
            }],
        }

        with pytest.raises(
            TradingValidationError,
            match="invalid_protection_replay",
        ):
            executor.apply_plan(
                plan,
                quotes=quotes,
                rates=rates,
                cycle_id="paper-protection-tampered-replay",
                now=observed_at,
            )

        assert tuple(executor.positions()) == (EUR_USD.symbol,)


def test_recovery_replay_ignores_the_partial_minute_before_position_open() -> None:
    position = ForexPosition(
        pair=EUR_USD,
        side="LONG",
        units=Decimal("100"),
        entry_price=Decimal("1.1002"),
        current_price=Decimal("1.1002"),
        stop_loss=Decimal("1.0992"),
        take_profit=Decimal("1.1022"),
        opened_at=NOW + timedelta(seconds=30),
    )
    quote = _quote(
        EUR_USD,
        "1.1005",
        "1.1007",
        NOW + timedelta(minutes=2),
    )
    partial = _history_bar(
        EUR_USD,
        timestamp=NOW,
        open="1.1005",
        high="1.1023",
        low="1.0991",
        close="1.1008",
    )

    trigger, examined = ForexPaperProtectionRuntime._find_recovery_exit(
        position=position,
        quote=quote,
        bars=(partial,),
        start=position.opened_at,
        now=NOW + timedelta(minutes=2),
    )

    assert trigger is None
    assert examined == 0

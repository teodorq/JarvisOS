from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.market_data.forex_environment import ForexDataSettings
from app.market_data.forex_models import ForexDataBundle
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_observation import ForexObservationJournal
from app.market_data.forex_paper_runtime import ForexDemoPaperRuntime


UTC = timezone.utc
NOW = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
BASE = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
}


def _bundle(
    now: datetime,
    *,
    eur_direction: str = "UP",
    blocked_pair: str = "",
) -> ForexDataBundle:
    quotes = {}
    bars = {}
    contexts = {}
    for pair in MAJOR_FOREX_PAIRS:
        prices = [BASE[pair.symbol]] * 31
        if pair.symbol == "EUR_USD" and eur_direction == "UP":
            prices[-1] += pair.pip_size * Decimal("20")
        elif pair.symbol == "EUR_USD" and eur_direction == "DOWN":
            prices[-1] -= pair.pip_size * Decimal("20")
        bars[pair.symbol] = tuple(
            ForexBar.create(
                pair=pair,
                timestamp=now - timedelta(minutes=15 * (30 - index)),
                open=price,
                high=price + pair.pip_size,
                low=price - pair.pip_size,
                close=price,
                tick_volume=100,
            )
            for index, price in enumerate(prices)
        )
        half = pair.pip_size / Decimal("2")
        quotes[pair.symbol] = ForexQuote.create(
            pair=pair,
            bid=prices[-1] - half,
            ask=prices[-1] + half,
            timestamp=now,
        )
        contexts[pair.symbol] = ForexSafetyContext(
            observed_at=now,
            market_open=True,
            calendar_ready=True,
            high_impact_event_blocked=pair.symbol == blocked_pair,
            conversion_to_pln_ready=True,
            independent_source_count=2,
        )
    conversion = ForexQuote.create(
        pair=USD_PLN_CONVERSION_PAIR,
        bid="3.999",
        ask="4.001",
        timestamp=now,
    )
    return ForexDataBundle(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=(conversion,),
        diagnostics={
            "primary_provider": "MT5_DEMO",
            "primary_pair_count": 7,
            "primary_closed_bar_count": 31,
            "cross_checked_pairs": tuple(quotes),
            "calendar_ready": True,
            "high_impact_event_count": 0,
            "nbp_effective_date": now.date().isoformat(),
            "pln_conversion_ready": True,
        },
    )


class FakeGateway:
    def __init__(
        self,
        *,
        fully_cross_checked: bool = True,
        eur_direction: str = "UP",
        blocked_pair: str = "",
    ) -> None:
        self.calls = 0
        self.fully_cross_checked = fully_cross_checked
        self.eur_direction = eur_direction
        self.blocked_pair = blocked_pair

    def collect(self, *, now: datetime) -> ForexDataBundle:
        self.calls += 1
        selected = _bundle(
            now,
            eur_direction=self.eur_direction,
            blocked_pair=self.blocked_pair,
        )
        if self.fully_cross_checked:
            return selected
        contexts = dict(selected.contexts)
        pair = MAJOR_FOREX_PAIRS[0]
        contexts[pair.symbol] = ForexSafetyContext(
            observed_at=now,
            market_open=True,
            calendar_ready=True,
            high_impact_event_blocked=False,
            conversion_to_pln_ready=True,
            independent_source_count=1,
        )
        return ForexDataBundle(
            quotes=selected.quotes,
            bars=selected.bars,
            contexts=contexts,
            conversion_quotes=selected.conversion_quotes,
            diagnostics={
                **selected.diagnostics,
                "cross_checked_pairs": tuple(selected.quotes)[1:],
            },
        )


def _ready_journal(root: Path) -> ForexObservationJournal:
    journal = ForexObservationJournal(root)
    for index in range(20):
        observed = NOW - timedelta(days=index % 3, minutes=index + 1)
        journal.record({
            "status": "OBSERVATION_RECORDED",
            "mode": "FOREX_OBSERVATION_ONLY",
            "observation_id": f"paper-runtime-evidence-{index:04d}",
            "observed_at": observed.isoformat(),
            "market_open": True,
            "fully_cross_checked": True,
            "opening_blocks": [],
            "assessments": [
                {"pair": pair.symbol, "action": "WATCH"}
                for pair in MAJOR_FOREX_PAIRS
            ],
            "proposed_plan": {"instructions": []},
            "execution": {"status": "NOT_EXECUTED"},
            "positions_unchanged": True,
            "order_network_access": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        })
    return journal


class ForexPaperRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def settings(self, *, enabled: bool = True, provider: str = "MT5_DEMO"):
        return ForexDataSettings(
            enabled=True,
            paper_autopilot_enabled=enabled,
            primary_provider=provider,
        )

    def test_disabled_runtime_does_not_read_market_or_modify_ledger(self) -> None:
        gateway = FakeGateway()
        result = ForexDemoPaperRuntime(
            self.root,
            settings=self.settings(enabled=False),
            gateway=gateway,  # type: ignore[arg-type]
        ).run_once(cycle_id="disabled-cycle", now=NOW)

        self.assertEqual(result["status"], "PAPER_CYCLE_BLOCKED")
        self.assertEqual(result["reason"], "PAPER_AUTOPILOT_NOT_ENABLED")
        self.assertEqual(gateway.calls, 0)
        self.assertFalse((self.root / "data/trading/forex_paper_ledger.json").exists())

    def test_non_mt5_primary_is_blocked_before_market_read(self) -> None:
        gateway = FakeGateway()
        result = ForexDemoPaperRuntime(
            self.root,
            settings=self.settings(provider="OANDA_PRACTICE"),
            gateway=gateway,  # type: ignore[arg-type]
        ).run_once(cycle_id="wrong-provider", now=NOW)

        self.assertEqual(result["reason"], "MT5_DEMO_PRIMARY_REQUIRED")
        self.assertEqual(gateway.calls, 0)

    def test_ready_runtime_observes_once_and_opens_local_paper_only(self) -> None:
        gateway = FakeGateway()
        runtime = ForexDemoPaperRuntime(
            self.root,
            settings=self.settings(),
            gateway=gateway,  # type: ignore[arg-type]
            journal=_ready_journal(self.root),
        )

        result = runtime.run_once(cycle_id="enabled-cycle", now=NOW)

        self.assertEqual(result["status"], "PAPER_CYCLE_COMPLETED")
        self.assertEqual(gateway.calls, 1)
        self.assertEqual(result["paper"]["execution"]["status"], "APPLIED")
        self.assertEqual(result["paper"]["account"]["position_count"], 1)
        self.assertTrue(result["unvalidated_strategy_demo_override"])
        self.assertFalse(result["broker_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertFalse(result["real_money_access"])

    def test_current_incomplete_cross_check_blocks_before_paper_execution(self) -> None:
        gateway = FakeGateway(fully_cross_checked=False)
        runtime = ForexDemoPaperRuntime(
            self.root,
            settings=self.settings(),
            gateway=gateway,  # type: ignore[arg-type]
            journal=_ready_journal(self.root),
        )

        result = runtime.run_once(cycle_id="incomplete-cycle", now=NOW)

        self.assertEqual(result["status"], "PAPER_CYCLE_BLOCKED")
        self.assertEqual(result["reason"], "CURRENT_OBSERVATION_BLOCKED")
        self.assertFalse(
            (self.root / "data/trading/forex_paper_ledger.json").exists()
        )
        self.assertFalse(result["broker_orders_sent"])
        self.assertFalse(result["live_orders_sent"])

    def test_unrelated_event_block_allows_verified_close_only_cycle(self) -> None:
        journal = _ready_journal(self.root)
        opened = ForexDemoPaperRuntime(
            self.root,
            settings=self.settings(),
            gateway=FakeGateway(),  # type: ignore[arg-type]
            journal=journal,
        ).run_once(cycle_id="close-only-open", now=NOW)
        self.assertEqual(opened["paper"]["account"]["position_count"], 1)

        closed = ForexDemoPaperRuntime(
            self.root,
            settings=self.settings(),
            gateway=FakeGateway(
                eur_direction="DOWN",
                blocked_pair="GBP_USD",
            ),  # type: ignore[arg-type]
            journal=journal,
        ).run_once(
            cycle_id="close-only-exit",
            now=NOW + timedelta(minutes=15),
        )

        self.assertEqual(closed["status"], "PAPER_CYCLE_COMPLETED")
        self.assertFalse(closed["paper"]["new_entries_allowed"])
        fills = [
            item["fill"]["action"]
            for item in closed["paper"]["execution"]["executions"]
        ]
        self.assertEqual(fills, ["CLOSE_LONG"])
        self.assertEqual(closed["paper"]["account"]["position_count"], 0)
        self.assertFalse(closed["broker_orders_sent"])
        self.assertFalse(closed["live_orders_sent"])

    def test_unrelated_event_block_allows_scoped_ready_entry(self) -> None:
        result = ForexDemoPaperRuntime(
            self.root,
            settings=self.settings(),
            gateway=FakeGateway(blocked_pair="GBP_USD"),  # type: ignore[arg-type]
            journal=_ready_journal(self.root),
        ).run_once(cycle_id="scoped-entry", now=NOW)

        self.assertEqual(result["status"], "PAPER_CYCLE_COMPLETED")
        self.assertTrue(result["paper"]["new_entries_allowed"])
        fills = [
            item["fill"]
            for item in result["paper"]["execution"]["executions"]
        ]
        self.assertEqual([item["action"] for item in fills], ["OPEN_LONG"])
        self.assertEqual([item["pair"] for item in fills], ["EUR_USD"])
        self.assertTrue(all(item["pair"] != "GBP_USD" for item in fills))
        self.assertFalse(result["broker_orders_sent"])
        self.assertFalse(result["live_orders_sent"])


if __name__ == "__main__":
    unittest.main()

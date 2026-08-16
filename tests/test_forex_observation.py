from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.market_data.forex_models import ForexDataBundle
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_observation import (
    ForexObservationJournal,
    ForexObservationService,
)
from app.trading.models import TradingValidationError


UTC = timezone.utc
BASE = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
}


def bundle(now: datetime, *, open_market: bool = True) -> ForexDataBundle:
    quotes = {}
    bars = {}
    contexts = {}
    for pair in MAJOR_FOREX_PAIRS:
        prices = [BASE[pair.symbol]] * 31
        if pair.symbol == "EUR_USD":
            prices[-1] += pair.pip_size * Decimal("20")
        bars[pair.symbol] = tuple(
            ForexBar.create(
                pair=pair,
                timestamp=now - timedelta(seconds=(30 - index) * 900),
                open=price,
                high=price + pair.pip_size,
                low=price - pair.pip_size,
                close=price,
                tick_volume="100",
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
            market_open=open_market,
            calendar_ready=True,
            high_impact_event_blocked=False,
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
            "primary_pair_count": len(quotes),
            "cross_checked_pairs": tuple(quotes),
            "calendar_ready": True,
            "high_impact_event_count": 1,
            "nbp_effective_date": now.date().isoformat(),
            "pln_conversion_ready": True,
        },
    )


class FakeGateway:
    def __init__(self, *, failing: bool = False) -> None:
        self.failing = failing

    def collect(self, *, now: datetime) -> ForexDataBundle:
        if self.failing:
            raise TradingValidationError("forex_data_gate: source_unavailable")
        return bundle(now)


class ForexObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    def service(self, *, failing: bool = False) -> ForexObservationService:
        return ForexObservationService(
            self.root,
            gateway=FakeGateway(failing=failing),  # type: ignore[arg-type]
        )

    def test_observation_records_plan_without_executing_it(self) -> None:
        service = self.service()
        result = service.observe_once(
            observation_id="forex-observation-0001",
            now=self.now,
        )

        self.assertEqual(result["status"], "OBSERVATION_RECORDED")
        self.assertEqual(result["proposed_plan"]["status"], "ENTRIES_READY")
        self.assertEqual(result["would_open_count"], 1)
        self.assertEqual(result["execution"]["status"], "NOT_EXECUTED")
        self.assertTrue(result["positions_unchanged"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertEqual(service.executor.status()["position_count"], 0)
        self.assertFalse(
            (self.root / "data/trading/forex_paper_ledger.json").exists()
        )
        self.assertTrue(
            (self.root / "data/trading/forex_observations.json").exists()
        )

    def test_duplicate_id_is_idempotent(self) -> None:
        service = self.service()
        first = service.observe_once(
            observation_id="forex-observation-replay",
            now=self.now,
        )
        replay = service.observe_once(
            observation_id="forex-observation-replay",
            now=self.now + timedelta(seconds=1),
        )

        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(service.journal.summary()["observation_count"], 1)

    def test_data_failure_is_recorded_fail_closed(self) -> None:
        service = self.service(failing=True)
        result = service.observe_once(
            observation_id="forex-observation-blocked",
            now=self.now,
        )

        self.assertEqual(result["status"], "DATA_BLOCKED")
        self.assertIn("SOURCE_UNAVAILABLE", result["opening_blocks"][0])
        self.assertTrue(result["positions_unchanged"])
        self.assertEqual(result["proposed_instruction_count"], 0)
        self.assertTrue(result["market_data_network_access"])

    def test_tampering_blocks_the_journal_summary(self) -> None:
        service = self.service()
        service.observe_once(
            observation_id="forex-observation-audit",
            now=self.now,
        )
        state = service.journal.snapshot()
        state["observations"][0]["would_open_count"] = 99
        service.journal.store.save(state)

        summary = service.journal.summary()
        self.assertEqual(summary["status"], "BLOCKED")
        self.assertFalse(summary["audit_chain_valid"])
        self.assertFalse(summary["paper_promotion_ready"])

    def test_paper_promotion_is_advisory_and_never_automatic(self) -> None:
        journal = ForexObservationJournal(self.root)
        for index in range(20):
            observed = self.now + timedelta(days=index % 3, minutes=index)
            journal.record({
                "status": "OBSERVATION_RECORDED",
                "mode": "FOREX_OBSERVATION_ONLY",
                "observation_id": f"forex-evidence-{index:04d}",
                "observed_at": observed.isoformat(),
                "market_open": True,
                "fully_cross_checked": True,
                "paper_orders_sent": False,
                "live_orders_sent": False,
            })

        summary = journal.summary()
        self.assertTrue(summary["paper_promotion_ready"])
        self.assertFalse(summary["automatic_promotion"])
        self.assertEqual(summary["qualified_market_day_count"], 3)


if __name__ == "__main__":
    unittest.main()

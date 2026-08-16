from __future__ import annotations

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.trading.forex_autopilot import ForexPaperAutopilot
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_risk import ForexRateBook
from app.trading.models import TradingValidationError
from app.trading.paper_broker import LiveTradingBlockedError


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


def market(
    now: datetime,
    *,
    eur_direction: str = "FLAT",
    sources: int = 2,
) -> tuple[
    dict[str, ForexQuote],
    dict[str, list[ForexBar]],
    dict[str, ForexSafetyContext],
    list[ForexQuote],
]:
    quotes: dict[str, ForexQuote] = {}
    bars: dict[str, list[ForexBar]] = {}
    contexts: dict[str, ForexSafetyContext] = {}
    for pair in MAJOR_FOREX_PAIRS:
        prices = [BASE[pair.symbol]] * 31
        if pair.symbol == "EUR_USD" and eur_direction == "UP":
            prices[-1] += pair.pip_size * Decimal("20")
        elif pair.symbol == "EUR_USD" and eur_direction == "DOWN":
            prices[-1] -= pair.pip_size * Decimal("20")
        bars[pair.symbol] = [
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
        ]
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
            high_impact_event_blocked=False,
            conversion_to_pln_ready=True,
            independent_source_count=sources,
        )
    conversion = [ForexQuote.create(
        pair=USD_PLN_CONVERSION_PAIR,
        bid="3.999",
        ask="4.001",
        timestamp=now,
    )]
    return quotes, bars, contexts, conversion


class ForexPaperAutopilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
        self.autopilot = ForexPaperAutopilot(self.temporary.name)

    def run_cycle(
        self,
        cycle_id: str,
        *,
        now: datetime | None = None,
        direction: str = "UP",
        sources: int = 2,
    ) -> dict:
        selected_now = now or self.now
        quotes, bars, contexts, conversion = market(
            selected_now,
            eur_direction=direction,
            sources=sources,
        )
        return self.autopilot.run_cycle(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            conversion_quotes=conversion,
            cycle_id=cycle_id,
            now=selected_now,
        )

    def test_cycle_opens_one_paper_position_and_replay_is_idempotent(self) -> None:
        first = self.run_cycle("forex-cycle-0001")
        replay = self.run_cycle("forex-cycle-0001")

        self.assertEqual(first["status"], "CYCLE_COMPLETED")
        self.assertEqual(first["execution"]["status"], "APPLIED")
        self.assertEqual(
            first["execution"]["executions"][0]["fill"]["action"],
            "OPEN_LONG",
        )
        self.assertFalse(first["live_orders_sent"])
        self.assertFalse(first["network_access"])
        self.assertTrue(replay["execution"]["idempotent_replay"])
        status = self.autopilot.executor.status()
        self.assertEqual(status["position_count"], 1)
        self.assertEqual(status["fill_count"], 1)
        self.assertTrue(status["audit_chain_valid"])

    def test_later_cycle_closes_existing_position_before_any_entry(self) -> None:
        self.run_cycle("forex-cycle-open")
        later = self.now + timedelta(minutes=15)
        result = self.run_cycle(
            "forex-cycle-close",
            now=later,
            direction="DOWN",
        )

        self.assertEqual(result["plan"]["status"], "CLOSES_READY")
        self.assertEqual(
            result["execution"]["executions"][0]["fill"]["action"],
            "CLOSE_LONG",
        )
        status = self.autopilot.executor.status()
        self.assertEqual(status["position_count"], 0)
        self.assertEqual(status["fill_count"], 2)

    def test_missing_second_source_produces_no_execution(self) -> None:
        result = self.run_cycle("forex-cycle-data", sources=1)
        self.assertEqual(result["plan"]["status"], "NO_ACTION")
        self.assertEqual(result["execution"]["status"], "NO_EXECUTION")
        self.assertEqual(result["account"]["position_count"], 0)

    def test_missing_pln_conversion_fails_closed_before_execution(self) -> None:
        quotes, bars, contexts, _conversion = market(
            self.now, eur_direction="UP"
        )
        result = self.autopilot.run_cycle(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            conversion_quotes=(),
            cycle_id="forex-cycle-nofx",
            now=self.now,
        )
        self.assertEqual(result["status"], "DATA_BLOCKED")
        self.assertFalse(result["live_orders_sent"])
        self.assertEqual(self.autopilot.executor.status()["position_count"], 0)

    def test_kill_switch_blocks_open_and_requires_exact_release_phrase(self) -> None:
        self.autopilot.executor.activate_kill_switch("test")
        blocked = self.run_cycle("forex-cycle-stop")
        self.assertEqual(blocked["execution"]["status"], "NO_EXECUTION")
        self.assertEqual(
            blocked["execution"]["rejections"][0]["code"],
            "KILL_SWITCH_ACTIVE",
        )
        self.assertFalse(self.autopilot.executor.release_kill_switch("odblokuj"))
        self.assertTrue(
            self.autopilot.executor.release_kill_switch("FOREX PAPER ODBLOKUJ")
        )
        allowed = self.run_cycle("forex-cycle-resume")
        self.assertEqual(allowed["execution"]["status"], "APPLIED")

    def test_executor_rechecks_forged_oversized_instruction(self) -> None:
        quotes, _bars, _contexts, conversion = market(
            self.now, eur_direction="UP"
        )
        rates = ForexRateBook(
            list(quotes.values()) + conversion,
            now=self.now,
        )
        plan = {
            "mode": "FOREX_PAPER_ONLY",
            "live_orders_sent": False,
            "instructions": [{
                "action": "OPEN_LONG",
                "pair": "EUR_USD",
                "units": "999999",
                "stop_loss": "1.1000",
            }],
        }
        result = self.autopilot.executor.apply_plan(
            plan,
            quotes=quotes,
            rates=rates,
            cycle_id="forex-cycle-forged",
            now=self.now,
        )
        self.assertEqual(result["status"], "NO_EXECUTION")
        self.assertEqual(
            result["rejections"][0]["code"], "EXECUTION_RISK_RECHECK"
        )
        self.assertEqual(self.autopilot.executor.status()["position_count"], 0)

    def test_executor_rejects_a_stale_direct_quote(self) -> None:
        quotes, _bars, _contexts, conversion = market(
            self.now, eur_direction="UP"
        )
        rates = ForexRateBook(
            list(quotes.values()) + conversion,
            now=self.now,
        )
        stale_now = self.now + timedelta(minutes=2)
        with self.assertRaisesRegex(TradingValidationError, "stale_rate_book"):
            self.autopilot.executor.apply_plan(
                {
                    "mode": "FOREX_PAPER_ONLY",
                    "live_orders_sent": False,
                    "instructions": [],
                },
                quotes=quotes,
                rates=rates,
                cycle_id="forex-cycle-stale",
                now=stale_now,
            )

    def test_live_execution_method_is_unconditionally_blocked(self) -> None:
        with self.assertRaises(LiveTradingBlockedError):
            ForexPaperExecutionEngine.submit_live_order({"pair": "EUR_USD"})

    def test_two_executors_cannot_duplicate_one_cycle(self) -> None:
        quotes, _bars, _contexts, conversion = market(
            self.now, eur_direction="UP"
        )
        rates = ForexRateBook(
            list(quotes.values()) + conversion,
            now=self.now,
        )
        plan = {
            "mode": "FOREX_PAPER_ONLY",
            "live_orders_sent": False,
            "instructions": [{
                "action": "OPEN_LONG",
                "pair": "EUR_USD",
                "units": "100",
                "stop_loss": "1.1000",
            }],
        }
        engines = (
            ForexPaperExecutionEngine(self.temporary.name),
            ForexPaperExecutionEngine(self.temporary.name),
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(
                lambda engine: engine.apply_plan(
                    plan,
                    quotes=quotes,
                    rates=rates,
                    cycle_id="forex-cycle-race",
                    now=self.now,
                ),
                engines,
            ))
        self.assertEqual(sum(item["idempotent_replay"] for item in outcomes), 1)
        self.assertEqual(engines[0].status()["fill_count"], 1)


if __name__ == "__main__":
    unittest.main()

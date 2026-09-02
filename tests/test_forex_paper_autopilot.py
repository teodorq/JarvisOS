from __future__ import annotations

from copy import deepcopy
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
from app.trading.forex_risk import ForexPaperPolicy, ForexRateBook
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
        allow_new_entries: bool = True,
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
            allow_new_entries=allow_new_entries,
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
        self.assertTrue(
            first["execution"]["executions"][0]["fill"]["take_profit"]
        )
        opened_fill = first["execution"]["executions"][0]["fill"]
        self.assertEqual(
            opened_fill["sample_contract_id"],
            self.autopilot.sample_contract["contract_id"],
        )
        self.assertEqual(
            opened_fill["sample_contract_fingerprint_sha256"],
            self.autopilot.sample_contract["fingerprint_sha256"],
        )
        self.assertFalse(first["live_orders_sent"])
        self.assertFalse(first["network_access"])
        self.assertTrue(replay["execution"]["idempotent_replay"])
        status = self.autopilot.executor.status()
        self.assertEqual(status["position_count"], 1)
        self.assertEqual(status["take_profit_protected_position_count"], 1)
        self.assertEqual(status["legacy_position_without_take_profit_count"], 0)
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
        self.assertEqual(
            result["execution"]["executions"][0]["fill"][
                "sample_contract_fingerprint_sha256"
            ],
            self.autopilot.sample_contract["fingerprint_sha256"],
        )
        closed_fill = result["execution"]["executions"][0]["fill"]
        self.assertEqual(closed_fill["opened_at"], self.now.isoformat())
        self.assertEqual(closed_fill["closed_at"], later.isoformat())
        status = self.autopilot.executor.status()
        self.assertEqual(status["position_count"], 0)
        self.assertEqual(status["fill_count"], 2)
        self.assertEqual(status["processed_cycle_count"], 2)
        self.assertEqual(status["last_cycle"]["cycle_id"], "forex-cycle-close")
        self.assertEqual(status["closed_trade_count"], 1)
        self.assertEqual(status["winning_trade_count"], 0)
        self.assertEqual(status["losing_trade_count"], 1)
        self.assertLess(Decimal(status["realized_pnl_pln"]), 0)
        performance = status["performance"]
        self.assertEqual(performance["valid_closed_trade_count"], 1)
        self.assertEqual(performance["profit_factor"], "0.0000")
        self.assertEqual(performance["maximum_consecutive_losses"], 1)
        self.assertTrue(performance["integrity"]["evidence_valid"])
        self.assertFalse(performance["sample_size_sufficient_for_review"])
        self.assertFalse(performance["performance_validated"])
        self.assertFalse(performance["live_promotion_ready"])
        diagnostics = performance["trade_diagnostics"]
        self.assertEqual(diagnostics["status"], "COMPLETE")
        self.assertEqual(diagnostics["holding_time_observed_count"], 1)
        self.assertEqual(diagnostics["average_holding_minutes"], "15.00")
        self.assertEqual(diagnostics["exit_reason_counts"]["stop_loss"], 1)
        self.assertTrue(diagnostics["diagnostics_complete"])
        self.assertEqual(status["open_positions"], [])

    def test_close_only_mode_removes_entries_but_preserves_exit(self) -> None:
        blocked_open = self.run_cycle(
            "forex-cycle-entry-blocked",
            allow_new_entries=False,
        )
        self.assertEqual(blocked_open["plan"]["status"], "NO_ACTION")
        self.assertEqual(blocked_open["execution"]["status"], "NO_EXECUTION")
        self.assertFalse(blocked_open["new_entries_allowed"])
        self.assertEqual(blocked_open["account"]["position_count"], 0)

        self.run_cycle("forex-cycle-close-only-open")
        closed = self.run_cycle(
            "forex-cycle-close-only-exit",
            now=self.now + timedelta(minutes=15),
            direction="DOWN",
            allow_new_entries=False,
        )
        fills = [
            item["fill"]["action"]
            for item in closed["execution"]["executions"]
        ]
        self.assertEqual(fills, ["CLOSE_LONG"])
        self.assertTrue(all(not action.startswith("OPEN_") for action in fills))
        self.assertEqual(closed["account"]["position_count"], 0)

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

    def test_three_losses_pause_entries_then_resume_after_cooldown(self) -> None:
        current = self.now
        for index in range(3):
            opened = self.run_cycle(
                f"forex-loss-open-{index}",
                now=current,
                direction="UP",
            )
            self.assertEqual(opened["execution"]["status"], "APPLIED")
            current += timedelta(minutes=15)
            closed = self.run_cycle(
                f"forex-loss-close-{index}",
                now=current,
                direction="DOWN",
            )
            self.assertEqual(
                closed["execution"]["executions"][0]["fill"]["action"],
                "CLOSE_LONG",
            )
            current += timedelta(minutes=15)

        safety = closed["account"]["loss_streak_safety"]
        self.assertTrue(safety["active"])
        self.assertEqual(safety["current_consecutive_losses"], 3)
        self.assertEqual(safety["threshold"], 3)
        blocked = self.run_cycle(
            "forex-loss-cooldown-blocked",
            now=current,
            direction="UP",
        )
        self.assertEqual(blocked["execution"]["status"], "NO_EXECUTION")
        self.assertEqual(
            blocked["execution"]["rejections"][0]["code"],
            "CONSECUTIVE_LOSS_COOLDOWN",
        )
        self.assertEqual(blocked["account"]["position_count"], 0)

        resumed = self.run_cycle(
            "forex-loss-cooldown-complete",
            now=current + timedelta(hours=6),
            direction="UP",
        )
        self.assertEqual(resumed["execution"]["status"], "APPLIED")
        self.assertFalse(
            resumed["account"]["new_entries_paused_by_loss_streak"]
        )
        self.assertEqual(
            resumed["account"]["loss_streak_safety"]["code"],
            "COOLDOWN_COMPLETE",
        )

    def test_loss_streak_policy_rejects_unsafe_values(self) -> None:
        with self.assertRaisesRegex(
            TradingValidationError,
            "unsafe_consecutive_loss_pause_threshold",
        ):
            ForexPaperPolicy(consecutive_loss_pause_threshold=1)
        with self.assertRaisesRegex(
            TradingValidationError,
            "unsafe_loss_streak_cooldown_minutes",
        ):
            ForexPaperPolicy(loss_streak_cooldown_minutes=14)
        with self.assertRaisesRegex(
            TradingValidationError,
            "unsafe_max_weekly_loss_pct",
        ):
            ForexPaperPolicy(max_weekly_loss_pct=Decimal("0.051"))

    def test_weekly_loss_limit_blocks_entries_and_resets_next_week(self) -> None:
        self.autopilot = ForexPaperAutopilot(
            self.temporary.name,
            policy=ForexPaperPolicy(
                max_weekly_loss_pct=Decimal("0.0001"),
            ),
        )
        self.run_cycle("forex-weekly-open")
        closed_at = self.now + timedelta(minutes=15)
        closed = self.run_cycle(
            "forex-weekly-close",
            now=closed_at,
            direction="DOWN",
        )

        safety = closed["account"]["weekly_loss_safety"]
        self.assertTrue(safety["active"])
        self.assertEqual(safety["code"], "WEEKLY_LOSS_LIMIT")
        self.assertEqual(safety["loss_limit_pln"], "10.00")
        self.assertLess(Decimal(safety["weekly_pnl_pln"]), Decimal("-10"))
        self.assertEqual(safety["remaining_loss_capacity_pln"], "0.00")

        blocked = self.run_cycle(
            "forex-weekly-blocked",
            now=closed_at + timedelta(minutes=15),
            direction="UP",
        )
        self.assertEqual(blocked["execution"]["status"], "NO_EXECUTION")
        self.assertEqual(
            blocked["execution"]["rejections"][0]["code"],
            "WEEKLY_LOSS_LIMIT",
        )
        self.assertTrue(
            blocked["account"]["new_entries_paused_by_weekly_loss"]
        )

        resumed = self.run_cycle(
            "forex-weekly-reset",
            now=self.now + timedelta(days=7),
            direction="UP",
        )
        self.assertEqual(resumed["execution"]["status"], "APPLIED")
        self.assertFalse(
            resumed["account"]["new_entries_paused_by_weekly_loss"]
        )
        self.assertEqual(
            resumed["account"]["weekly_loss_safety"]["weekly_pnl_pln"],
            "0.00",
        )

    def test_weekly_gate_fails_closed_when_fill_and_audit_diverge(self) -> None:
        self.run_cycle("forex-weekly-audit-open")
        closed_at = self.now + timedelta(minutes=15)
        self.run_cycle(
            "forex-weekly-audit-close",
            now=closed_at,
            direction="DOWN",
        )

        def tamper(state: dict) -> None:
            state["fills"][-1]["realized_pnl_pln"] = "0.00"

        self.autopilot.executor.ledger.transaction(tamper)
        safety = self.autopilot.executor.status(
            now=closed_at + timedelta(minutes=1)
        )["weekly_loss_safety"]
        self.assertTrue(safety["active"])
        self.assertEqual(safety["code"], "EXECUTION_AUDIT_MISMATCH")

        blocked = self.run_cycle(
            "forex-weekly-audit-blocked",
            now=closed_at + timedelta(minutes=15),
            direction="UP",
        )
        self.assertEqual(
            blocked["execution"]["rejections"][0]["code"],
            "EXECUTION_AUDIT_MISMATCH",
        )

    def test_weekly_loss_limit_never_blocks_existing_position_close(self) -> None:
        self.autopilot = ForexPaperAutopilot(
            self.temporary.name,
            policy=ForexPaperPolicy(
                max_weekly_loss_pct=Decimal("0.0001"),
            ),
        )
        quotes, _bars, _contexts, _conversion = market(
            self.now,
            eur_direction="UP",
        )

        def rates_at(selected_quotes: dict[str, ForexQuote], now: datetime):
            return ForexRateBook(
                list(selected_quotes.values()) + [
                    ForexQuote.create(
                        pair=USD_PLN_CONVERSION_PAIR,
                        bid="3.999",
                        ask="4.001",
                        timestamp=now,
                    )
                ],
                now=now,
            )

        for index, symbol in enumerate(("EUR_USD", "GBP_USD"), 1):
            quote = quotes[symbol]
            stop = quote.ask - quote.pair.pip_size * Decimal("10")
            target = quote.ask + quote.pair.pip_size * Decimal("20")
            result = self.autopilot.executor.apply_plan(
                {
                    "mode": "FOREX_PAPER_ONLY",
                    "live_orders_sent": False,
                    "sample_contract": self.autopilot.sample_contract,
                    "instructions": [{
                        "action": "OPEN_LONG",
                        "pair": symbol,
                        "units": "1000",
                        "stop_loss": str(stop),
                        "take_profit": str(target),
                    }],
                },
                quotes=quotes,
                rates=rates_at(quotes, self.now),
                cycle_id=f"forex-weekly-close-open-{index}",
                now=self.now,
            )
            self.assertEqual(result["status"], "APPLIED")

        close_at = self.now + timedelta(minutes=15)
        close_quotes, _bars, _contexts, _conversion = market(
            close_at,
            eur_direction="DOWN",
        )
        close_plan = {
            "mode": "FOREX_PAPER_ONLY",
            "live_orders_sent": False,
            "instructions": [{
                "action": "CLOSE_POSITION",
                "pair": "EUR_USD",
                "units": "1000",
                "reason_codes": ["STOP_LOSS_TRIGGERED"],
            }],
        }
        first_close = self.autopilot.executor.apply_plan(
            close_plan,
            quotes=close_quotes,
            rates=rates_at(close_quotes, close_at),
            cycle_id="forex-weekly-close-limit-trigger",
            now=close_at,
        )
        self.assertEqual(first_close["status"], "APPLIED")
        self.assertTrue(
            self.autopilot.executor.status(now=close_at)[
                "weekly_loss_safety"
            ]["active"]
        )

        second_close = self.autopilot.executor.apply_plan(
            {
                **close_plan,
                "instructions": [{
                    **close_plan["instructions"][0],
                    "pair": "GBP_USD",
                }],
            },
            quotes=close_quotes,
            rates=rates_at(close_quotes, close_at),
            cycle_id="forex-weekly-close-still-allowed",
            now=close_at,
        )
        self.assertEqual(second_close["status"], "APPLIED")
        self.assertEqual(
            second_close["executions"][0]["fill"]["action"],
            "CLOSE_LONG",
        )
        self.assertEqual(
            self.autopilot.executor.status(now=close_at)["position_count"],
            0,
        )
        with self.assertRaisesRegex(
            TradingValidationError,
            "unsafe_max_weekly_loss_pct",
        ):
            ForexPaperPolicy(max_weekly_loss_pct=Decimal("0.051"))

    def test_weekly_loss_limit_blocks_entries_and_resets_next_week(self) -> None:
        self.autopilot = ForexPaperAutopilot(
            self.temporary.name,
            policy=ForexPaperPolicy(
                max_weekly_loss_pct=Decimal("0.0001"),
            ),
        )
        self.run_cycle("forex-weekly-open")
        closed_at = self.now + timedelta(minutes=15)
        closed = self.run_cycle(
            "forex-weekly-close",
            now=closed_at,
            direction="DOWN",
        )

        safety = closed["account"]["weekly_loss_safety"]
        self.assertTrue(safety["active"])
        self.assertEqual(safety["code"], "WEEKLY_LOSS_LIMIT")
        self.assertEqual(safety["loss_limit_pln"], "10.00")
        self.assertLess(Decimal(safety["weekly_pnl_pln"]), Decimal("-10"))
        self.assertEqual(safety["remaining_loss_capacity_pln"], "0.00")

        blocked = self.run_cycle(
            "forex-weekly-blocked",
            now=closed_at + timedelta(minutes=15),
            direction="UP",
        )
        self.assertEqual(blocked["execution"]["status"], "NO_EXECUTION")
        self.assertEqual(
            blocked["execution"]["rejections"][0]["code"],
            "WEEKLY_LOSS_LIMIT",
        )
        self.assertTrue(
            blocked["account"]["new_entries_paused_by_weekly_loss"]
        )

        resumed = self.run_cycle(
            "forex-weekly-reset",
            now=self.now + timedelta(days=7),
            direction="UP",
        )
        self.assertEqual(resumed["execution"]["status"], "APPLIED")
        self.assertFalse(
            resumed["account"]["new_entries_paused_by_weekly_loss"]
        )
        self.assertEqual(
            resumed["account"]["weekly_loss_safety"]["weekly_pnl_pln"],
            "0.00",
        )

    def test_weekly_gate_fails_closed_when_fill_and_audit_diverge(self) -> None:
        self.run_cycle("forex-weekly-audit-open")
        closed_at = self.now + timedelta(minutes=15)
        self.run_cycle(
            "forex-weekly-audit-close",
            now=closed_at,
            direction="DOWN",
        )

        def tamper(state: dict) -> None:
            state["fills"][-1]["realized_pnl_pln"] = "0.00"

        self.autopilot.executor.ledger.transaction(tamper)
        safety = self.autopilot.executor.status(
            now=closed_at + timedelta(minutes=1)
        )["weekly_loss_safety"]
        self.assertTrue(safety["active"])
        self.assertEqual(safety["code"], "EXECUTION_AUDIT_MISMATCH")

        blocked = self.run_cycle(
            "forex-weekly-audit-blocked",
            now=closed_at + timedelta(minutes=15),
            direction="UP",
        )
        self.assertEqual(
            blocked["execution"]["rejections"][0]["code"],
            "EXECUTION_AUDIT_MISMATCH",
        )

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
            "sample_contract": self.autopilot.sample_contract,
            "instructions": [{
                "action": "OPEN_LONG",
                "pair": "EUR_USD",
                "units": "999999",
                "stop_loss": "1.1000",
                "take_profit": "1.10615",
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

    def test_executor_rejects_a_forged_take_profit_ratio(self) -> None:
        quotes, _bars, _contexts, conversion = market(
            self.now, eur_direction="UP"
        )
        rates = ForexRateBook(
            list(quotes.values()) + conversion,
            now=self.now,
        )
        result = self.autopilot.executor.apply_plan(
            {
                "mode": "FOREX_PAPER_ONLY",
                "live_orders_sent": False,
                "sample_contract": self.autopilot.sample_contract,
                "instructions": [{
                    "action": "OPEN_LONG",
                    "pair": "EUR_USD",
                    "units": "100",
                    "stop_loss": "1.1000",
                    "take_profit": "1.1040",
                }],
            },
            quotes=quotes,
            rates=rates,
            cycle_id="forex-cycle-target-policy",
            now=self.now,
        )
        self.assertEqual(result["status"], "NO_EXECUTION")
        self.assertEqual(
            result["rejections"][0]["code"],
            "TAKE_PROFIT_POLICY_MISMATCH",
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
        engines = (
            ForexPaperExecutionEngine(self.temporary.name),
            ForexPaperExecutionEngine(self.temporary.name),
        )
        plan = {
            "mode": "FOREX_PAPER_ONLY",
            "live_orders_sent": False,
            "sample_contract": engines[0].sample_contract,
            "instructions": [{
                "action": "OPEN_LONG",
                "pair": "EUR_USD",
                "units": "100",
                "stop_loss": "1.1000",
                "take_profit": "1.10615",
            }],
        }
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

    def test_executor_requires_the_exact_sample_contract_for_open(self) -> None:
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
                "take_profit": "1.10615",
            }],
        }
        with self.assertRaisesRegex(
            TradingValidationError,
            "sample_contract_required",
        ):
            self.autopilot.executor.apply_plan(
                plan,
                quotes=quotes,
                rates=rates,
                cycle_id="forex-contract-missing",
                now=self.now,
            )

        tampered = deepcopy(self.autopilot.sample_contract)
        tampered["fingerprint_sha256"] = "0" * 64
        plan["sample_contract"] = tampered
        with self.assertRaisesRegex(
            TradingValidationError,
            "sample_contract_mismatch",
        ):
            self.autopilot.executor.apply_plan(
                plan,
                quotes=quotes,
                rates=rates,
                cycle_id="forex-contract-tampered",
                now=self.now,
            )


if __name__ == "__main__":
    unittest.main()

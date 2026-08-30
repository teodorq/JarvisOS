from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.trading import (
    HistoricalPaperBacktester,
    HistoricalCsvLoader,
    LiveTradingBlockedError,
    MarketBar,
    MAJOR_FOREX_PAIRS,
    MarketQuote,
    PaperOrder,
    PaperTradingEngine,
    PaperTradingLedger,
    PaperTradingPolicy,
    StrategySignal,
    TradingControlCenter,
    TradingValidationError,
)


UTC = timezone.utc


def quote(
    now: datetime,
    *,
    bid: str = "99",
    ask: str = "100",
    symbol: str = "TEST",
) -> MarketQuote:
    return MarketQuote.create(
        symbol=symbol,
        bid=bid,
        ask=ask,
        timestamp=now,
        currency="PLN",
    )


def order(
    now: datetime,
    order_id: str,
    *,
    side: str = "BUY",
    quantity: str = "1",
) -> PaperOrder:
    return PaperOrder.create(
        client_order_id=order_id,
        symbol="TEST",
        side=side,
        quantity=quantity,
        created_at=now,
    )


class TradingModelTests(unittest.TestCase):
    def test_quote_rejects_crossed_market_and_naive_time(self) -> None:
        now = datetime.now(UTC)
        with self.assertRaisesRegex(TradingValidationError, "crossed_market"):
            quote(now, bid="101", ask="100")
        with self.assertRaisesRegex(TradingValidationError, "timezone_required"):
            quote(datetime.now())

    def test_bar_rejects_inconsistent_ohlc(self) -> None:
        with self.assertRaisesRegex(TradingValidationError, "high_inconsistent"):
            MarketBar.create(
                symbol="TEST",
                timestamp=datetime.now(UTC),
                open="100",
                high="99",
                low="98",
                close="100",
                volume="10",
            )

    def test_order_requires_valid_side_and_id(self) -> None:
        now = datetime.now(UTC)
        with self.assertRaisesRegex(TradingValidationError, "buy_or_sell_required"):
            order(now, "paper-0001", side="HOLD")
        with self.assertRaisesRegex(TradingValidationError, "client_order_id"):
            order(now, "short")

    def test_direct_construction_cannot_bypass_validation(self) -> None:
        now = datetime.now(UTC)
        with self.assertRaisesRegex(TradingValidationError, "non_positive"):
            PaperOrder(
                client_order_id="paper-direct-1",
                symbol="TEST",
                side="BUY",
                quantity=Decimal("-1"),
                created_at=now,
            )
        with self.assertRaisesRegex(TradingValidationError, "crossed_market"):
            MarketQuote(
                symbol="TEST",
                bid=Decimal("101"),
                ask=Decimal("100"),
                timestamp=now,
            )


class TradingPolicyTests(unittest.TestCase):
    def test_live_short_and_leverage_are_hard_disabled(self) -> None:
        policy = PaperTradingPolicy()
        self.assertFalse(policy.live_trading_enabled)
        self.assertFalse(policy.short_selling_enabled)
        self.assertFalse(policy.leverage_enabled)
        with self.assertRaises(TypeError):
            PaperTradingPolicy(live_trading_enabled=True)  # type: ignore[call-arg]

    def test_unsafe_limits_are_rejected(self) -> None:
        with self.assertRaisesRegex(TradingValidationError, "outside_safe_range"):
            PaperTradingPolicy(max_order_notional_pct=Decimal("0.06"))
        with self.assertRaisesRegex(TradingValidationError, "outside_safe_range"):
            PaperTradingPolicy(max_daily_loss_pct=Decimal("0.06"))


class PaperTradingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.policy = PaperTradingPolicy(initial_cash=Decimal("10000"))
        self.engine = PaperTradingEngine(self.temporary.name, policy=self.policy)
        self.now = datetime(2026, 8, 16, 10, 0, tzinfo=UTC)

    def test_fill_is_local_audited_and_idempotent(self) -> None:
        first = self.engine.submit(
            order(self.now, "paper-buy-0001"), quote(self.now), now=self.now
        )
        replay = self.engine.submit(
            order(self.now, "paper-buy-0001"), quote(self.now), now=self.now
        )

        self.assertEqual(first["status"], "FILLED")
        self.assertFalse(first["live_order_sent"])
        self.assertEqual(replay["fill"]["fill_id"], first["fill"]["fill_id"])
        self.assertTrue(replay["idempotent_replay"])
        status = self.engine.status()
        self.assertEqual(status["fill_count"], 1)
        self.assertEqual(status["position_count"], 1)
        self.assertTrue(status["audit_chain_valid"])
        self.assertFalse(status["network_access"])

    def test_two_engine_instances_cannot_duplicate_the_same_order(self) -> None:
        second_engine = PaperTradingEngine(
            self.temporary.name, policy=self.policy
        )
        selected_order = order(self.now, "paper-race-0001")
        selected_quote = quote(self.now)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda engine: engine.submit(
                        selected_order, selected_quote, now=self.now
                    ),
                    (self.engine, second_engine),
                )
            )

        self.assertEqual({result["status"] for result in results}, {"FILLED"})
        self.assertEqual(
            sum(bool(result["idempotent_replay"]) for result in results), 1
        )
        self.assertEqual(self.engine.status()["fill_count"], 1)

    def test_valid_sell_closes_position_and_records_profit(self) -> None:
        self.engine.submit(
            order(self.now, "paper-buy-0002"), quote(self.now), now=self.now
        )
        later = self.now + timedelta(seconds=10)
        result = self.engine.submit(
            order(later, "paper-sell-001", side="SELL"),
            quote(later, bid="109", ask="110"),
            now=later,
        )

        self.assertEqual(result["status"], "FILLED")
        self.assertGreater(Decimal(result["fill"]["realized_pnl"]), Decimal("0"))
        self.assertEqual(self.engine.status()["position_count"], 0)

    def test_risk_rejects_oversize_short_stale_and_wide_spread(self) -> None:
        cases = (
            (
                order(self.now, "paper-big-0001", quantity="100"),
                quote(self.now),
                "ORDER_NOTIONAL_LIMIT",
            ),
            (
                order(self.now, "paper-short-01", side="SELL"),
                quote(self.now),
                "SHORT_SELLING_BLOCKED",
            ),
            (
                order(self.now, "paper-stale-01"),
                quote(self.now - timedelta(minutes=2)),
                "STALE_QUOTE",
            ),
            (
                order(self.now, "paper-spread-1"),
                quote(self.now, bid="90", ask="110"),
                "SPREAD_TOO_WIDE",
            ),
        )
        for selected_order, selected_quote, expected in cases:
            with self.subTest(expected=expected):
                result = self.engine.submit(
                    selected_order, selected_quote, now=self.now
                )
                self.assertEqual(result["status"], "REJECTED")
                self.assertEqual(result["risk_code"], expected)
                self.assertFalse(result["live_order_sent"])

    def test_kill_switch_and_live_execution_block(self) -> None:
        activation = self.engine.activate_kill_switch("test bezpieczeństwa")
        blocked = self.engine.submit(
            order(self.now, "paper-stop-001"), quote(self.now), now=self.now
        )
        self.assertEqual(activation["status"], "KILL_SWITCH_ACTIVE")
        self.assertEqual(blocked["risk_code"], "KILL_SWITCH_ACTIVE")
        self.assertEqual(
            self.engine.release_kill_switch("niewłaściwe potwierdzenie")["status"],
            "CONFIRMATION_REQUIRED",
        )
        with self.assertRaises(LiveTradingBlockedError):
            self.engine.submit_live_order({"symbol": "TEST"})

    def test_audit_chain_detects_tampering(self) -> None:
        self.engine.submit(
            order(self.now, "paper-audit-01"), quote(self.now), now=self.now
        )
        state = self.engine.ledger.snapshot()
        self.assertTrue(PaperTradingLedger.verify_audit(state))
        tampered = deepcopy(state)
        tampered["audit"][0]["details"]["symbol"] = "CHANGED"
        self.assertFalse(PaperTradingLedger.verify_audit(tampered))


class HistoricalBacktestTests(unittest.TestCase):
    @staticmethod
    def bars() -> list[MarketBar]:
        start = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
        prices = ("100", "101", "110", "111")
        return [
            MarketBar.create(
                symbol="TEST",
                timestamp=start + timedelta(minutes=index),
                open=price,
                high=str(Decimal(price) + 1),
                low=str(Decimal(price) - 1),
                close=price,
                volume="100",
            )
            for index, price in enumerate(prices)
        ]

    def test_signals_fill_only_on_strictly_later_bars(self) -> None:
        bars = self.bars()
        signals = (
            StrategySignal.create(
                signal_id="signal-buy-01",
                symbol="TEST",
                side="BUY",
                quantity="1",
                timestamp=bars[0].timestamp,
            ),
            StrategySignal.create(
                signal_id="signal-sell-1",
                symbol="TEST",
                side="SELL",
                quantity="1",
                timestamp=bars[2].timestamp,
            ),
            StrategySignal.create(
                signal_id="signal-last-1",
                symbol="TEST",
                side="BUY",
                quantity="1",
                timestamp=bars[-1].timestamp,
            ),
        )
        result = HistoricalPaperBacktester(
            PaperTradingPolicy(initial_cash=Decimal("10000"))
        ).run(bars, signals)

        self.assertEqual(result["status"], "BACKTEST_COMPLETED")
        self.assertEqual(result["fill_count"], 2)
        self.assertTrue(result["look_ahead_blocked"])
        self.assertFalse(result["live_order_sent"])
        self.assertIn(
            {"signal_id": "signal-last-1", "code": "NO_NEXT_BAR"},
            result["rejections"],
        )
        for fill in result["fills"]:
            self.assertGreater(
                datetime.fromisoformat(fill["filled_at"]),
                datetime.fromisoformat(fill["signal_at"]),
            )


class HistoricalDatasetTests(unittest.TestCase):
    HEADER = "timestamp,symbol,open,high,low,close,volume,currency\n"

    def test_valid_csv_has_stable_fingerprint_and_aware_ordered_bars(self) -> None:
        content = self.HEADER + (
            "2026-01-05T09:00:00+00:00,TEST,100,101,99,100,10,PLN\n"
            "2026-01-05T09:01:00+00:00,TEST,101,102,100,101,11,PLN\n"
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.csv"
            path.write_text(content, encoding="utf-8")
            first = HistoricalCsvLoader().load(path)
            second = HistoricalCsvLoader().load(path)

        self.assertEqual(first.symbol, "TEST")
        self.assertEqual(first.currency, "PLN")
        self.assertEqual(len(first.bars), 2)
        self.assertEqual(first.fingerprint_sha256, second.fingerprint_sha256)
        self.assertEqual(len(first.fingerprint_sha256), 64)
        self.assertTrue(first.status()["local_only"])

    def test_csv_rejects_unsorted_naive_and_remote_data(self) -> None:
        cases = (
            (
                "unsorted.csv",
                self.HEADER
                + "2026-01-05T09:01:00+00:00,TEST,100,101,99,100,10,PLN\n"
                + "2026-01-05T09:00:00+00:00,TEST,100,101,99,100,10,PLN\n",
                "timestamps_not_strictly_increasing",
            ),
            (
                "naive.csv",
                self.HEADER
                + "2026-01-05T09:00:00,TEST,100,101,99,100,10,PLN\n"
                + "2026-01-05T09:01:00,TEST,100,101,99,100,10,PLN\n",
                "invalid_row_2",
            ),
        )
        with TemporaryDirectory() as directory:
            for name, content, expected in cases:
                with self.subTest(name=name):
                    path = Path(directory) / name
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(TradingValidationError, expected):
                        HistoricalCsvLoader().load(path)
        with self.assertRaisesRegex(TradingValidationError, "local_file_required"):
            HistoricalCsvLoader().load("https://example.com/history.csv")


class TradingControlAndRoutingTests(unittest.TestCase):
    def test_readiness_is_paper_only_and_secret_free(self) -> None:
        with TemporaryDirectory() as directory:
            center = TradingControlCenter(directory)
            status = center.status()
            rendered = center.format_status()

        self.assertEqual(status["mode"], "PAPER_ONLY")
        self.assertTrue(status["components"]["pre_trade_risk"])
        self.assertTrue(status["components"]["atomic_ledger"])
        self.assertTrue(status["components"]["next_bar_backtest"])
        self.assertTrue(status["components"]["chronological_holdout_backtest"])
        self.assertTrue(
            status["components"]["non_overlapping_walk_forward_backtest"]
        )
        self.assertTrue(
            status["components"]["mt5_demo_closed_m15_history_export"]
        )
        self.assertTrue(
            status["components"]["historical_dataset_fingerprint_recheck"]
        )
        self.assertTrue(status["components"]["historical_m15_quality_audit"])
        self.assertFalse(status["components"]["external_market_data"])
        self.assertFalse(status["components"]["external_paper_broker"])
        self.assertFalse(status["safety"]["live_trading_enabled"])
        self.assertIn("PAPER ONLY", rendered)
        self.assertIn("twardo zablokowane", rendered)
        self.assertIn("kwalifikowane 0/20", rendered)
        self.assertIn("dni rynkowe 0/3", rendered)
        self.assertIn("Bramka PAPER: ZABLOKOWANA", rendered)
        self.assertIn("wykonanie pozostaje WYŁĄCZONE", rendered)

    def test_owner_status_command_is_read_only_and_client_blocked(self) -> None:
        command = "Status paper tradingu"
        self.assertEqual(
            NaturalLanguageService.classify(command), "paper_trading_status"
        )
        self.assertTrue(PersonalAssistantController.matches(command))
        with TemporaryDirectory() as directory:
            controller = PersonalAssistantController(directory)
            thought = controller.plan(command)
            response = controller.handle(command)
        self.assertEqual(thought["handler"], "personal_assistant")
        self.assertEqual(thought["assistant_intent"], "paper_trading_status")
        self.assertTrue(thought["read_only"])
        self.assertIn("PAPER ONLY", response)
        self.assertIn(
            "tylko w trybie właściciela",
            ClientCapabilityPolicy.denial_message(command),
        )
        self.assertIn(
            "tylko w trybie właściciela",
            ClientCapabilityPolicy.denial_for_thought(
                {"assistant_intent": "paper_trading_status"}
            ),
        )

    def test_status_loads_ignored_forex_configuration_without_exposing_secret(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "forex.env").write_text(
                "JARVIS_OS_FOREX_DATA_ENABLED=true\n"
                "JARVIS_OS_FOREX_PRIMARY_PROVIDER=MT5_DEMO\n"
                "JARVIS_OS_TWELVE_DATA_API_KEY=placeholder\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                center = TradingControlCenter(root)
                status = center.status()
                rendered = center.format_status()

        self.assertTrue(status["forex"]["data_configuration_complete"])
        self.assertIn("Konfiguracja źródeł: kompletna", rendered)
        self.assertNotIn("placeholder", rendered)
        self.assertNotIn("placeholder", repr(status))

    def test_status_summarizes_last_autonomous_forex_paper_cycle(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "data" / "trading" / "forex_paper_last.json"
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps({
                    "status": "PAPER_CYCLE_COMPLETED",
                    "observed_at": "2026-08-21T09:03:45+00:00",
                    "paper": {
                        "status": "CYCLE_COMPLETED",
                        "assessments": [
                            {
                                "pair": pair.symbol,
                                "status": "READY",
                                "action": "WATCH",
                                "reason_codes": ["NO_NEW_CROSSOVER"],
                            }
                            for pair in MAJOR_FOREX_PAIRS
                        ],
                        "execution": {"status": "NO_EXECUTION", "executions": []},
                    },
                    "broker_orders_sent": False,
                    "live_orders_sent": False,
                    "real_money_access": False,
                }),
                encoding="utf-8",
            )
            center = TradingControlCenter(root)
            status = center.status()
            rendered = center.format_status()

        runtime = status["forex"]["last_runtime_cycle"]
        self.assertEqual(runtime["decision"], "NO_ENTRY_SIGNAL")
        self.assertEqual(runtime["ready_pair_count"], 7)
        self.assertFalse(runtime["live_orders_sent"])
        self.assertIn("gotowe pary 7/7", rendered)
        self.assertIn("Konto PAPER Forex: 100000.00 PLN", rendered)
        self.assertIn("Kohorty V1/V2", rendered)

    def test_status_distinguishes_closed_market_from_dead_observer(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = (
                root / "data" / "trading" / "forex_observer_status.json"
            )
            status_path.parent.mkdir(parents=True)
            status_path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "status": "MARKET_CLOSED_IDLE",
                    "checked_at": datetime.now(UTC).isoformat(),
                    "market_window_open": False,
                    "mt5_running": False,
                    "last_cycle_observed_at": "2026-08-24T14:35:11+00:00",
                    "broker_orders_sent": False,
                    "live_orders_sent": False,
                    "real_money_access": False,
                }),
                encoding="utf-8",
            )
            center = TradingControlCenter(root)
            snapshot = center.status()
            rendered = center.format_status()

        heartbeat = snapshot["forex"]["observer_runtime"]
        self.assertTrue(heartbeat["available"])
        self.assertFalse(heartbeat["stale"])
        self.assertEqual(heartbeat["status"], "MARKET_CLOSED_IDLE")
        self.assertFalse(heartbeat["mt5_running"])
        self.assertIn("rynek zamknięty", rendered)
        self.assertIn("MT5 uruchomi się automatycznie", rendered)

    def test_status_labels_explicit_unvalidated_demo_override(self) -> None:
        with TemporaryDirectory() as directory:
            center = TradingControlCenter(directory)
            snapshot = center.status()
            snapshot["forex"]["automatic_paper_execution"] = True
            snapshot["forex"]["observation"]["paper_promotion_ready"] = True
            snapshot["forex"]["historical_research"][
                "strategy_candidate_ready"
            ] = False
            with patch.object(center, "status", return_value=snapshot):
                rendered = center.format_status()

        self.assertIn("EKSPERYMENTALNY PAPER DEMO", rendered)
        self.assertIn("LIVE pozostaje zablokowany", rendered)
        self.assertIn("zbierać wyniki PAPER bez zmiany parametrów", rendered)

    def test_status_reports_a_watchdog_cycle_block_reason(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "data" / "trading" / "forex_paper_last.json"
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps({
                    "status": "PAPER_CYCLE_BLOCKED",
                    "reason": "CURRENT_OBSERVATION_BLOCKED",
                    "broker_orders_sent": False,
                    "live_orders_sent": False,
                    "real_money_access": False,
                }),
                encoding="utf-8",
            )
            center = TradingControlCenter(root)
            runtime = center.status()["forex"]["last_runtime_cycle"]
            rendered = center.format_status()

        self.assertEqual(runtime["decision"], "DATA_BLOCKED")
        self.assertEqual(
            runtime["reason_codes"], {"CURRENT_OBSERVATION_BLOCKED": 1}
        )
        self.assertIn("CURRENT_OBSERVATION_BLOCKED: 1", rendered)

    def test_observation_progress_phrases_are_owner_only_read_only_status(self) -> None:
        variants = (
            "Status obserwatora Forex",
            "Ile obserwacji Forex?",
            "Postęp obserwacji Forex",
            "Czy PAPER jest gotowy?",
        )
        for command in variants:
            with self.subTest(command=command):
                self.assertEqual(
                    NaturalLanguageService.classify(command),
                    "paper_trading_status",
                )
                self.assertTrue(PersonalAssistantController.matches(command))
                self.assertIn(
                    "tylko w trybie właściciela",
                    ClientCapabilityPolicy.denial_message(command),
                )

    def test_observation_review_is_owner_only_and_read_only(self) -> None:
        command = "Raport obserwacji Forex"
        self.assertEqual(
            NaturalLanguageService.classify(command),
            "forex_observation_review",
        )
        self.assertTrue(PersonalAssistantController.matches(command))
        with TemporaryDirectory() as directory:
            controller = PersonalAssistantController(directory)
            thought = controller.plan(command)
            response = controller.handle(command)
        self.assertTrue(thought["read_only"])
        self.assertIn("tylko odczyt", response)
        self.assertIn(
            "Raport nie może zmienić stanu PAPER/LIVE ani sam awansować V2",
            response,
        )
        self.assertIn(
            "tylko w trybie właściciela",
            ClientCapabilityPolicy.denial_for_thought(thought),
        )


class TradingSourceSafetyTests(unittest.TestCase):
    def test_trading_package_has_no_network_or_cloud_imports(self) -> None:
        root = Path(__file__).resolve().parents[1] / "app" / "trading"
        imported_roots: set[str] = set()
        source = ""
        for path in root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            source += "\n" + text.casefold()
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(
                        alias.name.split(".", 1)[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".", 1)[0])

        self.assertTrue(
            {"requests", "httpx", "urllib", "socket", "azure"}.isdisjoint(
                imported_roots
            )
        )
        for forbidden in (
            "api.alpaca.markets",
            "interactivebrokers.com",
            "paper-api.alpaca.markets",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexPosition,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
    major_pair,
    normalized_pair,
)
from app.trading.forex_risk import (
    ForexPaperPolicy,
    ForexPortfolioRiskEngine,
    ForexRateBook,
)
from app.trading.forex_scanner import ForexMarketScanner
from app.trading.models import TradingValidationError
from app.trading.paper_broker import LiveTradingBlockedError
from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.gui.client_capability_policy import ClientCapabilityPolicy


UTC = timezone.utc
BASE_PRICES = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
}


def series(
    pair: ForexPair,
    now: datetime,
    *,
    direction: str = "FLAT",
    positive_volume: bool = True,
) -> list[ForexBar]:
    base = BASE_PRICES[pair.symbol]
    prices = [base] * 31
    if direction == "UP":
        prices[-1] = base + pair.pip_size * Decimal("20")
    elif direction == "DOWN":
        prices[-1] = base - pair.pip_size * Decimal("20")
    return [
        ForexBar.create(
            pair=pair,
            timestamp=now - timedelta(seconds=(30 - index) * 900),
            open=price,
            high=price + pair.pip_size,
            low=price - pair.pip_size,
            close=price,
            tick_volume="100" if positive_volume else "0",
        )
        for index, price in enumerate(prices)
    ]


def quote_for(
    pair: ForexPair,
    now: datetime,
    *,
    price: Decimal | None = None,
    spread_pips: Decimal = Decimal("1"),
) -> ForexQuote:
    midpoint = price if price is not None else BASE_PRICES[pair.symbol]
    half_spread = pair.pip_size * spread_pips / Decimal("2")
    return ForexQuote.create(
        pair=pair,
        bid=midpoint - half_spread,
        ask=midpoint + half_spread,
        timestamp=now,
    )


def ready_context(now: datetime, *, source_count: int = 2) -> ForexSafetyContext:
    return ForexSafetyContext(
        observed_at=now,
        market_open=True,
        calendar_ready=True,
        high_impact_event_blocked=False,
        conversion_to_pln_ready=True,
        independent_source_count=source_count,
    )


def complete_market(
    now: datetime,
    *,
    direction_by_pair: dict[str, str] | None = None,
) -> tuple[
    dict[str, ForexQuote],
    dict[str, list[ForexBar]],
    dict[str, ForexSafetyContext],
]:
    directions = direction_by_pair or {}
    quotes: dict[str, ForexQuote] = {}
    bars: dict[str, list[ForexBar]] = {}
    contexts: dict[str, ForexSafetyContext] = {}
    for pair in MAJOR_FOREX_PAIRS:
        selected_bars = series(
            pair, now, direction=directions.get(pair.symbol, "FLAT")
        )
        bars[pair.symbol] = selected_bars
        quotes[pair.symbol] = quote_for(
            pair, now, price=selected_bars[-1].close
        )
        contexts[pair.symbol] = ready_context(now)
    return quotes, bars, contexts


def rate_book(now: datetime, quotes: dict[str, ForexQuote] | None = None) -> ForexRateBook:
    selected = list((quotes or complete_market(now)[0]).values())
    selected.append(ForexQuote.create(
        pair=USD_PLN_CONVERSION_PAIR,
        bid="3.999",
        ask="4.001",
        timestamp=now,
    ))
    return ForexRateBook(selected, now=now)


class ForexModelTests(unittest.TestCase):
    def test_universe_has_seven_unique_major_pairs_and_correct_pips(self) -> None:
        self.assertEqual(len(MAJOR_FOREX_PAIRS), 7)
        self.assertEqual(len({pair.symbol for pair in MAJOR_FOREX_PAIRS}), 7)
        self.assertEqual(major_pair("EUR/USD").pip_size, Decimal("0.0001"))
        self.assertEqual(major_pair("USD_JPY").pip_size, Decimal("0.01"))
        self.assertFalse(USD_PLN_CONVERSION_PAIR.tradable)

    def test_invalid_pair_quote_and_position_fail_closed(self) -> None:
        now = datetime.now(UTC)
        with self.assertRaisesRegex(TradingValidationError, "currencies_must_differ"):
            normalized_pair("EUR/EUR")
        pair = major_pair("EUR_USD")
        with self.assertRaisesRegex(TradingValidationError, "crossed_market"):
            ForexQuote.create(pair=pair, bid="1.2", ask="1.1", timestamp=now)
        with self.assertRaisesRegex(TradingValidationError, "long_stop_must_be_lower"):
            ForexPosition(
                pair=pair,
                side="LONG",
                units=Decimal("1000"),
                entry_price=Decimal("1.1"),
                current_price=Decimal("1.1"),
                stop_loss=Decimal("1.11"),
                opened_at=now,
            )
        with self.assertRaisesRegex(TradingValidationError, "boolean_required"):
            ForexSafetyContext(
                observed_at=now,
                market_open="yes",  # type: ignore[arg-type]
                calendar_ready=True,
                high_impact_event_blocked=False,
                conversion_to_pln_ready=True,
                independent_source_count=2,
            )


class ForexScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
        self.scanner = ForexMarketScanner()

    def test_missing_data_blocks_every_configured_pair(self) -> None:
        result = self.scanner.scan(
            quotes={}, bars={}, contexts={}, now=self.now
        )
        self.assertEqual(len(result), 7)
        self.assertTrue(all(item.status == "BLOCKED" for item in result))
        self.assertTrue(all(item.action == "WAIT" for item in result))
        self.assertTrue(all("DATA_MISSING" in item.reason_codes for item in result))

    def test_scanner_ranks_one_bullish_pair_across_full_universe(self) -> None:
        quotes, bars, contexts = complete_market(
            self.now, direction_by_pair={"EUR_USD": "UP"}
        )
        result = self.scanner.scan(
            quotes=quotes, bars=bars, contexts=contexts, now=self.now
        )

        self.assertEqual(len(result), 7)
        self.assertEqual(result[0].pair.symbol, "EUR_USD")
        self.assertEqual(result[0].action, "OPEN_LONG")
        self.assertTrue(result[0].can_open)
        self.assertEqual(sum(item.can_open for item in result), 1)

    def test_missing_second_source_blocks_open_but_not_analysis(self) -> None:
        pair = major_pair("EUR_USD")
        bars = series(pair, self.now, direction="UP")
        assessment = self.scanner.assess(
            pair=pair,
            quote=quote_for(pair, self.now, price=bars[-1].close),
            bars=bars,
            context=ready_context(self.now, source_count=1),
            now=self.now,
        )

        self.assertEqual(assessment.status, "READY")
        self.assertEqual(assessment.action, "WAIT")
        self.assertIn("SECOND_SOURCE_UNAVAILABLE", assessment.reason_codes)

    def test_stale_quote_wide_spread_and_missing_volume_are_blocked(self) -> None:
        pair = major_pair("EUR_USD")
        bars = series(pair, self.now)
        cases = (
            (
                ForexQuote.create(
                    pair=pair,
                    bid="1.0999",
                    ask="1.1001",
                    timestamp=self.now - timedelta(minutes=1),
                ),
                bars,
                "STALE_QUOTE",
            ),
            (quote_for(pair, self.now, spread_pips=Decimal("5")), bars, "SPREAD_TOO_WIDE"),
            (
                quote_for(pair, self.now),
                series(pair, self.now, positive_volume=False),
                "INSUFFICIENT_TICK_VOLUME",
            ),
        )
        for selected_quote, selected_bars, expected in cases:
            with self.subTest(expected=expected):
                result = self.scanner.assess(
                    pair=pair,
                    quote=selected_quote,
                    bars=selected_bars,
                    context=ready_context(self.now),
                    now=self.now,
                )
                self.assertEqual(result.status, "BLOCKED")
                self.assertIn(expected, result.reason_codes)

    def test_exit_is_ranked_before_a_new_entry(self) -> None:
        quotes, bars, contexts = complete_market(
            self.now,
            direction_by_pair={"EUR_USD": "DOWN", "GBP_USD": "UP"},
        )
        result = self.scanner.scan(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            positions={"EUR_USD": "LONG"},
            now=self.now,
        )
        self.assertEqual(result[0].pair.symbol, "EUR_USD")
        self.assertEqual(result[0].action, "CLOSE_LONG")
        self.assertEqual(result[1].pair.symbol, "GBP_USD")
        self.assertEqual(result[1].action, "OPEN_LONG")


class ForexPortfolioRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
        self.quotes = complete_market(self.now)[0]
        self.rates = rate_book(self.now, self.quotes)
        self.engine = ForexPortfolioRiskEngine()

    def test_rate_book_converts_through_usd_to_pln(self) -> None:
        eur_pln = self.rates.rate("EUR", "PLN")
        jpy_pln = self.rates.rate("JPY", "PLN")
        self.assertAlmostEqual(float(eur_pln), 4.4, places=3)
        self.assertAlmostEqual(float(jpy_pln), 4.0 / 150.0, places=5)

    def test_position_is_sized_by_risk_and_currency_exposure(self) -> None:
        decision = self.engine.evaluate_open(
            pair=major_pair("EUR_USD"),
            side="LONG",
            entry_price="1.1000",
            stop_loss="1.0980",
            equity_pln="100000",
            daily_pnl_pln="0",
            positions=(),
            rates=self.rates,
            now=self.now,
        )

        self.assertTrue(decision.allowed)
        self.assertGreaterEqual(decision.units, Decimal("100"))
        self.assertLessEqual(decision.units, Decimal("10000"))
        self.assertLessEqual(decision.risk_pln, Decimal("250"))
        self.assertTrue(all(
            exposure <= Decimal("10000")
            for exposure in decision.projected_currency_exposure_pln.values()
        ))

    def test_shared_usd_exposure_blocks_correlated_second_position(self) -> None:
        existing = ForexPosition(
            pair=major_pair("EUR_USD"),
            side="LONG",
            units=Decimal("2200"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0980"),
            opened_at=self.now,
        )
        decision = self.engine.evaluate_open(
            pair=major_pair("GBP_USD"),
            side="LONG",
            entry_price="1.2800",
            stop_loss="1.2780",
            equity_pln="100000",
            daily_pnl_pln="0",
            positions=(existing,),
            rates=self.rates,
            now=self.now,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "EXPOSURE_LIMIT")

    def test_daily_loss_duplicate_pair_and_position_count_fail_closed(self) -> None:
        pair = major_pair("EUR_USD")
        position = ForexPosition(
            pair=pair,
            side="LONG",
            units=Decimal("100"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0980"),
            opened_at=self.now,
        )
        common = {
            "pair": pair,
            "side": "LONG",
            "entry_price": "1.1000",
            "stop_loss": "1.0980",
            "equity_pln": "100000",
            "rates": self.rates,
            "now": self.now,
        }
        loss = self.engine.evaluate_open(
            **common, daily_pnl_pln="-1000", positions=()
        )
        duplicate = self.engine.evaluate_open(
            **common, daily_pnl_pln="0", positions=(position,)
        )
        self.assertEqual(loss.code, "DAILY_LOSS_LIMIT")
        self.assertEqual(duplicate.code, "PAIR_ALREADY_OPEN")
        with self.assertRaises(TypeError):
            ForexPaperPolicy(live_trading_enabled=True)  # type: ignore[call-arg]


class ForexCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
        self.scanner = ForexMarketScanner()
        self.coordinator = ForexPaperCoordinator()

    def test_best_approved_candidate_becomes_paper_instruction_only(self) -> None:
        quotes, bars, contexts = complete_market(
            self.now, direction_by_pair={"EUR_USD": "UP"}
        )
        assessments = self.scanner.scan(
            quotes=quotes, bars=bars, contexts=contexts, now=self.now
        )
        result = self.coordinator.plan(
            assessments=assessments,
            quotes=quotes,
            positions={},
            rates=rate_book(self.now, quotes),
            equity_pln="100000",
            daily_pnl_pln="0",
            now=self.now,
        )

        self.assertEqual(result["status"], "ENTRIES_READY")
        self.assertEqual(result["instructions"][0]["pair"], "EUR_USD")
        self.assertEqual(result["instructions"][0]["action"], "OPEN_LONG")
        self.assertFalse(result["live_orders_sent"])
        self.assertFalse(result["network_access"])

    def test_close_instruction_has_priority_over_new_entry(self) -> None:
        quotes, bars, contexts = complete_market(
            self.now,
            direction_by_pair={"EUR_USD": "DOWN", "GBP_USD": "UP"},
        )
        position = ForexPosition(
            pair=major_pair("EUR_USD"),
            side="LONG",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=quotes["EUR_USD"].midpoint,
            stop_loss=Decimal("1.0980"),
            opened_at=self.now - timedelta(hours=1),
        )
        assessments = self.scanner.scan(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            positions={"EUR_USD": "LONG"},
            now=self.now,
        )
        result = self.coordinator.plan(
            assessments=assessments,
            quotes=quotes,
            positions={"EUR_USD": position},
            rates=rate_book(self.now, quotes),
            equity_pln="100000",
            daily_pnl_pln="0",
            now=self.now,
        )
        self.assertEqual(result["status"], "CLOSES_READY")
        self.assertEqual(len(result["instructions"]), 1)
        self.assertEqual(result["instructions"][0]["action"], "CLOSE_POSITION")
        with self.assertRaises(LiveTradingBlockedError):
            self.coordinator.submit_live_order({"pair": "EUR_USD"})

    def test_stop_loss_closes_even_when_trend_signal_says_watch(self) -> None:
        pair = major_pair("EUR_USD")
        quote = ForexQuote.create(
            pair=pair,
            bid="1.0979",
            ask="1.0981",
            timestamp=self.now,
        )
        position = ForexPosition(
            pair=pair,
            side="LONG",
            units=Decimal("1000"),
            entry_price=Decimal("1.1000"),
            current_price=Decimal("1.0980"),
            stop_loss=Decimal("1.0980"),
            opened_at=self.now - timedelta(hours=1),
        )
        from app.trading.forex_scanner import ForexPairAssessment

        assessment = ForexPairAssessment(
            pair=pair,
            status="READY",
            action="WATCH",
            trend="UP",
            score=Decimal("10"),
            reason_codes=("LONG_TREND_INTACT",),
            assessed_at=self.now,
        )
        rates = ForexRateBook([
            quote,
            ForexQuote.create(
                pair=USD_PLN_CONVERSION_PAIR,
                bid="3.999",
                ask="4.001",
                timestamp=self.now,
            ),
        ], now=self.now)
        result = self.coordinator.plan(
            assessments=(assessment,),
            quotes={pair.symbol: quote},
            positions={pair.symbol: position},
            rates=rates,
            equity_pln="100000",
            daily_pnl_pln="0",
            now=self.now,
        )
        self.assertEqual(result["status"], "CLOSES_READY")
        self.assertEqual(
            result["instructions"][0]["reason_codes"],
            ["STOP_LOSS_TRIGGERED"],
        )

    def test_owner_status_reports_forex_readiness_and_client_is_blocked(self) -> None:
        command = "Status Forex"
        self.assertEqual(
            NaturalLanguageService.classify(command), "paper_trading_status"
        )
        self.assertTrue(PersonalAssistantController.matches(command))
        with TemporaryDirectory() as directory:
            response = PersonalAssistantController(Path(directory)).handle(command)
        self.assertIn("skaner 7 głównych par", response)
        self.assertIn("automatyczne wejścia pozostają zablokowane", response)
        self.assertIn(
            "tylko w trybie właściciela",
            ClientCapabilityPolicy.denial_message(command),
        )


class ForexSourceSafetyTests(unittest.TestCase):
    def test_forex_modules_do_not_import_network_or_broker_sdks(self) -> None:
        root = Path(__file__).resolve().parents[1] / "app" / "trading"
        imported_roots: set[str] = set()
        source = ""
        for path in root.glob("forex_*.py"):
            text = path.read_text(encoding="utf-8")
            source += text.casefold()
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(
                        alias.name.split(".", 1)[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".", 1)[0])
        self.assertTrue(
            {"requests", "httpx", "urllib", "socket", "oandapyv20"}.isdisjoint(
                imported_roots
            )
        )
        self.assertNotIn("api-fxtrade.oanda.com", source)
        self.assertNotIn("api-fxpractice.oanda.com", source)


if __name__ == "__main__":
    unittest.main()

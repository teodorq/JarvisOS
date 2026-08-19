from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.trading.forex_historical import (
    BidirectionalForexHistoricalBacktester,
    FixedForexCrossoverSignalGenerator,
    ForexHistoricalPolicy,
    ForexHistoricalSignal,
    ForexHistoricalWalkForwardValidator,
    ForexWalkForwardPolicy,
)
from app.trading.models import MarketBar, TradingValidationError


UTC = timezone.utc


def bars(prices: list[str], *, symbol: str = "EUR_USD") -> tuple[MarketBar, ...]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    currency = symbol.split("_")[1]
    result = []
    for index, raw in enumerate(prices):
        price = Decimal(raw)
        result.append(MarketBar.create(
            symbol=symbol,
            timestamp=start + timedelta(minutes=15 * index),
            open=price,
            high=price + Decimal("0.001"),
            low=price - Decimal("0.001"),
            close=price,
            volume="100",
            currency=currency,
        ))
    return tuple(result)


def oscillating(count: int) -> tuple[MarketBar, ...]:
    prices = []
    pattern = tuple(Decimal(str(value)) for value in (1, 2, 3, 4, 5, 4, 3, 2))
    for index in range(count):
        prices.append(
            str(
                Decimal("1.1000")
                + pattern[index % len(pattern)] / Decimal("1000")
            )
        )
    return bars(prices)


class ForexSignalGeneratorTests(unittest.TestCase):
    def test_signals_use_closed_past_bars_and_are_deterministic(self) -> None:
        policy = ForexHistoricalPolicy(fast_window=2, slow_window=4)
        generator = FixedForexCrossoverSignalGenerator(policy)
        series = bars([
            "1.00", "1.00", "1.00", "1.00", "1.02", "1.04",
            "1.02", "1.00", "0.98", "0.96", "0.98", "1.00", "1.02",
        ])

        first = generator.generate(series)
        second = generator.generate(series)

        self.assertEqual(first, second)
        self.assertTrue(any(item.action == "OPEN_LONG" for item in first))
        self.assertTrue(any(item.action == "OPEN_SHORT" for item in first))
        self.assertTrue(generator.audit()["current_or_past_bars_only"])
        self.assertFalse(generator.audit()["future_bar_access"])
        self.assertFalse(generator.audit()["parameter_optimization_performed"])
        for end in range(policy.slow_window + 1, len(series) + 1):
            prefix = series[:end]
            prefix_signals = generator.generate(prefix)
            expected = tuple(
                item for item in first if item.timestamp <= prefix[-1].timestamp
            )
            self.assertEqual(prefix_signals, expected)

    def test_invalid_history_fails_closed(self) -> None:
        generator = FixedForexCrossoverSignalGenerator(
            ForexHistoricalPolicy(fast_window=2, slow_window=4)
        )
        series = bars(["1.00", "1.01", "1.02", "1.03", "1.04"])
        with self.assertRaisesRegex(TradingValidationError, "strictly_ordered"):
            generator.generate(tuple(reversed(series)))
        wrong = list(series)
        wrong[-1] = MarketBar.create(
            symbol="GBP_USD",
            timestamp=wrong[-1].timestamp,
            open="1",
            high="1",
            low="1",
            close="1",
            volume="1",
            currency="USD",
        )
        with self.assertRaisesRegex(TradingValidationError, "one_pair"):
            generator.generate(wrong)


class ForexHistoricalBacktesterTests(unittest.TestCase):
    def test_long_short_reversals_fill_only_on_next_bar(self) -> None:
        series = bars([
            "1.0000", "1.0100", "1.0200", "1.0300", "1.0200", "1.0100",
        ])
        signals = (
            ForexHistoricalSignal(
                signal_id="long-1",
                symbol="EUR_USD",
                action="OPEN_LONG",
                timestamp=series[0].timestamp,
                fast_average="1.1",
                slow_average="1.0",
            ),
            ForexHistoricalSignal(
                signal_id="short-1",
                symbol="EUR_USD",
                action="OPEN_SHORT",
                timestamp=series[3].timestamp,
                fast_average="0.9",
                slow_average="1.0",
            ),
        )
        result = BidirectionalForexHistoricalBacktester().run(series, signals)

        self.assertEqual(result["status"], "FOREX_HISTORICAL_BACKTEST_COMPLETED")
        self.assertEqual(result["trade_count"], 2)
        self.assertTrue(result["long_and_short_supported"])
        self.assertTrue(result["same_bar_execution_blocked"])
        self.assertTrue(result["synthetic_cost_model"])
        self.assertFalse(result["portfolio_pln_aggregation_performed"])
        self.assertFalse(result["broker_connection_used"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertGreater(
            result["fills"][0]["filled_at"],
            signals[0].timestamp.isoformat(),
        )
        self.assertEqual(result["trades"][-1]["exit_reason"], "FORCED_WINDOW_CLOSE")

    def test_last_bar_signal_is_rejected(self) -> None:
        series = bars(["1.0000", "1.0100", "1.0200"])
        last = ForexHistoricalSignal(
            signal_id="last",
            symbol="EUR_USD",
            action="OPEN_LONG",
            timestamp=series[-1].timestamp,
            fast_average="1.1",
            slow_average="1.0",
        )
        result = BidirectionalForexHistoricalBacktester().run(series, (last,))
        self.assertEqual(result["trade_count"], 0)
        self.assertEqual(
            result["rejections"],
            [{"signal_id": "last", "code": "NO_NEXT_BAR"}],
        )

    def test_signal_outside_window_and_invalid_bar_type_fail_closed(self) -> None:
        series = bars(["1.0000", "1.0100", "1.0200"])
        early = ForexHistoricalSignal(
            signal_id="early",
            symbol="EUR_USD",
            action="OPEN_LONG",
            timestamp=series[0].timestamp - timedelta(minutes=15),
            fast_average="1.1",
            slow_average="1.0",
        )
        result = BidirectionalForexHistoricalBacktester().run(series, (early,))
        self.assertEqual(
            result["rejections"],
            [{"signal_id": "early", "code": "SIGNAL_OUTSIDE_WINDOW"}],
        )
        with self.assertRaisesRegex(TradingValidationError, "market_bar_required"):
            BidirectionalForexHistoricalBacktester().run(
                (series[0], object()),  # type: ignore[arg-type]
                (),
            )

    def test_synthetic_costs_are_conservative_on_a_flat_market(self) -> None:
        series = bars(["1.0000", "1.0000", "1.0000"])
        selected = ForexHistoricalSignal(
            signal_id="flat-long",
            symbol="EUR_USD",
            action="OPEN_LONG",
            timestamp=series[0].timestamp,
            fast_average="1.1",
            slow_average="1.0",
        )
        without_costs = BidirectionalForexHistoricalBacktester(
            ForexHistoricalPolicy(
                assumed_spread_pips=Decimal("0"),
                assumed_slippage_pips=Decimal("0"),
            )
        ).run(series, (selected,))
        with_costs = BidirectionalForexHistoricalBacktester().run(
            series,
            (selected,),
        )
        self.assertEqual(without_costs["net_profit_quote"], "0.00")
        self.assertLess(Decimal(with_costs["net_profit_quote"]), Decimal("0"))
        self.assertGreater(
            Decimal(with_costs["estimated_spread_slippage_cost_quote"]),
            Decimal("0"),
        )


class ForexWalkForwardTests(unittest.TestCase):
    def test_fixed_strategy_is_generated_inside_isolated_windows(self) -> None:
        series = oscillating(220)
        validator = ForexHistoricalWalkForwardValidator(
            ForexHistoricalPolicy(fast_window=2, slow_window=4),
            walk_forward_policy=ForexWalkForwardPolicy(
                training_bar_count=80,
                testing_bar_count=40,
                step_bar_count=40,
                minimum_window_count=3,
            ),
        )

        first = validator.run(series)
        second = validator.run(series)

        self.assertEqual(first, second)
        self.assertEqual(first["window_count"], 3)
        self.assertGreater(first["out_of_sample_trade_count"], 0)
        self.assertTrue(first["past_only_warmup_used"])
        self.assertTrue(first["chronological_splits_valid"])
        self.assertTrue(first["out_of_sample_windows_non_overlapping"])
        self.assertFalse(first["parameter_optimization_performed"])
        self.assertFalse(first["strategy_performance_validated"])
        self.assertFalse(first["automatic_paper_promotion"])
        for previous, current in zip(first["windows"], first["windows"][1:]):
            self.assertLess(
                previous["testing_ended_at"],
                current["testing_started_at"],
            )
        for window in first["windows"]:
            for trade in window["testing"]["trades"]:
                self.assertGreater(trade["opened_at"], trade["signal_at"])

    def test_overlapping_windows_and_insufficient_history_are_blocked(self) -> None:
        with self.assertRaisesRegex(TradingValidationError, "overlapping_test_windows"):
            ForexWalkForwardPolicy(
                training_bar_count=80,
                testing_bar_count=40,
                step_bar_count=20,
            )
        validator = ForexHistoricalWalkForwardValidator(
            walk_forward_policy=ForexWalkForwardPolicy(
                training_bar_count=100,
                testing_bar_count=50,
                step_bar_count=50,
                minimum_window_count=2,
            )
        )
        with self.assertRaisesRegex(TradingValidationError, "insufficient_bars"):
            validator.run(oscillating(149))


if __name__ == "__main__":
    unittest.main()

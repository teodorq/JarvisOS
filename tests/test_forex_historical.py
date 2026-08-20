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


def ohlc_bars(
    rows: list[tuple[str, str, str, str]],
) -> tuple[MarketBar, ...]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    return tuple(
        MarketBar.create(
            symbol="EUR_USD",
            timestamp=start + timedelta(minutes=15 * index),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume="100",
            currency="USD",
        )
        for index, (open_price, high, low, close) in enumerate(rows)
    )


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
    def test_opposite_crossover_closes_without_same_bar_reentry(self) -> None:
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
        result = BidirectionalForexHistoricalBacktester(
            ForexHistoricalPolicy(
                minimum_stop_pips=Decimal("100"),
                maximum_stop_pips=Decimal("100"),
                take_profit_reward_risk=Decimal("5"),
            )
        ).run(series, signals)

        self.assertEqual(result["status"], "FOREX_HISTORICAL_BACKTEST_COMPLETED")
        self.assertEqual(result["trade_count"], 1)
        self.assertTrue(result["long_and_short_supported"])
        self.assertTrue(result["same_bar_execution_blocked"])
        self.assertTrue(result["synthetic_cost_model"])
        self.assertFalse(result["portfolio_pln_aggregation_performed"])
        self.assertFalse(result["broker_connection_used"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertTrue(result["stop_loss_formula_matches_paper_coordinator"])
        self.assertFalse(result["position_sizing_matches_paper_coordinator"])
        self.assertTrue(result["take_profit_research_only"])
        self.assertGreater(
            result["fills"][0]["filled_at"],
            signals[0].timestamp.isoformat(),
        )
        self.assertEqual(result["trades"][-1]["exit_reason"], "OPPOSITE_CROSSOVER")
        self.assertFalse(any(
            fill["action"] == "OPEN_SHORT" for fill in result["fills"]
        ))

    def test_short_position_can_open_from_flat_and_close_at_window_end(self) -> None:
        series = bars(["1.0000", "1.0000", "1.0000"])
        selected = ForexHistoricalSignal(
            signal_id="flat-short",
            symbol="EUR_USD",
            action="OPEN_SHORT",
            timestamp=series[0].timestamp,
            fast_average="0.9",
            slow_average="1.0",
        )
        result = BidirectionalForexHistoricalBacktester(
            ForexHistoricalPolicy(
                minimum_stop_pips=Decimal("100"),
                maximum_stop_pips=Decimal("100"),
                take_profit_reward_risk=Decimal("5"),
            )
        ).run(series, (selected,))
        self.assertEqual(result["trade_count"], 1)
        self.assertEqual(result["trades"][0]["side"], "SHORT")
        self.assertEqual(result["trades"][0]["exit_reason"], "FORCED_WINDOW_CLOSE")

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
                minimum_stop_pips=Decimal("100"),
                maximum_stop_pips=Decimal("100"),
                take_profit_reward_risk=Decimal("5"),
            )
        ).run(series, (selected,))
        with_costs = BidirectionalForexHistoricalBacktester(
            ForexHistoricalPolicy(
                minimum_stop_pips=Decimal("100"),
                maximum_stop_pips=Decimal("100"),
                take_profit_reward_risk=Decimal("5"),
            )
        ).run(series, (selected,))
        self.assertEqual(without_costs["net_profit_quote"], "0.00")
        self.assertLess(Decimal(with_costs["net_profit_quote"]), Decimal("0"))
        self.assertGreater(
            Decimal(with_costs["estimated_spread_slippage_cost_quote"]),
            Decimal("0"),
        )

    def test_stop_target_and_ambiguous_bar_use_conservative_order(self) -> None:
        scenarios = (
            (
                "stop",
                ("1.0000", "1.0005", "0.9985", "0.9995"),
                "STOP_LOSS_TRIGGERED",
            ),
            (
                "target",
                ("1.0000", "1.0025", "0.9995", "1.0020"),
                "TAKE_PROFIT_TRIGGERED",
            ),
            (
                "both",
                ("1.0000", "1.0030", "0.9980", "1.0000"),
                "STOP_LOSS_AMBIGUOUS_BAR",
            ),
        )
        policy = ForexHistoricalPolicy(
            assumed_spread_pips=Decimal("0"),
            assumed_slippage_pips=Decimal("0"),
            minimum_stop_pips=Decimal("10"),
            maximum_stop_pips=Decimal("10"),
            take_profit_reward_risk=Decimal("2"),
        )
        for name, trigger_bar, expected_reason in scenarios:
            with self.subTest(name=name):
                series = ohlc_bars([
                    ("1.0000", "1.0001", "0.9999", "1.0000"),
                    trigger_bar,
                    (trigger_bar[3], trigger_bar[3], trigger_bar[3], trigger_bar[3]),
                ])
                selected = ForexHistoricalSignal(
                    signal_id=f"risk-{name}",
                    symbol="EUR_USD",
                    action="OPEN_LONG",
                    timestamp=series[0].timestamp,
                    fast_average="1.1",
                    slow_average="1.0",
                )
                result = BidirectionalForexHistoricalBacktester(policy).run(
                    series,
                    (selected,),
                )
                self.assertEqual(result["trade_count"], 1)
                self.assertEqual(result["trades"][0]["exit_reason"], expected_reason)
                self.assertEqual(result["trades"][0]["stop_loss"], "0.999000")
                self.assertEqual(result["trades"][0]["take_profit"], "1.002000")
        self.assertTrue(result["ambiguous_stop_target_bar_uses_stop_first"])

    def test_stop_gap_uses_worse_open_and_blocks_same_cycle_entry(self) -> None:
        series = ohlc_bars([
            ("1.0000", "1.0001", "0.9999", "1.0000"),
            ("1.0000", "1.0005", "0.9995", "1.0000"),
            ("0.9950", "0.9960", "0.9940", "0.9950"),
        ])
        signals = (
            ForexHistoricalSignal(
                signal_id="gap-long",
                symbol="EUR_USD",
                action="OPEN_LONG",
                timestamp=series[0].timestamp,
                fast_average="1.1",
                slow_average="1.0",
            ),
            ForexHistoricalSignal(
                signal_id="gap-short",
                symbol="EUR_USD",
                action="OPEN_SHORT",
                timestamp=series[1].timestamp,
                fast_average="0.9",
                slow_average="1.0",
            ),
        )
        policy = ForexHistoricalPolicy(
            assumed_spread_pips=Decimal("0"),
            assumed_slippage_pips=Decimal("0"),
            minimum_stop_pips=Decimal("10"),
            maximum_stop_pips=Decimal("10"),
        )
        result = BidirectionalForexHistoricalBacktester(policy).run(
            series,
            signals,
        )
        self.assertEqual(result["trades"][0]["exit_reason"], "STOP_LOSS_GAP")
        self.assertEqual(result["trades"][0]["exit_execution_price"], "0.995000")
        self.assertIn(
            {"signal_id": "gap-short", "code": "RISK_EXIT_PRIORITY"},
            result["rejections"],
        )
        self.assertFalse(any(
            fill["action"] == "OPEN_SHORT" for fill in result["fills"]
        ))


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

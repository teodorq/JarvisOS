from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.trading import (
    ChronologicalHoldoutValidator,
    HistoricalWalkForwardValidator,
    MarketBar,
    PaperTradingPolicy,
    StrategySignal,
    TradingValidationError,
    WalkForwardPolicy,
)


UTC = timezone.utc


def bars(count: int = 20) -> list[MarketBar]:
    start = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    result = []
    for index in range(count):
        price = Decimal("100") + Decimal(index)
        result.append(MarketBar.create(
            symbol="TEST",
            timestamp=start + timedelta(minutes=index),
            open=price,
            high=price + Decimal("1"),
            low=price - Decimal("1"),
            close=price,
            volume="100",
            currency="PLN",
        ))
    return result


def signal(series: list[MarketBar], index: int, side: str) -> StrategySignal:
    return StrategySignal.create(
        signal_id=f"walk-{side.lower()}-{index:04d}",
        symbol="TEST",
        side=side,
        quantity="1",
        timestamp=series[index].timestamp,
    )


class ChronologicalHoldoutTests(unittest.TestCase):
    def test_unseen_period_is_later_isolated_and_read_only(self) -> None:
        series = bars(10)
        result = ChronologicalHoldoutValidator(
            PaperTradingPolicy(initial_cash=Decimal("10000"))
        ).run(
            training_bars=series[:6],
            testing_bars=series[6:],
            testing_signals=(
                signal(series, 6, "BUY"),
                signal(series, 8, "SELL"),
            ),
        )

        self.assertEqual(result["status"], "CHRONOLOGICAL_HOLDOUT_COMPLETED")
        self.assertLess(result["training_ended_at"], result["testing_started_at"])
        self.assertTrue(result["chronological_split_valid"])
        self.assertFalse(result["period_overlap_detected"])
        self.assertTrue(result["test_account_isolated"])
        self.assertTrue(result["same_bar_execution_blocked"])
        self.assertFalse(result["external_signal_generation_audited"])
        self.assertEqual(result["testing"]["fill_count"], 2)
        self.assertTrue(result["testing"]["look_ahead_blocked"])
        self.assertFalse(result["automatic_paper_promotion"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])

    def test_overlap_and_signal_reuse_are_rejected(self) -> None:
        series = bars(10)
        selected = signal(series, 2, "BUY")
        validator = ChronologicalHoldoutValidator()
        with self.assertRaisesRegex(TradingValidationError, "periods_overlap"):
            validator.run(
                training_bars=series[:6],
                testing_bars=series[5:],
            )
        with self.assertRaisesRegex(
            TradingValidationError,
            "signal_reused_across_periods",
        ):
            validator.run(
                training_bars=series[:5],
                testing_bars=series[5:],
                training_signals=(selected,),
                testing_signals=(
                    StrategySignal.create(
                        signal_id=selected.signal_id,
                        symbol="TEST",
                        side="BUY",
                        quantity="1",
                        timestamp=series[6].timestamp,
                    ),
                ),
            )


class HistoricalWalkForwardTests(unittest.TestCase):
    def test_rolling_windows_are_non_overlapping_and_deterministic(self) -> None:
        series = bars()
        signals = tuple(
            signal(series, index, side)
            for index, side in (
                (6, "BUY"),
                (8, "SELL"),
                (10, "BUY"),
                (12, "SELL"),
                (14, "BUY"),
                (16, "SELL"),
            )
        )
        validator = HistoricalWalkForwardValidator(
            PaperTradingPolicy(initial_cash=Decimal("10000")),
            walk_forward_policy=WalkForwardPolicy(
                training_bar_count=6,
                testing_bar_count=4,
                step_bar_count=4,
                minimum_window_count=3,
            ),
        )

        first = validator.run(series, signals)
        second = validator.run(series, signals)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "WALK_FORWARD_COMPLETED")
        self.assertEqual(first["window_count"], 3)
        self.assertEqual(first["out_of_sample_fill_count"], 6)
        self.assertEqual(first["profitable_out_of_sample_window_count"], 3)
        self.assertTrue(first["chronological_splits_valid"])
        self.assertTrue(first["out_of_sample_windows_non_overlapping"])
        self.assertTrue(first["same_bar_execution_blocked"])
        self.assertTrue(first["research_only"])
        self.assertFalse(first["external_signal_generation_audited"])
        self.assertFalse(first["parameter_optimization_performed_by_validator"])
        self.assertFalse(first["automatic_paper_promotion"])
        self.assertFalse(first["paper_orders_sent"])
        self.assertFalse(first["live_orders_sent"])
        for previous, current in zip(first["windows"], first["windows"][1:]):
            self.assertLess(previous["testing_ended_at"], current["testing_started_at"])
        for window in first["windows"]:
            for fill in window["testing"]["fills"]:
                self.assertGreater(fill["filled_at"], fill["signal_at"])

    def test_invalid_policy_history_and_window_count_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            TradingValidationError,
            "overlapping_test_windows",
        ):
            WalkForwardPolicy(
                training_bar_count=6,
                testing_bar_count=4,
                step_bar_count=3,
            )
        series = bars(10)
        validator = HistoricalWalkForwardValidator(
            walk_forward_policy=WalkForwardPolicy(
                training_bar_count=6,
                testing_bar_count=4,
                step_bar_count=4,
                minimum_window_count=2,
            )
        )
        with self.assertRaisesRegex(
            TradingValidationError,
            "insufficient_window_count",
        ):
            validator.run(series, ())
        with self.assertRaisesRegex(
            TradingValidationError,
            "history_not_strictly_chronological",
        ):
            validator.run(tuple(reversed(series)), ())
        with self.assertRaisesRegex(
            TradingValidationError,
            "history_signal_required",
        ):
            validator.run(series, (object(),))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

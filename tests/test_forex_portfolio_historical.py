from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.trading.forex_models import HISTORICAL_FOREX_PAIRS
from app.trading.forex_portfolio_historical import (
    ForexPortfolioHistoricalBacktester,
    ForexPortfolioHistoricalPolicy,
    ForexPortfolioHistoricalWalkForwardValidator,
    ForexPortfolioWalkForwardPolicy,
)
from app.trading.forex_scanner import ForexScannerPolicy
from app.trading.models import MarketBar, TradingValidationError


def _histories(count: int = 100) -> dict[str, tuple[MarketBar, ...]]:
    started = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    bases = {
        "EUR_USD": Decimal("1.1000"),
        "GBP_USD": Decimal("1.2800"),
        "USD_JPY": Decimal("145.00"),
        "USD_CHF": Decimal("0.8800"),
        "AUD_USD": Decimal("0.6600"),
        "USD_CAD": Decimal("1.3500"),
        "NZD_USD": Decimal("0.6100"),
        "USD_PLN": Decimal("4.0000"),
    }
    result: dict[str, tuple[MarketBar, ...]] = {}
    for pair in HISTORICAL_FOREX_PAIRS:
        price = bases[pair.symbol]
        bars = []
        for index in range(count):
            if pair.symbol == "USD_PLN":
                change = Decimal("0")
            else:
                direction = Decimal("1") if (index // 10) % 2 else Decimal("-1")
                change = pair.pip_size * Decimal("12") * direction
            opened = price
            closed = price + change
            wick = pair.pip_size * Decimal("3")
            bars.append(MarketBar.create(
                symbol=pair.symbol,
                timestamp=started + timedelta(minutes=15 * index),
                open=opened,
                high=max(opened, closed) + wick,
                low=min(opened, closed) - wick,
                close=closed,
                volume="100",
                currency=pair.quote_currency,
            ))
            price = closed
        result[pair.symbol] = tuple(bars)
    return result


class ForexPortfolioHistoricalTests(unittest.TestCase):
    def policy(self) -> ForexPortfolioHistoricalPolicy:
        return ForexPortfolioHistoricalPolicy(
            scanner=ForexScannerPolicy(fast_window=3, slow_window=5),
        )

    def test_replays_paper_portfolio_sizing_and_take_profit_in_pln(self) -> None:
        result = ForexPortfolioHistoricalBacktester(self.policy()).run(_histories())

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["account_currency"], "PLN")
        self.assertTrue(result["portfolio_pln_aggregation_performed"])
        self.assertTrue(result["historical_pln_conversion_series_verified"])
        self.assertTrue(result["position_sizing_matches_paper_coordinator"])
        self.assertTrue(result["take_profit_matches_paper"])
        self.assertLessEqual(result["maximum_concurrent_positions_observed"], 2)
        self.assertGreater(result["trade_count"], 0)
        opens = [fill for fill in result["fills"] if fill["action"].startswith("OPEN_")]
        self.assertTrue(opens)
        for fill in opens:
            entry = Decimal(fill["entry_price"])
            stop = Decimal(fill["stop_loss"])
            target = Decimal(fill["take_profit"])
            self.assertAlmostEqual(
                abs(target - entry),
                abs(entry - stop) * Decimal("2"),
                places=12,
            )
            self.assertLessEqual(Decimal(fill["units"]), Decimal("10000"))
            self.assertLess(fill["signal_observed_through"], fill["executed_at"])
        self.assertFalse(result["broker_connection_used"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])

    def test_requires_the_historical_usd_pln_conversion_series(self) -> None:
        histories = _histories()
        histories.pop("USD_PLN")
        with self.assertRaisesRegex(TradingValidationError, "complete_pair_set_required"):
            ForexPortfolioHistoricalBacktester(self.policy()).run(histories)

    def test_rejects_unaligned_pair_timestamps(self) -> None:
        histories = _histories()
        first = histories["USD_PLN"][0]
        histories["USD_PLN"] = (
            MarketBar.create(
                symbol=first.symbol,
                timestamp=first.timestamp + timedelta(minutes=1),
                open=first.open,
                high=first.high,
                low=first.low,
                close=first.close,
                volume=first.volume,
                currency=first.currency,
            ),
            *histories["USD_PLN"][1:],
        )
        with self.assertRaisesRegex(TradingValidationError, "timestamps_not_aligned"):
            ForexPortfolioHistoricalBacktester(self.policy()).run(histories)

    def test_walk_forward_is_read_only_and_reports_fixed_checks(self) -> None:
        validator = ForexPortfolioHistoricalWalkForwardValidator(
            historical_policy=self.policy(),
            walk_forward_policy=ForexPortfolioWalkForwardPolicy(
                training_bar_count=50,
                testing_bar_count=20,
                step_bar_count=20,
                minimum_trade_count=1,
                minimum_profitable_window_ratio=Decimal("0.50"),
            ),
        )
        result = validator.run(_histories(100))

        self.assertEqual(result["window_count"], 2)
        self.assertTrue(result["chronological_splits_valid"])
        self.assertTrue(result["out_of_sample_windows_non_overlapping"])
        self.assertTrue(result["past_only_warmup_used"])
        self.assertFalse(result["parameter_optimization_performed"])
        self.assertFalse(result["automatic_paper_promotion"])
        self.assertFalse(result["broker_connection_used"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])


if __name__ == "__main__":
    unittest.main()

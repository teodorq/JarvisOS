from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.market_data.mt5_history import Mt5DemoHistoricalExporter
from app.trading.dataset import HistoricalCsvLoader
from app.trading.forex_models import (
    ForexBar,
    HISTORICAL_FOREX_PAIRS,
    MAJOR_FOREX_PAIRS,
)
from app.trading.models import TradingValidationError


UTC = timezone.utc
NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
BASE = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
    "USD_PLN": Decimal("4.0000"),
}


class FakeHistorySource:
    def __init__(
        self,
        *,
        incomplete: bool = False,
        unexpected_gap: bool = False,
        misaligned_pair: bool = False,
        duplicate_timestamp: bool = False,
        weekend_misaligned_pair: bool = False,
        shifted_pair_bars: int = 0,
        open_last_bar: bool = False,
    ) -> None:
        self.incomplete = incomplete
        self.unexpected_gap = unexpected_gap
        self.misaligned_pair = misaligned_pair
        self.duplicate_timestamp = duplicate_timestamp
        self.weekend_misaligned_pair = weekend_misaligned_pair
        self.shifted_pair_bars = shifted_pair_bars
        self.open_last_bar = open_last_bar
        self.calls: list[dict[str, object]] = []

    def fetch_history(self, pairs, *, bar_count: int, now: datetime):
        selected = tuple(pairs)
        self.calls.append({
            "pairs": tuple(pair.symbol for pair in selected),
            "bar_count": bar_count,
            "now": now,
        })
        if self.incomplete:
            selected = selected[:1]
        result = {}
        for pair in selected:
            base = BASE[pair.symbol]
            timestamps = [
                now
                - timedelta(minutes=(bar_count - index) * 15)
                - timedelta(
                    minutes=15 if self.unexpected_gap and index < 100 else 0
                )
                for index in range(bar_count)
            ]
            if self.weekend_misaligned_pair:
                split = bar_count // 2
                friday = datetime(2026, 8, 14, 20, 45, tzinfo=UTC)
                sunday = datetime(2026, 8, 16, 21, 0, tzinfo=UTC)
                timestamps = [
                    friday - timedelta(minutes=(split - index - 1) * 15)
                    for index in range(split)
                ] + [
                    sunday + timedelta(minutes=(index - split) * 15)
                    for index in range(split, bar_count)
                ]
            if self.misaligned_pair and pair.symbol == "USD_JPY":
                timestamps.pop(100)
                timestamps.insert(0, timestamps[0] - timedelta(minutes=15))
            if self.weekend_misaligned_pair and pair.symbol == "USD_JPY":
                split = bar_count // 2
                timestamps.pop(split)
                timestamps.insert(0, timestamps[0] - timedelta(minutes=15))
            if self.shifted_pair_bars and pair.symbol == "USD_JPY":
                timestamps = [
                    timestamp
                    - timedelta(minutes=self.shifted_pair_bars * 15)
                    for timestamp in timestamps
                ]
            if self.open_last_bar:
                timestamps[-1] = now
            if self.duplicate_timestamp and pair.symbol == "EUR_USD":
                timestamps[100] = timestamps[99]
            result[pair.symbol] = tuple(
                ForexBar.create(
                    pair=pair,
                    timestamp=timestamps[index],
                    open=base + pair.pip_size * index,
                    high=base + pair.pip_size * (index + 1),
                    low=base + pair.pip_size * max(0, index - 1),
                    close=base + pair.pip_size * index,
                    tick_volume="100",
                )
                for index in range(bar_count)
            )
        return result


class Mt5HistoryExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_export_is_atomic_fingerprinted_local_and_secret_free(self) -> None:
        source = FakeHistorySource()
        result = Mt5DemoHistoricalExporter(
            self.root,
            source=source,  # type: ignore[arg-type]
        ).export(MAJOR_FOREX_PAIRS, bar_count=200, now=NOW)

        self.assertEqual(result["status"], "MT5_DEMO_HISTORY_EXPORTED")
        self.assertEqual(result["pair_count"], 7)
        self.assertEqual(result["bar_count_per_pair"], 200)
        self.assertEqual(source.calls[0]["bar_count"], 232)
        self.assertEqual(result["source_bar_count_per_pair"], 232)
        self.assertEqual(
            result["timestamp_alignment"]["method"],
            "LATEST_COMMON_M15_TIMESTAMPS",
        )
        self.assertTrue(result["closed_bars_only"])
        self.assertTrue(result["fingerprints_verified"])
        self.assertFalse(result["account_identifier_stored"])
        self.assertFalse(result["credentials_stored"])
        self.assertFalse(result["order_network_access"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        export_path = Path(result["export_path"])
        self.assertTrue(export_path.is_dir())
        self.assertFalse(any(path.name.startswith(".mt5-history-") for path in export_path.parent.iterdir()))
        manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
        serialized = json.dumps(manifest).casefold()
        for forbidden in (
            '"password":',
            '"token":',
            '"secret":',
            '"account_id":',
            '"login":',
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(len(manifest["datasets"]), 7)
        for item in manifest["datasets"]:
            dataset = HistoricalCsvLoader().load(export_path / item["file"])
            self.assertEqual(len(dataset.bars), 200)
            self.assertEqual(dataset.symbol, item["pair"])
            self.assertEqual(dataset.currency, item["currency"])
            self.assertEqual(dataset.fingerprint_sha256, item["fingerprint_sha256"])
        verified = Mt5DemoHistoricalExporter(self.root).verify_latest()
        self.assertEqual(verified["status"], "MT5_DEMO_HISTORY_VERIFIED")
        self.assertEqual(verified["pair_count"], 7)
        self.assertTrue(verified["all_fingerprints_match"])
        self.assertTrue(verified["timestamps_aligned_across_pairs"])
        self.assertTrue(verified["research_quality_ready"])
        self.assertFalse(verified["historical_pln_conversion_ready"])
        self.assertFalse(verified["strategy_performance_validated"])
        self.assertEqual(verified["quality_issues"], [])
        self.assertTrue(all(item["matches_manifest"] for item in verified["datasets"]))
        self.assertTrue(all(item["positive_tick_volume_ratio"] == "1.000000" for item in verified["datasets"]))
        self.assertTrue(all(item["unexpected_gap_count"] == 0 for item in verified["datasets"]))
        self.assertFalse((self.root / "data/trading/forex_paper_ledger.json").exists())

    def test_portfolio_export_includes_non_tradable_usd_pln_history(self) -> None:
        result = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(),  # type: ignore[arg-type]
        ).export(HISTORICAL_FOREX_PAIRS, bar_count=200, now=NOW)
        self.assertEqual(result["pair_count"], 8)
        self.assertEqual(result["tradable_pair_count"], 7)
        self.assertTrue(result["conversion_pair_included"])
        verified = Mt5DemoHistoricalExporter(self.root).verify_latest()
        self.assertTrue(verified["historical_pln_conversion_ready"])
        self.assertEqual(verified["tradable_pair_count"], 7)

    def test_verification_detects_a_changed_csv(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(),  # type: ignore[arg-type]
        )
        result = exporter.export(MAJOR_FOREX_PAIRS, bar_count=200, now=NOW)
        first = Path(result["export_path"]) / "eur_usd_m15.csv"
        content = first.read_text(encoding="utf-8")
        first.write_text(content.replace(",100,USD\n", ",101,USD\n", 1), encoding="utf-8")

        with self.assertRaisesRegex(TradingValidationError, "fingerprint_mismatch"):
            exporter.verify_latest()

    def test_verification_reports_an_unexpected_intraday_gap(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(unexpected_gap=True),  # type: ignore[arg-type]
        )
        exporter.export(MAJOR_FOREX_PAIRS, bar_count=200, now=NOW)

        verified = exporter.verify_latest()

        self.assertFalse(verified["research_quality_ready"])
        self.assertIn("UNEXPECTED_M15_GAPS", verified["quality_issues"])
        self.assertTrue(all(item["unexpected_gap_count"] == 1 for item in verified["datasets"]))

    def test_export_aligns_a_pair_with_one_missing_timestamp(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(misaligned_pair=True),  # type: ignore[arg-type]
        )
        result = exporter.export(HISTORICAL_FOREX_PAIRS, bar_count=200, now=NOW)

        timestamps = []
        for raw in result["datasets"]:
            dataset = HistoricalCsvLoader().load(
                Path(result["export_path"]) / raw["file"]
            )
            timestamps.append(tuple(bar.timestamp for bar in dataset.bars))
        self.assertTrue(all(series == timestamps[0] for series in timestamps))
        verified = exporter.verify_latest()
        self.assertTrue(verified["timestamps_aligned_across_pairs"])
        self.assertNotIn(
            "PAIR_TIMESTAMPS_NOT_ALIGNED",
            verified["quality_issues"],
        )

    def test_weekend_open_mismatch_is_aligned_without_quality_loss(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(  # type: ignore[arg-type]
                weekend_misaligned_pair=True,
            ),
        )

        result = exporter.export(
            HISTORICAL_FOREX_PAIRS,
            bar_count=200,
            now=NOW,
        )
        alignment = result["timestamp_alignment"]
        self.assertEqual(alignment["common_timestamp_count_before_trim"], 231)
        self.assertTrue(all(
            value == 1
            for value in alignment[
                "non_common_timestamp_count_per_pair"
            ].values()
        ))
        verified = exporter.verify_latest()
        self.assertTrue(verified["timestamps_aligned_across_pairs"])
        self.assertTrue(verified["research_quality_ready"])
        self.assertEqual(verified["quality_issues"], [])
        self.assertTrue(all(
            item["weekend_gap_count"] == 1
            and item["unexpected_gap_count"] == 0
            for item in verified["datasets"]
        ))

    def test_alignment_buffer_exhaustion_fails_before_export(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(shifted_pair_bars=33),  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(
            TradingValidationError,
            "insufficient_aligned_history",
        ):
            exporter.export(HISTORICAL_FOREX_PAIRS, bar_count=200, now=NOW)
        self.assertFalse((self.root / "data/trading/history").exists())

    def test_incomplete_source_fails_before_creating_an_export(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(incomplete=True),  # type: ignore[arg-type]
        )
        with self.assertRaisesRegex(
            TradingValidationError,
            "incomplete_history_set",
        ):
            exporter.export(MAJOR_FOREX_PAIRS, bar_count=200, now=NOW)
        self.assertFalse((self.root / "data/trading/history").exists())

    def test_duplicate_source_timestamp_fails_before_export(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(duplicate_timestamp=True),  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(
            TradingValidationError,
            "duplicate_history_bars",
        ):
            exporter.export(HISTORICAL_FOREX_PAIRS, bar_count=200, now=NOW)
        self.assertFalse((self.root / "data/trading/history").exists())

    def test_open_source_bar_fails_before_export(self) -> None:
        exporter = Mt5DemoHistoricalExporter(
            self.root,
            source=FakeHistorySource(open_last_bar=True),  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(
            TradingValidationError,
            "source_contains_open_bar",
        ):
            exporter.export(HISTORICAL_FOREX_PAIRS, bar_count=200, now=NOW)
        self.assertFalse((self.root / "data/trading/history").exists())


if __name__ == "__main__":
    unittest.main()

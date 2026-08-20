"""Atomic local export of closed MetaTrader 5 DEMO M15 history."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterable

from app.core.project_paths import resolve_project_root
from app.market_data.mt5_demo import Mt5DemoReadOnlySource
from app.trading.dataset import HistoricalCsvLoader
from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    HISTORICAL_FOREX_PAIRS,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.models import TradingValidationError, aware_utc


_MAJOR_SYMBOLS = frozenset(pair.symbol for pair in MAJOR_FOREX_PAIRS)
_HISTORICAL_SYMBOLS = frozenset(pair.symbol for pair in HISTORICAL_FOREX_PAIRS)
_EXPORT_DIRECTORY = re.compile(r"^mt5-demo-m15-[0-9]{8}T[0-9]{12}Z$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def _integer(value: object, code: str) -> int:
    if type(value) is not int:
        raise TradingValidationError(code)
    return value


class Mt5DemoHistoricalExporter:
    """Create an immutable, fingerprinted local dataset without order access."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        source: Mt5DemoReadOnlySource | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.history_root = self.project_root / "data" / "trading" / "history"
        self.source = source or Mt5DemoReadOnlySource()
        self.loader = HistoricalCsvLoader()

    def export(
        self,
        pairs: Iterable[ForexPair] = HISTORICAL_FOREX_PAIRS,
        *,
        bar_count: int = 5_000,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        selected = tuple(pairs)
        if any(not isinstance(pair, ForexPair) for pair in selected):
            raise TradingValidationError("mt5_history: invalid_major_pair_set")
        symbols = tuple(pair.symbol for pair in selected)
        if (
            not selected
            or len(set(symbols)) != len(symbols)
            or any(symbol not in _HISTORICAL_SYMBOLS for symbol in symbols)
            or type(bar_count) is not int
            or not 200 <= bar_count <= 50_000
        ):
            raise TradingValidationError("mt5_history: invalid_major_pair_set")
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        history = self.source.fetch_history(
            selected,
            bar_count=bar_count,
            now=selected_now,
        )
        if set(history) != set(symbols):
            raise TradingValidationError("mt5_history: incomplete_history_set")
        normalized_history = {
            symbol: tuple(history[symbol]) for symbol in symbols
        }
        if any(len(normalized_history[symbol]) != bar_count for symbol in symbols):
            raise TradingValidationError("mt5_history: incomplete_pair_history")

        self.history_root.mkdir(parents=True, exist_ok=True)
        export_id = "mt5-demo-m15-" + selected_now.strftime("%Y%m%dT%H%M%S%fZ")
        target = self.history_root / export_id
        if target.exists():
            raise TradingValidationError("mt5_history: export_id_collision")
        temporary = Path(tempfile.mkdtemp(
            prefix=".mt5-history-",
            dir=self.history_root,
        ))
        try:
            datasets = []
            for pair in selected:
                file_name = pair.symbol.lower() + "_m15.csv"
                path = temporary / file_name
                self._write_pair(path, pair, normalized_history[pair.symbol])
                dataset = self.loader.load(path)
                if (
                    dataset.symbol != pair.symbol
                    or dataset.currency != pair.quote_currency
                    or len(dataset.bars) != bar_count
                ):
                    raise TradingValidationError(
                        "mt5_history: exported_dataset_mismatch"
                    )
                datasets.append({
                    "pair": pair.symbol,
                    "currency": pair.quote_currency,
                    "timeframe": "M15",
                    "file": file_name,
                    "bar_count": len(dataset.bars),
                    "start_at": dataset.bars[0].timestamp.isoformat(),
                    "end_at": dataset.bars[-1].timestamp.isoformat(),
                    "fingerprint_sha256": dataset.fingerprint_sha256,
                })
            manifest = {
                "status": "MT5_DEMO_HISTORY_EXPORTED",
                "mode": "READ_ONLY_HISTORICAL_RESEARCH",
                "export_id": export_id,
                "provider": "MT5_DEMO",
                "timeframe": "M15",
                "exported_at": selected_now.isoformat(),
                "pair_count": len(selected),
                "tradable_pair_count": sum(pair.tradable for pair in selected),
                "conversion_pair_included": (
                    USD_PLN_CONVERSION_PAIR.symbol in symbols
                ),
                "bar_count_per_pair": bar_count,
                "pair_symbols": list(symbols),
                "datasets": datasets,
                "closed_bars_only": True,
                "fingerprints_verified": True,
                "demo_account_required": True,
                "account_identifier_stored": False,
                "credentials_stored": False,
                "order_network_access": False,
                "paper_orders_sent": False,
                "live_orders_sent": False,
            }
            self._write_manifest(temporary / "manifest.json", manifest)
            os.replace(temporary, target)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
            raise
        result = dict(manifest)
        result["export_path"] = str(target)
        result["manifest_path"] = str(target / "manifest.json")
        return result

    def verify_latest(self) -> dict[str, Any]:
        """Re-read the newest export and compare every current CSV fingerprint."""
        if not self.history_root.is_dir():
            raise TradingValidationError("mt5_history: no_export_available")
        candidates = sorted(
            path for path in self.history_root.iterdir()
            if path.is_dir() and _EXPORT_DIRECTORY.fullmatch(path.name)
        )
        if not candidates:
            raise TradingValidationError("mt5_history: no_export_available")
        return self.verify(candidates[-1])

    def verify(self, export_path: str | Path) -> dict[str, Any]:
        target = Path(export_path).expanduser().resolve(strict=False)
        try:
            target.relative_to(self.history_root.resolve(strict=False))
        except ValueError as error:
            raise TradingValidationError(
                "mt5_history: export_outside_history_root"
            ) from error
        if not target.is_dir() or not _EXPORT_DIRECTORY.fullmatch(target.name):
            raise TradingValidationError("mt5_history: invalid_export_directory")
        manifest_path = target / "manifest.json"
        resolved_manifest = manifest_path.resolve(strict=False)
        try:
            resolved_manifest.relative_to(target)
        except ValueError as error:
            raise TradingValidationError("mt5_history: invalid_manifest") from error
        if (
            not resolved_manifest.is_file()
            or resolved_manifest.stat().st_size <= 0
            or resolved_manifest.stat().st_size > 1_000_000
        ):
            raise TradingValidationError("mt5_history: invalid_manifest")
        try:
            manifest = json.loads(resolved_manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise TradingValidationError("mt5_history: invalid_manifest") from error
        if not isinstance(manifest, dict) or any(
            manifest.get(key) != expected
            for key, expected in (
                ("status", "MT5_DEMO_HISTORY_EXPORTED"),
                ("mode", "READ_ONLY_HISTORICAL_RESEARCH"),
                ("provider", "MT5_DEMO"),
                ("timeframe", "M15"),
                ("export_id", target.name),
                ("closed_bars_only", True),
                ("demo_account_required", True),
                ("account_identifier_stored", False),
                ("credentials_stored", False),
                ("order_network_access", False),
                ("paper_orders_sent", False),
                ("live_orders_sent", False),
            )
        ):
            raise TradingValidationError("mt5_history: invalid_manifest_contract")
        try:
            exported_at = aware_utc(
                datetime.fromisoformat(
                    str(manifest.get("exported_at", "")).replace("Z", "+00:00")
                ),
                "exported_at",
            )
        except (TypeError, ValueError, TradingValidationError) as error:
            raise TradingValidationError(
                "mt5_history: invalid_manifest_timestamp"
            ) from error
        raw_datasets = manifest.get("datasets", [])
        datasets = list(raw_datasets) if isinstance(raw_datasets, list) else []
        pair_count = _integer(
            manifest.get("pair_count"),
            "mt5_history: invalid_manifest_datasets",
        )
        bars_per_pair = _integer(
            manifest.get("bar_count_per_pair"),
            "mt5_history: invalid_manifest_datasets",
        )
        if (
            not datasets
            or len(datasets) != pair_count
            or len(datasets) > len(HISTORICAL_FOREX_PAIRS)
            or not 200 <= bars_per_pair <= 50_000
        ):
            raise TradingValidationError("mt5_history: invalid_manifest_datasets")
        verified = []
        seen_pairs: set[str] = set()
        timestamp_series: dict[str, tuple[datetime, ...]] = {}
        quality_issues: set[str] = set()
        for raw in datasets:
            if not isinstance(raw, dict):
                raise TradingValidationError("mt5_history: invalid_dataset_entry")
            pair = str(raw.get("pair", ""))
            file_name = str(raw.get("file", ""))
            fingerprint = str(raw.get("fingerprint_sha256", ""))
            if (
                pair not in _HISTORICAL_SYMBOLS
                or pair in seen_pairs
                or not file_name
                or Path(file_name).name != file_name
                or Path(file_name).suffix.casefold() != ".csv"
                or not _FINGERPRINT.fullmatch(fingerprint)
                or raw.get("timeframe") != "M15"
            ):
                raise TradingValidationError("mt5_history: invalid_dataset_entry")
            dataset_path = (target / file_name).resolve(strict=False)
            try:
                dataset_path.relative_to(target)
            except ValueError as error:
                raise TradingValidationError(
                    "mt5_history: dataset_outside_export"
                ) from error
            dataset = self.loader.load(dataset_path)
            dataset_bar_count = _integer(
                raw.get("bar_count"),
                "mt5_history: invalid_dataset_entry",
            )
            if (
                dataset.symbol != pair
                or dataset.currency != str(raw.get("currency", ""))
                or len(dataset.bars) != dataset_bar_count
                or dataset_bar_count != bars_per_pair
                or dataset.bars[0].timestamp.isoformat() != raw.get("start_at")
                or dataset.bars[-1].timestamp.isoformat() != raw.get("end_at")
                or dataset.bars[-1].timestamp >= exported_at
                or dataset.fingerprint_sha256 != fingerprint
            ):
                raise TradingValidationError("mt5_history: fingerprint_mismatch")
            timestamps = tuple(bar.timestamp for bar in dataset.bars)
            timestamp_series[pair] = timestamps
            positive_volume_count = sum(bar.volume > 0 for bar in dataset.bars)
            gaps = []
            weekend_gap_count = 0
            for left, right in zip(dataset.bars, dataset.bars[1:]):
                seconds = int((right.timestamp - left.timestamp).total_seconds())
                if seconds == 900:
                    continue
                gaps.append(seconds)
                if (
                    left.timestamp.weekday() == 4
                    and right.timestamp.weekday() in {6, 0}
                    and 24 * 3600 <= seconds <= 80 * 3600
                ):
                    weekend_gap_count += 1
            unexpected_gap_count = len(gaps) - weekend_gap_count
            if positive_volume_count * 100 < len(dataset.bars) * 99:
                quality_issues.add("LOW_POSITIVE_TICK_VOLUME_RATIO")
            if unexpected_gap_count:
                quality_issues.add("UNEXPECTED_M15_GAPS")
            seen_pairs.add(pair)
            verified.append({
                "pair": pair,
                "bar_count": len(dataset.bars),
                "fingerprint_sha256": dataset.fingerprint_sha256,
                "matches_manifest": True,
                "positive_tick_volume_ratio": (
                    f"{positive_volume_count / len(dataset.bars):.6f}"
                ),
                "gap_count": len(gaps),
                "weekend_gap_count": weekend_gap_count,
                "unexpected_gap_count": unexpected_gap_count,
            })
        if seen_pairs != set(manifest.get("pair_symbols", []) or []):
            raise TradingValidationError("mt5_history: pair_set_mismatch")
        first_timestamps = next(iter(timestamp_series.values()))
        timestamps_aligned = all(
            timestamps == first_timestamps
            for timestamps in timestamp_series.values()
        )
        if not timestamps_aligned:
            quality_issues.add("PAIR_TIMESTAMPS_NOT_ALIGNED")
        return {
            "status": "MT5_DEMO_HISTORY_VERIFIED",
            "mode": "READ_ONLY_HISTORICAL_RESEARCH",
            "export_id": target.name,
            "export_path": str(target),
            "pair_count": len(verified),
            "tradable_pair_count": len(seen_pairs & _MAJOR_SYMBOLS),
            "conversion_pair_included": (
                USD_PLN_CONVERSION_PAIR.symbol in seen_pairs
            ),
            "historical_pln_conversion_ready": (
                USD_PLN_CONVERSION_PAIR.symbol in seen_pairs
            ),
            "bar_count_per_pair": bars_per_pair,
            "datasets": verified,
            "all_fingerprints_match": True,
            "timestamps_aligned_across_pairs": timestamps_aligned,
            "expected_interval_seconds": 900,
            "quality_issues": sorted(quality_issues),
            "research_quality_ready": not quality_issues,
            "strategy_performance_validated": False,
            "closed_bars_only": manifest.get("closed_bars_only") is True,
            "account_identifier_stored": False,
            "credentials_stored": False,
            "order_network_access": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }

    @staticmethod
    def _write_pair(
        path: Path,
        pair: ForexPair,
        bars: tuple[ForexBar, ...],
    ) -> None:
        if any(bar.pair != pair for bar in bars):
            raise TradingValidationError("mt5_history: pair_mismatch")
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=(
                    "timestamp",
                    "symbol",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "currency",
                ),
                lineterminator="\n",
            )
            writer.writeheader()
            for bar in bars:
                writer.writerow({
                    "timestamp": bar.timestamp.isoformat(),
                    "symbol": pair.symbol,
                    "open": str(bar.open),
                    "high": str(bar.high),
                    "low": str(bar.low),
                    "close": str(bar.close),
                    "volume": str(bar.tick_volume),
                    "currency": pair.quote_currency,
                })
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                manifest,
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


__all__ = ["Mt5DemoHistoricalExporter"]

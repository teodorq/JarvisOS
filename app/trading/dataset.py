"""Validated, local-only historical CSV datasets for paper research."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any

from app.trading.models import MarketBar, TradingValidationError


@dataclass(frozen=True, slots=True)
class HistoricalDataset:
    symbol: str
    currency: str
    bars: tuple[MarketBar, ...]
    fingerprint_sha256: str
    source_name: str

    def status(self) -> dict[str, Any]:
        return {
            "status": "VALIDATED",
            "symbol": self.symbol,
            "currency": self.currency,
            "bar_count": len(self.bars),
            "start_at": self.bars[0].timestamp.isoformat(),
            "end_at": self.bars[-1].timestamp.isoformat(),
            "fingerprint_sha256": self.fingerprint_sha256,
            "source_name": self.source_name,
            "local_only": True,
        }


class HistoricalCsvLoader:
    """Load one-symbol OHLCV data without network paths or implicit fixes."""

    REQUIRED_COLUMNS = {
        "timestamp",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "currency",
    }
    MAX_FILE_BYTES = 100 * 1024 * 1024
    MAX_ROWS = 500_000

    def load(self, source: str | Path) -> HistoricalDataset:
        raw_path = str(source or "").strip()
        if not raw_path or "://" in raw_path or raw_path.startswith(("\\", "//")):
            raise TradingValidationError("dataset: local_file_required")
        path = Path(raw_path).expanduser().resolve(strict=False)
        if not path.is_file():
            raise TradingValidationError("dataset: file_not_found")
        size = path.stat().st_size
        if size <= 0:
            raise TradingValidationError("dataset: empty_file")
        if size > self.MAX_FILE_BYTES:
            raise TradingValidationError("dataset: file_too_large")

        bars: list[MarketBar] = []
        fingerprint = hashlib.sha256()
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = {str(field or "").strip().casefold() for field in reader.fieldnames or ()}
            if not self.REQUIRED_COLUMNS.issubset(fields):
                raise TradingValidationError("dataset: required_columns_missing")
            for row_number, raw in enumerate(reader, 2):
                if len(bars) >= self.MAX_ROWS:
                    raise TradingValidationError("dataset: row_limit_exceeded")
                row = {
                    str(key or "").strip().casefold(): str(value or "").strip()
                    for key, value in raw.items()
                }
                try:
                    timestamp = datetime.fromisoformat(
                        row["timestamp"].replace("Z", "+00:00")
                    )
                    bar = MarketBar.create(
                        symbol=row["symbol"],
                        timestamp=timestamp,
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        close=row["close"],
                        volume=row["volume"],
                        currency=row["currency"],
                    )
                except (KeyError, ValueError, TradingValidationError) as exc:
                    raise TradingValidationError(
                        f"dataset: invalid_row_{row_number}"
                    ) from exc
                if bars and bar.timestamp <= bars[-1].timestamp:
                    raise TradingValidationError(
                        f"dataset: timestamps_not_strictly_increasing_at_{row_number}"
                    )
                bars.append(bar)
                canonical = "|".join((
                    bar.timestamp.isoformat(),
                    bar.symbol,
                    str(bar.open),
                    str(bar.high),
                    str(bar.low),
                    str(bar.close),
                    str(bar.volume),
                    bar.currency,
                ))
                fingerprint.update(canonical.encode("utf-8"))
                fingerprint.update(b"\n")

        if len(bars) < 2:
            raise TradingValidationError("dataset: at_least_two_rows_required")
        symbols = {bar.symbol for bar in bars}
        currencies = {bar.currency for bar in bars}
        if len(symbols) != 1:
            raise TradingValidationError("dataset: one_symbol_required")
        if len(currencies) != 1:
            raise TradingValidationError("dataset: one_currency_required")
        return HistoricalDataset(
            symbol=bars[0].symbol,
            currency=bars[0].currency,
            bars=tuple(bars),
            fingerprint_sha256=fingerprint.hexdigest(),
            source_name=path.name,
        )


__all__ = ["HistoricalCsvLoader", "HistoricalDataset"]

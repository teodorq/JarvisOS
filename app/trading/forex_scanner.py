"""Deterministic multi-pair Forex scanner with fail-closed data gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
)
from app.trading.models import TradingValidationError, aware_utc


@dataclass(frozen=True, slots=True)
class ForexScannerPolicy:
    fast_window: int = 10
    slow_window: int = 30
    max_quote_age_seconds: int = 10
    max_context_age_seconds: int = 30
    # MT5 timestamps a candle at its opening time. Because the adapter reads
    # only the previous, fully closed M15 candle, its timestamp is normally
    # between 15 and 30 minutes old. Keep a small synchronization allowance
    # without accepting a candle older than two M15 periods plus one minute.
    max_closed_bar_age_seconds: int = 1_860
    expected_bar_seconds: int = 900
    max_gap_factor: int = 3
    max_spread_pips: Decimal = Decimal("2.5")
    max_quote_deviation_pct: Decimal = Decimal("0.02")
    minimum_positive_volume_ratio: Decimal = Decimal("0.80")

    def __post_init__(self) -> None:
        if not 2 <= self.fast_window < self.slow_window <= 200:
            raise TradingValidationError("forex_scanner: invalid_windows")
        if not 1 <= self.max_quote_age_seconds <= 60:
            raise TradingValidationError("forex_scanner: invalid_quote_age")
        if not 1 <= self.max_context_age_seconds <= 300:
            raise TradingValidationError("forex_scanner: invalid_context_age")
        if not 60 <= self.expected_bar_seconds <= 86_400:
            raise TradingValidationError("forex_scanner: invalid_timeframe")
        if self.max_closed_bar_age_seconds < self.expected_bar_seconds:
            raise TradingValidationError("forex_scanner: invalid_bar_age")
        if not 1 <= self.max_gap_factor <= 10:
            raise TradingValidationError("forex_scanner: invalid_gap_factor")
        if not Decimal("0.1") <= self.max_spread_pips <= Decimal("10"):
            raise TradingValidationError("forex_scanner: invalid_spread_limit")
        if not Decimal("0.001") <= self.max_quote_deviation_pct <= Decimal("0.05"):
            raise TradingValidationError("forex_scanner: invalid_deviation_limit")
        if not Decimal("0.50") <= self.minimum_positive_volume_ratio <= Decimal("1"):
            raise TradingValidationError("forex_scanner: invalid_volume_ratio")


@dataclass(frozen=True, slots=True)
class ForexPairAssessment:
    pair: ForexPair
    status: str
    action: str
    trend: str
    score: Decimal
    reason_codes: tuple[str, ...]
    spread_pips: Decimal = Decimal("0")
    volatility_pct: Decimal = Decimal("0")
    last_price: Decimal = Decimal("0")
    assessed_at: datetime | None = None

    @property
    def can_open(self) -> bool:
        return self.status == "READY" and self.action in {
            "OPEN_LONG",
            "OPEN_SHORT",
        }

    @property
    def should_close(self) -> bool:
        return self.status == "READY" and self.action in {
            "CLOSE_LONG",
            "CLOSE_SHORT",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair.symbol,
            "status": self.status,
            "action": self.action,
            "trend": self.trend,
            "score": str(self.score.quantize(Decimal("0.01"))),
            "reason_codes": list(self.reason_codes),
            "spread_pips": str(self.spread_pips.quantize(Decimal("0.01"))),
            "volatility_pct": str(
                self.volatility_pct.quantize(Decimal("0.0001"))
            ),
            "last_price": str(self.last_price),
            "assessed_at": self.assessed_at.isoformat() if self.assessed_at else "",
            "paper_only": True,
        }


class ForexMarketScanner:
    """Assess every configured pair; never submits an order."""

    def __init__(
        self,
        universe: Iterable[ForexPair] = MAJOR_FOREX_PAIRS,
        *,
        policy: ForexScannerPolicy | None = None,
    ) -> None:
        pairs = tuple(universe)
        if not pairs or len({pair.symbol for pair in pairs}) != len(pairs):
            raise TradingValidationError("forex_scanner: invalid_universe")
        if any(not pair.tradable for pair in pairs):
            raise TradingValidationError("forex_scanner: conversion_pair_not_tradable")
        self.universe = pairs
        self.policy = policy or ForexScannerPolicy()

    def scan(
        self,
        *,
        quotes: Mapping[str, ForexQuote],
        bars: Mapping[str, Iterable[ForexBar]],
        contexts: Mapping[str, ForexSafetyContext],
        positions: Mapping[str, str] | None = None,
        now: datetime | None = None,
    ) -> tuple[ForexPairAssessment, ...]:
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        current_positions = {
            str(key).upper(): str(value).upper()
            for key, value in dict(positions or {}).items()
        }
        assessments: list[ForexPairAssessment] = []
        for pair in self.universe:
            quote = quotes.get(pair.symbol)
            context = contexts.get(pair.symbol)
            series = bars.get(pair.symbol)
            if quote is None or context is None or series is None:
                assessments.append(self._blocked(pair, "DATA_MISSING", selected_now))
                continue
            assessments.append(
                self.assess(
                    pair=pair,
                    quote=quote,
                    bars=series,
                    context=context,
                    position_side=current_positions.get(pair.symbol, ""),
                    now=selected_now,
                )
            )
        priority = {
            "CLOSE_LONG": 0,
            "CLOSE_SHORT": 0,
            "OPEN_LONG": 1,
            "OPEN_SHORT": 1,
            "WAIT": 2,
            "WATCH": 3,
        }
        return tuple(sorted(
            assessments,
            key=lambda item: (priority.get(item.action, 9), -item.score, item.pair.symbol),
        ))

    def assess(
        self,
        *,
        pair: ForexPair,
        quote: ForexQuote,
        bars: Iterable[ForexBar],
        context: ForexSafetyContext,
        position_side: str = "",
        now: datetime | None = None,
    ) -> ForexPairAssessment:
        selected_now = aware_utc(now or datetime.now(timezone.utc), "now")
        series = list(bars)
        required = self.policy.slow_window + 1
        if quote.pair != pair or any(bar.pair != pair for bar in series):
            return self._blocked(pair, "PAIR_MISMATCH", selected_now)
        if len(series) < required:
            return self._blocked(pair, "INSUFFICIENT_BARS", selected_now)
        timestamps = [bar.timestamp for bar in series]
        if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
            return self._blocked(pair, "BARS_NOT_STRICTLY_ORDERED", selected_now)
        quote_age = Decimal(str((selected_now - quote.timestamp).total_seconds()))
        if quote_age < Decimal("-2"):
            return self._blocked(pair, "QUOTE_FROM_FUTURE", selected_now)
        if quote_age > self.policy.max_quote_age_seconds:
            return self._blocked(pair, "STALE_QUOTE", selected_now)
        context_age = (selected_now - context.observed_at).total_seconds()
        if context_age < -2 or context_age > self.policy.max_context_age_seconds:
            return self._blocked(pair, "STALE_SAFETY_CONTEXT", selected_now)
        bar_age = (selected_now - series[-1].timestamp).total_seconds()
        if bar_age < -2 or bar_age > self.policy.max_closed_bar_age_seconds:
            return self._blocked(pair, "STALE_CLOSED_BAR", selected_now)
        recent = series[-required:]
        max_gap = self.policy.expected_bar_seconds * self.policy.max_gap_factor
        if any(
            (right.timestamp - left.timestamp).total_seconds() > max_gap
            for left, right in zip(recent, recent[1:])
        ):
            return self._blocked(pair, "BAR_GAP_DETECTED", selected_now)
        spread = quote.spread_pips
        if spread > self.policy.max_spread_pips:
            return self._blocked(
                pair, "SPREAD_TOO_WIDE", selected_now, spread=spread
            )
        deviation = abs(quote.midpoint - recent[-1].close) / recent[-1].close
        if deviation > self.policy.max_quote_deviation_pct:
            return self._blocked(
                pair, "QUOTE_BAR_DIVERGENCE", selected_now, spread=spread
            )
        positive_volume = sum(bar.tick_volume > 0 for bar in recent)
        volume_ratio = Decimal(positive_volume) / Decimal(len(recent))
        if volume_ratio < self.policy.minimum_positive_volume_ratio:
            return self._blocked(
                pair, "INSUFFICIENT_TICK_VOLUME", selected_now, spread=spread
            )

        closes = [bar.close for bar in recent]
        fast = self._mean(closes[-self.policy.fast_window:])
        slow = self._mean(closes[-self.policy.slow_window:])
        previous_fast = self._mean(
            closes[-self.policy.fast_window - 1:-1]
        )
        previous_slow = self._mean(
            closes[-self.policy.slow_window - 1:-1]
        )
        returns = [
            abs(current / previous - Decimal("1"))
            for previous, current in zip(closes, closes[1:])
        ]
        volatility = self._mean(returns) if returns else Decimal("0")
        strength = abs(fast - slow) / slow
        score = min(
            Decimal("100"),
            (strength / max(volatility, Decimal("0.000001"))) * Decimal("10"),
        )
        trend = "UP" if fast > slow else "DOWN" if fast < slow else "FLAT"
        side = str(position_side or "").strip().upper()
        if side not in {"", "LONG", "SHORT"}:
            return self._blocked(pair, "INVALID_POSITION_SIDE", selected_now)

        action = "WATCH"
        reasons: tuple[str, ...] = ("NO_NEW_CROSSOVER",)
        if side == "LONG":
            action = "CLOSE_LONG" if fast <= slow else "WATCH"
            reasons = ("LONG_EXIT_CROSSOVER",) if action.startswith("CLOSE") else ("LONG_TREND_INTACT",)
        elif side == "SHORT":
            action = "CLOSE_SHORT" if fast >= slow else "WATCH"
            reasons = ("SHORT_EXIT_CROSSOVER",) if action.startswith("CLOSE") else ("SHORT_TREND_INTACT",)
        elif previous_fast <= previous_slow and fast > slow:
            action, reasons = "OPEN_LONG", ("BULLISH_CROSSOVER",)
        elif previous_fast >= previous_slow and fast < slow:
            action, reasons = "OPEN_SHORT", ("BEARISH_CROSSOVER",)

        if action.startswith("OPEN") and context.opening_blocks:
            action = "WAIT"
            reasons = context.opening_blocks
        elif action.startswith("CLOSE") and not context.market_open:
            action = "WAIT"
            reasons = ("MARKET_CLOSED", "CLOSE_PENDING")
        return ForexPairAssessment(
            pair=pair,
            status="READY",
            action=action,
            trend=trend,
            score=score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            reason_codes=reasons,
            spread_pips=spread,
            volatility_pct=volatility * Decimal("100"),
            last_price=quote.midpoint,
            assessed_at=selected_now,
        )

    @staticmethod
    def _mean(values: list[Decimal]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values))

    @staticmethod
    def _blocked(
        pair: ForexPair,
        code: str,
        now: datetime,
        *,
        spread: Decimal = Decimal("0"),
    ) -> ForexPairAssessment:
        return ForexPairAssessment(
            pair=pair,
            status="BLOCKED",
            action="WAIT",
            trend="UNKNOWN",
            score=Decimal("0"),
            reason_codes=(code,),
            spread_pips=spread,
            assessed_at=now,
        )


__all__ = [
    "ForexMarketScanner",
    "ForexPairAssessment",
    "ForexScannerPolicy",
]

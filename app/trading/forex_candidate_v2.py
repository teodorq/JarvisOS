"""Frozen, observation-only Forex candidate with an H1 trend-regime gate."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Iterable, Mapping

from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexPosition,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
)
from app.trading.forex_scanner import (
    ForexMarketScanner,
    ForexPairAssessment,
    ForexScannerPolicy,
)
from app.trading.models import TradingValidationError, aware_utc


@dataclass(frozen=True, slots=True)
class ForexRegimeCandidatePolicy:
    """Immutable preregistration; values cannot be tuned by callers."""

    candidate_id: str = field(
        default="FOREX_REGIME_V2_20260820",
        init=False,
    )
    frozen_after: datetime = field(
        default=datetime(2026, 8, 20, 20, 35, tzinfo=timezone.utc),
        init=False,
    )
    m15_fast_window: int = field(default=10, init=False)
    m15_slow_window: int = field(default=30, init=False)
    h1_fast_window: int = field(default=20, init=False)
    h1_slow_window: int = field(default=50, init=False)
    required_m15_bar_count: int = field(default=211, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frozen_after", aware_utc(self.frozen_after))

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "frozen_after": self.frozen_after.isoformat(),
            "entry_timeframe": "M15",
            "entry_fast_window": self.m15_fast_window,
            "entry_slow_window": self.m15_slow_window,
            "regime_timeframe": "H1_FROM_CLOSED_M15",
            "regime_fast_window": self.h1_fast_window,
            "regime_slow_window": self.h1_slow_window,
            "required_m15_bar_count": self.required_m15_bar_count,
            "parameter_optimization_allowed": False,
            "automatic_paper_promotion": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        canonical = json.dumps(
            self.as_dict(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def forward_eligible(self, observed_at: datetime) -> bool:
        return aware_utc(observed_at, "observed_at") > self.frozen_after


class ForexRegimeFilteredScanner:
    """Apply a fixed H1 regime gate to new M15 entries, never to exits."""

    def __init__(
        self,
        universe: Iterable[ForexPair] = MAJOR_FOREX_PAIRS,
    ) -> None:
        self.candidate_policy = ForexRegimeCandidatePolicy()
        self.policy = ForexScannerPolicy(
            fast_window=self.candidate_policy.m15_fast_window,
            slow_window=self.candidate_policy.m15_slow_window,
        )
        self.base = ForexMarketScanner(universe, policy=self.policy)
        self.universe = self.base.universe
        self.required_history_count = (
            self.candidate_policy.required_m15_bar_count
        )

    def scan(
        self,
        *,
        quotes: Mapping[str, ForexQuote],
        bars: Mapping[str, Iterable[ForexBar]],
        contexts: Mapping[str, ForexSafetyContext],
        positions: Mapping[str, str] | None = None,
        now: datetime | None = None,
    ) -> tuple[ForexPairAssessment, ...]:
        assessments = self.base.scan(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            positions=positions,
            now=now,
        )
        filtered: list[ForexPairAssessment] = []
        for assessment in assessments:
            if not assessment.can_open:
                filtered.append(assessment)
                continue
            series = tuple(bars.get(assessment.pair.symbol, ()))
            gate = self._regime_gate(assessment, series)
            filtered.append(gate)
        priority = {
            "CLOSE_LONG": 0,
            "CLOSE_SHORT": 0,
            "OPEN_LONG": 1,
            "OPEN_SHORT": 1,
            "WAIT": 2,
            "WATCH": 3,
        }
        return tuple(sorted(
            filtered,
            key=lambda item: (
                priority.get(item.action, 9),
                -item.score,
                item.pair.symbol,
            ),
        ))

    def audit(self) -> dict[str, Any]:
        return {
            "strategy": "FROZEN_M15_CROSSOVER_WITH_H1_REGIME",
            "policy": self.candidate_policy.as_dict(),
            "policy_fingerprint_sha256": (
                self.candidate_policy.fingerprint_sha256
            ),
            "research_only": True,
            "paper_execution_enabled": False,
            "live_execution_enabled": False,
        }

    def _regime_gate(
        self,
        assessment: ForexPairAssessment,
        series: tuple[ForexBar, ...],
    ) -> ForexPairAssessment:
        closes = self._complete_h1_closes(assessment.pair, series)
        required = self.candidate_policy.h1_slow_window
        if len(closes) < required:
            return replace(
                assessment,
                action="WAIT",
                reason_codes=("CANDIDATE_V2_H1_HISTORY_INSUFFICIENT",),
            )
        fast = self._mean(closes[-self.candidate_policy.h1_fast_window:])
        slow = self._mean(closes[-required:])
        last = closes[-1]
        aligned = (
            assessment.action == "OPEN_LONG" and fast > slow and last > slow
        ) or (
            assessment.action == "OPEN_SHORT" and fast < slow and last < slow
        )
        if not aligned:
            return replace(
                assessment,
                action="WAIT",
                reason_codes=("CANDIDATE_V2_H1_REGIME_NOT_ALIGNED",),
            )
        return replace(
            assessment,
            reason_codes=(
                *assessment.reason_codes,
                "CANDIDATE_V2_H1_REGIME_ALIGNED",
            ),
        )

    @staticmethod
    def _complete_h1_closes(
        pair: ForexPair,
        values: Iterable[ForexBar],
    ) -> tuple[Decimal, ...]:
        series = tuple(values)
        if any(not isinstance(bar, ForexBar) or bar.pair != pair for bar in series):
            return ()
        if any(
            right.timestamp <= left.timestamp
            for left, right in zip(series, series[1:])
        ):
            return ()
        grouped: dict[datetime, list[ForexBar]] = {}
        for bar in series:
            hour = bar.timestamp.replace(minute=0, second=0, microsecond=0)
            grouped.setdefault(hour, []).append(bar)
        closes: list[Decimal] = []
        for hour in sorted(grouped):
            group = grouped[hour]
            if tuple(bar.timestamp.minute for bar in group) != (0, 15, 30, 45):
                continue
            if any(
                (right.timestamp - left.timestamp).total_seconds() != 900
                for left, right in zip(group, group[1:])
            ):
                continue
            closes.append(group[-1].close)
        return tuple(closes)

    @staticmethod
    def _mean(values: Iterable[Decimal]) -> Decimal:
        selected = tuple(values)
        if not selected:
            raise TradingValidationError("forex_candidate_v2: empty_mean")
        return sum(selected, Decimal("0")) / Decimal(len(selected))


__all__ = [
    "ForexRegimeCandidatePolicy",
    "ForexRegimeFilteredScanner",
]

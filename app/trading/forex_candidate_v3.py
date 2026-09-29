"""Frozen, research-only Forex candidate with volatility-normalized strength."""

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
class ForexStrengthCandidatePolicy:
    """Immutable preregistration; values cannot be tuned by callers."""

    candidate_id: str = field(
        default="FOREX_STRENGTH_V3_20260929",
        init=False,
    )
    frozen_after: datetime = field(
        default=datetime(2026, 9, 29, 17, 9, 11, tzinfo=timezone.utc),
        init=False,
    )
    m15_fast_window: int = field(default=10, init=False)
    m15_slow_window: int = field(default=30, init=False)
    atr_window: int = field(default=14, init=False)
    minimum_separation_atr: Decimal = field(default=Decimal("0.10"), init=False)
    minimum_displacement_atr: Decimal = field(default=Decimal("0.25"), init=False)
    required_m15_bar_count: int = field(default=31, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frozen_after", aware_utc(self.frozen_after))

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "frozen_after": self.frozen_after.isoformat(),
            "entry_timeframe": "M15",
            "entry_fast_window": self.m15_fast_window,
            "entry_slow_window": self.m15_slow_window,
            "strength_measure": "ATR_NORMALIZED_MA_SEPARATION_AND_DISPLACEMENT",
            "atr_window": self.atr_window,
            "minimum_separation_atr": str(self.minimum_separation_atr),
            "minimum_displacement_atr": str(self.minimum_displacement_atr),
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


class ForexStrengthFilteredScanner:
    """Filter only new weak crossovers; never block an existing-position exit."""

    def __init__(
        self,
        universe: Iterable[ForexPair] = MAJOR_FOREX_PAIRS,
    ) -> None:
        self.candidate_policy = ForexStrengthCandidatePolicy()
        self.policy = ForexScannerPolicy(
            fast_window=self.candidate_policy.m15_fast_window,
            slow_window=self.candidate_policy.m15_slow_window,
        )
        self.base = ForexMarketScanner(universe, policy=self.policy)
        self.universe = self.base.universe
        self.required_history_count = self.candidate_policy.required_m15_bar_count

    def scan(
        self,
        *,
        quotes: Mapping[str, ForexQuote],
        bars: Mapping[str, Iterable[ForexBar]],
        contexts: Mapping[str, ForexSafetyContext],
        positions: Mapping[str, str | ForexPosition] | None = None,
        now: datetime | None = None,
    ) -> tuple[ForexPairAssessment, ...]:
        assessments = self.base.scan(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            positions=positions,
            now=now,
        )
        filtered = [
            self._strength_gate(
                assessment,
                tuple(bars.get(assessment.pair.symbol, ())),
            )
            if assessment.can_open
            else assessment
            for assessment in assessments
        ]
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
            "strategy": "FROZEN_M15_CROSSOVER_WITH_ATR_STRENGTH",
            "policy": self.candidate_policy.as_dict(),
            "policy_fingerprint_sha256": self.candidate_policy.fingerprint_sha256,
            "research_only": True,
            "paper_execution_enabled": False,
            "live_execution_enabled": False,
        }

    def _strength_gate(
        self,
        assessment: ForexPairAssessment,
        series: tuple[ForexBar, ...],
    ) -> ForexPairAssessment:
        policy = self.candidate_policy
        if len(series) < policy.required_m15_bar_count or any(
            not isinstance(bar, ForexBar) or bar.pair != assessment.pair
            for bar in series
        ):
            return replace(
                assessment,
                action="WAIT",
                reason_codes=("CANDIDATE_V3_STRENGTH_HISTORY_INVALID",),
            )
        selected = series[-policy.required_m15_bar_count:]
        if any(
            right.timestamp <= left.timestamp
            for left, right in zip(selected, selected[1:])
        ):
            return replace(
                assessment,
                action="WAIT",
                reason_codes=("CANDIDATE_V3_STRENGTH_HISTORY_INVALID",),
            )
        atr = self._atr(selected, policy.atr_window)
        fast = self._mean(tuple(
            bar.close for bar in selected[-policy.m15_fast_window:]
        ))
        slow = self._mean(tuple(
            bar.close for bar in selected[-policy.m15_slow_window:]
        ))
        separation = abs(fast - slow)
        displacement = abs(selected[-1].close - slow)
        if (
            atr <= 0
            or separation < atr * policy.minimum_separation_atr
            or displacement < atr * policy.minimum_displacement_atr
        ):
            return replace(
                assessment,
                action="WAIT",
                reason_codes=("CANDIDATE_V3_SIGNAL_STRENGTH_TOO_LOW",),
            )
        return replace(
            assessment,
            reason_codes=(
                *assessment.reason_codes,
                "CANDIDATE_V3_SIGNAL_STRENGTH_CONFIRMED",
            ),
        )

    @staticmethod
    def _atr(values: tuple[ForexBar, ...], window: int) -> Decimal:
        selected = values[-window - 1:]
        ranges = tuple(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
            for previous, current in zip(selected, selected[1:])
        )
        if len(ranges) != window:
            raise TradingValidationError("forex_candidate_v3: atr_history_invalid")
        return sum(ranges, Decimal("0")) / Decimal(window)

    @staticmethod
    def _mean(values: tuple[Decimal, ...]) -> Decimal:
        if not values:
            raise TradingValidationError("forex_candidate_v3: empty_mean")
        return sum(values, Decimal("0")) / Decimal(len(values))


__all__ = [
    "ForexStrengthCandidatePolicy",
    "ForexStrengthFilteredScanner",
]

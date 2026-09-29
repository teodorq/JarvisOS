from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.trading.forex_candidate_v3 import (
    ForexStrengthCandidatePolicy,
    ForexStrengthFilteredScanner,
)
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
)


PAIR = MAJOR_FOREX_PAIRS[0]
NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def _bars(*, impulse: Decimal) -> tuple[ForexBar, ...]:
    start = NOW - timedelta(minutes=15 * 31)
    values = [Decimal("1.0800")] * 30 + [Decimal("1.0800") + impulse]
    return tuple(
        ForexBar.create(
            pair=PAIR,
            timestamp=start + timedelta(minutes=15 * index),
            open=value,
            high=value + Decimal("0.0001"),
            low=value - Decimal("0.0001"),
            close=value,
            tick_volume=100,
        )
        for index, value in enumerate(values)
    )


def _scan(bars: tuple[ForexBar, ...], position: str | None = None):
    quote = ForexQuote.create(
        pair=PAIR,
        bid=bars[-1].close - Decimal("0.00005"),
        ask=bars[-1].close + Decimal("0.00005"),
        timestamp=NOW,
    )
    context = ForexSafetyContext(
        observed_at=NOW,
        market_open=True,
        calendar_ready=True,
        high_impact_event_blocked=False,
        conversion_to_pln_ready=True,
        independent_source_count=2,
    )
    return ForexStrengthFilteredScanner((PAIR,)).scan(
        quotes={PAIR.symbol: quote},
        bars={PAIR.symbol: bars},
        contexts={PAIR.symbol: context},
        positions={PAIR.symbol: position} if position else {},
        now=NOW,
    )[0]


def test_strong_volatility_normalized_crossover_is_retained() -> None:
    assessment = _scan(_bars(impulse=Decimal("0.0020")))

    assert assessment.action == "OPEN_LONG"
    assert "CANDIDATE_V3_SIGNAL_STRENGTH_CONFIRMED" in assessment.reason_codes


def test_weak_crossover_is_filtered_without_opening() -> None:
    assessment = _scan(_bars(impulse=Decimal("0.0001")))

    assert assessment.action == "WAIT"
    assert assessment.reason_codes == ("CANDIDATE_V3_SIGNAL_STRENGTH_TOO_LOW",)


def test_strength_gate_never_blocks_an_existing_position_exit() -> None:
    bars = list(_bars(impulse=Decimal("0.0020")))
    last = bars[-1]
    bars[-1] = ForexBar.create(
        pair=PAIR,
        timestamp=last.timestamp,
        open=last.open - Decimal("0.0040"),
        high=last.high,
        low=last.low - Decimal("0.0040"),
        close=last.close - Decimal("0.0040"),
        tick_volume=last.tick_volume,
    )

    assessment = _scan(tuple(bars), position="LONG")

    assert assessment.action == "CLOSE_LONG"


def test_v3_preregistration_is_stable_forward_only_and_not_tunable() -> None:
    policy = ForexStrengthCandidatePolicy()

    assert policy.fingerprint_sha256 == ForexStrengthCandidatePolicy().fingerprint_sha256
    assert not policy.forward_eligible(policy.frozen_after)
    assert policy.forward_eligible(policy.frozen_after + timedelta(seconds=1))
    with pytest.raises(TypeError):
        ForexStrengthCandidatePolicy(atr_window=10)  # type: ignore[call-arg]
    audit = ForexStrengthFilteredScanner().audit()
    assert audit["research_only"] is True
    assert audit["paper_execution_enabled"] is False
    assert audit["live_execution_enabled"] is False

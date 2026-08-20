from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.trading.forex_candidate_v2 import (
    ForexRegimeCandidatePolicy,
    ForexRegimeFilteredScanner,
)
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
)


class ForexCandidateV2Tests(unittest.TestCase):
    pair = MAJOR_FOREX_PAIRS[0]
    now = datetime(2026, 8, 21, 12, tzinfo=timezone.utc)

    def _bars(self, *, rising: bool, count: int = 211) -> tuple[ForexBar, ...]:
        start = self.now - timedelta(minutes=15 * count)
        values: list[Decimal] = []
        trend_count = max(1, count - 31)
        for index in range(count):
            if index < trend_count:
                move = Decimal(index) * Decimal("0.00005")
                value = Decimal("1.0800") + (move if rising else -move)
            elif index < count - 1:
                value = values[-1]
            else:
                value = values[-1] + Decimal("0.0020")
            values.append(value)
        return tuple(
            ForexBar.create(
                pair=self.pair,
                timestamp=start + timedelta(minutes=15 * index),
                open=value,
                high=value + Decimal("0.0001"),
                low=value - Decimal("0.0001"),
                close=value,
                tick_volume=100,
            )
            for index, value in enumerate(values)
        )

    def _scan(self, bars: tuple[ForexBar, ...], position: str | None = None):
        quote = ForexQuote.create(
            pair=self.pair,
            bid=bars[-1].close - Decimal("0.00005"),
            ask=bars[-1].close + Decimal("0.00005"),
            timestamp=self.now,
        )
        context = ForexSafetyContext(
            observed_at=self.now,
            market_open=True,
            calendar_ready=True,
            high_impact_event_blocked=False,
            conversion_to_pln_ready=True,
            independent_source_count=2,
        )
        return ForexRegimeFilteredScanner((self.pair,)).scan(
            quotes={self.pair.symbol: quote},
            bars={self.pair.symbol: bars},
            contexts={self.pair.symbol: context},
            positions={self.pair.symbol: position} if position else {},
            now=self.now,
        )[0]

    def test_aligned_h1_regime_allows_base_long_entry(self) -> None:
        assessment = self._scan(self._bars(rising=True))
        self.assertEqual(assessment.action, "OPEN_LONG")
        self.assertIn("CANDIDATE_V2_H1_REGIME_ALIGNED", assessment.reason_codes)

    def test_opposing_h1_regime_blocks_base_long_entry(self) -> None:
        assessment = self._scan(self._bars(rising=False))
        self.assertEqual(assessment.action, "WAIT")
        self.assertEqual(
            assessment.reason_codes,
            ("CANDIDATE_V2_H1_REGIME_NOT_ALIGNED",),
        )

    def test_insufficient_h1_history_fails_closed(self) -> None:
        assessment = self._scan(self._bars(rising=True, count=31))
        self.assertEqual(assessment.action, "WAIT")
        self.assertEqual(
            assessment.reason_codes,
            ("CANDIDATE_V2_H1_HISTORY_INSUFFICIENT",),
        )

    def test_regime_gate_never_blocks_an_existing_position_exit(self) -> None:
        bars = list(self._bars(rising=True, count=31))
        last = bars[-1]
        bars[-1] = ForexBar.create(
            pair=self.pair,
            timestamp=last.timestamp,
            open=last.open - Decimal("0.0040"),
            high=last.high,
            low=last.low - Decimal("0.0040"),
            close=last.close - Decimal("0.0040"),
            tick_volume=last.tick_volume,
        )
        assessment = self._scan(tuple(bars), position="LONG")
        self.assertEqual(assessment.action, "CLOSE_LONG")

    def test_preregistration_is_stable_and_forward_only(self) -> None:
        policy = ForexRegimeCandidatePolicy()
        self.assertEqual(
            policy.fingerprint_sha256,
            ForexRegimeCandidatePolicy().fingerprint_sha256,
        )
        self.assertFalse(policy.forward_eligible(policy.frozen_after))
        self.assertTrue(
            policy.forward_eligible(policy.frozen_after + timedelta(seconds=1))
        )
        self.assertFalse(ForexRegimeFilteredScanner().audit()["paper_execution_enabled"])
        self.assertFalse(ForexRegimeFilteredScanner().audit()["live_execution_enabled"])


if __name__ == "__main__":
    unittest.main()

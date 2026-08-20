from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.trading.forex_models import MAJOR_FOREX_PAIRS
from app.trading.forex_research_status import ForexHistoricalResearchGate


def report(*, candidate: bool = False) -> dict:
    return {
        "status": "FOREX_MULTI_PAIR_RESEARCH_COMPLETED",
        "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
        "source_export_id": "mt5-demo-m15-20260819T181026263354Z",
        "source_fingerprints_verified": True,
        "source_quality_ready": True,
        "pair_count": len(MAJOR_FOREX_PAIRS),
        "pairs": [
            {
                "pair": pair.symbol,
                "average_out_of_sample_return_pct": (
                    "0.0100" if candidate or index < 2 else "-0.0100"
                ),
            }
            for index, pair in enumerate(MAJOR_FOREX_PAIRS)
        ],
        "portfolio_pln_aggregation_performed": False,
        "parameter_optimization_performed": False,
        "stop_loss_formula_matches_paper_coordinator": True,
        "position_sizing_matches_paper_coordinator": candidate,
        "take_profit_research_only": not candidate,
        "strategy_performance_validated": candidate,
        "broker_connection_used": False,
        "paper_orders_sent": False,
        "live_orders_sent": False,
    }


class ForexHistoricalResearchGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "data" / "trading" / "research" / "latest.json"
        self.path.parent.mkdir(parents=True)

    def write(self, value: dict) -> None:
        self.path.write_text(
            json.dumps(value, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_missing_and_malformed_reports_fail_closed(self) -> None:
        gate = ForexHistoricalResearchGate(self.root)
        missing = gate.status()
        self.assertEqual(missing["status"], "NOT_AVAILABLE")
        self.assertFalse(missing["strategy_candidate_ready"])
        self.path.write_text("{broken", encoding="utf-8")
        malformed = gate.status()
        self.assertEqual(malformed["status"], "INVALID")
        self.assertFalse(malformed["strategy_candidate_ready"])

    def test_current_research_mismatches_keep_paper_blocked(self) -> None:
        self.write(report())
        status = ForexHistoricalResearchGate(self.root).status()
        self.assertEqual(status["status"], "BLOCKED")
        self.assertEqual(status["positive_average_pair_count"], 2)
        self.assertIn(
            "PAPER_POSITION_SIZING_NOT_REPLAYED",
            status["strategy_candidate_blocks"],
        )
        self.assertIn(
            "TAKE_PROFIT_NOT_IMPLEMENTED_IN_PAPER",
            status["strategy_candidate_blocks"],
        )
        self.assertFalse(status["automatic_paper_promotion"])
        self.assertFalse(status["paper_orders_sent"])
        self.assertFalse(status["live_orders_sent"])

    def test_only_a_fully_matching_validated_report_can_be_ready(self) -> None:
        self.write(report(candidate=True))
        status = ForexHistoricalResearchGate(self.root).status()
        self.assertEqual(status["status"], "READY")
        self.assertEqual(status["strategy_candidate_blocks"], [])
        self.assertTrue(status["strategy_candidate_ready"])
        self.assertEqual(status["positive_average_pair_count"], 7)
        self.assertFalse(status["automatic_paper_promotion"])

    def test_order_flag_or_incomplete_pair_set_invalidates_report(self) -> None:
        unsafe = report(candidate=True)
        unsafe["paper_orders_sent"] = True
        self.write(unsafe)
        self.assertEqual(
            ForexHistoricalResearchGate(self.root).status()["status"],
            "INVALID",
        )
        incomplete = report(candidate=True)
        incomplete["pairs"] = incomplete["pairs"][:-1]
        self.write(incomplete)
        self.assertEqual(
            ForexHistoricalResearchGate(self.root).status()["status"],
            "INVALID",
        )


if __name__ == "__main__":
    unittest.main()

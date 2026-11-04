from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from cloud_service.forex_paper_job import (
    CloudPaperJobError,
    PaperStateArchive,
    _public_result,
)


class CloudForexPaperJobTests(unittest.TestCase):
    def test_state_archive_round_trip_keeps_only_trading_json(self) -> None:
        state = PaperStateArchive()
        with TemporaryDirectory() as source_dir, TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            wanted = source / "data" / "trading" / "research" / "latest.json"
            wanted.parent.mkdir(parents=True)
            wanted.write_text('{"paper_only": true}', encoding="utf-8")
            ignored = source / "data" / "trading" / ".runtime.lock"
            ignored.write_text("not state", encoding="utf-8")

            payload = state.build(source)
            target = Path(target_dir)
            state.extract(payload, target)

            self.assertEqual(
                json.loads(
                    (target / "data" / "trading" / "research" / "latest.json")
                    .read_text(encoding="utf-8")
                ),
                {"paper_only": True},
            )
            self.assertFalse(
                (target / "data" / "trading" / ".runtime.lock").exists()
            )

    def test_state_archive_rejects_path_traversal(self) -> None:
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("data/trading/../../secret.json", "{}")
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(CloudPaperJobError, "unsafe_member"):
                PaperStateArchive().extract(output.getvalue(), Path(directory))

    def test_public_result_never_claims_broker_or_real_money_access(self) -> None:
        result = _public_result({
            "status": "PAPER_CYCLE_COMPLETED",
            "cycle_id": "azure-cycle",
            "observed_at": "2026-11-03T10:00:00+00:00",
            "observation": {
                "status": "DATA_BLOCKED",
                "fully_cross_checked": False,
                "positions_unchanged": True,
                "opening_blocks": [
                    "FOREX_OBSERVATION:_EXAMPLE_FAILURE",
                    "unsafe value with spaces",
                ],
                "execution": {
                    "status": "NOT_EXECUTED",
                    "reason": "FOREX_OBSERVATION:_EXAMPLE_FAILURE",
                },
                "data": {
                    "calendar_source_state": "CACHE_FAILSAFE",
                    "nbp_source_state": "CACHE_FALLBACK",
                    "ignored": "must-not-leak",
                },
            },
            "paper": {
                "account": {"position_count": 2},
                "assessments": [
                    {"status": "READY", "reason_codes": ["NO_ENTRY_SIGNAL"]},
                    {"status": "BLOCKED", "reason_codes": ["SPREAD_TOO_WIDE"]},
                ],
                "execution": {"executions": []},
            },
            "v3_shadow_plan_observation": {
                "status": "SHADOW_PLAN_OBSERVED",
                "plan": {
                    "decision_status": "ENTRIES_READY",
                    "assessments": [
                        {
                            "status": "READY",
                            "reason_codes": [
                                "BULLISH_CROSSOVER",
                                "CANDIDATE_V3_SIGNAL_STRENGTH_CONFIRMED",
                            ],
                        },
                        {
                            "status": "BLOCKED",
                            "reason_codes": ["SPREAD_TOO_WIDE"],
                        },
                    ],
                    "instructions": [{"action": "OPEN_LONG"}],
                },
            },
            "v3_shadow_simulation": {
                "status": "SHADOW_SIMULATION_CYCLE_COMPLETED",
                "execution": {
                    "executions": [{"action": "OPEN_LONG"}],
                },
                "account": {
                    "position_count": 1,
                    "closed_trade_count": 3,
                    "balance_pln": "10012.34",
                    "equity_pln": "10014.00",
                    "unrealized_pnl_pln": "1.66",
                    "realized_pnl_pln": "12.34",
                    "winning_trade_count": 2,
                    "losing_trade_count": 1,
                    "breakeven_trade_count": 0,
                    "win_rate_pct": "66.67",
                    "open_positions": [],
                    "performance": {"status": "COLLECTING_SAMPLE"},
                },
            },
            "broker_orders_sent": True,
            "live_orders_sent": True,
            "real_money_access": True,
            "secret": "must-not-leak",
        })
        self.assertEqual(result["position_count"], 2)
        self.assertEqual(result["v3_position_count"], 1)
        self.assertEqual(result["v3_closed_trade_count"], 3)
        self.assertEqual(result["v3_realized_pnl_pln"], "12.34")
        self.assertEqual(result["v3_balance_pln"], "10012.34")
        self.assertEqual(result["v3_equity_pln"], "10014.00")
        self.assertEqual(result["v3_winning_trade_count"], 2)
        self.assertEqual(
            result["v3_plan_observation_status"], "SHADOW_PLAN_OBSERVED"
        )
        self.assertEqual(result["v3_decision_status"], "ENTRIES_READY")
        self.assertEqual(result["v3_ready_pair_count"], 1)
        self.assertEqual(result["v3_blocked_pair_count"], 1)
        self.assertEqual(result["v3_instruction_count"], 1)
        self.assertEqual(result["v3_execution_count"], 1)
        self.assertEqual(
            result["v3_reason_codes"],
            {
                "BULLISH_CROSSOVER": 1,
                "CANDIDATE_V3_SIGNAL_STRENGTH_CONFIRMED": 1,
                "SPREAD_TOO_WIDE": 1,
            },
        )
        self.assertEqual(
            result["v3_performance"]["status"], "COLLECTING_SAMPLE"
        )
        self.assertEqual(result["observation_status"], "DATA_BLOCKED")
        self.assertEqual(
            result["observation_reason"],
            "FOREX_OBSERVATION:_EXAMPLE_FAILURE",
        )
        self.assertFalse(result["observation_fully_cross_checked"])
        self.assertTrue(result["observation_positions_unchanged"])
        self.assertEqual(
            result["observation_opening_blocks"],
            ["FOREX_OBSERVATION:_EXAMPLE_FAILURE"],
        )
        self.assertEqual(result["calendar_source_state"], "CACHE_FAILSAFE")
        self.assertEqual(result["nbp_source_state"], "CACHE_FALLBACK")
        self.assertEqual(result["runtime_decision"], "NO_ENTRY_SIGNAL")
        self.assertEqual(result["runtime_ready_pair_count"], 1)
        self.assertEqual(result["runtime_blocked_pair_count"], 1)
        self.assertEqual(result["runtime_execution_count"], 0)
        self.assertEqual(
            result["runtime_reason_codes"],
            {"NO_ENTRY_SIGNAL": 1, "SPREAD_TOO_WIDE": 1},
        )
        self.assertFalse(result["broker_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertFalse(result["real_money_access"])
        self.assertNotIn("secret", result)
        self.assertNotIn("ignored", result)

    def test_public_result_drops_unsafe_reference_source_states(self) -> None:
        result = _public_result({
            "observation": {
                "data": {
                    "calendar_source_state": "unsafe state with spaces",
                    "nbp_source_state": {"secret": "no"},
                },
            },
        })

        self.assertEqual(result["calendar_source_state"], "")
        self.assertEqual(result["nbp_source_state"], "")


if __name__ == "__main__":
    unittest.main()

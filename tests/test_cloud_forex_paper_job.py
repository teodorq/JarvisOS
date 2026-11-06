from __future__ import annotations

from io import BytesIO
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from cloud_service.forex_paper_job import (
    CloudPaperJobError,
    PaperStateArchive,
    _log_summary,
    _market_closed_result,
    _public_result,
    run,
)


class CloudForexPaperJobTests(unittest.TestCase):
    def test_closed_market_result_is_safe_and_skips_fresh_status(self) -> None:
        now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
        result = _market_closed_result(
            now,
            "azure-20261107T120000Z-000000000001",
        )
        summary = _log_summary(result)

        self.assertEqual(result["status"], "PAPER_CYCLE_SKIPPED")
        self.assertEqual(result["reason"], "MARKET_CLOSED")
        self.assertFalse(result["status_snapshot_persisted"])
        self.assertEqual(summary["status"], "PAPER_CYCLE_SKIPPED")
        self.assertEqual(summary["runtime_decision"], "MARKET_CLOSED")
        self.assertEqual(summary["reason"], "MARKET_CLOSED")
        self.assertFalse(summary["broker_orders_sent"])
        self.assertFalse(summary["live_orders_sent"])
        self.assertFalse(summary["real_money_access"])

    def test_closed_market_run_uses_no_blob_or_provider_runtime(self) -> None:
        saturday = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
        with (
            patch(
                "cloud_service.forex_paper_job._validate_settings",
                return_value=object(),
            ),
            patch(
                "cloud_service.forex_paper_job._configured_blob"
            ) as configured_blob,
            patch(
                "cloud_service.forex_paper_job.ForexDemoPaperRuntime"
            ) as runtime,
        ):
            result = run(now=saturday)

        configured_blob.assert_not_called()
        runtime.assert_not_called()
        self.assertEqual(result["reason"], "MARKET_CLOSED")
        self.assertFalse(result["status_snapshot_persisted"])

    def test_log_summary_is_small_and_drops_cloud_history_details(self) -> None:
        result = _public_result({
            "status": "PAPER_CYCLE_COMPLETED",
            "mode": "AUTONOMOUS_AZURE_FOREX_PAPER",
            "cycle_id": "azure-20261105T171059Z-03787a1e21a4",
            "paper": {"account": {"position_count": 1}},
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }, activity_events=[{
            "sequence": 1,
            "event_id": "000000000000000000000001",
            "occurred_at": "2026-11-05T17:10:59+00:00",
            "kind": "DATA_RECOVERED",
            "state": "brief",
            "message": "sensitive owner-facing detail",
        }])
        result["status_snapshot_persisted"] = True
        summary = _log_summary(result)

        self.assertEqual(summary["status"], "PAPER_CYCLE_COMPLETED")
        self.assertEqual(summary["activity_event_count"], 1)
        self.assertEqual(summary["latest_activity_sequence"], 1)
        self.assertEqual(summary["latest_activity_kind"], "DATA_RECOVERED")
        self.assertTrue(summary["status_snapshot_persisted"])
        self.assertFalse(summary["broker_orders_sent"])
        self.assertFalse(summary["live_orders_sent"])
        self.assertFalse(summary["real_money_access"])
        encoded = json.dumps(summary, ensure_ascii=False)
        self.assertLess(len(encoded.encode("utf-8")), 1_024)
        self.assertNotIn("activity_events", summary)
        self.assertNotIn("sensitive owner-facing detail", encoded)
        self.assertNotIn("v3_open_positions", summary)

    def test_log_summary_fails_closed_on_untrusted_values(self) -> None:
        summary = _log_summary({
            "status": "unsafe status with spaces",
            "runtime_ready_pair_count": True,
            "position_count": 999,
            "activity_events": "not-a-list",
            "broker_orders_sent": True,
            "live_orders_sent": True,
            "real_money_access": True,
        })

        self.assertEqual(summary["status"], "")
        self.assertEqual(summary["mode"], "")
        self.assertEqual(summary["cycle_id"], "")
        self.assertEqual(summary["runtime_ready_pair_count"], 0)
        self.assertEqual(summary["position_count"], 0)
        self.assertEqual(summary["activity_event_count"], 0)
        self.assertFalse(summary["broker_orders_sent"])
        self.assertFalse(summary["live_orders_sent"])
        self.assertFalse(summary["real_money_access"])

    def test_public_result_sanitizes_provider_failure_reason(self) -> None:
        result = _public_result({
            "status": "PAPER_CYCLE_BLOCKED",
            "cycle_id": "azure-provider-failure",
            "observed_at": "2026-11-04T21:02:50+00:00",
            "reason": "market_data_provider: TWELVE_DATA_CLOUD_HTTP_429",
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        })

        self.assertEqual(
            result["reason"],
            "MARKET_DATA_PROVIDER:_TWELVE_DATA_CLOUD_HTTP_429",
        )
        self.assertFalse(result["broker_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertFalse(result["real_money_access"])

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
                "opening_blocks_by_pair": {
                    "EUR_USD": [
                        "SECOND_SOURCE_UNAVAILABLE",
                        "unsafe value with spaces",
                    ],
                    "BAD_PAIR": ["HIGH_IMPACT_EVENT_WINDOW"],
                },
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
            "v3_shadow_activation": {
                "status": "ALREADY_ACTIVE",
            },
            "v3_forward_evidence": {
                "status": "COLLECTING_FORWARD_EVIDENCE",
                "candidate_id": "FOREX_STRENGTH_V3R2_20261104",
                "source_state_valid": True,
                "observation_sample_complete": False,
                "accepted_cycle_count": 4,
                "minimum_accepted_cycle_count": 20,
                "accepted_market_day_count": 1,
                "minimum_market_day_count": 3,
                "invalid_cycle_count": 0,
                "exclusions": {"SUPERSEDED_CANDIDATE": 12},
                "invalid_issues": {},
                "accepted_observations": [{"secret": "must-not-leak"}],
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
        self.assertEqual(result["v3_activation_status"], "ALREADY_ACTIVE")
        self.assertEqual(
            result["v3_forward_status"],
            "COLLECTING_FORWARD_EVIDENCE",
        )
        self.assertEqual(
            result["v3_forward_candidate_id"],
            "FOREX_STRENGTH_V3R2_20261104",
        )
        self.assertEqual(result["v3_forward_accepted_cycle_count"], 4)
        self.assertEqual(
            result["v3_forward_exclusions"],
            {"SUPERSEDED_CANDIDATE": 12},
        )
        self.assertNotIn("accepted_observations", result)
        self.assertEqual(result["v3_activation_reason"], "")
        self.assertEqual(result["v3_plan_reason"], "")
        self.assertEqual(result["v3_decision_status"], "ENTRIES_READY")
        self.assertEqual(result["v3_simulation_reason"], "")
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
        self.assertEqual(
            result["observation_opening_blocks_by_pair"],
            {"EUR_USD": ["SECOND_SOURCE_UNAVAILABLE"]},
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
            "v3_shadow_activation": {
                "status": "unsafe status with spaces",
                "reason": {"secret": "no"},
            },
            "v3_shadow_plan_observation": {
                "plan": {"reason": "unsafe reason with spaces"},
            },
            "v3_shadow_simulation": {
                "reason": "unsafe simulation reason",
            },
        })

        self.assertEqual(result["calendar_source_state"], "")
        self.assertEqual(result["nbp_source_state"], "")
        self.assertEqual(result["v3_activation_status"], "")
        self.assertEqual(result["v3_activation_reason"], "")
        self.assertEqual(result["v3_plan_reason"], "")
        self.assertEqual(result["v3_simulation_reason"], "")


if __name__ == "__main__":
    unittest.main()

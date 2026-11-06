from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import sys
import types
import unittest
from unittest.mock import patch

from cloud_service.forex_status_store import (
    AzureBlobForexStatusStore,
    ForexStatusNotReady,
    ForexStatusStoreError,
    MemoryForexStatusStore,
    forex_status_store_from_environment,
    forex_status_view,
    sanitize_forex_status,
)


def sample_status() -> dict:
    return {
        "schema_version": 1,
        "status": "PAPER_CYCLE_COMPLETED",
        "mode": "AUTONOMOUS_AZURE_FOREX_PAPER",
        "cycle_id": "cycle-123",
        "observed_at": "2026-11-03T10:00:00+00:00",
        "reason": "",
        "observation_status": "READY",
        "observation_reason": "",
        "observation_fully_cross_checked": True,
        "observation_positions_unchanged": False,
        "observation_opening_blocks": [],
        "observation_opening_blocks_by_pair": {
            "EUR_USD": ["SECOND_SOURCE_UNAVAILABLE"],
        },
        "calendar_source_state": "FRESH",
        "nbp_source_state": "FRESH",
        "runtime_decision": "NO_ENTRY_SIGNAL",
        "runtime_ready_pair_count": 6,
        "runtime_blocked_pair_count": 1,
        "runtime_execution_count": 0,
        "runtime_reason_codes": {"NO_ENTRY_SIGNAL": 6, "SPREAD_TOO_WIDE": 1},
        "runtime_high_impact_event_window": False,
        "position_count": 1,
        "v3_status": "SHADOW_SIMULATION_CYCLE_COMPLETED",
        "v3_forward_status": "COLLECTING_FORWARD_EVIDENCE",
        "v3_forward_candidate_id": "FOREX_STRENGTH_V3R2_20261104",
        "v3_forward_source_state_valid": True,
        "v3_forward_sample_complete": False,
        "v3_forward_accepted_cycle_count": 4,
        "v3_forward_minimum_cycle_count": 20,
        "v3_forward_accepted_market_day_count": 1,
        "v3_forward_minimum_market_day_count": 3,
        "v3_forward_invalid_cycle_count": 0,
        "v3_forward_exclusions": {"SUPERSEDED_CANDIDATE": 12},
        "v3_forward_invalid_issues": {},
        "v3_activation_status": "ALREADY_ACTIVE",
        "v3_activation_reason": "",
        "v3_plan_observation_status": "SHADOW_PLAN_OBSERVED",
        "v3_plan_reason": "",
        "v3_decision_status": "NO_ACTION",
        "v3_simulation_reason": "",
        "v3_ready_pair_count": 6,
        "v3_blocked_pair_count": 1,
        "v3_instruction_count": 0,
        "v3_execution_count": 0,
        "v3_reason_codes": {
            "NO_NEW_CROSSOVER": 5,
            "CANDIDATE_V3_SIGNAL_STRENGTH_TOO_LOW": 1,
            "SPREAD_TOO_WIDE": 1,
        },
        "v3_balance_pln": "10005.00",
        "v3_equity_pln": "10007.50",
        "v3_unrealized_pnl_pln": "2.50",
        "v3_realized_pnl_pln": "5.00",
        "v3_position_count": 1,
        "v3_closed_trade_count": 4,
        "v3_winning_trade_count": 2,
        "v3_losing_trade_count": 1,
        "v3_breakeven_trade_count": 1,
        "v3_win_rate_pct": "50.00",
        "v3_open_positions": [{
            "pair": "EUR_USD",
            "side": "LONG",
            "entry_price": "1.1000",
            "current_price": "1.1010",
            "stop_loss": "1.0950",
            "take_profit": "1.1100",
            "opened_at": "2026-11-03T09:00:00+00:00",
            "initial_risk_pln": "10.00",
        }],
        "v3_performance": {
            "status": "COLLECTING_SAMPLE",
            "valid_closed_trade_count": 4,
            "minimum_closed_trades_for_review": 30,
            "sample_progress_pct": "13.33",
            "win_rate_pct": "50.00",
            "net_realized_pnl_pln": "5.00",
            "average_trade_pnl_pln": "1.25",
            "profit_factor": "1.50",
            "maximum_closed_trade_drawdown_pln": "3.00",
            "maximum_closed_trade_drawdown_pct": "0.03",
            "maximum_consecutive_losses": 1,
            "pair_breakdown": {
                "EUR_USD": {
                    "closed_trade_count": 4,
                    "win_rate_pct": "50.00",
                    "net_realized_pnl_pln": "5.00",
                    "average_trade_pnl_pln": "1.25",
                    "profit_factor": "1.50",
                },
            },
        },
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


class FakeProperties:
    def __init__(self, size: int) -> None:
        self.size = size


class FakeDownload:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def readall(self) -> bytes:
        return self.value


class FakeBlob:
    def __init__(self, value: bytes | None = None) -> None:
        self.value = value
        self.options: dict = {}

    def get_blob_properties(self) -> FakeProperties:
        if self.value is None:
            raise type("ResourceNotFoundError", (Exception,), {})()
        return FakeProperties(len(self.value))

    def download_blob(self) -> FakeDownload:
        return FakeDownload(self.value or b"")

    def upload_blob(self, value: bytes, **options) -> None:
        self.value = bytes(value)
        self.options = options


class FakeContentSettings:
    def __init__(self, *, content_type: str) -> None:
        self.content_type = content_type


class CloudForexStatusTests(unittest.TestCase):
    def test_sanitizer_is_strict_allowlist_and_paper_only(self) -> None:
        value = sample_status()
        value["secret"] = "must-not-leak"
        result = sanitize_forex_status(value)

        self.assertNotIn("secret", result)
        self.assertFalse(result["broker_orders_sent"])
        self.assertEqual(result["v3_open_positions"][0]["pair"], "EUR_USD")
        self.assertEqual(result["runtime_ready_pair_count"], 6)
        self.assertEqual(result["runtime_reason_codes"]["NO_ENTRY_SIGNAL"], 6)
        self.assertEqual(result["v3_decision_status"], "NO_ACTION")
        self.assertEqual(
            result["observation_opening_blocks_by_pair"],
            {"EUR_USD": ["SECOND_SOURCE_UNAVAILABLE"]},
        )
        self.assertEqual(result["v3_activation_status"], "ALREADY_ACTIVE")
        self.assertEqual(result["v3_forward_accepted_cycle_count"], 4)
        self.assertEqual(
            result["v3_forward_exclusions"],
            {"SUPERSEDED_CANDIDATE": 12},
        )
        self.assertEqual(result["v3_ready_pair_count"], 6)
        self.assertEqual(result["v3_reason_codes"]["NO_NEW_CROSSOVER"], 5)

        value["real_money_access"] = True
        with self.assertRaisesRegex(ForexStatusStoreError, "unsafe_mode"):
            sanitize_forex_status(value)

    def test_invalid_position_and_nonfinite_number_fail_closed(self) -> None:
        value = sample_status()
        value["v3_open_positions"][0]["pair"] = "../../secret"
        with self.assertRaisesRegex(ForexStatusStoreError, "invalid_position"):
            sanitize_forex_status(value)

        value = sample_status()
        value["v3_balance_pln"] = "NaN"
        with self.assertRaisesRegex(ForexStatusStoreError, "invalid_decimal"):
            sanitize_forex_status(value)

        value = sample_status()
        value["v3_ready_pair_count"] = 8
        with self.assertRaisesRegex(ForexStatusStoreError, "invalid_count"):
            sanitize_forex_status(value)

        value = sample_status()
        value["observation_opening_blocks_by_pair"] = {
            "BAD_PAIR": ["SECOND_SOURCE_UNAVAILABLE"],
        }
        with self.assertRaisesRegex(
            ForexStatusStoreError, "invalid_pair_blocks"
        ):
            sanitize_forex_status(value)

    def test_memory_store_isolated_and_view_reports_freshness(self) -> None:
        store = MemoryForexStatusStore(sample_status())
        first = store.read()
        first["status"] = "CHANGED"
        self.assertEqual(store.read()["status"], "PAPER_CYCLE_COMPLETED")

        fresh = forex_status_view(
            store.read(),
            now=datetime(2026, 11, 3, 11, 0, tzinfo=timezone.utc),
        )
        stale = forex_status_view(
            store.read(),
            now=datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
            + timedelta(hours=3),
        )
        self.assertTrue(fresh["fresh"])
        self.assertFalse(stale["fresh"])
        self.assertEqual(stale["status"], "PAPER_STATUS_STALE")
        self.assertEqual(stale["reason"], "STATUS_SNAPSHOT_STALE")
        self.assertEqual(stale["v3_position_count"], 0)
        self.assertEqual(stale["v3_open_positions"], [])
        self.assertEqual(stale["v3_decision_status"], "STATUS_UNAVAILABLE")
        self.assertEqual(stale["v3_activation_status"], "STATUS_UNAVAILABLE")
        self.assertEqual(stale["v3_plan_reason"], "")
        self.assertEqual(stale["v3_reason_codes"], {})

        future = forex_status_view(
            store.read(),
            now=datetime(2026, 11, 3, 9, 40, tzinfo=timezone.utc),
        )
        self.assertFalse(future["fresh"])
        self.assertEqual(future["reason"], "STATUS_TIMESTAMP_IN_FUTURE")
        self.assertEqual(future["v3_open_positions"], [])

    def test_empty_memory_store_is_not_ready(self) -> None:
        with self.assertRaises(ForexStatusNotReady):
            MemoryForexStatusStore().read()

    def test_blob_store_round_trip_contains_only_sanitized_json(self) -> None:
        blob = FakeBlob()
        store = AzureBlobForexStatusStore(blob)
        value = sample_status()
        value["secret"] = "must-not-leak"
        fake_blob_module = types.ModuleType("azure.storage.blob")
        fake_blob_module.ContentSettings = FakeContentSettings
        with patch.dict(
            sys.modules, {"azure.storage.blob": fake_blob_module}
        ):
            store.write(value)

        raw = json.loads((blob.value or b"").decode("utf-8"))
        self.assertNotIn("secret", raw)
        self.assertTrue(blob.options["overwrite"])
        self.assertEqual(
            blob.options["content_settings"].content_type,
            "application/json; charset=utf-8",
        )
        self.assertEqual(store.read()["cycle_id"], "cycle-123")
        self.assertTrue(store.access_verified)

    def test_environment_rejects_blob_path_traversal(self) -> None:
        environment = {
            "JARVIS_OS_FOREX_STATUS_CONTAINER": "forex-paper-status",
            "JARVIS_OS_REMOTE_STORAGE_ACCOUNT": "jarvisstorage123",
            "JARVIS_OS_FOREX_STATUS_BLOB": "../secret.json",
        }
        with patch.dict(os.environ, environment, clear=False):
            with self.assertRaisesRegex(
                ForexStatusStoreError, "invalid_blob_name"
            ):
                forex_status_store_from_environment()


if __name__ == "__main__":
    unittest.main()

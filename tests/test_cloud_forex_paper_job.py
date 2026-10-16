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
            },
            "paper": {"account": {"position_count": 2}},
            "v3_shadow_simulation": {
                "status": "SHADOW_SIMULATION_CYCLE_COMPLETED",
                "account": {
                    "position_count": 1,
                    "closed_trade_count": 3,
                    "realized_pnl_pln": "12.34",
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
        self.assertFalse(result["broker_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertFalse(result["real_money_access"])
        self.assertNotIn("secret", result)


if __name__ == "__main__":
    unittest.main()

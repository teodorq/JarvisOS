from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.business.audit_center import BusinessAuditCenter


class B84BusinessAuditCenterTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.audit = BusinessAuditCenter(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_records_and_counts_events(self) -> None:
        self.audit.record("COMMAND", decision="ALLOW", detail="status")
        self.audit.record("COMMAND", decision="DENY", detail="write")
        status = self.audit.status()
        self.assertEqual(status["stage"], "B84")
        self.assertEqual(status["event_count"], 2)
        self.assertEqual(status["decision_counts"]["ALLOW"], 1)
        self.assertEqual(status["decision_counts"]["DENY"], 1)

    def test_sync_access_events_is_deduplicated(self) -> None:
        access = {
            "active_role": "OWNER",
            "audit_events": [{
                "timestamp": "2026-07-18T00:00:00+00:00",
                "action": "COMMAND_AUTHORIZATION",
                "decision": "ALLOW",
                "role": "OWNER",
                "detail": "autonomy.read:status",
            }],
        }
        self.audit.sync_access_events(access)
        self.audit.sync_access_events(access)
        self.assertEqual(self.audit.status()["event_count"], 1)

    def test_export_writes_json_and_text(self) -> None:
        self.audit.record("CHECKPOINT", decision="CREATED")
        result = self.audit.export_report()
        export = result["export"]
        json_path = Path(export["json_path"])
        text_path = Path(export["text_path"])
        self.assertTrue(json_path.is_file())
        self.assertTrue(text_path.is_file())
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["type"], "JARVIS_BUSINESS_AUDIT_REPORT")
        self.assertEqual(payload["event_count"], 1)

    def test_event_storage_is_bounded(self) -> None:
        self.audit.MAX_EVENTS = 20
        for index in range(35):
            self.audit.record(f"EVENT_{index}")
        self.assertEqual(self.audit.status()["event_count"], 20)


if __name__ == "__main__":
    unittest.main()

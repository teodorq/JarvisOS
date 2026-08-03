from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomy_governance_store import (
    AutonomyGovernanceStore,
)
from app.ai.software_engineer.software_engineer_autonomy_operations_router import (
    SoftwareEngineerAutonomyOperationsRouter,
)
from app.ai.software_engineer.unified_autonomy_control_center_service import (
    UnifiedAutonomyControlCenterService,
)
from app.gui.command_safety import is_read_only_learning_command


class _Supervisor:
    def __init__(self) -> None:
        self.start_background = MagicMock(return_value={
            "success": True,
            "status": "STARTED",
        })
        self.stop_background = MagicMock(return_value={
            "success": True,
            "status": "STOPPED",
        })
        self.pause = MagicMock(return_value={
            "success": True,
            "status": "PAUSED",
        })
        self.resume = MagicMock(return_value={
            "success": True,
            "status": "RESUMED",
        })


class B731ControlCenterLifecycleRoutingTests(unittest.TestCase):
    def test_natural_control_center_commands_route_to_lifecycle_actions(self):
        cases = {
            "Uruchom centrum sterowania autonomią": "b73_start",
            "Zatrzymaj centrum sterowania autonomią": "b73_stop",
            "Wstrzymaj centrum sterowania autonomią": "b73_pause",
            "Wznów centrum sterowania autonomią": "b73_resume",
        }
        for command, expected in cases.items():
            normalized = " ".join(command.casefold().split())
            self.assertEqual(
                SoftwareEngineerAutonomyOperationsRouter._action(
                    "",
                    normalized,
                ),
                expected,
                command,
            )

    def test_lifecycle_commands_require_confirmation_not_read_only(self):
        commands = (
            "Uruchom centrum sterowania autonomią",
            "Zatrzymaj centrum sterowania autonomią",
            "Wstrzymaj centrum sterowania autonomią",
            "Wznów centrum sterowania autonomią",
        )
        for command in commands:
            self.assertFalse(is_read_only_learning_command(command), command)
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż centrum sterowania autonomią"
            )
        )

    def test_stop_phase_survives_follow_up_status(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            services = {
                stage: _Supervisor()
                for stage in ("B68", "B69", "B70", "B72", "B74", "B79")
            }
            center = UnifiedAutonomyControlCenterService(
                directory,
                store=store,
                services=services,
            )

            started = center.start_safe_supervisors()
            self.assertTrue(started["success"])
            self.assertEqual(store.runtime("B73")["phase"], "READY")

            stopped = center.stop_all_supervisors()
            self.assertTrue(stopped["success"])
            self.assertEqual(store.runtime("B73")["phase"], "STOPPED")
            self.assertFalse(store.runtime("B73")["enabled"])

            status = center.status()
            self.assertEqual(status["runtime"]["phase"], "STOPPED")
            self.assertEqual(store.runtime("B73")["phase"], "STOPPED")
            self.assertEqual(status["decision"], "MONITOR")

    def test_pause_and_resume_update_control_center_phase(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            services = {
                stage: _Supervisor()
                for stage in ("B68", "B69", "B70", "B72", "B74", "B79")
            }
            center = UnifiedAutonomyControlCenterService(
                directory,
                store=store,
                services=services,
            )
            paused = center.pause_all_supervisors()
            self.assertTrue(paused["success"])
            self.assertEqual(store.runtime("B73")["phase"], "PAUSED")
            center.status()
            self.assertEqual(store.runtime("B73")["phase"], "PAUSED")

            resumed = center.resume_safe_supervisors()
            self.assertTrue(resumed["success"])
            self.assertEqual(store.runtime("B73")["phase"], "READY")


if __name__ == "__main__":
    unittest.main()

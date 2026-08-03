from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.software_engineer.software_engineer_strategic_execution_router import (
    SoftwareEngineerStrategicExecutionRouter,
)


class B582DispatchPrecedenceFixTests(unittest.TestCase):
    """Explicit B58 commands override stale GUI approval context."""

    def setUp(self) -> None:
        self.router = SoftwareEngineerStrategicExecutionRouter()
        self.controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split())
        )

    def test_dispatch_command_overrides_stale_status_operation(self) -> None:
        service = MagicMock()
        service.dispatch_next.return_value = {
            "success": True,
            "status": "STRATEGIC_EXECUTION_JOB_DISPATCHED",
            "job_id": "longrun-b58",
        }
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_execution_router."
            "bootstrap_strategic_execution",
            return_value=service,
        ):
            result = self.router.try_handle(
                self.controller,
                command="Wykonaj następne zadanie strategiczne",
                objective="",
                context={
                    "operation": "strategic_execution_status",
                    "auto_approve": False,
                },
            )

        self.assertEqual(
            result["status"],
            "STRATEGIC_EXECUTION_JOB_DISPATCHED",
        )
        service.dispatch_next.assert_called_once_with()
        service.status.assert_not_called()

    def test_start_command_overrides_stale_status_operation(self) -> None:
        service = MagicMock()
        service.start.return_value = {
            "success": True,
            "status": "STRATEGIC_EXECUTION_STARTED",
        }
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_execution_router."
            "bootstrap_strategic_execution",
            return_value=service,
        ):
            result = self.router.try_handle(
                self.controller,
                command="Uruchom wykonanie strategiczne",
                objective="",
                context={"operation": "strategic_execution_status"},
            )

        self.assertEqual(result["status"], "STRATEGIC_EXECUTION_STARTED")
        service.start.assert_called_once_with()
        service.status.assert_not_called()

    def test_status_command_remains_read_only(self) -> None:
        service = MagicMock()
        service.status.return_value = {
            "success": True,
            "status": "STRATEGIC_EXECUTION_STATUS",
        }
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_execution_router."
            "bootstrap_strategic_execution",
            return_value=service,
        ):
            result = self.router.try_handle(
                self.controller,
                command="Pokaż status wykonania strategicznego",
                objective="",
                context={"operation": "strategic_execution_dispatch"},
            )

        self.assertEqual(result["status"], "STRATEGIC_EXECUTION_STATUS")
        service.status.assert_called_once_with()
        service.dispatch_next.assert_not_called()

    def test_direct_action_precedence(self) -> None:
        normalized = "wykonaj następne zadanie strategiczne"
        self.assertEqual(
            self.router._action(
                "strategic_execution_status",
                normalized,
            ),
            "dispatch",
        )


if __name__ == "__main__":
    unittest.main()

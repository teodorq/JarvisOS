from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.software_engineer.software_engineer_strategic_development_router import (
    SoftwareEngineerStrategicDevelopmentRouter,
)


class B574ApprovalContextRoutingFixTests(unittest.TestCase):
    """Explicit refresh commands override stale GUI approval context."""

    def test_refresh_command_overrides_roadmap_operation(self) -> None:
        router = SoftwareEngineerStrategicDevelopmentRouter()
        commands = (
            "Odśwież roadmapę rozwoju",
            "Odswiez roadmape rozwoju",
            "Refresh development roadmap",
        )
        for command in commands:
            with self.subTest(command=command):
                normalized = " ".join(command.casefold().split())
                self.assertEqual(
                    router._action(
                        "strategic_development_roadmap",
                        normalized,
                    ),
                    "refresh",
                )

    def test_refresh_command_overrides_generic_operation(self) -> None:
        router = SoftwareEngineerStrategicDevelopmentRouter()
        normalized = "odśwież roadmapę rozwoju"
        self.assertEqual(
            router._action("strategic_development", normalized),
            "refresh",
        )

    def test_read_only_roadmap_operation_remains_read_only(self) -> None:
        router = SoftwareEngineerStrategicDevelopmentRouter()
        normalized = "pokaż roadmapę rozwoju"
        self.assertEqual(
            router._action(
                "strategic_development_roadmap",
                normalized,
            ),
            "roadmap",
        )

    def test_full_router_refreshes_after_gui_confirmation_context(self) -> None:
        router = SoftwareEngineerStrategicDevelopmentRouter()
        service = MagicMock()
        service.refresh.return_value = {
            "success": True,
            "status": "STRATEGIC_DEVELOPMENT_ROADMAP_REFRESHED",
        }
        controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split())
        )
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_development_router."
            "bootstrap_strategic_development",
            return_value=service,
        ):
            result = router.try_handle(
                controller,
                command="Odśwież roadmapę rozwoju",
                objective="",
                context={
                    "operation": "strategic_development_roadmap",
                    "auto_approve": False,
                },
            )

        self.assertEqual(
            result["status"],
            "STRATEGIC_DEVELOPMENT_ROADMAP_REFRESHED",
        )
        service.refresh.assert_called_once_with()
        service.roadmap.assert_not_called()


if __name__ == "__main__":
    unittest.main()

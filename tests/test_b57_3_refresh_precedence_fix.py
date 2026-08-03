from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.software_engineer.software_engineer_strategic_development_router import (
    SoftwareEngineerStrategicDevelopmentRouter,
)


class B573RefreshPrecedenceFixTests(unittest.TestCase):
    """Refresh commands must not be swallowed by the roadmap read route."""

    def test_refresh_phrase_wins_over_overlapping_roadmap_phrase(self) -> None:
        router = SoftwareEngineerStrategicDevelopmentRouter()
        commands = (
            "Odśwież roadmapę rozwoju",
            "Odswiez roadmape rozwoju",
            "Refresh development roadmap",
        )
        for command in commands:
            with self.subTest(command=command):
                normalized = " ".join(command.casefold().split())
                self.assertEqual(router._action("", normalized), "refresh")

    def test_read_only_roadmap_command_still_routes_to_roadmap(self) -> None:
        router = SoftwareEngineerStrategicDevelopmentRouter()
        commands = (
            "Pokaż roadmapę rozwoju",
            "Pokaz roadmape rozwoju",
            "Development roadmap",
        )
        for command in commands:
            with self.subTest(command=command):
                normalized = " ".join(command.casefold().split())
                self.assertEqual(router._action("", normalized), "roadmap")

    def test_full_router_calls_refresh_not_roadmap(self) -> None:
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
                context={"auto_approve": False},
            )
        self.assertEqual(
            result["status"],
            "STRATEGIC_DEVELOPMENT_ROADMAP_REFRESHED",
        )
        service.refresh.assert_called_once_with()
        service.roadmap.assert_not_called()


if __name__ == "__main__":
    unittest.main()

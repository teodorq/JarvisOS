from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_command_router import (
    SoftwareEngineerCommandRouter,
)


class B521LearningRoutingFixTests(unittest.TestCase):

    COMMAND = "Pokaż status uczenia autonomicznego"

    def test_controller_accepts_exact_gui_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                self.COMMAND
            )
        )

    def test_brain_routes_exact_gui_command_to_software_engineer(
        self,
    ) -> None:
        disabled = MagicMock()
        disabled.can_handle.return_value = False
        brain = SimpleNamespace(
            cognitive=MagicMock(),
            software_engineer_controller=SimpleNamespace(
                can_handle=(
                    AutonomousSoftwareEngineerController.can_handle
                )
            ),
            autonomous_dev_controller=disabled,
            architect_controller=disabled,
            meta_controller=disabled,
            executive_controller=disabled,
            director_controller=disabled,
            improvement_controller=disabled,
            evolution_controller=disabled,
            continuous_dev_controller=disabled,
            reasoning_service=disabled,
            research_service=disabled,
            autodev_router=disabled,
        )

        thought = BrainCommandRouter().think(
            brain,
            self.COMMAND,
        )

        self.assertEqual(
            thought["handler"],
            "autonomous_software_engineer",
        )

    def test_command_returns_learning_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            engine = MagicMock()
            engine.status.return_value = {
                "success": True,
                "status": "AUTONOMOUS_LEARNING_STATUS",
                "operation": "autonomous_learning",
                "profile": {
                    "active": False,
                    "observations": 1,
                    "confidence": 0.2,
                },
                "store": {
                    "episodes": 1,
                    "training_runs": 0,
                    "path": (
                        Path(temp)
                        / "data/autodev/autonomous_learning.json"
                    ).as_posix(),
                },
                "errors": [],
            }
            controller = SimpleNamespace(
                project_root=Path(temp),
                autonomous_learning_engine=engine,
                can_handle=(
                    AutonomousSoftwareEngineerController.can_handle
                ),
                _normalize=(
                    AutonomousSoftwareEngineerController._normalize
                ),
                _extract_objective=lambda command: str(command),
            )

            response = SoftwareEngineerCommandRouter().handle(
                controller,
                self.COMMAND,
                {
                    "metadata": {
                        "source": "Brain",
                    },
                },
            )

            self.assertEqual(
                response["status"],
                "AUTONOMOUS_LEARNING_STATUS",
            )
            engine.status.assert_called_once_with()

    def test_formatter_reports_learning_counts_and_metrics(
        self,
    ) -> None:
        text = BrainResponseFormatter()._format_software_engineer_response(
            {
                "success": True,
                "status": "AUTONOMOUS_LEARNING_STATUS",
                "operation": "autonomous_learning",
                "profile": {
                    "active": True,
                    "observations": 8,
                    "confidence": 0.75,
                },
                "store": {
                    "episodes": 8,
                    "training_runs": 2,
                    "path": "data/autodev/autonomous_learning.json",
                },
                "last_training_run": {
                    "training_run_id": "learning-demo",
                    "analysis": {
                        "observations": 8,
                        "success_rate": 0.75,
                        "rollback_rate": 0.125,
                        "retry_rate": 0.25,
                    },
                },
                "errors": [],
            }
        )

        self.assertIn("Epizody: 8", text)
        self.assertIn("Przebiegi uczenia: 2", text)
        self.assertIn("Skuteczność: 75.0%", text)
        self.assertIn("Rollbacki: 12.5%", text)
        self.assertIn("Przebiegi z retry: 25.0%", text)


if __name__ == "__main__":
    unittest.main()
